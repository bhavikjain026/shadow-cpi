#!/usr/bin/env python3
"""Build results/nowcast_<month>.json (and nowcast_latest.json) with model (c), for the seal.

    python build_nowcast.py 2026-10 --cutoff 2026-10-28             # the real build (may spend credits)
    python build_nowcast.py 2026-10 --cutoff 2026-10-28 --dry-run   # cache only, 0 credits, writes nothing

The prediction is `shadow_cpi.predict.predict_month(month, "c", inp)`: the same function the scored replay called
(tools/score_replay.py), not a copy. Observed gold, silver, LPG and petrol come from `run_replay_layers.observed_layers`,
the same code that wrote results/replay_layers.csv. Only evidence up to the cutoff (23:59 IST) is used. Range and
P(headline >= 6.0%): Amendment 2 (`shadow_cpi.live_range`). A test month (Jan-Sep 2026) can be rebuilt with --dry-run
only, to check that the builder reproduces the scored number.
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone

import run_replay_layers as R
from shadow_cpi import cpi_math as M
from shadow_cpi import evidence as E
from shadow_cpi import official as O
from shadow_cpi import predict as P
from shadow_cpi.budget import Budgeted, CacheMiss, spent
from shadow_cpi.live_range import LIVE_MONTHS, live_range, scored_misses
from shadow_cpi.recorder import Recorder
from shadow_cpi.settings import ROOT, models
from shadow_cpi.tavily import Tavily

REPLAY_IBJA = ("2025-01", "2026-09")    # the scored replay's IBJA call: same batches, so the same cache entries
IST = timezone(timedelta(hours=5, minutes=30))


def cutoff_utc(cutoff):
    return datetime.fromisoformat(f"{cutoff}T23:59:00").replace(tzinfo=IST).astimezone(timezone.utc).isoformat()


def ibja_rates(tav, month, missing):
    """IBJA daily rates: the replay's cached call, plus the live month's reports (live months only)."""
    rates, _, _ = E.ibja_daily(tav.charge("ibja-iocl"), O.month_range(*REPLAY_IBJA))
    if month > REPLAY_IBJA[1]:
        live = O.month_range(M.add_months(REPLAY_IBJA[1], 1), month)
        try:
            more, _, failed = E.ibja_daily(tav.charge("live-month", "ibja-iocl"), live)
            rates.update(more)
            if failed:
                missing.append(f"IBJA: {len(failed)} report(s) not readable")
        except CacheMiss:
            missing.append(f"IBJA gold/silver reports for {', '.join(live)} (not in the cache)")
    return rates


def gather(month, cutoff, tav):
    """Inputs for predict_month, with everything after the cutoff removed. Returns (inp, notes, missing)."""
    inp = P.load_inputs()
    missing = []
    factors = inp["factors"]
    window_end = min(E.month_window(month)[1], cutoff)
    ibja = {d: r for d, r in ibja_rates(tav, month, missing).items() if d <= cutoff}
    rec = getattr(tav, "rec", None)                          # the cache and flight recorder this run reads
    lpg_rev, petrol, iocl_at = (R.cached_lpg_petrol(rec.cache_dir, rec.history_log) if rec
                                else R.cached_lpg_petrol())
    lpg_rev = [r for r in lpg_rev if r[0] <= cutoff]
    petrol = {d: v for d, v in petrol.items() if d <= cutoff}
    row = {"month": month}
    observed = R.observed_layers(month, row, ibja, lpg_rev, petrol, factors, iocl_at, window_end)
    inp["observed"][month] = row
    if observed["lpg"]["gap"]:
        missing.append(f"IOCL LPG list: saved copy retrieved {iocl_at[:10]}, before {window_end} (re-extract after "
                       "the cutoff day; until then LPG is an Amendment 1 (a) gap and follows trend)")
    if observed["gold"]["change"] is None:
        missing.append(f"IBJA: gold/silver need >= 5 trading days in both months (have "
                       f"{observed['gold']['days_now']}/{observed['gold']['days_prev']})")
    last_petrol = max((d for d in petrol if d.startswith(month)), default="none")
    if month > REPLAY_IBJA[1] and last_petrol < window_end:
        missing.append(f"PPAC petrol: last {month} row in the saved archive is {last_petrol}, before {window_end} "
                       "(re-extract)")
    man = ROOT / "manifests" / f"{month}.json"
    if man.exists():
        inp["events"][month] = json.loads(man.read_text())["events"]
    else:
        inp["events"][month] = []
        missing.append(f"evidence run for {month}: no manifests/{month}.json, so no events or quotes")
    fetched = json.loads((ROOT / "data" / "official" / "doca" / "raw" / "fetch_summary.json").read_text())["at"]
    if fetched[:10] < cutoff and month > REPLAY_IBJA[1]:
        missing.append(f"DoCA spine: fetched {fetched[:10]}, before the cutoff {cutoff} (re-fetch by hand, then "
                       "rebuild data/spine.csv)")
    in_force = [r for r in lpg_rev if r[0] <= window_end]
    notes = {"observed": {k: {x: y for x, y in v.items()} for k, v in observed.items()},
             "iocl_row_in_force": {"effective": in_force[-1][0], "line": in_force[-1][2], "list_retrieved": iocl_at}
             if in_force else None,
             "events_used": len(inp["events"][month]), "spine_fetched_utc": fetched,
             "spine_foods_with_month": sorted(f for f in E.SPINE_FOODS
                                              if E.spine_change(inp["spine"], f, month)[0] is not None)}
    return inp, notes, missing


def build(month, cutoff, cache_only=True, run_skeptic=False):
    if month in O.TEST_MONTHS and not cache_only:
        raise SystemExit("test months are scored already: rebuild them with --dry-run only")
    if month not in O.TEST_MONTHS and month not in LIVE_MONTHS:
        raise SystemExit(f"{month} is neither a test month nor a live month {LIVE_MONTHS}")
    rec = Recorder()
    tav = Budgeted(Tavily(recorder=rec), ["live-month"], cache_only=cache_only)
    inp, notes, missing = gather(month, cutoff, tav)
    pc = P.predict_month(month, "c", inp)
    pb = P.predict_month(month, "b", inp)
    out = {"target_month": month, "label": "experimental nowcast", "model": "c", "headline_yoy": pc["yoy"],
           "evidence_cutoff_utc": cutoff_utc(cutoff), "dry_run": cache_only, "created_utc":
           datetime.now(timezone.utc).isoformat()}
    if month in LIVE_MONTHS:
        skeptic = {"n_contrary": 0, "status": "not run (dry run)" if cache_only else "not requested"}
        if run_skeptic and not cache_only:
            from tools.score_replay import skeptic as run
            from shadow_cpi.nemotron import Nemotron
            n, checks = run(month, pc, inp, tav.charge("skeptic", f"skeptic/{month}"), Nemotron(recorder=rec))
            skeptic = {"n_contrary": n, "status": "run (search snippets)", "checks": checks}
        misses = scored_misses(inp["published"][O.HEADLINE], O.TEST_MONTHS)
        rng = live_range(pc["yoy"], misses.values(), skeptic["n_contrary"])
        out.update({"range_low": rng["low"], "range_high": rng["high"], "range_level": 0.8, "range": rng,
                    "p_headline_ge_6": rng["p_headline_ge_6"], "skeptic": skeptic,
                    "replay_inside_range": {"n": 5, "of": 9}})
    names = {c: inp["meta"].get(c, {}).get("name", c) for c in pc["contrib_division_pp"]}
    top = sorted(pc["contrib_division_pp"].items(), key=lambda kv: -abs(kv[1]))[:3]
    out.update({"coverage": {"observed": pc["coverage_observed"], "carried": 1 - pc["coverage_observed"]},
                "contributors": [{"code": c, "name": names[c], "pp": pp} for c, pp in top],
                "tavily_attribution": {"pred_without_tavily": pb["yoy"], "pred_with_tavily": pc["yoy"],
                                       "coverage_without": pb["coverage_observed"],
                                       "coverage_with": pc["coverage_observed"]},
                "evidence": pc["evidence"], "inputs": notes, "missing_inputs": missing,
                "manifest": f"manifests/{month}.json", "code_commit": E.code_commit(), "model_ids": models(),
                "credits_live_month": spent("live-month"),
                "tavily_provenance": [p for p in rec.provenance if p["service"] == "tavily"]})   # Amendment F
    return out


def main():
    ap = argparse.ArgumentParser(description="Build the experimental nowcast for one month with model (c).")
    ap.add_argument("month")
    ap.add_argument("--cutoff", required=True, help="last evidence day, YYYY-MM-DD (23:59 IST)")
    ap.add_argument("--dry-run", action="store_true", help="cache only (0 credits); print, write nothing")
    ap.add_argument("--skeptic", action="store_true", help="run the skeptic counter-searches (credits)")
    a = ap.parse_args()
    out = build(a.month, a.cutoff, cache_only=a.dry_run, run_skeptic=a.skeptic)
    text = json.dumps(out, ensure_ascii=False, indent=1, default=float)
    if a.dry_run:
        print(text)
        return
    for name in (f"nowcast_{a.month}.json", "nowcast_latest.json"):
        (ROOT / "results" / name).write_text(text + "\n", encoding="utf-8")
    print(f"wrote results/nowcast_{a.month}.json and results/nowcast_latest.json")


if __name__ == "__main__":
    sys.exit(main())
