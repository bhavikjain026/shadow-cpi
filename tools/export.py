#!/usr/bin/env python3
"""Research exports (0 credits, no API call): exports/nowcast.csv, exports/evidence.csv, exports/radar.jsonl.

    python tools/export.py

Schemas and coverage limits: docs/exports_schema.md. Quotes are the short cited line only (at most QUOTE_MAX
characters), never a page's full text. Every value is copied from a committed results file.
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
OUT = ROOT / "exports"
QUOTE_MAX = 200
NOWCAST_COLS = ["month", "model", "nowcast_yoy", "range_low", "range_high", "official_yoy", "inside_range",
                "measured_share", "source"]
EVIDENCE_COLS = ["source", "month", "kind", "change", "effective_date", "quote_short", "url", "page_date",
                 "search_request_id", "search_response_sha256", "seal"]


def short(q):
    q = " ".join((q or "").split())
    return q if len(q) <= QUOTE_MAX else q[:QUOTE_MAX - 1] + "…"


def nowcast_rows():
    rows = []
    with (ROOT / "results" / "replay.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append({"month": r["month"], "model": "v1 (c)", "nowcast_yoy": r["c_tavily_pred"],
                         "range_low": r["c_range_low"], "range_high": r["c_range_high"], "official_yoy": r["actual_yoy"],
                         "inside_range": r["c_inside_range"], "measured_share": r["c_coverage_observed"],
                         "source": "results/replay.csv"})
    for m in json.loads((ROOT / "results" / "v2_score_lock.json").read_text())["months"]:
        rows.append({"month": m["month"], "model": "v2 (experimental)", "nowcast_yoy": m["v2"],
                     "range_low": m["range"][0], "range_high": m["range"][1], "official_yoy": m["actual"],
                     "inside_range": m["inside"], "measured_share": m["measured"],
                     "source": "results/v2_score_lock.json"})
    return rows


def evidence_rows():
    d = json.loads((ROOT / "results" / "custody.json").read_text(encoding="utf-8"))
    return [{**{k: r.get(k) for k in EVIDENCE_COLS if k != "quote_short"}, "quote_short": short(r["quote"])}
            for r in d["rows"]]


def radar_rows():
    p = ROOT / "v2" / "radar" / "radar_2026-10.json"
    if not p.exists():
        return []
    r = json.loads(p.read_text(encoding="utf-8"))
    return [{"kind": e["kind"], "effective_date": e["effective_date"], "states": e["states"], "change": e["change"],
             "tier": e["tier"], "tavily_only": e["tavily_only"], "effect_pp": e.get("effect_pp"),
             "sources": [{"url": s["url"], "domain": s["domain"], "published": s["published"],
                          "quote_short": short(s["line"]), "search_request_id": s.get("search_request_id"),
                          "extract_request_id": s.get("extract_request_id")} for s in e["sources"]]}
            for e in r["events"]]


def write():
    OUT.mkdir(exist_ok=True)
    for name, cols, rows in (("nowcast.csv", NOWCAST_COLS, nowcast_rows()),
                             ("evidence.csv", EVIDENCE_COLS, evidence_rows())):
        with (OUT / name).open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
    (OUT / "radar.jsonl").write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in radar_rows()),
                                     encoding="utf-8")


if __name__ == "__main__":
    write()
    print("exports/: nowcast.csv, evidence.csv, radar.jsonl")
