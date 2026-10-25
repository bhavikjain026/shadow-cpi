#!/usr/bin/env python3
"""Build results/custody.json: for every verified number, its chain of custody (0 credits, no API call).

    python tools/build_custody.py

quote -> URL -> page date -> search request_id + response hash -> extract request_id + response hash -> page hash
-> seal, read from the saved cards (v2/radar/, v2/ablation/, v2/evidence/events_*.json). Where a link was not logged
(runs before Amendment F provenance, e.g. arms A and B and the scored v2 months) it says "not logged".
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "results" / "custody.json"
NOT_LOGGED = "not logged"


def seal_for(source, month):
    if source == "radar":
        sha = ROOT / "v2" / "radar" / f"radar_{month}.frozen.sha256"
        return f"radar frozen, SHA-256 {sha.read_text().strip()}" if sha.exists() else \
            "radar not frozen yet (freeze 29 Oct 23:59 IST)"
    sealed = ROOT / "sealed" / f"{month}.sha256"
    if sealed.exists():
        return f"sealed/{month}.json, SHA-256 {sealed.read_text().strip()}"
    return "not sealed (development data)" if source.startswith("arm ") else "not sealed (replay month)"


def entries(source, month, cards):
    out = []
    for c in cards:
        for cl in c.get("claims", []):
            if cl.get("status") != "verified":
                continue
            out.append({"source": source, "month": month, "kind": cl.get("kind"), "change": cl.get("change"),
                        "price": cl.get("price") if cl.get("price") is not None else cl.get("new_price"),
                        "effective_date": cl.get("effective_date"), "quote": cl.get("line"), "url": c["url"],
                        "page_date": c.get("published"), "printed_date": c.get("printed_date"),
                        "search_request_id": c.get("search_request_id") or NOT_LOGGED,
                        "search_response_sha256": c.get("search_response_sha256") or NOT_LOGGED,
                        "extract_request_id": c.get("extract_request_id") or NOT_LOGGED,
                        "extract_response_sha256": c.get("extract_response_sha256") or NOT_LOGGED,
                        "page_sha256": c.get("page_sha256") or NOT_LOGGED, "seal": seal_for(source, month)})
    return out


def build():
    rows = []
    radar = ROOT / "v2" / "radar" / "radar_2026-10.json"
    if radar.exists():
        rows += entries("radar", "2026-10", json.loads(radar.read_text(encoding="utf-8"))["cards"])
    for f in sorted((ROOT / "v2" / "evidence").glob("events_*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        rows += entries("v2 scored evidence", d["month"], d["cards"])
    for f in sorted((ROOT / "v2" / "ablation").glob("arm_*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        rows += entries(f"arm {d['arm']}", d["month"], d["cards"])
    out = {"rows": rows, "not_logged": NOT_LOGGED,
           "note": "request_id + response SHA-256 were logged from Amendment F on (arms C, T, T+dates, H and the radar); "
                   "earlier runs (arms A and B, the scored v2 months) say 'not logged'"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    return out


if __name__ == "__main__":
    o = build()
    logged = sum(r["search_request_id"] != NOT_LOGGED for r in o["rows"])
    print(f"{OUT.relative_to(ROOT)}: {len(o['rows'])} verified numbers, {logged} with a logged search request_id")
