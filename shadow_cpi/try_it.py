"""'Try it: search the past' (app page app_pages/try_it.py): a visitor's question, searched twice with our key.

  - No time lock: a plain Tavily search, no dates.
  - Time lock: timelock.timelocked_search(client, question, cutoff): the 30 days ending on the cutoff, Tavily's
    published-date filter on.
Each result is flagged from Tavily's published_date only: after the cutoff yes / no / undated. A date flag is not a
Wayback-confirmed leak (the Field Report has the measured result).

Guardrails (config/budget.json plans["try-it"], caps "try-it" and "try-it-day"): `per_run` credits per run; at most
`per_day` credits per UTC day and `lifetime` credits in all for this page, counted in one process-wide Store (seeded
from the ledger's try-it rows, so a process restart keeps the count) and reserved under a lock before any call;
`per_session` runs per visitor session; an identical (question, cutoff) within `cache_hours` is answered from the
Store for free. The account floors of plans.app_live (credit_floor, usage_floor via Tavily's free GET /usage, fail
closed) apply too, and every call is held to the hard caps by shadow_cpi.budget and goes through the Recorder.

Input: at most MAX_QUESTION characters after removing control characters; the question is only ever sent as a Tavily
search query (no page is fetched from anything the visitor types).
"""
import re
import threading
import unicodedata
from datetime import date, datetime, timedelta, timezone

from timelock import timelocked_search
from timelock.dates import iso_date

from .budget import LEDGER, Budgeted, load_budget, read_ledger
from .live_run import KEY_VARS, credits_left, limits as app_live_limits, setting, usage_remaining

BUDGET, DAY_BUDGET = "try-it", "try-it-day"
BASE = {"topic": "news", "search_depth": "basic", "max_results": 5, "include_published_date": True}
MAX_QUESTION = 200
MIN_CUTOFF = date(2025, 1, 1)
COLAB_URL = ("https://colab.research.google.com/github/bhavikjain026/shadow-cpi/blob/main/notebooks/"
             "reproduce_leak.ipynb")
YES, NO, UNDATED = "yes", "no", "undated"
_BIDI = set("‪‫‬‭‮⁦⁧⁨⁩")   # direction overrides: display spoofing


class Refused(Exception):
    """A run that is not allowed (bad input or a cap). The message is shown to the visitor as it is."""


def limits(cfg=None):
    return (cfg or load_budget())["plans"]["try-it"]


def tavily_key():
    """Our Tavily key (environment, else the Streamlit secret), or None. Never shown or logged."""
    return setting(KEY_VARS[0])


def clean_question(text):
    """Control characters (and direction overrides) become spaces, whitespace collapses; then at most MAX_QUESTION
    characters. Refused if nothing is left."""
    s = "".join(" " if unicodedata.category(ch) == "Cc" or ch in _BIDI else ch for ch in (text or ""))
    s = " ".join(s.split())[:MAX_QUESTION].strip()
    if not s:
        raise Refused("Type a question to start.")
    return s


def check_cutoff(cutoff, today):
    """ISO cutoff on or after MIN_CUTOFF and before today (UTC)."""
    try:
        d = cutoff if isinstance(cutoff, date) else date.fromisoformat(str(cutoff))
    except ValueError:
        raise Refused("Pick a cutoff date.") from None
    if d < MIN_CUTOFF:
        raise Refused(f"Pick a cutoff on or after {MIN_CUTOFF.day} {MIN_CUTOFF:%b %Y}.")
    if d >= today:
        raise Refused("The cutoff has to be in the past (yesterday at the latest).")
    return d.isoformat()


def after(published, cutoff):
    """'yes' when Tavily's published date is after the cutoff, 'no' when on or before it, 'undated' when missing."""
    d = iso_date(published)
    return UNDATED if not d else YES if d > cutoff else NO


def summary(res):
    """'No time lock: X of N results dated after the cutoff · Time lock: Y of M'."""
    def count(side):
        rows = res[side]["results"]
        return sum(r["after"] == YES for r in rows), len(rows)
    (x, n), (y, m) = count("open"), count("locked")
    return f"No time lock: {x} of {n} results dated after the cutoff · Time lock: {y} of {m}"


