#!/usr/bin/env python3
"""Paired statistics, no dates (arm A) vs time lock (arm C), from the saved per-case outcomes: results/paired_stats.json.
Exploratory, added after scoring; changes no headline. 0 credits, offline.

    python tools/build_paired_stats.py

A case counts as a leak for an arm when any result it kept is a confirmed leak (label L), initial pass. Pairs are by
case. Two-sided exact McNemar on the discordant cases; the rule of three and the exact one-sided bound for the zero.
tools/build_posthoc_stats.py reports the same tests with a pooled field-report cross-check; this file recomputes them
straight from the per-case rows for the pilot and the replication and states the discordant cases.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from v2 import date_test as DT  # noqa: E402

OUT = ROOT / "results" / "paired_stats.json"
LABEL = "exploratory, added after scoring; changes no headline"


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def leaks(rows, arm):
    return {row["id"] for row in rows if any(r["label"] == "L" for r in row["arms"].get(arm, {}).get("results", []))}


def paired(rows, a="A", c="C"):
    ids = {row["id"] for row in rows if a in row["arms"] and c in row["arms"]}
    la, lc = leaks(rows, a) & ids, leaks(rows, c) & ids
    only_a, only_c = sorted(la - lc), sorted(lc - la)
    return {"cases": len(ids), "leaks_no_dates": len(la), "leaks_time_lock": len(lc), "both": len(la & lc),
            "only_no_dates": len(only_a), "only_time_lock": len(only_c), "only_no_dates_cases": only_a,
            "only_time_lock_cases": only_c, "p_exact_two_sided": DT.mcnemar_exact(len(only_a), len(only_c))}


def zero_bound(x, n):
    if x:
        return None
    return {"leaks": x, "cases": n, "rule_of_three_upper": 3 / n, "exact_one_sided_95_upper": 1 - 0.05 ** (1 / n),
            "wilson95": list(DT.wilson(x, n))}


def build():
    pilot, rep = load("results/date_field_test.json")["rows"], load("results/replication.json")["rows"]
    rep = [r for r in rep if r["type"] == "price"]
    studies = {"pilot": paired(pilot), "replication": paired(rep), "pooled": paired(pilot + rep)}
    p = studies["pooled"]
    out = {"label": LABEL, "pass": "initial pass", "no_dates": "arm A", "time_lock": "arm C",
           "sources": ["results/date_field_test.json", "results/replication.json"], "studies": studies,
           "zero": zero_bound(p["leaks_time_lock"], p["cases"])}
    known = load("results/posthoc_stats.json")["mcnemar"]
    for k, key in (("pilot", "date_test"), ("replication", "replication"), ("pooled", "pooled")):
        if abs(studies[k]["p_exact_two_sided"] - known[key]["p_exact"]) > 1e-12:
            raise SystemExit(f"{k}: McNemar differs from results/posthoc_stats.json")
    return out


if __name__ == "__main__":
    res = build()
    OUT.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    print(f"{LABEL}: " + "; ".join(f"{k} p={s['p_exact_two_sided']:.2g}" for k, s in res["studies"].items())
          + f" -> {OUT.relative_to(ROOT)}")
