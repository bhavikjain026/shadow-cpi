"""Leak-free research trajectories: every search an agent made for a task, what the time lock said about each result,
and which results were kept as evidence, sealed with a SHA-256 "retrieval receipt" (standard library only).

    from timelock.trajectories import CachedTavily, generate
    traj = generate({"question": "RBI repo rate decision", "searches": [{"query": "RBI repo rate", "topic": "news"}]},
                    "2026-10-06", client=CachedTavily("cache"))        # replay only: 0 credits, no network
    traj["evidence"]["kept"], traj["receipt"]["sha256"]

Offline by default: with no client and no search_fn, generate() refuses rather than call Tavily; pass live=True for a
live TavilyHTTP client. CachedTavily serves saved responses from a Recorder cache (cache/<service>/<request hash>.json)
and raises CacheMiss when a request was never saved: a replay never quietly makes a live call or skips a step.

A result is kept only if code's own look-ahead check (timelock.check_result) says "safe" for every date it can see:
Tavily's date, a date in the address, and the page's own date read by extract_as_of. Undated (date_flag) and
post-cutoff (leak) results are dropped with the reason. The search_fn's own labels are recorded but never trusted, and
a last check refuses to return a trajectory whose kept evidence carries any date after the cutoff.

No page text is written: each result carries a short quote (at most QUOTE_WORDS words of the snippet, else the title)
and, when a page was read, only the SHA-256 of its text.
"""
import functools
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

from timelock.asof import LIVE, WAYBACK, Wayback, extract_as_of
from timelock.check import DATE_FLAG, LEAK, SAFE, check_result
from timelock.clients import TavilyHTTP
from timelock.dates import iso_date, url_date
from timelock.search import _iso, timelocked_search

FORMAT = "timelock-trajectory/1"
QUOTE_WORDS = 25
NOT_RUN = "not_run"                     # extract status when no extract_fn was given
SKIPPED = "skipped"                     # extract status for a result the search check already dropped
_AUTO = object()


class CacheMiss(LookupError):
    """A replay asked for a response that was never saved. Never caught here: a replay with a gap fails loudly."""


