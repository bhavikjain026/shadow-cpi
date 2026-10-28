"""Time-locked search, then each result read as it was on the cutoff (TAVILY_API_KEY=... python -m examples.asof_search)."""
from timelock import TavilyHTTP, extract_as_of, timelocked_search

client, cutoff = TavilyHTTP(), "2026-10-06"                     # 1 search credit + 1 Extract credit per page
results = timelocked_search(client, "RBI monetary policy repo rate decision October 2026", cutoff, topic="news",
                            max_results=3, include_published_date=True)
for r in results:
    page = extract_as_of(client, r["url"], cutoff, published_date=r.get("published_date"))
    print(r["status"], r["url"], page["provenance"])
    print((page["text"] or "no as-of copy: do not use this page")[:300])
