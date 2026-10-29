"""timelock: search the web as it was on a past date. Standard library only; no Shadow CPI imports.

    from timelock import TavilyHTTP, timelocked_search
    results = timelocked_search(TavilyHTTP(), "RBI repo rate decision October 2026", cutoff="2026-10-06")

extract_as_of(client, url, cutoff) reads a page as it was on the cutoff (Wayback) or refuses; timelock/asof.py.

See "Use it in 10 lines" in the repository README and examples/timelock_rbi.py.
"""
from timelock.asof import LIVE, NO_COPY, UNVERIFIED, URL_MISMATCH, WAYBACK, Wayback, extract_as_of
from timelock.check import DATE_FLAG, LEAK, SAFE, check_result, check_results
from timelock.clients import Replay, TavilyHTTP
from timelock.feedback import build_feedback, own_end_dates, own_request_ids, reason_for, report_leaks, send_feedback
from timelock.dates import iso_date, page_date, url_date
from timelock.search import (DEFAULT_DAYS, REFUSED, Results, TimeLockError, response_sha256, timelocked_search,
                             window)

__all__ = ["timelocked_search", "window", "Results", "TimeLockError", "REFUSED", "DEFAULT_DAYS", "response_sha256",
           "check_result", "check_results", "SAFE", "DATE_FLAG", "LEAK", "iso_date", "url_date", "page_date",
           "TavilyHTTP", "Replay", "build_feedback", "send_feedback", "reason_for", "report_leaks", "own_request_ids", "own_end_dates",
           "extract_as_of", "Wayback", "LIVE", "WAYBACK", "NO_COPY",
           "URL_MISMATCH", "UNVERIFIED"]
