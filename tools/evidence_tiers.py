#!/usr/bin/env python3
"""Evidence tiers and case-level bounds (exploratory, added after scoring; 0 credits, reads saved files only).

    python tools/evidence_tiers.py            # writes results/evidence_tiers.json

For the date test (pilot) and the replication, per arm (A no dates, C time lock), each saved result at the initial pass
is put in one tier by the headline's own label (v2/date_test.label, as stored in the results files):
  Archived = P  the Wayback Machine has a copy on or before the cutoff
  Leak     = L  confirmed after the cutoff (Wayback plus an independent date)
  Unknown  = F or U  not confirmed either way: lookup failed, no capture, or a date flag with no capture
Undated results (no Tavily date) are counted alongside; they sit in the tiers as well.
Bounds at case level: best case = cases with a confirmed leak (the headline count), worst case = cases with a
confirmed leak OR any Unknown result. A bounding range, not a new result: no headline changes.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from v2.date_test import label, url_date, wilson  # noqa: E402

OUT = ROOT / "results" / "evidence_tiers.json"
SOURCES = (("pilot", "results/date_field_test.json"), ("replication", "results/replication.json"))
# where each test's logged Wayback retry (recovered captures per URL) is saved; True = nested under ["retry"]["log"]
RETRY = {"pilot": ("results/date_field_test_wayback_retry.json", False), "replication": ("results/replication.json", True)}
ARMS = ("A", "C")
LABEL = ("exploratory, added after scoring; a bounding range, not a new result; cannot change any headline")
TIER = {"P": "archived", "L": "leak", "F": "unknown", "U": "unknown"}


def tier(result):
    return TIER[result["label"]]


def unknown_kind(result):
    if result["captures"] is None:
        return "lookup_failed"
    return "no_capture" if not result["captures"] else "capture_unconfirmed"


def counts(results):
    out = {"results": len(results), "archived": 0, "leak": 0, "unknown": 0,
           "unknown_lookup_failed": 0, "unknown_no_capture": 0, "unknown_capture_unconfirmed": 0,
           "unknown_with_date_flag": 0, "undated": 0}
    for r in results:
        out[tier(r)] += 1
        if tier(r) == "unknown":
            out["unknown_" + unknown_kind(r)] += 1
            out["unknown_with_date_flag"] += r["label"] == "F"
        out["undated"] += r["tavily_date"] is None
    return out


def bound(k, n):
    lo, hi = wilson(k, n)
    return {"k": k, "n": n, "wilson95": [lo, hi]}


def case_bounds(cases):
    """cases: list of result lists (one per case) for one arm."""
    n = len(cases)
    best = sum(any(tier(r) == "leak" for r in c) for c in cases)
    worst = sum(any(tier(r) in ("leak", "unknown") for r in c) for c in cases)
    return {"best_case": bound(best, n), "worst_case": bound(worst, n)}


def load(rel, root=ROOT):
    return json.loads((Path(root) / rel).read_text(encoding="utf-8"))


def retried(res, cutoff, recovered):
    """The same result after the logged Wayback retry: a failed lookup (captures None) takes the captures the retry
    recovered for its URL and is relabelled by the headline rule; every other result is untouched."""
    if res["captures"] is not None or res["url"] not in recovered:
        return res
    caps = recovered[res["url"]]
    return {**res, "captures": caps, "label": label(cutoff, caps, res["tavily_date"], url_date(res["url"]), res.get("page_date"))}


def arm_block(per_arm):
    by_source = {s: {**counts([r for c in cases for r in c]), **case_bounds(cases)} for s, cases in per_arm.items()}
    pooled = [c for cases in per_arm.values() for c in cases]
    return {"pooled": {**counts([r for c in pooled for r in c]), **case_bounds(pooled)}, "by_source": by_source}


def build(root=ROOT):
    per = {a: {} for a in ARMS}
    after = {a: {} for a in ARMS}
    for name, rel in SOURCES:
        data = load(rel, root)
        log = load(RETRY[name][0], root)
        recovered = (log["retry"]["log"] if RETRY[name][1] else log)["recovered_captures"]
        for row in data["rows"]:
            for a in ARMS:
                rs = row["arms"][a]["results"]
                per[a].setdefault(name, []).append(rs)
                after[a].setdefault(name, []).append([retried(r, row["cutoff"], recovered) for r in rs])
    arms = {a: {**arm_block(per[a]), "after_retry": arm_block(after[a])} for a in ARMS}
    headline = load("results/replication.json", root)["pooled"]["price"]["arms"]
    retry_head = {"pilot": load(RETRY["pilot"][0], root)["after"]["arms"],
                  "replication": load("results/replication.json", root)["retry"]["metrics"]["price"]["arms"]}
    for a in ARMS:      # the after-retry best case must reproduce the retry files' own leak counts
        for name in retry_head:
            if arms[a]["after_retry"]["by_source"][name]["best_case"]["k"] != retry_head[name][a]["leak_cases"]:
                raise SystemExit(f"arm {a} {name}: after-retry best case differs from the retry file's leak count")
    for a in ARMS:      # the best case IS the headline count: refuse to write if they ever differ
        if arms[a]["pooled"]["best_case"]["k"] != headline[a]["leak_cases"] or arms[a]["pooled"]["best_case"]["n"] != headline[a]["cases"]:
            raise SystemExit(f"arm {a}: best case differs from the headline pooled count")
    return {"label": LABEL, "pass": "initial pass (results as saved, before the logged Wayback retry)",
            "rule": "labels as stored by v2/date_test.label; Unknown = labels F and U",
            "after_retry_pass": "after retry (failed archive lookups re-run and logged; same rule; the initial pass stays primary)",
            "sources": [rel for _, rel in SOURCES] + [v[0] for v in RETRY.values() if v[0] not in dict(SOURCES).values()] + ["results/replication.json (pooled headline, for the check)"],
            "arms": arms}


if __name__ == "__main__":
    if OUT.exists():
        raise SystemExit(f"{OUT.name} exists; delete it deliberately to rebuild")
    out = build()
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({a: {k: out["arms"][a]["pooled"][k] for k in ("results", "archived", "leak", "unknown", "best_case", "worst_case")}
                      for a in ARMS}, indent=1))
