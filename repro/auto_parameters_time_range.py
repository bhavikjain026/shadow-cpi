"""Tavily item 1: auto_parameters picks a recent time_range for a query about a past month.

    TAVILY_API_KEY=... python repro/auto_parameters_time_range.py      # 2 credits (auto_parameters is billed as 2)

Sends a query that names a month well in the past, with auto_parameters and max_results only (no dates), then prints
the parameters Tavily says it chose and the months the results are dated. Today's index may differ from ours.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

MAX_CREDITS = 2
QUERY = "electricity tariff hike India March 2026"
ASKED_MONTH = "2026-03"


def main():
    resp = C.call("/search", {"query": QUERY, "auto_parameters": True, "max_results": 10, "include_usage": True},
                  estimate=2)
    results = resp.get("results") or []
    months = C.tally(C.month_of(r.get("published_date")) for r in results)
    print(f"query: {QUERY!r} (asks about {ASKED_MONTH}); no start_date/end_date sent")
    print(f"auto_parameters echo: {resp.get('auto_parameters')}")
    print(f"{len(results)} results; published_date by month (None = undated): {months}")
    print(f"results dated {ASKED_MONTH}: {months.get(ASKED_MONTH, 0)} of {len(results)}")


if __name__ == "__main__":
    C.run(main)
