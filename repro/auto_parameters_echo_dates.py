"""Tavily item 2: with explicit dates, the auto_parameters echo still reports a time_range.

    TAVILY_API_KEY=... python repro/auto_parameters_echo_dates.py      # 2 credits

Sends auto_parameters together with our own start_date/end_date, then prints the echo and whether the results sit
inside the window we sent (so you can see whether the dates were applied even though the echo may not show them).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

MAX_CREDITS = 2
QUERY = "electricity tariff hike India March 2026"
START, END = "2026-03-01", "2026-03-31"


def main():
    resp = C.call("/search", {"query": QUERY, "auto_parameters": True, "start_date": START, "end_date": END,
                              "max_results": 10, "include_usage": True}, estimate=2)
    echo = resp.get("auto_parameters") or {}
    results = resp.get("results") or []
    dated = [str(r["published_date"])[:10] for r in results if r.get("published_date")]
    inside = [d for d in dated if START <= d <= END]
    print(f"sent window: {START} to {END}")
    print(f"auto_parameters echo: {echo}")
    print(f"echo shows start_date or end_date: {bool(echo.get('start_date') or echo.get('end_date'))}; "
          f"echo shows time_range: {'time_range' in echo}")
    print(f"{len(dated)} dated results, {len(inside)} inside the window ({len(results) - len(dated)} undated)")


if __name__ == "__main__":
    C.run(main)
