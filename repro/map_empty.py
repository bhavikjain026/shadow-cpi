"""Tavily item 5: Map returns empty results silently.

    TAVILY_API_KEY=... python repro/map_empty.py      # 2 credits (Map with instructions)
    TAVILY_API_KEY=... python repro/map_empty.py --no-instructions      # 1 credit

Maps a regulator site that returned nothing for us (merc.gov.in) and prints whether an empty answer comes with any
reason: an error, failed_results, or another field. The site may answer differently by the time you run it.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

MAX_CREDITS = 2
SITE = "https://merc.gov.in"


def main():
    body = {"url": SITE, "limit": 10, "allow_external": False, "include_usage": True}
    with_instructions = "--no-instructions" not in sys.argv
    if with_instructions:
        body["instructions"] = "tariff orders 2026"
    resp = C.call("/map", body, estimate=2 if with_instructions else 1)
    urls = resp.get("results") or []
    print(f"site: {SITE}; instructions: {with_instructions}")
    print(f"response keys: {sorted(resp)}")
    print(f"{len(urls)} urls; failed_results: {resp.get('failed_results')!r}; error: {resp.get('error')!r}")
    if not urls:
        print("empty answer; reason-like keys present: "
              f"{sorted(k for k in resp if k in ('reason', 'message', 'detail', 'warning', 'failed_results', 'error'))}")


if __name__ == "__main__":
    C.run(main)