class Store:
    """One per server process: credits this page spent per UTC day and in all, and the answer cache."""

    def __init__(self, ledger=None):
        self.lock = threading.Lock()
        self.days, self.total, self.cache = {}, 0, {}
        for e in read_ledger() if ledger is None else ledger:
            if BUDGET in e.get("budgets", []) and not e.get("cached"):
                self._add(e["time"][:10], e.get("credits") or 0)

    def _add(self, day, credits):
        self.days[day] = self.days.get(day, 0) + credits
        self.total += credits

    def cached(self, key, now, hours):
        with self.lock:
            hit = self.cache.get(key)
            if hit and now - hit[0] < timedelta(hours=hours):
                return hit[1]
            self.cache.pop(key, None)
            return None

    def reserve(self, day, lim):
        """Takes `per_run` credits from today's and the lifetime allowance, or raises Refused (nothing taken)."""
        cost = lim["per_run"]
        with self.lock:
            if self.days.get(day, 0) + cost > lim["per_day"]:
                raise Refused(f"Today's {lim['per_day']} search credits for this page are used up (resets at "
                              "00:00 UTC).")
            if self.total + cost > lim["lifetime"]:
                raise Refused(f"This page's {lim['lifetime']} search credits are used up.")
            self._add(day, cost)
        return cost

    def settle(self, day, reserved, actual, key=None, result=None, now=None):
        """Replaces the reservation with what Tavily reported, and caches the answer."""
        with self.lock:
            self._add(day, actual - reserved)
            if result is not None:
                self.cache[key] = (now, result)


_STORE = None
_STORE_LOCK = threading.Lock()


def store():
    """The process-wide Store (made on first use)."""
    global _STORE
    with _STORE_LOCK:
        if _STORE is None:
            _STORE = Store()
        return _STORE


class _Client:
    """timelocked_search wants client.search(query, **kw) -> dict; Budgeted.search returns (response, call id)."""

    def __init__(self, tav, tag):
        self.tav, self.tag = tav, tag

    def search(self, query, **params):
        return self.tav.search(query, tag=self.tag, **params)[0]


def _rows(results, cutoff):
    return [{"title": r.get("title") or r.get("url"), "url": r.get("url"),
             "published_date": iso_date(r.get("published_date")) or None,
             "after": after(r.get("published_date"), cutoff)} for r in results or []]


def search_both(tav, question, cutoff):
    """The two searches through a Budgeted-like client `tav` (search -> (response, id)); returns both sides."""
    used = tav.used
    plain = _Client(tav, "live:try it open").search(question, **BASE)
    out = {"open": {"results": _rows(plain.get("results"), cutoff), "credits": tav.used - used,
                    "request_id": plain.get("request_id")}}
    used = tav.used
    locked = timelocked_search(_Client(tav, "live:try it locked"), question, cutoff, **BASE)
    out["locked"] = {"results": _rows(locked, cutoff), "credits": tav.used - used,
                     "request_id": locked.request_id, "window": locked.window}
    return out


