#!/usr/bin/env python3
"""Build results/cost_vs_results.json: Tavily Search cost against what came back, by (search_depth, max_results),
from saved runs only (0 credits, no API call).

    python tools/build_cost_table.py [--log logs/flight_recorder.jsonl] [--cache cache]

The flight recorder (git-ignored) lists every search, whether it was a cache hit, and its cache key. The cache file
holds the request (search_depth, max_results) and the response (results, published_date, response_time). Credits are
Tavily's own count (include_usage) saved in the flight recorder, which matches the ledger (results/credit_ledger.jsonl)
wherever both exist and also covers the calls made before the ledger started; the ledger fills any gap.
A search sent with auto_parameters and no search_depth is its own row, "auto" (Tavily chose the depth). Only real calls are counted (cache hits
cost nothing and would repeat a real call's results). Written once from a machine that has the cache, so the field
report can be rebuilt from committed files alone. No page text is copied: counts, credits and seconds only.

This is descriptive, not an experiment: each setting was used by different tasks with different queries, so the rows
are not a controlled comparison (the note in the file says so).
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from shadow_cpi.budget import read_ledger  # noqa: E402
from shadow_cpi.recorder import CACHE_DIR, LOG_FILE, read_log  # noqa: E402

OUT = ROOT / "results" / "cost_vs_results.json"
DEFAULT_MAX = 5                       # Tavily's documented default when max_results is not sent
NOTE = ("Descriptive, from saved runs: each setting was used by different tasks and queries, so rows are not a "
        "controlled comparison. Real calls only; credits are Tavily's own count per call.")


def depth_of(req):
    return req.get("search_depth") or ("auto" if req.get("auto_parameters") else "basic")


def task_of(tag):
    """'v2:ablation T 2026-03' -> 'ablation', 'radar:2026-10-26 corroborate' -> 'radar', 'poll-2026-01' -> 'poll'."""
    t = re.sub(r"^v2:", "", tag or "").split(":")[0].split(" ")[0]
    return re.sub(r"-\d{4}-\d{2}(-\d{2})?$", "", t)


def request_of(cache_dir, entry):
    p = Path(cache_dir) / "tavily" / f"{entry['cache_key']}.json"
    if not p.exists():
        return None, None
    d = json.loads(p.read_text(encoding="utf-8"))
    return d.get("request") or {}, d.get("response") or {}


def build(log=LOG_FILE, cache_dir=CACHE_DIR, ledger=None):
    ledger = ledger if ledger is not None else read_ledger()
    credits = defaultdict(int)
    for r in ledger:
        credits[r["call_id"]] += r.get("credits") or 0
    groups = defaultdict(list)
    missing = 0
    for e in read_log(log):
        if e.get("service") != "tavily" or e.get("endpoint") != "/search" or e.get("cached"):
            continue
        req, resp = request_of(cache_dir, e)
        if req is None:
            missing += 1
            continue
        results = resp.get("results") or []
        key = (depth_of(req), req.get("max_results") or DEFAULT_MAX)
        cr = e.get("credits") if e.get("credits") is not None else credits.get(e["id"], 0)
        groups[key].append({"credits": cr, "n": len(results),
                            "dated": sum(1 for x in results if x.get("published_date")),
                            "seconds": resp.get("response_time"), "tag": task_of(e.get("tag"))})
    rows = []
    for (depth, mx), calls in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        n_res = sum(c["n"] for c in calls)
        cr = sum(c["credits"] for c in calls)
        secs = [float(c["seconds"]) for c in calls if c["seconds"] not in (None, "")]
        rows.append({"search_depth": depth, "max_results": mx, "calls": len(calls), "credits": cr,
                     "credits_per_call": cr / len(calls), "results": n_res, "results_per_call": n_res / len(calls),
                     "fill_rate": n_res / (mx * len(calls)), "credits_per_100_results": 100 * cr / n_res if n_res
                     else None, "dated_share": sum(c["dated"] for c in calls) / n_res if n_res else None,
                     "median_seconds": median(secs) if secs else None, "mean_seconds": mean(secs) if secs else None,
                     "tasks": sorted({c["tag"] for c in calls if c["tag"]})})
    return {"built": date.today().isoformat(), "note": NOTE, "credits_spent_building": 0, "rows": rows,
            "calls_without_cache_file": missing, "default_max_results": DEFAULT_MAX}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--log", default=LOG_FILE)
    ap.add_argument("--cache", default=CACHE_DIR)
    a = ap.parse_args(argv)
    out = build(a.log, a.cache)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for r in out["rows"]:
        print(f"{r['search_depth']:8} max {r['max_results']:>2}: {r['calls']:4} calls, {r['credits']:4} credits, "
              f"{r['results_per_call']:.1f} results/call")
    print(f"wrote {OUT.relative_to(ROOT).as_posix()} ({out['calls_without_cache_file']} calls without a cache file)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
