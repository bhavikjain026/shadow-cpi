#!/usr/bin/env python3
"""v2 issue 4: regional-language recall on the 29 known Jan-Sep 2026 changes (Amendment C; report only).

    python -m v2.recall                # runs the month event layer Jan-Sep (hard cap 'v2-issue4', 150 credits)
    python -m v2.recall --cache-only   # 0 credits

A known change is found directly by v2 if a claim verified by code has the same kind (fuel = petrol or diesel), the
same effective month (the same date +-2 days where the reference gives one) and, for a state change, a shared state.
v1's figure is the audit's FOUND column. Writes v2/evidence/recall_2026.json.
"""
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from shadow_cpi.budget import BudgetExceeded, Budgeted, spent  # noqa: E402
from shadow_cpi.nemotron import Nemotron  # noqa: E402
from shadow_cpi.recorder import Recorder  # noqa: E402
from shadow_cpi.settings import models  # noqa: E402
from shadow_cpi.tavily import Tavily  # noqa: E402
from v2 import ledger as LG  # noqa: E402
from v2.events import run_month  # noqa: E402

BUDGET = "v2-issue4"
MONTHS = [f"2026-{m:02d}" for m in range(1, 10)]
REFERENCE = Path(__file__).resolve().parent / "recall_reference.json"
COMPATIBLE = {"fuel": {"petrol", "diesel"}}


def matches(ref, cl):
    """True if a verified claim is the reference change (kind, month or date +-2 days, place)."""
    if cl.get("status") != "verified" or cl.get("kind") not in COMPATIBLE.get(ref["kind"], {ref["kind"]}):
        return False
    eff = cl.get("effective_date") or ""
    if not eff.startswith(ref["month"]):
        return False
    if ref.get("date") and abs((date.fromisoformat(eff) - date.fromisoformat(ref["date"])).days) > 2:
        return False
    return not ref["states"] or bool(set(ref["states"]) & set(cl.get("states") or []))


def score(claims_by_month, reference=None):
    ref = reference or json.loads(REFERENCE.read_text(encoding="utf-8"))["changes"]
    rows = []
    for r in ref:
        hit = next(((m, cl) for m, cls in claims_by_month.items() for cl in cls if matches(r, cl)), None)
        rows.append({**r, "v2": "FOUND" if hit else "MISSED",
                     "v2_match": {"month": hit[0], "line": hit[1].get("line"), "url": hit[1].get("url"),
                                  "read_by": hit[1].get("read_by")} if hit else None})
    return rows


def run(cache_only=False):
    rec = Recorder()
    tav = Budgeted(Tavily(recorder=rec), [BUDGET], cache_only=cache_only)
    nem = Nemotron(recorder=rec)
    nano, sup = models()["small"], models()["mid"]
    claims, stopped, done = {}, "", []
    for m in MONTHS:
        try:
            cards = run_month(m, tav, nem, nano, sup)
        except BudgetExceeded as e:
            stopped = f"stopped at {m}: {e}"
            break
        claims[m] = [{**cl, "url": c["url"]} for c in cards for cl in c["claims"] if "status" in cl]
        done.append(m)
        print(f"{m}: {len(cards)} pages, {sum(cl['status'] == 'verified' for cl in claims[m])} verified claims; "
              f"credits {spent(BUDGET)}", flush=True)
    rows = score(claims)
    ver = [cl for cls in claims.values() for cl in cls if cl["status"] == "verified"]
    out = {"built_utc": datetime.now(timezone.utc).isoformat(), "months_run": done, "stopped": stopped,
           "v1_found": sum(r["v1"] == "FOUND" for r in rows), "v2_found": sum(r["v2"] == "FOUND" for r in rows),
           "total": len(rows), "changes": rows,
           "verified_by_model": {mdl: sum(cl.get("read_by") == mdl for cl in ver) for mdl in (nano, sup)},
           "verified_by_kind": {k: sum(cl.get("kind") == k for cl in ver) for k in sorted({cl.get("kind") or "none"
                                                                                           for cl in ver})},
           "credits_budget": BUDGET, "credits_spent": spent(BUDGET)}
    (LG.ROOT / "recall_2026.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    return out


RECALL_LOCK = ROOT / "results" / "v2_recall_lock.json"
SCORE_LOCK = ROOT / "results" / "v2_score_lock.json"


def ledger_claims(rows, months=MONTHS):
    """Ledger rows -> {month: claims} in the shape `matches` takes (states from the ledger's comma-joined field)."""
    out = {m: [] for m in months}
    for r in rows:
        if r["month"] in out:
            out[r["month"]].append({"status": r["status"], "kind": r.get("kind"), "line": r["line"], "url": r["url"],
                                    "effective_date": r.get("effective_date"), "read_by": r.get("model"),
                                    "states": [x for x in (r.get("state") or "").split(", ") if x]})
    return out


def from_ledger():
    """Issue 14: recall computed ONCE over Jan-Sep from the evidence ledger, with the matcher committed in db2984c,
    after v2 was scored. Also gives the pre-registered 'v2 better than v1' verdict (Amendment D)."""
    if RECALL_LOCK.exists():
        raise SystemExit(f"v2 recall is already computed ({RECALL_LOCK}); it is computed once.")
    if not SCORE_LOCK.exists():
        raise SystemExit("score v2 first (python -m v2.score)")
    sc = json.loads(SCORE_LOCK.read_text())
    rows = score(ledger_claims(LG.read()))
    v1, v2 = sum(r["v1"] == "FOUND" for r in rows), sum(r["v2"] == "FOUND" for r in rows)
    out = {"computed_utc": datetime.now(timezone.utc).isoformat(), "matcher": "v2/recall.py at db2984c, unchanged",
           "source": "v2/evidence/ledger.jsonl (issue 14 run)", "v1_found": v1, "v2_found": v2, "total": len(rows),
           "incomplete_months": sc.get("incomplete_months", []), "changes": rows,
           "v2_mae": sc["v2"]["mae"], "v1_mae": sc["v1"]["mae"],
           "v2_better_than_v1": sc["v2"]["mae"] < sc["v1"]["mae"] and v2 > 9}
    RECALL_LOCK.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    return out


if __name__ == "__main__" and "--from-ledger" in sys.argv:
    o = from_ledger()
    print(f"recall (direct): v1 {o['v1_found']} of {o['total']}, v2 {o['v2_found']} of {o['total']}; "
          f"incomplete months: {o['incomplete_months'] or 'none'}; v2 better than v1: {o['v2_better_than_v1']}")
elif __name__ == "__main__":
    o = run(cache_only="--cache-only" in sys.argv)
    print(f"recall: v1 {o['v1_found']} of {o['total']}, v2 {o['v2_found']} of {o['total']}; verified by model "
          f"{o['verified_by_model']}; credits {o['credits_spent']}; {o['stopped'] or 'all months run'}")