def run(question, cutoff, session_runs, *, key=None, st_store=None, now=None, cfg=None, ledger_path=LEDGER,
        tav=None, usage_fetch=None):
    """(result, cached?) for one visitor request, or raises Refused with the message to show. Cheapest checks first;
    credits are reserved in the Store before any call. `tav`: a Budgeted-like client for tests."""
    cfg = cfg or load_budget()
    lim, app = limits(cfg), app_live_limits(cfg)
    now = now or datetime.now(timezone.utc)
    day = now.date().isoformat()
    q = clean_question(question)
    cut = check_cutoff(cutoff, now.date())
    s = st_store or store()
    ck = (q.casefold(), cut)
    hit = s.cached(ck, now, lim["cache_hours"])
    if hit:
        return hit, True
    key = key or tavily_key()
    if not key:
        raise Refused("Live search is switched off on this copy of the app (no API key).")
    if session_runs >= lim["per_session"]:
        raise Refused(f"You have used this visit's {lim['per_session']} searches.")
    ledger = read_ledger(ledger_path)
    if credits_left(cfg, ledger) - lim["per_run"] < app["credit_floor"]:
        raise Refused(f"Live search is paused: the Tavily balance is close to the floor of {app['credit_floor']} "
                      "credits kept in reserve.")
    remaining, why = usage_remaining(key, usage_fetch, cfg, ledger)
    if remaining is None:
        raise Refused(f"Live search is paused: {why}.")
    if remaining < app["usage_floor"]:
        raise Refused(f"Live search is paused: fewer than {app['usage_floor']} Tavily credits left.")
    reserved = s.reserve(day, lim)
    if tav is None:
        from .recorder import Recorder
        from .tavily import Tavily
        tav = Budgeted(Tavily(api_key=key, recorder=Recorder(use_cache=False)), [BUDGET, f"{DAY_BUDGET}/{day}"],
                       cfg=cfg, ledger_path=ledger_path, fresh=True)
    try:
        sides = search_both(tav, q, cut)
    except Exception:
        s.settle(day, reserved, max(reserved, tav.used))          # keep the reservation: never under-count
        raise
    res = {"question": q, "cutoff": cut, "utc": now.isoformat(), "source": "live", **sides}
    s.settle(day, reserved, tav.used, ck, res, now)
    return res, False


# Saved examples on the opening screen (results/leak_demo.json): F3, a leak the time lock kept out; C5, thin evidence
# (the time lock returned results, none of them Wayback-confirmed as published before the cutoff).
SAVED_CASES = ("F3", "C5")
CONFIRMED_PRE = ("confirmed pre-cutoff", "valid")           # leak_demo.json labels for a Wayback-confirmed pre-cutoff page


def example(leak_demo, date_test_built=None, case_id="F3"):
    """A saved example: one Leak demo case (results/leak_demo.json), flagged by the same rule as a live run, each row
    also carrying the case's Wayback label, its confirmed-leak flag and its excerpt."""
    c = next((c for c in (leak_demo or {}).get("cases", []) if c["id"] == case_id), None)
    if not c:
        return None
    res = {"question": c["query"], "cutoff": c["cutoff"], "utc": date_test_built, "source": "saved", "case": case_id,
           "test": c["test"], "test_name": c.get("test_name")}
    for side in ("open", "locked"):
        req = c[side]["request"]
        rows = _rows(c[side]["results"], c["cutoff"])
        for row, r in zip(rows, c[side]["results"]):
            row.update(wayback=r.get("label"), leak=bool(r.get("leak")), quote=r.get("quote"))
        res[side] = {"results": rows, "credits": c[side].get("credits"), "request": req,
                     "request_id": c[side].get("request_id"), "max_results": req.get("max_results"),
                     "latency_s": c[side].get("latency_s")}
        if side == "locked":
            res[side]["window"] = [req.get("start_date"), req.get("end_date")]
    return res


def _day(d):
    d = date.fromisoformat(d[:10])
    return f"{d.day} {d:%b %Y}"


def verdict(res):
    """The answer that sits at the top of the opening screen: (headline, thin) where thin is None or the plain
    statement that the time lock returned no usable pre-cutoff evidence. Saved examples are judged by their Wayback
    labels (a confirmed leak; a page confirmed published before the cutoff); live runs by Tavily's published_date."""
    o, k = res["open"]["results"], res["locked"]["results"]
    if res.get("source") == "saved":
        usable = sum((r.get("wayback") or "").startswith(CONFIRMED_PRE) for r in k)
        head = (f"No time lock: {sum(r['leak'] for r in o)} of {len(o)} results confirmed (Wayback) as published after "
                f"the cutoff · Time lock: {sum(r['leak'] for r in k)} of {len(k)}")
        why = (f"None of the {len(k)} time-locked results was confirmed as published before the cutoff (no archive "
               "record either way), so none counts as evidence.")
    else:
        usable = sum(r["after"] == NO for r in k)
        head = summary(res)
        why = (f"None of the {len(k)} time-locked results is dated on or before the cutoff." if k
               else "The time-locked search returned no results.")
    if usable:
        return head, None
    return head, f"{why} Nothing knowable before {_day(res['cutoff'])}; we don't guess."
