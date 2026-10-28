"""Try it: search the past (shadow_cpi/try_it.py, app_pages/try_it.py). Fake Tavily clients only: no live call."""
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from shadow_cpi import try_it as T
from shadow_cpi.budget import Budgeted, load_budget, read_ledger
from shadow_cpi.recorder import Recorder
from shadow_cpi.tavily import Tavily

ROOT = Path(__file__).resolve().parent.parent
NOW = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)
DAY = NOW.date().isoformat()
CUT = "2026-05-29"
OK_USAGE = lambda: {"account": {"plan_limit": 1000, "plan_usage": 0}}       # noqa: E731
KEY = "test-key-not-real"

OPEN_RESULTS = [{"url": "https://a.example/p1", "title": "After [it]", "published_date": "2026-09-21"},
                {"url": "https://b.example/p2", "title": "Before", "published_date": "Mon, 25 May 2026 10:00:00 GMT"},
                {"url": "https://c.example/p3", "title": "No date"}]
LOCKED_RESULTS = [{"url": "https://d.example/p4", "title": "Locked 1", "published_date": "2026-05-19"},
                  {"url": "https://e.example/p5", "title": "Locked 2", "published_date": "2026-05-15"}]


class FakeTav:
    """Budgeted-like: search(query, tag=, **params) -> (response, call id); 1 credit per call."""

    def __init__(self, fail=False):
        self.calls, self.used, self.fail = [], 0, fail

    def search(self, query, tag=None, **params):
        self.calls.append({"query": query, "tag": tag, **params})
        if self.fail:
            raise ConnectionError("network down")
        self.used += 1
        locked = "start_date" in params
        return {"request_id": f"req-{len(self.calls)}",
                "results": LOCKED_RESULTS if locked else OPEN_RESULTS, "usage": {"credits": 1}}, "cid"


@pytest.fixture
def ledger(tmp_path):
    return tmp_path / "ledger.jsonl"


RUN = T.run                                     # the page tests replace T.run; go() keeps the real one


def go(question="petrol diesel price hike India May 2026", cutoff=CUT, runs=0, store=None, tav=None, ledger=None,
       **kw):
    kw.setdefault("usage_fetch", OK_USAGE)
    kw.setdefault("key", KEY)
    return RUN(question, cutoff, runs, st_store=store if store is not None else T.Store([]), now=NOW,
                 tav=tav if tav is not None else FakeTav(), ledger_path=ledger, **kw)


# ---------- both columns and the flags ----------
def test_both_searches_columns_and_flags(ledger):
    tav = FakeTav()
    res, hit = go(tav=tav, ledger=ledger)
    assert not hit and res["source"] == "live"
    plain, locked = tav.calls
    assert not {"start_date", "end_date", "filter_by_published_date"} & plain.keys()
    assert locked["start_date"] == "2026-04-30" and locked["end_date"] == CUT
    assert locked["filter_by_published_date"] is True
    assert [r["after"] for r in res["open"]["results"]] == ["yes", "no", "undated"]
    assert [r["published_date"] for r in res["open"]["results"]] == ["2026-09-21", "2026-05-25", None]
    assert [r["after"] for r in res["locked"]["results"]] == ["no", "no"]
    assert res["locked"]["window"] == ["2026-04-30", CUT]
    assert res["open"]["credits"] == res["locked"]["credits"] == 1
    assert T.summary(res) == ("No time lock: 1 of 3 results dated after the cutoff · Time lock: 0 of 2")
    assert KEY not in json.dumps(res)


def test_after_flag_rule():
    assert T.after("2026-05-30", CUT) == "yes"
    assert T.after("2026-05-29T23:00:00", CUT) == "no"
    assert T.after("", CUT) == T.after(None, CUT) == T.after("not a date", CUT) == "undated"


# ---------- input safety ----------
def test_question_is_cleaned_and_capped():
    assert T.clean_question("  rbi\x00 repo\nrate\t\x1b[31m  ") == "rbi repo rate [31m"
    assert T.clean_question("a‮b") == "a b"
    assert T.clean_question("पेट्रोल‍ कीमत") == "पेट्रोल‍ कीमत"       # joiners in Indic text stay
    assert len(T.clean_question("x" * 500)) == T.MAX_QUESTION == 200
    for empty in ("", "   ", "\x00\x07"):
        with pytest.raises(T.Refused, match="Type a question"):
            T.clean_question(empty)


