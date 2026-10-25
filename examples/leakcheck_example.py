"""10-line example: label a Tavily response's results against a replay cutoff (no API call here)."""
from shadow_cpi.leakcheck import check_results

response = {"results": [  # e.g. resp from Tavily(...).search("RBI repo rate decision October 2026")
    {"url": "https://news.example/2026/10/07/rbi-hikes", "published_date": "2026-10-07"},
    {"url": "https://news.example/rbi-preview", "published_date": "2026-10-03"},
    {"url": "https://news.example/rbi-explainer"}]}                     # undated: flagged, not dropped
counts, labelled = check_results(response["results"], cutoff="2026-10-06")
print(counts)                                                          # {'safe': 1, 'date_flag': 1, 'leak': 1}
