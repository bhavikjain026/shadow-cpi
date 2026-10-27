"""Tavily item 3: Extract has no as-of view, so Search dates do not freeze page content.

    TAVILY_API_KEY=... python repro/extract_no_asof.py      # 1 credit

Extracts the TCS results preview we call R196 (Tavily dated it 2026-07-07; the page was updated 2026-07-09) and
prints every date-like field Extract returns and every "updated" line in the text. If the page has changed again, the
text will differ from ours; the point is that Extract returns the page as it is now and says nothing about when the
copy was taken.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

MAX_CREDITS = 2
URL = ("https://www.business-standard.com/markets/news/tcs-q1-result-expectations-preview-dividend-record-date-"
       "revenue-seen-flat-wage-hikes-to-weigh-on-margins-126070700096_1.html")
DATE_KEYS = re.compile(r"date|crawl|updated|as_of|fetched|time", re.I)


def main():
    resp = C.call("/extract", {"urls": [URL], "extract_depth": "basic", "include_usage": True}, estimate=1)
    got = (resp.get("results") or [{}])[0]
    text = got.get("raw_content") or ""
    print(f"url: {URL}")
    print(f"top-level response keys: {sorted(resp)}")
    print(f"result keys: {sorted(got)}")
    print(f"date-like keys (as-of / crawl date would show here): {sorted(k for k in list(resp) + list(got) if DATE_KEYS.search(k))}")
    hits = re.findall(r"(?i)(?:updated|modified|published)[^\n]{0,60}", text)[:5]
    print(f"{len(text)} characters of text; 'updated/published' lines in it: {hits}")


if __name__ == "__main__":
    C.run(main)