@pytest.mark.parametrize("cutoff", ["2026-10-28", "2026-12-01", "2024-12-31", "yesterday"])
def test_cutoff_must_be_past_and_from_2025(cutoff, ledger):
    tav = FakeTav()
    with pytest.raises(T.Refused):
        go(cutoff=cutoff, tav=tav, ledger=ledger)
    assert tav.calls == []


def test_earliest_and_latest_cutoffs_allowed(ledger):
    for cut in ("2025-01-01", "2026-10-27"):
        assert go(cutoff=cut, ledger=ledger)[0]["cutoff"] == cut


def test_question_only_reaches_tavily_search(ledger):
    tav = FakeTav()
    go(question="https://evil.example/page?x=1", tav=tav, ledger=ledger)
    assert [c["query"] for c in tav.calls] == ["https://evil.example/page?x=1"] * 2
    assert not hasattr(tav, "extract_calls")                    # FakeTav has no extract: nothing else was called


# ---------- caps ----------
def test_caps_as_configured():
    cfg = load_budget()
    lim = T.limits(cfg)
    assert (lim["per_run"], lim["per_day"], lim["lifetime"], lim["per_session"], lim["cache_hours"]) == \
        (2, 25, 600, 3, 24)
    assert cfg["caps"]["try-it"] == 600 and cfg["caps"]["try-it-day"] == 25


def test_per_session_limit(ledger):
    tav = FakeTav()
    with pytest.raises(T.Refused, match="this visit's 3 searches"):
        go(runs=3, tav=tav, ledger=ledger)
    assert tav.calls == []
    go(runs=2, ledger=ledger)


def test_daily_cap(ledger):
    s = T.Store([])
    s.days[DAY] = 23
    s.total = 23
    go(store=s, ledger=ledger)
    assert s.days[DAY] == 25
    tav = FakeTav()
    with pytest.raises(T.Refused, match="Today's 25 search credits"):
        go(question="another question", store=s, tav=tav, ledger=ledger)
    assert tav.calls == [] and s.days[DAY] == 25
    s.days[DAY] = 24                                            # one credit left is not enough for a run of two
    with pytest.raises(T.Refused, match="Today's 25"):
        go(question="third", store=s, ledger=ledger)


def test_lifetime_cap_counts_the_ledger(ledger):
    rows = [{"time": f"2026-10-{d:02d}T10:00:00+00:00", "credits": 24, "budgets": ["try-it", f"try-it-day/x{d}"]}
            for d in range(1, 26)]                              # 25 days x 24 = 600 credits
    rows.append({"time": "2026-10-26T10:00:00+00:00", "credits": 0, "cached": True, "budgets": ["try-it"]})
    rows.append({"time": "2026-10-26T10:00:00+00:00", "credits": 9, "budgets": ["run-now"]})
    s = T.Store(rows)
    assert s.total == 600 and s.days["2026-10-01"] == 24 and DAY not in s.days
    tav = FakeTav()
    with pytest.raises(T.Refused, match="This page's 600 search credits are used up"):
        go(store=s, tav=tav, ledger=ledger)
    assert tav.calls == []
    s.total = 598
    go(store=s, ledger=ledger)
    assert s.total == 600


def test_account_floors_fail_closed(ledger):
    with pytest.raises(T.Refused, match="usage check failed"):
        go(usage_fetch=lambda: (_ for _ in ()).throw(TimeoutError()), ledger=ledger)
    with pytest.raises(T.Refused, match="fewer than"):
        go(usage_fetch=lambda: {"account": {"plan_limit": 1000, "plan_usage": 1000}},
           cfg={**load_budget(), "addon_credits": 0}, ledger=ledger)
    cfg = load_budget()
    ledger.write_text(json.dumps({"time": "2026-10-01T00:00:00+00:00", "credits": T.credits_left(cfg, []) - 400,
                                  "budgets": ["x"]}) + "\n")
    tav = FakeTav()
    with pytest.raises(T.Refused, match="floor of 400"):
        go(tav=tav, ledger=ledger)
    assert tav.calls == []


