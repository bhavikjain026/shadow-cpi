#!/usr/bin/env python3
"""Build results/call_receipts.json: one row per real Tavily call in the credit ledger, with Tavily's own
response_time (0 credits, no API call).

    python tools/build_call_receipts.py [--log logs/flight_recorder.jsonl] [--cache cache]

The ledger (committed) has each call's endpoint, credits and budgets; Tavily's response_time sits only in the cached
response (git-ignored). The flight recorder maps the ledger's call_id to the cache file. Written once from a machine
that has the cache, so the field report can be rebuilt from committed files alone; tools/radar_daily.sh re-runs it
after each radar run. Append-only for response_time: a call already in the file keeps the value recorded for it. Left out: cache hits (0 credits,
`cached`), calls a reconcile row marks as phantom (cache hits charged by the old budget bug), and reconcile rows
themselves (kept as totals in `reconcile`). No page text is copied: ids, numbers and dates only.
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from shadow_cpi.budget import read_ledger  # noqa: E402
from shadow_cpi.recorder import CACHE_DIR, LOG_FILE, read_log  # noqa: E402

OUT = ROOT / "results" / "call_receipts.json"


def experiments(budgets):
    """Every experiment a call was charged to: its budgets' top-level names, without per-month slices of a parent
    budget (a call charged to 'prompt-t' and 'chase' counts in both, as the ledger's caps count it)."""
    names = list(dict.fromkeys(b.split("/")[0] for b in budgets))
    return [n for n in names if not n.endswith("-month")] or names


def build(log=LOG_FILE, cache=CACHE_DIR, ledger=None, out=OUT):
    ledger = ledger if ledger is not None else read_ledger()
    flight = {e["id"]: e for e in read_log(log) if e.get("service") == "tavily"}
    # append-only: a call already in the receipts keeps its recorded response_time (a repeated search overwrites
    # the cache file, so re-reading the cache would give an older call a later response's time)
    known = {r["call_id"]: r["response_time"] for r in json.loads(Path(out).read_text(encoding="utf-8"))["rows"]
             if r["response_time"] is not None} if Path(out).exists() else {}
    phantom = {c for e in ledger for c in e.get("phantom_of", [])}
    rows, missing = [], 0
    for e in ledger:
        if not e["endpoint"].startswith("/") or e.get("cached") or e["call_id"] in phantom:
            continue
        fr = flight.get(e["call_id"])
        rt = known.get(e["call_id"])
        if rt is None and fr:
            p = Path(cache) / "tavily" / f"{fr['cache_key']}.json"
            if p.exists():
                rt = json.loads(p.read_text(encoding="utf-8"))["response"].get("response_time")
        missing += rt is None
        rows.append({"call_id": e["call_id"], "time": e["time"], "endpoint": e["endpoint"],
                     "experiments": experiments(e["budgets"]), "credits": e["credits"],
                     "response_time": float(rt) if rt is not None else None, "request_id": e.get("request_id")})
    rec = [{k: e.get(k) for k in ("call_id", "time", "credits", "budgets", "note")} for e in ledger
           if e["endpoint"] == "reconcile"]
    res = {"built": date.today().isoformat(), "rows": rows, "reconcile": rec, "without_response_time": missing,
           "note": "response_time is Tavily's own field from the saved response; ledger credits are Tavily's "
                   "include_usage count, which can read 0 for calls below Tavily's reporting threshold"}
    head = json.dumps({k: v for k, v in res.items() if k != "rows"}, ensure_ascii=False)[:-1]
    body = ",\n".join(json.dumps(r, ensure_ascii=False) for r in rows)          # one call per line
    Path(out).write_text(f'{head}, "rows": [\n{body}\n]}}\n', encoding="utf-8")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default=str(LOG_FILE))
    ap.add_argument("--cache", default=str(CACHE_DIR))
    a = ap.parse_args()
    r = build(a.log, a.cache)
    print(f"{OUT.relative_to(ROOT)}: {len(r['rows'])} calls, {r['without_response_time']} without response_time")
