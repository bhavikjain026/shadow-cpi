#!/usr/bin/env python3
"""Do the verified price events lean towards rises? results/evidence_asymmetry.json.
Exploratory, added after scoring; changes no headline. 0 credits, offline.

    python tools/build_evidence_asymmetry.py

Scored replay months Jan-Sep 2026. A verified event is an item x month with a signed change in the evidence the scored
replay used (results/replay_predictions.json, arm c: government spine, observed series, announced events) or among the
announced events the v2 scorer moved (results/v2_score_lock.json). Official sign: the item's index this month against
last month (data/cpi_tidy.csv, published item rows); a zero change is neither a rise nor a fall. Share = official
rises (or falls) with any verified event that month, over all official rises (or falls). Shown over every official item
and over the items that ever had evidence (the only ones the pipeline could speak to).
"""
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from shadow_cpi.official import TEST_MONTHS  # noqa: E402

OUT = ROOT / "results" / "evidence_asymmetry.json"
LABEL = "exploratory, added after scoring; changes no headline"
LAYER = {"spine": "measured", "observed": "measured", "event+trend": "announced"}


def sign(x):
    return "rise" if x > 0 else "fall" if x < 0 else "flat"


def official_signs(tidy=ROOT / "data" / "cpi_tidy.csv", months=TEST_MONTHS):
    idx, names = {}, {}
    with open(tidy, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["level"] == "item" and r["index"] and r["imputed"] != "Y":
                idx[(r["code"], r["month"])] = float(r["index"])
                names[r["code"]] = r["name"]
    out = {}
    for m in months:
        y, mo = int(m[:4]), int(m[5:])
        prev = f"{y - 1}-12" if mo == 1 else f"{y}-{mo - 1:02d}"
        out[m] = {c: sign(idx[(c, m)] / idx[(c, prev)] - 1) for (c, mm) in idx if mm == m and (c, prev) in idx}
    return out, names


def evidence(replay, lock, months=TEST_MONTHS):
    ev = defaultdict(dict)                     # month -> code -> {"change", "layer"}
    for m in months:
        for code, v in replay[m]["c"]["evidence"].items():
            if v.get("change") is not None:
                ev[m][code] = {"change": v["change"], "layer": LAYER[v["source"]]}
    v2 = defaultdict(dict)
    for b in lock["month_builds"]:
        for e in b["moving_events"]:
            v2[b["month"]][e["cpi_code"]] = e["change"]
    return ev, v2


def share(num, den):
    return {"with_event": num, "of": den, "share": num / den if den else None}


def build():
    replay = json.loads((ROOT / "results" / "replay_predictions.json").read_text(encoding="utf-8"))
    lock = json.loads((ROOT / "results" / "v2_score_lock.json").read_text(encoding="utf-8"))
    off, names = official_signs()
    ev, v2 = evidence(replay, lock)
    covered = {c for m in ev for c in ev[m]}
    events = [(m, c, sign(e["change"]), e["layer"]) for m in ev for c, e in ev[m].items()]
    by_item = defaultdict(Counter)
    for m, c, s, _ in events:
        by_item[c][s] += 1
    sh = {}
    for scope, keep, layer in (("all_official_items", lambda c: True, None),
                               ("items_with_any_evidence", lambda c: c in covered, None),
                               ("all_official_items_announced_only", lambda c: True, "announced")):
        sh[scope] = {}
        for s in ("fall", "rise"):
            pool = [(m, c) for m in TEST_MONTHS for c, v in off[m].items() if v == s and keep(c)]
            sh[scope][s] = share(sum(c in ev[m] and layer in (None, ev[m][c]["layer"]) for m, c in pool), len(pool))
    agree = Counter()
    for m, c, s, _ in events:
        agree[(s, off[m].get(c, "not published"))] += 1
    return {"label": LABEL, "months": TEST_MONTHS, "sources": ["results/replay_predictions.json (arm c evidence)",
            "results/v2_score_lock.json (moving_events)", "data/cpi_tidy.csv"],
            "events_replay": {"item_months": len(events), **{s: sum(e[2] == s for e in events) for s in ("rise", "fall", "flat")},
                              "by_layer": {l: {s: sum(e[2] == s and e[3] == l for e in events) for s in ("rise", "fall", "flat")}
                                           for l in ("measured", "announced")}},
            "events_v2_announced": {"item_months": sum(len(v) for v in v2.values()),
                                    **{s: sum(sign(x) == s for v in v2.values() for x in v.values())
                                       for s in ("rise", "fall", "flat")}},
            "by_item": {c: {"name": names.get(c, c), **{s: n for s, n in k.items()}} for c, k in sorted(by_item.items())},
            "official_item_months": {s: sum(v == s for m in TEST_MONTHS for v in off[m].values()) for s in ("rise", "fall", "flat")},
            "covered_items": len(covered), "share_of_official": sh,
            "event_vs_official_sign": {f"{a} -> {b}": n for (a, b), n in sorted(agree.items())}}


if __name__ == "__main__":
    res = build()
    OUT.write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{LABEL}: events {res['events_replay']['rise']} rises, {res['events_replay']['fall']} falls -> {OUT.relative_to(ROOT)}")
