"""timelocked_search: a Tavily search inside a date window that cannot reach past the cutoff.

Tavily's own date filter is the first lock: every call sends start_date/end_date and
filter_by_published_date=true. Our date check is the second: each result is labelled safe / date_flag / leak
from every date we can see (Tavily's published_date, a date in the address, the page's own date when the page
text was extracted), so a post-cutoff page that slips through the filter is still marked as a leak.
"""
import hashlib
import json
from datetime import date, timedelta

from timelock.check import DATE_FLAG, LEAK, SAFE, check_result
from timelock.dates import iso_date, page_date as read_page_date

DEFAULT_DAYS = 30                                           # default window: the 30 days ending on the cutoff
REFUSED = ("time_range", "days", "auto_parameters")         # would set their own window (auto_parameters can pick
                                                            # a time_range)


class TimeLockError(ValueError):
    """A caller tried to move the window past the cutoff or switch the date filter off."""


def response_sha256(response):
    """SHA-256 of a response: its JSON with sorted keys, no spaces, UTF-8."""
    blob = json.dumps(response, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _iso(name, value):
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError:
        raise TimeLockError(f"{name} must be an ISO date (YYYY-MM-DD), got {value!r}") from None


def window(cutoff, start_date=None, end_date=None):
    """(start, end) as ISO dates. end defaults to the cutoff and may not be after it; start defaults to
    DEFAULT_DAYS - 1 days before the end and may not be after it."""
    cut = _iso("cutoff", cutoff)
    end = _iso("end_date", end_date) if end_date is not None else cut
    if end > cut:
        raise TimeLockError(f"end_date {end} is after the cutoff {cut}")
    start = (_iso("start_date", start_date) if start_date is not None else
             (date.fromisoformat(end) - timedelta(days=DEFAULT_DAYS - 1)).isoformat())
    if start > end:
        raise TimeLockError(f"start_date {start} is after end_date {end}")
    return start, end


class Results(list):
    """The labelled results, plus the call's receipt: window, request_id, response_sha256, counts, response."""

    def __init__(self, items, *, cutoff, window, response, sha256=None):
        super().__init__(items)
        self.cutoff, self.window, self.response = cutoff, window, response
        self.request_id = response.get("request_id")
        self.response_sha256 = sha256 or response_sha256(response)
        self.counts = {lab: sum(r["status"] == lab for r in items) for lab in (SAFE, DATE_FLAG, LEAK)}

    def safe(self):
        return [r for r in self if r["status"] == SAFE]


def timelocked_search(client, query, cutoff, *, page_dates=None, **tavily_kwargs):
    """One Tavily search that cannot see past `cutoff` (ISO date). Returns Results: a list of Tavily's results,
    each with 'published_date' (ISO or None; Tavily's text in 'published_date_raw'), 'page_date' (when the page
    text was extracted, e.g. include_raw_content=True, or given in `page_dates`), 'status' (safe / date_flag /
    leak), 'request_id' and 'response_sha256'.

    `client` is anything with .search(query, **kwargs) -> dict: tavily-python's TavilyClient, timelock.TavilyHTTP,
    or timelock.Replay for a saved response. `tavily_kwargs` go to Tavily (topic, max_results, include_domains,
    start_date/end_date to narrow the window, ...). An end_date after the cutoff, filter_by_published_date other
    than True, time_range, days or auto_parameters raises TimeLockError before any call.
    `page_dates` is an optional {url: ISO date} read from the page another way; it wins over the extracted one."""
    cut = _iso("cutoff", cutoff)
    bad = sorted(k for k in tavily_kwargs if k in REFUSED)
    if bad:
        raise TimeLockError(f"the time lock owns the window; remove {', '.join(bad)}")
    if tavily_kwargs.pop("filter_by_published_date", True) is not True:
        raise TimeLockError("filter_by_published_date is always on inside the time lock")
    start, end = window(cut, tavily_kwargs.pop("start_date", None), tavily_kwargs.pop("end_date", None))
    page_dates = {u: _iso(f"page date for {u}", d) for u, d in (page_dates or {}).items() if d}
    resp = client.search(query, start_date=start, end_date=end, filter_by_published_date=True, **tavily_kwargs)
    receipt = {"request_id": resp.get("request_id"), "response_sha256": response_sha256(resp)}
    out = []
    for r in resp.get("results") or []:
        pd = page_dates.get(r.get("url")) or read_page_date(r.get("raw_content"))[0]
        out.append({**r, "published_date": iso_date(r.get("published_date")) or None,
                    "published_date_raw": r.get("published_date"), "page_date": pd,
                    "status": check_result(r, cut, page_date=pd), **receipt})
    return Results(out, cutoff=cut, window=[start, end], response=resp, sha256=receipt["response_sha256"])