def request_hash(service, endpoint, body):
    """The Recorder's cache key (same formula as shadow_cpi.recorder.request_hash; timelock does not import it)."""
    blob = json.dumps({"s": service, "e": endpoint, "b": body}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class CachedTavily:
    """Replay-only Tavily client over a Recorder cache directory. .search/.extract return the saved response for
    exactly this request (include_usage added, as shadow_cpi.tavily does for every call) or raise CacheMiss."""

    def __init__(self, cache_dir):
        self.cache_dir = Path(cache_dir)
        self.retrieved_at = None                    # retrieved_at of the last response served (ISO UTC)

    def load(self, service, endpoint, body):
        path = self.cache_dir / service / f"{request_hash(service, endpoint, body)}.json"
        if not path.exists():
            what = body.get("query") or body.get("urls") or body.get("url")
            raise CacheMiss(f"no saved {service} {endpoint} response for {what!r} in {self.cache_dir}")
        saved = json.loads(path.read_text(encoding="utf-8"))
        self.retrieved_at = saved.get("retrieved_at")
        return saved["response"]

    def search(self, query, **params):
        return self.load("tavily", "/search", {"query": query, **params, "include_usage": True})

    def extract(self, urls, **params):
        """The saved response for exactly these urls; else, for one url, that page's result out of a saved call
        with the same other parameters that asked for several urls at once (the date test extracted in batches)."""
        body = {"urls": list(urls), **params, "include_usage": True}
        try:
            return self.load("tavily", "/extract", body)
        except CacheMiss:
            if len(body["urls"]) != 1:
                raise
        url, rest = body["urls"][0], {k: v for k, v in body.items() if k != "urls"}
        for path in self._batches().get((url, json.dumps(rest, sort_keys=True)), []):
            saved = json.loads(path.read_text(encoding="utf-8"))
            resp = saved["response"]
            hit = [r for r in resp.get("results") or [] if r.get("url") == url]
            if hit:
                self.retrieved_at = saved.get("retrieved_at")
                return {"results": hit[:1], "request_id": resp.get("request_id"), "batch_of": len(saved["request"]
                                                                                                 ["urls"])}
        raise CacheMiss(f"no saved tavily /extract response for {url!r} in {self.cache_dir}")

    @functools.lru_cache(maxsize=None)
    def _batches(self):
        """{(url, other params as JSON): [cache files]} over every saved multi-url /extract call."""
        out = {}
        for path in sorted((self.cache_dir / "tavily").glob("*.json")):
            saved = json.loads(path.read_text(encoding="utf-8"))
            req = saved.get("request") or {}
            if saved.get("endpoint") == "/extract" and len(req.get("urls") or []) > 1:
                rest = json.dumps({k: v for k, v in req.items() if k != "urls"}, sort_keys=True)
                for u in req["urls"]:
                    out.setdefault((u, rest), []).append(path)
        return out


class CachedWayback(Wayback):
    """Wayback lookups from the same cache (service 'direct', as tools/asof_demo_r196.py records them). A lookup that
    was never saved reads as a failed lookup (extract_as_of then refuses the page: "no as-of copy"), so the refusal is
    recorded in the trajectory instead of fetched live; `missing="raise"` turns it into a CacheMiss instead."""

    def __init__(self, cache, missing="refuse"):
        super().__init__()
        self.cache, self.missing = cache, missing

    def _get(self, url):
        try:
            resp = self.cache.load("direct", "GET", {"url": url})
        except CacheMiss:
            if self.missing == "raise":
                raise
            raise OSError(f"Wayback lookup not in the offline cache: {url}") from None
        if "final_url" not in resp:                 # saved by another tool in another shape: not usable here
            raise OSError(f"cached Wayback response has no final_url: {url}")
        return resp["final_url"], resp["text"]


def cached_extract_fn(cache, **wayback_kw):
    """extract_fn for replay: the saved Tavily Extract response, cached Wayback lookups, strict as-of rules, and the
    saved response's own retrieval time as 'now', so the same cache always gives the same trajectory."""
    archive = CachedWayback(cache, **wayback_kw)

    def fn(url, cutoff, published_date=None):
        cache.extract([url], extract_depth="basic")             # CacheMiss here if the page was never extracted
        now = datetime.fromisoformat(cache.retrieved_at) if cache.retrieved_at else None
        return extract_as_of(cache, url, cutoff, published_date=published_date, archive=archive, now=now,
                             strict=True)
    return fn


def live_extract_fn(client, **kw):
    """extract_fn for live mode: extract_as_of with strict=True (Tavily Extract + Wayback; costs credits)."""
    return functools.partial(_live_extract, client, kw)


def _live_extract(client, kw, url, cutoff, published_date=None):
    return extract_as_of(client, url, cutoff, published_date=published_date, strict=True, **kw)


def clip(text, n=QUOTE_WORDS):
    words = (text or "").split()
    return " ".join(words[:n]) + ("…" if len(words) > n else "")


def short_quote(result):
    """(quote, 'snippet' | 'title'): the first sentence of Tavily's snippet, else the title; at most QUOTE_WORDS."""
    first = next((s for s in re.split(r"(?<=[.!?।])\s+|\n+", result.get("content") or "") if s.strip()), "")
    return (clip(first), "snippet") if first else (clip(result.get("title")), "title")


def receipt_sha256(trajectory):
    """SHA-256 of the trajectory without its 'receipt' field: JSON, sorted keys, no spaces, UTF-8."""
    body = {k: v for k, v in trajectory.items() if k != "receipt"}
    blob = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def verify_receipt(trajectory):
    return trajectory.get("receipt", {}).get("sha256") == receipt_sha256(trajectory)


def _task(task):
    """{'question', 'searches': [{'query', **tavily params}]}; a plain string is one search for that string."""
    if isinstance(task, str):
        return {"question": task, "searches": [{"query": task}]}
    searches = task.get("searches") or [{"query": task["question"]}]
    return {**task, "searches": [dict(s) for s in searches]}


def _extract_record(page):
    prov = page.get("provenance") or {}
    ev = page.get("evidence") or {}
    return {"status": prov.get("source") or "refused", "reason": prov.get("reason"),
            "capture_time": prov.get("capture_time"), "page_date": ev.get("page_date"),
            "change_signals": ev.get("changed"), "request_id": page.get("request_id"),
            "text_sha256": page.get("text_sha256")}


def _decide(verdict, extract, require_as_of=False):
    if verdict == LEAK:
        return "dropped", "leak: a date after the cutoff"
    if verdict == DATE_FLAG:
        return "dropped", "date_flag: no date we can check"
    if require_as_of and extract["status"] not in (LIVE, WAYBACK):
        return "dropped", f"safe by every date, but no page copy as of the cutoff ({extract.get('reason') or 'not read'})"
    if extract["status"] == "refused":
        return "kept", f"safe by every date; page text refused ({extract['reason']}), snippet quote only"
    if extract["status"] == NOT_RUN:
        return "kept", "safe by every date; page not read (no extract_fn)"
    return "kept", f"safe by every date; page read as of the cutoff ({extract['status']})"


def _dates(row):
    return [d for d in (row["published_date"], row["url_date"], row["page_date"]) if d]


def generate(task, cutoff, search_fn=None, extract_fn=_AUTO, *, client=None, live=False, require_as_of=False):
    """One trajectory (a JSON-ready dict) for `task` under `cutoff` (ISO date).

    task: a question string, or {'question': ..., 'searches': [{'query': ..., **tavily params}, ...]}.
    search_fn(query, cutoff, **params) -> list of Tavily results with 'request_id' / 'response_sha256' (a
      timelock.Results); defaults to timelocked_search on `client`. With no client: refused unless live=True.
    extract_fn(url, cutoff, published_date) -> an extract_as_of dict, run only on results the search check called
      safe; defaults to cached_extract_fn for a CachedTavily client, live_extract_fn for a live one; None = not run.
    require_as_of: also drop safe results whose page could not be read as of the cutoff. Off by default: a kept
      result is then dated on or before the cutoff, but its snippet comes from today's page unless as_of_verified.
    Raises CacheMiss (replay gap) and TimeLockError (a search tried to leave the window) without catching them."""
    cut = _iso("cutoff", cutoff)
    task = _task(task)
    if search_fn is None:
        if client is None:
            if not live:
                raise ValueError("offline by default: pass client=CachedTavily(cache_dir), a search_fn, or live=True")
            client = TavilyHTTP()
        search_fn = functools.partial(timelocked_search, client)
    if extract_fn is _AUTO:
        extract_fn = (cached_extract_fn(client) if isinstance(client, CachedTavily) else
                      live_extract_fn(client) if client is not None else None)
    mode = "replay" if isinstance(client, CachedTavily) else "live" if client is not None else "custom"

    searches, rows = [], []
    for step, spec in enumerate(task["searches"], 1):
        params = {k: v for k, v in spec.items() if k != "query"}
        res = search_fn(spec["query"], cut, **params)
        searches.append({"step": step, "query": spec["query"], "params": params,
                         "window": getattr(res, "window", None),
                         "request_id": getattr(res, "request_id", None) or (res[0].get("request_id") if res else None),
                         "response_sha256": (getattr(res, "response_sha256", None) or
                                             (res[0].get("response_sha256") if res else None)),
                         "n_results": len(res)})
        for rank, r in enumerate(res, 1):
            pub = iso_date(r.get("published_date")) or None
            first = check_result({**r, "published_date": pub}, cut, page_date=r.get("page_date"))
            extract = {"status": SKIPPED if first != SAFE else NOT_RUN}
            if first == SAFE and extract_fn is not None:
                extract = _extract_record(extract_fn(r.get("url"), cut, pub))
            page_date = r.get("page_date") or extract.get("page_date")
            verdict = check_result({**r, "published_date": pub}, cut, page_date=page_date)
            decision, why = _decide(verdict, extract, require_as_of)
            q, qfrom = short_quote(r)
            rows.append({"step": step, "rank": rank, "url": r.get("url"), "title": clip(r.get("title")),
                         "published_date": pub, "url_date": url_date(r.get("url")), "page_date": page_date,
                         "search_label": r.get("status"), "verdict": verdict, "extract": extract,
                         "decision": decision, "reason": why, "quote": q, "quote_from": qfrom})

    leaked = [r["url"] for r in rows if r["decision"] == "kept" and any(d > cut for d in _dates(r))]
    if leaked:                                     # cannot happen through _decide; refuse rather than emit it
        raise AssertionError(f"kept evidence dated after the cutoff {cut}: {leaked}")
    kept = [{"step": r["step"], "rank": r["rank"], "url": r["url"], "quote": r["quote"],
             "dates": sorted(set(_dates(r))), "as_of_verified": r["extract"]["status"] in (LIVE, WAYBACK),
             "why": r["reason"]} for r in rows if r["decision"] == "kept"]
    dropped = [{"step": r["step"], "rank": r["rank"], "url": r["url"], "why": r["reason"]}
               for r in rows if r["decision"] == "dropped"]
    traj = {"format": FORMAT, "mode": mode, "require_as_of": require_as_of, "task": {k: v for k, v in task.items() if k != "searches"},
            "cutoff": cut, "searches": searches, "results": rows,
            "evidence": {"kept": kept, "dropped": dropped},
            "counts": {"results": len(rows), "kept": len(kept), "dropped": len(dropped),
                       **{lab: sum(r["verdict"] == lab for r in rows) for lab in (SAFE, DATE_FLAG, LEAK)}}}
    traj["receipt"] = {"algorithm": "sha256", "over": "the trajectory without 'receipt', JSON sorted keys, no spaces",
                       "sha256": receipt_sha256(traj)}
    return traj


def dumps(trajectory):
    return json.dumps(trajectory, ensure_ascii=False, sort_keys=True, indent=1) + "\n"
