#!/usr/bin/env python3
"""Build results/replay_sep.jsonl: the September Live build as a sanitised event stream (0 credits, no API call).

    python tools/build_replay_recording.py

Read from the committed run (v2/evidence/run_2026-09_basket.json) in the order the Live build page plays it: the
spine and official-series item cards, then the announced-price pages, then the moving events. One JSON line per
event: item, place, a short quote (the same cap as exports/evidence.csv, tools/export.py QUOTE_MAX), URL, page date,
verdict and reason, the search/extract request_id and response SHA-256 where the credit ledger logged them, and the
needle after the event. No page text: the page cache holds copyrighted article text and stays local.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from export import short  # noqa: E402
from shadow_cpi.budget import read_ledger  # noqa: E402

RUN = ROOT / "v2" / "evidence" / "run_2026-09_basket.json"
OUT = ROOT / "results" / "replay_sep.jsonl"


def provenance(call, ledger):
    """Tavily request_id + response SHA-256 from the credit ledger, or 'not logged' (this run predates Amendment F
    logging, and cache hits have no ledger row)."""
    e = ledger.get(call) or {}
    return ({"request_id": e["request_id"], "response_sha256": e.get("response_sha256")} if e.get("request_id")
            else "not logged")


def events(run, ledger):
    needle, steps, out = run["needle"]["start"], iter(run["timeline"]), []
    out.append({"seq": 0, "type": "start", "needle_after": needle, "built_utc": run["built_utc"],
                "month": run["month"], "cutoff": run["cutoff"]})
    for c in run["item_cards"]:
        if c["status"] == "verified":
            needle = next(steps)["yoy_after"]
        out.append({"type": "item", "item": c["name"], "place": "India", "source": c["source"],
                    "detail": c.get("detail"), "change": c.get("change"), "verdict": c["status"],
                    "reason": c["reason"], "needle_after": needle})
    for c in run["cards"]:
        claims = [cl for cl in c["claims"] if "status" in cl]
        main = next((cl for cl in claims if cl["status"] == "verified"), claims[0] if claims else {})
        out.append({"type": "page", "item": c.get("kind"), "place": main.get("region") or "",
                    "quote_short": short(main["line"]) if main.get("line") else None, "url": c["url"],
                    "page_date": c.get("published"), "verdict": c["status"], "reason": c["reason"],
                    "claims_checked": len(claims), "claims_verified": sum(cl["status"] == "verified" for cl in claims),
                    "search": provenance(c.get("search_call"), ledger),
                    "extract": provenance(c.get("extract_call"), ledger), "needle_after": needle})
    for m in run["moving_events"]:
        needle = next(steps)["yoy_after"]
        out.append({"type": "moving_event", "item": m["event_kind"], "place": m["where"], "change": m["change"],
                    "effective_date": m["effective_date"], "urls": m["urls"], "verdict": "applied",
                    "reason": f"Amendment A: {m['n_sources']} source(s), weight share {m['weight_share']:.4f}",
                    "needle_after": needle})
    for i, e in enumerate(out):
        e["seq"] = i
    return out


def build(run_path=RUN, out=OUT):
    run = json.loads(Path(run_path).read_text(encoding="utf-8"))
    ledger = {e["call_id"]: e for e in read_ledger()}
    ev = events(run, ledger)
    Path(out).write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in ev), encoding="utf-8")
    return ev


if __name__ == "__main__":
    ev = build()
    print(f"{OUT.relative_to(ROOT)}: {len(ev)} events, final needle {ev[-1]['needle_after']:.6f}%")