def test_failed_run_keeps_its_reservation(ledger):
    s = T.Store([])
    with pytest.raises(ConnectionError):
        go(store=s, tav=FakeTav(fail=True), ledger=ledger)
    assert s.days[DAY] == s.total == 2 and s.cache == {}


def test_real_budgeted_client_charges_both_caps_in_the_ledger(tmp_path, ledger):
    sent = []

    def transport(method, url, key, body, timeout):
        sent.append(body)
        locked = "start_date" in body
        return {"request_id": "r", "results": LOCKED_RESULTS if locked else OPEN_RESULTS, "usage": {"credits": 1}}

    rec = Recorder(cache_dir=tmp_path / "cache", log_file=tmp_path / "fr.jsonl", use_cache=False)
    tav = Budgeted(Tavily(api_key=KEY, recorder=rec, transport=transport), [T.BUDGET, f"{T.DAY_BUDGET}/{DAY}"],
                   ledger_path=ledger, fresh=True)
    s = T.Store([])
    res, _ = go(store=s, tav=tav, ledger=ledger)
    rows = read_ledger(ledger)
    assert [r["budgets"] for r in rows] == [["try-it", f"try-it-day/{DAY}"]] * 2
    assert sum(r["credits"] for r in rows) == 2 == s.total
    assert all(KEY not in json.dumps(b) for b in sent) and KEY not in (tmp_path / "fr.jsonl").read_text()
    assert T.Store(rows).total == 2                             # a new process starts from the ledger


# ---------- cache ----------
def test_identical_request_within_24h_is_cached(ledger):
    s = T.Store([])
    first, hit = go(store=s, ledger=ledger)
    assert not hit
    tav = FakeTav()
    again, hit = go(question="  PETROL diesel price hike   india may 2026 ", store=s, tav=tav, ledger=ledger, runs=3,
                    key=None)
    assert hit and again is first and tav.calls == [] and s.total == 2
    other, hit = go(cutoff="2026-05-28", store=s, ledger=ledger)
    assert not hit
    later = NOW + timedelta(hours=24, minutes=1)
    tav = FakeTav()
    T.run("petrol diesel price hike India May 2026", CUT, 0, st_store=s, now=later, tav=tav, key=KEY,
          usage_fetch=OK_USAGE, ledger_path=ledger)
    assert len(tav.calls) == 2


# ---------- missing key ----------
def test_missing_key_is_refused_before_any_call(monkeypatch, ledger):
    monkeypatch.delenv("SCPI_TAVILY_API_KEY", raising=False)
    monkeypatch.setattr(T, "setting", lambda name: None)
    tav = FakeTav()
    with pytest.raises(T.Refused, match="no API key"):
        go(key=None, tav=tav, ledger=ledger)
    assert tav.calls == []


def test_saved_example_is_f3_read_from_the_results_file():
    demo = json.loads((ROOT / "results" / "leak_demo.json").read_text())
    res = T.example(demo, "2026-10-22T12:26:26+00:00")
    case = next(c for c in demo["cases"] if c["id"] == "F3")
    assert res["source"] == "saved" and res["question"] == case["query"] and res["cutoff"] == "2026-05-29"
    assert [r["url"] for r in res["open"]["results"]] == [r["url"] for r in case["open"]["results"]]
    assert T.summary(res).startswith("No time lock: 1 of 3 results dated after the cutoff · Time lock: 0 of 3")
    assert T.example(demo, None, "nope") is None


# ---------- the page ----------
st = pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402


@pytest.fixture
def app_env(monkeypatch):
    monkeypatch.chdir(ROOT)
    monkeypatch.setenv("SHADOW_CPI_NO_ANIMATION", "1")
    for k in ("SCPI_TAVILY_API_KEY", "SCPI_NEBIUS_API_KEY", "RUN_LIVE_ENABLED"):
        monkeypatch.delenv(k, raising=False)


def page(own=False):
    """Search the past, the default page; own=True picks "Your own question (live)" (shown only with a key)."""
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    at.run()
    if own:
        at.radio[0].set_value("Your own question (live)").run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def text(at):
    parts = [m.value for m in at.markdown] + [c.value for c in at.caption] + [i.value for i in at.info]
    parts += [w.value for w in at.warning] + [s.value for s in at.success] + [t.value for t in at.title]
    return "\n".join(parts)


