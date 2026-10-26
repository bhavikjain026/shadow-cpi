#!/usr/bin/env python3
"""Display files for the Live build and time machine month picker: one per scored month, Jan-Sep 2026.

    python -m v2.months        # 0 credits: cache only, no new model call

Rebuilds each month from what the issue 14 scoring run saved (v2/evidence/events_<month>.json and the cached
official series), with the scorer's own functions (v2.score.build_month's steps), in the same shape as the
September basket run so the Live build page replays it. Display only: each month's final number must equal the
v2 figure in results/v2_score_lock.json, or the build stops. Writes v2/evidence/month_<month>.json.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import build_nowcast as BN  # noqa: E402
from shadow_cpi import official as O  # noqa: E402
from shadow_cpi.budget import Budgeted  # noqa: E402
from shadow_cpi.recorder import Recorder  # noqa: E402
from shadow_cpi.tavily import Tavily  # noqa: E402
from v2 import basket as B  # noqa: E402
from v2 import ledger as LG  # noqa: E402
from v2 import rules as R  # noqa: E402
from v2 import score as S  # noqa: E402
from v2.needle import path  # noqa: E402

# Months whose evidence was looked at while v2's rules were built (v2/PREREGISTRATION.md): not clean tests.
DEVELOPMENT = {
    "2026-09": "September was v2's development month: the basket build, Amendments A and B and the time machine were "
               "built while looking at September's evidence, so September is not a clean test of v2. The other "
               "eight months are.",
    "2026-04": "April was the milk tracer month for v2 (issue 1), so April's milk evidence was looked at while the "
               "rules were built.",
}


def build(month, lock, rec):
    cut = R.cutoff(month)
    inp, notes, missing = BN.gather(month, cut, Budgeted(Tavily(recorder=rec), [S.BUDGET], cache_only=True))
    meta = inp["meta"]
    item_cards = B.spine_cards(inp, month, meta) + B.observed_cards(inp["observed"][month], notes, month, meta,
                                                                    inp["factors"])
    saved = json.loads((LG.ROOT / f"events_{month}.json").read_text(encoding="utf-8"))
    cards = saved["cards"]
    for c in cards:
        c.setdefault("domain", c["url"].split("/")[2] if "//" in c["url"] else c["url"])
    moving = S.moving_events(cards, month)
    steps = [c for c in item_cards if c["status"] == "verified"]
    seq = [(c["cpi_code"], "level", c["change"]) for c in steps] + [(m["cpi_code"], "add", m["applied"])
                                                                    for m in moving]
    start, after = path(month, seq, inp)
    end = after[-1] if after else start
    scored = next(r for r in lock["months"] if r["month"] == month)
    if abs(end - scored["v2"]) > 1e-9:
        raise SystemExit(f"{month}: rebuilt {end} != scored {scored['v2']}; the display would not match the score")
    w = inp["weights"]
    total = sum(w[g] for g in O.codes_at("group", w))
    measured, timeline = 0.0, []
    for (code, mode, value), yoy_after, src in zip(seq, after, steps + moving):
        measured += w[code] * src.get("weight_share", 1.0)
        timeline.append({"cpi_code": code, "name": B.name_of(meta, code), "kind": src["kind"], "mode": mode,
                         "value": value, "yoy_after": yoy_after, "measured_after": measured / total,
                         "weight": w[code], "weight_share": src.get("weight_share", 1.0)})
    preds = json.loads((ROOT / "results" / "replay_predictions.json").read_text())
    return B.add_jumps({"month": month, "cutoff": cut, "window": list(R.window(month)),
            "built_utc": datetime.now(timezone.utc).isoformat(), "source": "issue 14 scoring run (display rebuild)",
            "item_cards": item_cards, "cards": cards, "moving_events": moving, "timeline": timeline,
            "needle": {"start": start, "end": end}, "measured_share": measured / total,
            "tiles": B.basket_tiles(inp, meta, [c for c, _, _ in seq]),
            "v1": {"c": preds[month]["c"]["yoy"], "a": preds[month]["a"]["yoy"]}, "official": scored["actual"],
            "notes": missing, "development": DEVELOPMENT.get(month, ""), "complete": saved.get("complete", True),
            "stages": B.stages(timeline, start),
            "time_machine": B.time_machine(month, item_cards, moving, inp, meta, total, Tavily(recorder=rec)),
            "credits_budget": S.BUDGET, "credits_spent": 0}, month, inp)        # jumps: display only


def main(months=S.MONTHS):
    lock = json.loads(S.LOCK.read_text())
    rec = Recorder()
    for m in months:
        out = build(m, lock, rec)
        (LG.ROOT / f"month_{m}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float))
        print(f"{m}: {len(out['cards'])} pages, {len(out['moving_events'])} moving events, "
              f"needle {out['needle']['end']:.3f} (matches the score lock)", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:] or S.MONTHS)
