"""pit_search: a Tavily search inside a time lock the caller cannot move.

Every call sends start_date/end_date and filter_by_published_date=true (and include_usage, via shadow_cpi.tavily),
keeps Tavily's request_id and the response's SHA-256 (also written to the Flight Recorder by Recorder), and runs
shadow_cpi.leakcheck.check_result on every result. Tavily's filter is the first lock, our date check the second:
  - safe results are kept;
  - undated results are flagged, not trusted (kept apart, never mixed into `kept`);
  - results with any date after the cutoff are dropped as leaks, whatever Tavily's filter let through.
"""
from datetime import date

from shadow_cpi.leakcheck import DATE_FLAG, LEAK, SAFE, check_result
from shadow_cpi.recorder import provenance

# parameters that would move or loosen the window; the lock owns them
LOCKED = ("start_date", "end_date", "filter_by_published_date", "time_range", "days", "auto_parameters")


class TimeLockError(ValueError):
    """A caller tried to set a parameter the time lock owns."""


def window_for(cutoff, start=None):
    """(start, end): `start` (default: the first day of the cutoff's month) to the cutoff, both ISO dates."""
    end = date.fromisoformat(cutoff).isoformat()
    s = date.fromisoformat(start).isoformat() if start else end[:8] + "01"
    if s > end:
        raise TimeLockError(f"window start {s} is after the cutoff {end}")
    return s, end


def pit_search(query, cutoff, *, start=None, tavily=None, page_dates=None, parent=None, tag="pit", **params):
    """One time-locked search. Returns {'query', 'cutoff', 'window', 'call_id', 'request_id', 'response_sha256',
    'credits', 'response_time', 'counts', 'kept', 'flagged', 'leaks', 'results'}.

    `params` are passed to Tavily search (topic, max_results, include_domains, ...), except the LOCKED ones.
    `page_dates` is an optional {url: ISO date} from the page itself (e.g. v2.date_test.page_date); a page date after
    the cutoff makes a result a leak even when Tavily's date is inside the window.
    `credits` is Tavily's usage.credits as returned; it can read 0 for calls below Tavily's reporting threshold, so
    count credits from the ledger or /usage, not by summing this field."""
    bad = sorted(k for k in params if k in LOCKED)
    if bad:
        raise TimeLockError(f"the time lock owns {', '.join(bad)}; set the cutoff (and start) instead")
    if tavily is None:
        from shadow_cpi.tavily import Tavily
        tavily = Tavily()
    s, e = window_for(cutoff, start)
    resp, call_id = tavily.search(query, start_date=s, end_date=e, filter_by_published_date=True,
                                  parent=parent, tag=tag, **params)
    page_dates = page_dates or {}
    results = [{**r, "pit_label": check_result(r, e, page_date=page_dates.get(r.get("url")))}
               for r in resp.get("results", [])]
    by = {lab: [r for r in results if r["pit_label"] == lab] for lab in (SAFE, DATE_FLAG, LEAK)}
    return {"query": query, "cutoff": e, "window": [s, e], "call_id": call_id, **provenance(resp),
            "credits": (resp.get("usage") or {}).get("credits"), "response_time": resp.get("response_time"),
            "counts": {lab: len(v) for lab, v in by.items()}, "kept": by[SAFE], "flagged": by[DATE_FLAG],
            "leaks": by[LEAK], "results": results}
