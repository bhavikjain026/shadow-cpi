#!/usr/bin/env python3
"""MCP server exposing timelock's timelocked_search as one tool (stdio). Setup: mcp/README.md.

    pip install -r mcp/requirements.txt
    TAVILY_API_KEY=... python mcp/server.py
    TIMELOCK_REPLAY=tests/fixtures/timelock/rbi_2026-10-06_locked.json python mcp/server.py   # saved response, no key

Only results dated on or before the cutoff reach the model with their URL, title and snippet; undated results and
leaks come back as domain, dates and status only (a news URL's slug can state the outcome).
"""
import os
import sys
from pathlib import Path

# the repository root, appended (not prepended) so the installed `mcp` package wins over this folder
sys.path.append(str(Path(__file__).resolve().parents[1]))
from timelock import SAFE, Replay, TavilyHTTP, timelocked_search  # noqa: E402

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


def build_server():
    from mcp.server.fastmcp import FastMCP
    server = FastMCP("timelock")
    server.tool(name="timelocked_search")(search)
    return server


if __name__ == "__main__":
    build_server().run()
