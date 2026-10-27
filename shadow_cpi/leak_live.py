"""Leak demo, live mode: one question, one cutoff, two Tavily searches (no time lock; Tavily's time lock), results
labelled only "date flag" or "safe". No Nemotron, no Wayback, so never "leak": a live date flag is a date signal,
not a confirmed leak.

Off unless RUN_LIVE_ENABLED (shadow_cpi.live_run.gate with tavily_only=True: the credit floor, the daily and
per-visitor limits and Tavily's /usage check). Each run is held to the hard caps 'run-now' and 'run-now-scan' by
shadow_cpi.budget and recorded in the same daily count as Home's "Run live".
"""
import json
import time
from datetime import date, datetime, timedelta, timezone

from .budget import LEDGER, Budgeted
from .live_run import STATE_FILE, runs_on
from .tavily import iso_date

BASE = {"topic": "news", "search_depth": "basic", "max_results": 5, "include_published_date": True}
WINDOW_DAYS = 29                                   # the finance check's window: cutoff - 29 days to the cutoff
MAX_QUESTION = 200


def params(cutoff, locked):
    """The two request bodies (minus the query): no time lock, and Tavily's time lock."""
    if not locked:
        return {**BASE, "filter_by_published_date": False}
    start = (date.fromisoformat(cutoff) - timedelta(days=WINDOW_DAYS)).isoformat()
    return {**BASE, "start_date": start, "end_date": cutoff, "filter_by_published_date": True}


def label(published, cutoff):
    """'date flag' when Tavily's published date is after the cutoff or missing (unknown is never safe), else 'safe'."""
    d = iso_date(published)
    return "safe" if d and d <= cutoff else "date flag"


def run_pair(tavily_key, question, cutoff, now=None, path=STATE_FILE, transport=None, recorder=None,
             ledger_path=LEDGER):
    """Both searches for one question. Records the run (daily count) before any call. Returns both sides with the
    request body sent, credits, latency, Tavily's request id and the labelled results."""
    from .recorder import Recorder
    from .tavily import Tavily
    q = " ".join((question or "").split())[:MAX_QUESTION]
    if not q:
        raise ValueError("empty question")
    date.fromisoformat(cutoff)
    now = now or datetime.now(timezone.utc)
    day = now.date().isoformat()
    n = runs_on(day, path) + 1
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps({"day": day, "n": n, "started_utc": now.isoformat(), "what": "leak demo"}) + "\n")
    kw = {"transport": transport} if transport else {}
    tav = Budgeted(Tavily(api_key=tavily_key, recorder=recorder or Recorder(use_cache=False), **kw),
                   ["run-now", f"run-now-scan/{day}#{n}"], ledger_path=ledger_path, fresh=True)
    out = {"question": q, "cutoff": cutoff, "utc": now.isoformat()}
    for side, locked in (("open", False), ("locked", True)):
        body = {"query": q, **params(cutoff, locked)}
        used, t0 = tav.used, time.time()
        resp, _ = tav.search(q, **params(cutoff, locked), tag=f"live:leak demo {side}")
        out[side] = {"request": {**body, "include_usage": True}, "credits": tav.used - used,
                     "latency_s": resp.get("response_time", round(time.time() - t0, 2)),
                     "request_id": resp.get("request_id"),
                     "results": [{"url": r.get("url"), "title": r.get("title") or r.get("url"),
                                  "published_date": iso_date(r.get("published_date")) or None,
                                  "label": label(r.get("published_date"), cutoff)} for r in resp.get("results", [])]}
    return out