def test_page_without_key_explains_and_shows_the_saved_example(app_env, monkeypatch):
    monkeypatch.setattr(T, "setting", lambda name: None)
    at = page()
    t = text(at)
    assert "Search the past" in t and "there is no Tavily key" in t
    assert "Saved example, not a live run: Leak results case F3" in t             # preselected
    assert "No time lock: 1 of 3 results confirmed (Wayback) as published after the cutoff · Time lock: 0 of 3" in t
    assert "Wayback: confirmed leak (Wayback)" in t and "Nothing knowable" not in t
    assert not at.button and not at.text_input                  # no form without a key
    assert at.radio[0].options == [o for o in at.radio[0].options if "Your own question" not in o]


def test_thin_evidence_example_says_so_plainly(app_env, monkeypatch):
    """C5: the time lock returned 5 results and the Wayback Machine confirmed none of them before the cutoff."""
    monkeypatch.setattr(T, "setting", lambda name: None)
    at = page()
    thin = next(o for o in at.radio[0].options if "(thin evidence)" in o)
    at.radio[0].set_value(thin).run()
    t = text(at)
    assert "Saved example, not a live run: Leak results case C5" in t
    assert ("None of the 5 time-locked results was confirmed as published before the cutoff (no archive record "
            "either way), so none counts as evidence. Nothing knowable before 22 Jul 2026; we don't guess.") in t
    order = []                                                     # main-area text in page order

    def walk(node):
        for c in getattr(node, "children", {}).values():
            if c.type in ("markdown", "warning"):
                order.append(c.value)
            walk(c)
    walk(at.main)
    at_ = lambda s: next(i for i, v in enumerate(order) if s in v)            # noqa: E731
    assert at_("Time lock: 0 of 5") < at_("Nothing knowable") < at_("**No time lock**")         # verdict on top


def test_verdict_on_a_live_run_with_nothing_dated_before_the_cutoff():
    res = {"source": "live", "cutoff": "2026-05-29",
           "open": {"results": [{"after": T.YES}]}, "locked": {"results": [{"after": T.UNDATED}]}}
    head, thin = T.verdict(res)
    assert head == "No time lock: 1 of 1 results dated after the cutoff · Time lock: 0 of 1"
    assert thin.endswith("Nothing knowable before 29 May 2026; we don't guess.")
    res["locked"]["results"] = [{"after": T.NO}]
    assert T.verdict(res)[1] is None


def test_page_runs_both_searches_and_shows_two_columns(app_env, monkeypatch):
    monkeypatch.setattr(T, "setting", lambda name: KEY if name == "SCPI_TAVILY_API_KEY" else None)
    seen = []

    def fake_run(q, cut, runs):
        seen.append((q, cut, runs))
        return go(q, cut.isoformat(), runs, ledger=Path("/nonexistent/ledger.jsonl"))

    monkeypatch.setattr(T, "run", fake_run)
    at = page(own=True)
    at.text_input[0].set_value("petrol diesel price hike India May 2026")
    at.date_input[0].set_value(date(2026, 5, 29))
    at.button[0].click()
    at.run()
    assert not at.exception
    t = text(at)
    assert seen == [("petrol diesel price hike India May 2026", date(2026, 5, 29), 0)]
    assert "No time lock: 1 of 3 results dated after the cutoff · Time lock: 0 of 2" in t
    assert "after cutoff: **yes**" in t and "after cutoff: undated" in t and "After \\[it\\]" in t
    assert "Locked 1" in t and KEY not in t
    assert at.session_state["try_it_runs"] == 1


def test_page_cap_shows_a_polite_message_and_the_colab_link(app_env, monkeypatch):
    monkeypatch.setattr(T, "setting", lambda name: KEY if name == "SCPI_TAVILY_API_KEY" else None)

    def refuse(q, cut, runs):
        raise T.Refused("Today's 25 search credits for this page are used up (resets at 00:00 UTC).")

    monkeypatch.setattr(T, "run", refuse)
    at = page(own=True)
    at.text_input[0].set_value("anything")
    at.button[0].click()
    at.run()
    t = text(at)
    assert "Today's 25 search credits" in t and "your own Tavily key in Colab" in t
    assert any(T.COLAB_URL in str(e.proto) for e in at.get("link_button"))
