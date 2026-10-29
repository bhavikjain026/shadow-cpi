#!/usr/bin/env python3
"""MCP server exposing timelock's timelocked_search, extract_as_of and check_leaks as three tools (stdio). Setup: mcp/README.md.

    pip install -r mcp/requirements.txt
    TAVILY_API_KEY=... python mcp/server.py
    TIMELOCK_REPLAY=tests/fixtures/timelock/rbi_2026-10-06_locked.json python mcp/server.py   # saved response, no key

Only results dated on or before the cutoff reach the model with their URL, title and snippet; undated results and
leaks come back as domain, dates and status only (a news URL's slug can state the outcome). extract_as_of returns
a page's text only as it was on the cutoff (live copy if unchanged, else a Wayback capture), or no text.
check_leaks audits results you already have (any search tool's output): no API call, no credit.
"""
import functools
import json
import os
import sys
from pathlib import Path

# the repository root, appended (not prepended) so the installed `mcp` package wins over this folder
sys.path.append(str(Path(__file__).resolve().parents[1]))
from timelock import (DATE_FLAG, LEAK, SAFE, Replay, TavilyHTTP, TimeLockError, check_result,  # noqa: E402
                      extract_as_of, iso_date, timelocked_search, url_date, window)

from urllib.parse import urlparse  # noqa: E402

# what a date_flag or leak result keeps: no text and no full URL (news slugs often state the outcome)
SHOWN_IF_NOT_SAFE = ("published_date", "url_date", "page_date", "status")


def structured_errors(tool):
    """A refusal by the time lock (a date that is not YYYY-MM-DD, an end_date after the cutoff, ...) comes back as
    {"error": {"code", "message", "field", ...}} instead of an exception, so the model can read it and correct the
    call. Other failures (no key, a network error) still raise."""
    @functools.wraps(tool)
    def wrapper(*args, **kwargs):
        try:
            return tool(*args, **kwargs)
        except TimeLockError as e:
            return e.to_dict()
    return wrapper


def client():
    replay = os.environ.get("TIMELOCK_REPLAY")
    return Replay(replay) if replay else TavilyHTTP()


@structured_errors
def search(query: str, cutoff: str, topic: str = "general", max_results: int = 5,
           include_domains: list[str] | None = None, exclude_domains: list[str] | None = None,
           start_date: str | None = None, end_date: str | None = None, search_depth: str = "basic",
           include_raw_content: bool = False) -> dict:
    """Search the web as it was on `cutoff` (YYYY-MM-DD): nothing published after it. The cutoff is a date the
    user or task sets; do not move it to get more results. The cutoff day itself is inside the window; a result
    counts by the UTC date of its published_date. A cutoff date means the end of that day in UTC: results dated on or before it (in UTC) pass; for IST, a page published 00:00–05:30 IST on the next day still counts as the cutoff day, so pass the previous day if you need a strict IST cutoff.

    Refused (returns {"error": {"code", "message", "field"}} and makes no search): a cutoff, start_date or end_date
    that is not YYYY-MM-DD (invalid_date); an end_date after the cutoff (end_date_after_cutoff: the window may be
    narrowed, never extended); a start_date after the end_date (start_date_after_end_date). The server never sends
    time_range, days or auto_parameters (they would set their own window) and the published-date filter is always on.

    Withheld from what you read: each result has a status. safe (dated on or before the cutoff) comes with title,
    URL and snippet. date_flag (no date anywhere: cannot be trusted) and leak (dated after the cutoff) come back as
    domain, dates and status only, because a news URL's slug often states the outcome. A snippet is a pointer, not
    evidence: read the page (extract_as_of) before quoting it. include_raw_content=True also checks each page's own
    published/updated date (page text is not returned)."""
    window(cutoff, start_date, end_date)                # refuse bad dates before a client (or a key) is needed
    return run(client(), query, cutoff, topic=topic, max_results=max_results, include_domains=include_domains,
               exclude_domains=exclude_domains, start_date=start_date, end_date=end_date, search_depth=search_depth,
               include_raw_content=include_raw_content)


def run(tavily, query, cutoff, *, include_raw_content=False, **params):
    """search() with an explicit client (tests pass a saved response). Empty optional parameters are not sent."""
    kw = {k: v for k, v in params.items() if v is not None}
    if include_raw_content:
        kw["include_raw_content"] = True
    results = timelocked_search(tavily, query, cutoff, include_published_date=True, **kw)
    shown = [{k: v for k, v in r.items() if k != "raw_content"} if r["status"] == SAFE else
             {"domain": urlparse(r.get("url") or "").netloc, **{k: r.get(k) for k in SHOWN_IF_NOT_SAFE}}
             for r in results]
    return {"cutoff": results.cutoff, "window": results.window, "counts": results.counts,
            "request_id": results.request_id, "response_sha256": results.response_sha256, "results": shown}


