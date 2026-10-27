"""Tavily item 4 (feature request): separate original-publication and last-modified dates.

    TAVILY_API_KEY=... python repro/published_vs_modified.py      # 1 credit

Searches for the TCS results preview with raw page text and prints, for each result, Tavily's published_date next to
any "published" / "updated" date written in the page text, so a gap between the two is visible. Tavily documents
published_date as published or last updated; this only shows that you cannot tell which one you got.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

MAX_CREDITS = 2
QUERY = "TCS Q1 results expectations preview dividend record date"
LINE = re.compile(r"(?i)\b(published|updated|modified)\b[^\n]{0,50}")


def main():
    resp = C.call("/search", {"query": QUERY, "topic": "news", "max_results": 5, "include_published_date": True,
                              "include_raw_content": True, "include_usage": True}, estimate=1)
    for r in resp.get("results") or []:
        m = LINE.search(r.get("raw_content") or "")
        print(f"{r.get('published_date')!s:>26}  page says: {m.group(0).strip()[:70] if m else '-'}  {r['url'][:80]}")


if __name__ == "__main__":
    C.run(main)
