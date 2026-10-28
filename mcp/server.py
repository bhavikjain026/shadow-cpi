#!/usr/bin/env python3
"""MCP server exposing timelock's timelocked_search and extract_as_of as two tools (stdio). Setup: mcp/README.md.

    pip install -r mcp/requirements.txt
    TAVILY_API_KEY=... python mcp/server.py
    TIMELOCK_REPLAY=tests/fixtures/timelock/rbi_2026-10-06_locked.json python mcp/server.py   # saved response, no key

Only results dated on or before the cutoff reach the model with their URL, title and snippet; undated results and
leaks come back as domain, dates and status only (a news URL's slug can state the outcome). extract_as_of returns
a page's text only as it was on the cutoff (live copy if unchanged, else a Wayback capture), or no text.
"""
import os
import sys
from pathlib import Path

# the repository root, appended (not prepended) so the installed `mcp` package wins over this folder
sys.path.append(str(Path(__file__).resolve().parents[1]))
from timelock import SAFE, Replay, TavilyHTTP, extract_as_of, timelocked_search  # noqa: E402

from urllib.parse import urlparse  # noqa: E402

# what a date_flag or leak result keeps: no text and no full URL (news slugs often state the outcome)
SHOWN_IF_NOT_SAFE = ("published_date", "url_date", "page_date", "status")


def client():
    replay = os.environ.get("TIMELOCK_REPLAY")
    return Replay(replay) if replay else TavilyHTTP()


def search(query: str, cutoff: str, topic: str = "general", max_results: int = 5,
           include_domains: list[str] | None = None, exclude_domains: list[str] | None = None,
           start_date: str | None = None, end_date: str | None = None, search_depth: str = "basic",
           include_raw_content: bool = False) -> dict:
    """Search the web as it was on `cutoff` (YYYY-MM-DD): nothing published after it. The cutoff is a date the
    user or task sets; do not move it to get more results. start_date/end_date may narrow the window, never extend
    it past the cutoff. Each result has a status: safe (dated on or before the cutoff; title and snippet included),
    date_flag (undated: not trusted) or leak (dated after the cutoff); those two come back as domain, dates and status
    only. A snippet is a
    pointer, not evidence: read the page before quoting it. include_raw_content=True also checks each page's own
    published/updated date (page text is not returned)."""
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


def as_of(url: str, cutoff: str, published_date: str | None = None, max_chars: int = 20000,
          strict: bool = False) -> dict:
    """Read the page at `url` as it was on `cutoff` (YYYY-MM-DD). Tavily Extract returns the page as it is now, so
    if anything suggests it changed after the cutoff (its own date, Tavily's `published_date` from the search that
    found it, or Wayback captures that differ), the latest Wayback Machine capture on or before the cutoff is returned
    instead. If there is none, `text` is null and the reason is "no as-of copy": do not use the page. If nothing
    suggests a change but no capture on or before the cutoff confirms it, the live page comes back with the reason
    "unverified: no archive copy before the cutoff" (strict=true refuses it instead). If Extract answers for another
    address, `text` is null and the reason is "url mismatch". `provenance` says which copy you got (source
    tavily_live or wayback_asof, capture_time, reason)."""
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


def build_server():
    from mcp.server.fastmcp import FastMCP
    server = FastMCP("timelock")
    server.tool(name="timelocked_search")(search)
    server.tool(name="extract_as_of")(as_of)
    return server


if __name__ == "__main__":
    build_server().run()
