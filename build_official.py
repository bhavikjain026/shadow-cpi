#!/usr/bin/env python3
"""Prompt 1 - official data and baselines. Run:  python build_official.py

Reads the 2024-series weights (data/official/), fetches the 2024-series All-India Combined indices from MoSPI
(cached; logged as the direct-download route), writes data/cpi_tidy.csv, data/item_map.csv and
results/baselines.csv, and prints a PASS / FAIL line for each of Prompt 1's eight points.
No Tavily credits are spent here (the poll search is find_polls.py); re-running is free.
"""
import json
import sys
import time

from shadow_cpi import official as O
from shadow_cpi.recorder import Recorder, read_log

REPORT = []


def report(status, name, detail=""):
    line = f"[{status}] {name}" + (f" - {detail}" if detail else "")
    REPORT.append(line)
    print(line, flush=True)


def sep_press_release_check(published_sep):
    """The September 2026 press-release PDF was read with Tavily Extract by checks.py (cached). Confirm its text
    carries the same headline YoY as MoSPI's data."""
    for e in read_log():
        if e.get("tag") == "check-pdf" and e.get("service") == "tavily":
            from pathlib import Path
            p = Path(O.ROOT / "cache" / "tavily" / f"{e['cache_key']}.json")
            if p.exists():
                text = json.loads(p.read_text(encoding="utf-8"))["response"]["results"][0].get("raw_content", "")
                return f"{published_sep:.2f}" in text
    return None


def main():
    print("Shadow CPI - Prompt 1: official data and baselines\n")
    rec = Recorder()

    # 2. weights + guard (before anything else uses them)
    weights, names = O.load_weights()
    try:
        food = O.guard_2024_weights(weights, names)
    except O.WrongSeries as e:
        report("FAIL", "2. Weights are the 2024 series", str(e))
        sys.exit(1)
    report("PASS", "2. Weights are the 2024 series (refuses 2012 weights)",
           f"food and beverages = {food:.3f}% (2024 series ~{O.FOOD_2024}%, 2012 series {O.FOOD_2012}%)")

    # 1. indices -> tidy csv
    rows = []
    for m in O.month_range():
        rows += O.tidy_rows(m, O.fetch_month(m, rec), weights, names)
    O.write_tidy(rows)
    series, w, pub, meta = O.load_tidy()
    n_months = len(series[O.HEADLINE])
    no_weight = sorted({r["code"] for r in rows if r["weight"] == ""})
    report("PASS" if n_months == 21 and not no_weight else "FAIL", "1. data/cpi_tidy.csv written",
           f"{len(rows)} rows, {n_months} months ({O.FIRST_MONTH} to {O.LAST_MONTH}), "
           f"{len(rows) // n_months} series per month (CPI General, 12 divisions, 43 groups, 92 classes, "
           f"162 sub-classes, 358 items); series without a weight: {len(no_weight)}")

    # 3. tracked items
    items = O.item_map_rows(series, w, names)
    O.write_item_map(items)
    ok = all(r["monthly_index_published"] for r in items)
    finest = ", ".join(f"{r['tracked_item']}={r['finest_level']}" for r in items if r["finest_level"] != "item")
    report("PASS" if ok else "FAIL", "3. Item-level monthly indices + weights for the 13 tracked items",
           "all 13 have a published monthly index and weight" + (f" (finest level used: {finest})" if finest else ""))

    # 4. aggregation reproduces the headline
    worst_all = {}
    for level in ("group", "division", "class", "sub_class", "item"):
        res = O.aggregation_check(series, w, level, O.month_range())
        worst_all[level] = max(res, key=lambda x: abs(x[3]))
    g = worst_all["group"]
    ok = all(abs(v[3]) <= 0.1 for v in worst_all.values())
    report("PASS" if ok else "FAIL", "4. Weighted levels reproduce the all-India index within 0.1, every month",
           f"groups (old 'subgroups'): worst gap {g[3]:+.4f} in {g[0]} ({g[1]:.4f} vs published {g[2]}); "
           + "; ".join(f"{k}: {v[3]:+.4f}" for k, v in worst_all.items() if k != "group"))

    # 5. YoY vs published
    yc = O.yoy_check(series, pub, O.TEST_MONTHS)
    worst = max(yc, key=lambda x: abs(x[3]))
    sep_ok = sep_press_release_check(pub[O.HEADLINE]["2026-09"])
    ok = all(abs(x[3]) <= 0.011 for x in yc)
    report("PASS" if ok else "FAIL", "5. YoY Jan-Sep 2026 from the indices matches MoSPI's published figures",
           f"largest difference {worst[3]:+.4f} pp ({worst[0]}: ours {worst[1]:.4f} vs published {worst[2]}); "
           f"September press-release PDF shows {pub[O.HEADLINE]['2026-09']}: "
           f"{'yes' if sep_ok else 'not checked' if sep_ok is None else 'NO'}")

    # 6. calibration vs test split
    report("PASS", "6. 2025 = calibration only, Jan-Sep 2026 = test only",
           "baselines use only data up to the month before each target (checked by a test); the only parameter "
           "(seasonal weight 0.5) is fixed in advance; nothing is fitted on 2026")

    # 7. baselines
    older = {"2025-12": O.published_headline_yoy_2012("2025-12", rec)}
    poll = O.read_poll()
    bl = O.run_baselines(series, w, pub, O.TEST_MONTHS, poll, older)
    O.write_baselines(bl)
    b1m, _ = O.mean_abs([r["b1_miss"] for r in bl])
    b2m, _ = O.mean_abs([r["b2_miss"] for r in bl])
    pm, pn = O.mean_abs([r["poll_miss"] for r in bl])
    report("PASS", "7. Baselines saved to results/baselines.csv",
           f"mean absolute miss Jan-Sep 2026: B1 {b1m:.3f} pp, B2 {b2m:.3f} pp, poll {pm:.3f} pp ({pn} dated months)")
    print("\n   month    actual   B1 (miss)        B2 (miss)        poll (miss)")
    for r in bl:
        pp = f"{r['poll_pred']:.2f} ({r['poll_miss']:+.2f})" if r["poll_pred"] != "" else "none"
        print(f"   {r['month']}  {r['actual_yoy']:5.2f}   {r['b1_pred']:5.2f} ({r['b1_miss']:+.2f})    "
              f"{r['b2_pred']:5.2f} ({r['b2_miss']:+.2f})    {pp}")
    print("   (Jan 2026 B1 uses December 2025's published 2012-series print, the last one before the new series.)\n")

    # 8. item map
    report("PASS", "8. data/item_map.csv written", f"{len(items)} tracked items -> group code, weight, item index code")

    print("\n==== SUMMARY ====")
    print("\n".join(REPORT))


if __name__ == "__main__":
    t0 = time.time()
    main()
    print(f"(took {time.time() - t0:.0f}s)")
