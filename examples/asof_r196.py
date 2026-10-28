"""extract_as_of on R196: the page as it was on the cutoff, or no text (TAVILY_API_KEY=... python -m examples.asof_r196)."""
import sys

from timelock import TavilyHTTP, extract_as_of

R196 = ("https://www.business-standard.com/markets/news/tcs-q1-result-expectations-preview-dividend-record-date-"
        "revenue-seen-flat-wage-hikes-to-weigh-on-margins-126070700096_1.html")
url, cutoff = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else (R196, "2026-07-08")
page = extract_as_of(TavilyHTTP(), url, cutoff, published_date="2026-07-07" if url == R196 else None)  # 1 credit
print(page["provenance"])           # source tavily_live | wayback_asof | None, capture_time, reason
print(page["evidence"]["changed"], page["request_id"], page["live_sha256"][:12])
print((page["text"] or "no as-of copy: do not use this page")[:500])
