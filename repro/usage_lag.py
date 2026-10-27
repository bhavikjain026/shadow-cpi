"""Tavily item 7: /usage lags per-call usage.

    TAVILY_API_KEY=... python repro/usage_lag.py      # 1 credit (one basic search; GET /usage is free)

Reads GET /usage, makes one basic search that reports its own credits, reads GET /usage again straight away, and
prints the three numbers. If /usage has caught up the difference is the search's credits; if it lags, it is smaller.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

MAX_CREDITS = 2


def plan_usage(resp):
    return ((resp.get("account") or {}).get("plan_usage"), (resp.get("key") or {}).get("usage"))


def main():
    before = C.call("/usage", None, estimate=0, method="GET")
    resp = C.call("/search", {"query": "RBI repo rate", "max_results": 1, "include_usage": True}, estimate=1)
    after = C.call("/usage", None, estimate=0, method="GET")
    spent = (resp.get("usage") or {}).get("credits")
    print(f"/usage (account plan_usage, key usage) before: {plan_usage(before)}; after: {plan_usage(after)}")
    print(f"the search reported {spent} credit(s); /usage moved by "
          f"{(plan_usage(after)[0] or 0) - (plan_usage(before)[0] or 0)} (account) and "
          f"{(plan_usage(after)[1] or 0) - (plan_usage(before)[1] or 0)} (key)")


if __name__ == "__main__":
    C.run(main)