@structured_errors
def as_of(url: str, cutoff: str, published_date: str | None = None, max_chars: int = 20000,
          strict: bool = False) -> dict:
    """Read the page at `url` as it was on `cutoff` (YYYY-MM-DD). A cutoff date means the end of that day in UTC: results dated on or before it (in UTC) pass; for IST, a page published 00:00–05:30 IST on the next day still counts as the cutoff day, so pass the previous day if you need a strict IST cutoff. Tavily Extract returns the page as it is now, so
    if anything suggests it changed after the cutoff (its own date, Tavily's `published_date` from the search that
    found it, or Wayback captures that differ), the latest Wayback Machine capture on or before the cutoff is returned
    instead. If there is none, `text` is null and the reason is "no as-of copy": do not use the page. If nothing
    suggests a change but no capture on or before the cutoff confirms it, the live page comes back with the reason
    "unverified: no archive copy before the cutoff" (strict=true refuses it instead). If Extract answers for another
    address, `text` is null and the reason is "url mismatch". `provenance` says which copy you got (source
    tavily_live or wayback_asof, capture_time, reason; for a Wayback copy also capture_timestamp and capture_digest).

    Refused: a cutoff that is not YYYY-MM-DD (returns {"error": {"code": "invalid_date", ...}}); the live page
    whenever anything suggests it changed after the cutoff (text is null, reason "no as-of copy", because it would
    show you the future); a Wayback capture that is not status 200 or is dated after the cutoff; Extract text for
    another address ("url mismatch"). Needs a live Tavily key (1 credit)."""
    window(cutoff)                                      # refuse a bad cutoff before a client (or a key) is needed
    tavily = client()
    if isinstance(tavily, Replay):
        raise ValueError("extract_as_of needs a live Tavily key (TIMELOCK_REPLAY holds a saved search only)")
    return run_as_of(tavily, url, cutoff, published_date=published_date, max_chars=max_chars, strict=strict)


def run_as_of(tavily, url, cutoff, *, published_date=None, max_chars=20000, archive=None, strict=False):
    """as_of() with an explicit client and archive (tests pass fakes). Text is cut to max_chars."""
    out = extract_as_of(tavily, url, cutoff, published_date=published_date, archive=archive, strict=strict)
    text = out["text"]
    return {**out, "text": text[:max_chars] if text is not None else None,
            "truncated": text is not None and len(text) > max_chars}


@structured_errors
def check_leaks(results_json: str, cutoff: str) -> dict:
    """Audit search results for look-ahead against `cutoff` (YYYY-MM-DD). `results_json` is the JSON of a list of
    results or of a whole search response with a "results" list; each result may carry url, published_date and
    page_date. No API call. Returns counts (safe / date_flag / leak), how many results are `undated`, the `leaks`
    (dated after the cutoff, with the dates seen) and `re_read`: the URLs of every leak and undated result, to read
    with extract_as_of (1 credit each) instead of trusting their current text. A safe result is only dated on or before
    the cutoff; it may still have been edited since, which extract_as_of also catches. A cutoff that is not
    YYYY-MM-DD returns {"error": {"code": "invalid_date", ...}}; results_json that is not a JSON list of results (or
    an object with a "results" list) is an error. Nothing is refused otherwise: this tool only labels, it never
    hides a result or fetches anything."""
    cut = window(cutoff)[1]
    try:
        data = json.loads(results_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"results_json is not valid JSON: {e}") from None
    items = data.get("results") if isinstance(data, dict) else data
    if not isinstance(items, list) or not all(isinstance(r, dict) for r in items):
        raise ValueError('results_json must be a list of result objects or an object with a "results" list')
    counts, leaks, re_read, undated = {SAFE: 0, DATE_FLAG: 0, LEAK: 0}, [], [], 0
    for r in items:
        page = iso_date(r.get("page_date")) or None
        status = check_result(r, cut, page_date=page)
        counts[status] += 1
        if status == SAFE:
            continue
        if status == DATE_FLAG:
            undated += 1
        else:
            leaks.append({"url": r.get("url"), "status": status, "published_date": iso_date(r.get("published_date")) or None,
                          "url_date": url_date(r.get("url")), "page_date": page})
        if r.get("url") and r["url"] not in re_read:
            re_read.append(r["url"])
    return {"cutoff": cut, "checked": len(items), "counts": counts, "undated": undated, "leaks": leaks,
            "re_read": re_read}


def build_server():
    from mcp.server.fastmcp import FastMCP
    server = FastMCP("timelock")
    server.tool(name="timelocked_search")(search)
    server.tool(name="extract_as_of")(as_of)
    server.tool(name="check_leaks")(check_leaks)
    return server


if __name__ == "__main__":
    build_server().run()
