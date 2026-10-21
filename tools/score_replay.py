#!/usr/bin/env python3
"""Prompt 3: predict, run the skeptic, then score ONCE (docs/preregistration.md).

    python tools/score_replay.py                     # the one scoring run (refuses if results/score_lock.json exists)
    python tools/score_replay.py --bugfix "reason"   # only after a logged bug fix; keeps the earlier score files
    python tools/score_replay.py --bugfix "reason" --cache-only   # same, skeptic from the cache only (0 credits)

Order: (1) predictions for all models (no official figure for the target month is read); (2) skeptic counter-searches
(hard cap 'skeptic'); (3) scoring against MoSPI's published YoY, leave-one-out 80% ranges, GO rule.
"""
import csv
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from shadow_cpi import official as O  # noqa: E402
from shadow_cpi import predict as P  # noqa: E402
from shadow_cpi.budget import BudgetExceeded, Budgeted, read_ledger  # noqa: E402
from shadow_cpi.evidence import MONTHS_EN, month_window  # noqa: E402
from shadow_cpi.nemotron import Nemotron  # noqa: E402
from shadow_cpi.recorder import Recorder  # noqa: E402
from shadow_cpi.settings import models  # noqa: E402
from shadow_cpi.tavily import Tavily  # noqa: E402
from shadow_cpi.verify import norm  # noqa: E402

RES = ROOT / "results"
LOCK = RES / "score_lock.json"
MODELS = ["a", "b", "c", "c_strict"]
FALL = ["fell", "fall", "drop", "declin", "cheaper", "cut", "lower", "eased", "slump", "सस्ता", "सस्ते", "घट", "गिराव",
        "कमी"]
RISE = ["rose", "rise", "hike", "increase", "costlier", "surge", "jump", "महंग", "बढ़", "इजाफा", "उछाल"]


def percentile(xs, q):
    xs = sorted(xs)
    k = (len(xs) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def component_name(code, meta):
    base = code.split("#")[0]
    return re.sub(r"\s*\(.*?\)", "", meta.get(base, {}).get("name", base)).strip()


def skeptic(month, pred_c, inp, tav, nem):
    """Top 3 components by |contribution to predicted MoM| -> one opposite-direction counter-search each (snippets
    only). Returns (n_verified_contrary, details)."""
    top = sorted(pred_c["mom_pp"].items(), key=lambda kv: -abs(kv[1]))[:3]
    start, end = month_window(month)
    mname = f"{MONTHS_EN[int(month[5:]) - 1]} {month[:4]}"
    details, n = [], 0
    for code, pp in top:
        name = component_name(code, inp["meta"])
        words = FALL if pp > 0 else RISE
        q = f"{name} price {'fall cheaper' if pp > 0 else 'hike rise'} {mname} India"
        resp, cid = tav.search(q, topic="news", search_depth="basic", max_results=8, start_date=start, end_date=end,
                               tag=f"skeptic:{code} search")
        text = "\n".join(r.get("content") or "" for r in resp.get("results", []))
        token = next((t for t in re.findall(r"[a-z]{4,}", norm(name))), norm(name))
        contrary = []
        if text.strip():
            quotes, _ = nem.price_quotes(models()["mid"], text, name, tag=f"skeptic:{code} quotes", parent=cid)
            for qq in quotes:
                line = norm(qq.get("quote") or "")
                if qq.get("verified") and token in line and any(norm(w) in line for w in words):
                    contrary.append(qq.get("quote"))
        n += len(contrary)
        details.append({"code": code, "name": name, "contribution_mom_pp": pp, "query": q,
                        "n_results": len(resp.get("results", [])), "contrary_verified": contrary})
    return n, details


def direction_hit(pred, actual, prev):
    if abs(actual - prev) < 0.005:
        return abs(pred - prev) < 0.05
    return (pred - prev > 0) == (actual - prev > 0)


def credits_for(month):
    led = read_ledger()
    months_budgets = (f"replay-layers-month/{month}", f"skeptic/{month}")
    sel = [e for e in led if any(b in e["budgets"] for b in months_budgets)]
    return len(sel), sum(e["credits"] for e in sel)


def main():
    bugfix = next((sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == "--bugfix"), None)
    if LOCK.exists() and not bugfix:
        raise SystemExit(f"Already scored ({LOCK}). Scoring runs once; use --bugfix \"reason\" after a logged fix.")
    prereg = (ROOT / "docs" / "preregistration.md").read_bytes()
    inp = P.load_inputs()

    # (1) predictions - no official figure for the target month is used
    preds = {m: {mod: P.predict_month(m, mod, inp) for mod in MODELS} for m in O.TEST_MONTHS}
    (RES / "replay_predictions.json").write_text(json.dumps(
        {m: {mod: {k: v for k, v in p.items() if k != "mom_pp"} for mod, p in d.items()} for m, d in preds.items()},
        indent=1, default=float))

    # (2) skeptic (hard cap 'skeptic'; snippets only for replay months)
    rec = Recorder()
    base = Budgeted(Tavily(recorder=rec), ["skeptic"], cache_only="--cache-only" in sys.argv)   # re-scores: 0 credits
    nem = Nemotron(recorder=rec)
    sk = {}
    for m in O.TEST_MONTHS:
        try:
            sk[m] = skeptic(m, preds[m]["c"], inp, base.charge("skeptic", f"skeptic/{m}"), nem)
        except BudgetExceeded as e:
            print(f"skeptic stopped at {m}: {e}")
            sk[m] = (0, [{"note": f"not run: {e}"}])
    (RES / "skeptic_replay.json").write_text(json.dumps({m: {"n_contrary": v[0], "checks": v[1]} for m, v in sk.items()},
                                                        ensure_ascii=False, indent=1))

    # (3) scoring - once
    pub = inp["published"][O.HEADLINE]
    base_rows = {r["month"]: r for r in csv.DictReader((RES / "baselines.csv").open())}
    actual = {m: pub[m] for m in O.TEST_MONTHS}
    miss = {mod: {m: preds[m][mod]["yoy"] - actual[m] for m in O.TEST_MONTHS} for mod in MODELS}
    b1 = {m: float(base_rows[m]["b1_pred"]) for m in O.TEST_MONTHS}
    poll = {m: float(base_rows[m]["poll_pred"]) for m in O.TEST_MONTHS if base_rows[m]["poll_pred"]}
    rows = []
    for m in O.TEST_MONTHS:
        others = [miss["c"][k] for k in O.TEST_MONTHS if k != m]
        q10, q90 = percentile(others, 0.10), percentile(others, 0.90)
        pc = preds[m]["c"]["yoy"]
        lo, hi = pc - q90, pc - q10
        note = ""
        if sk[m][0] >= 2:
            lo, hi = pc - (pc - lo) * 1.5, pc + (hi - pc) * 1.5
            note = f"skeptic: {sk[m][0]} verified contrary quotes, range widened 50%"
        rows.append({"month": m, "actual_yoy": actual[m], "a_trend_pred": preds[m]["a"]["yoy"],
                     "b_spine_pred": preds[m]["b"]["yoy"], "c_tavily_pred": pc,
                     "c_strict_pred": preds[m]["c_strict"]["yoy"], "c_range_low": lo, "c_range_high": hi,
                     "c_inside_range": lo <= actual[m] <= hi, "b_coverage_observed": preds[m]["b"]["coverage_observed"],
                     "c_coverage_observed": preds[m]["c"]["coverage_observed"], "tier": "strict+exploratory",
                     "note": note, "b1_pred": b1[m], "poll_pred": poll.get(m, "")})
    mae = {mod: sum(abs(v) for v in miss[mod].values()) / 9 for mod in MODELS}
    mae["B1"] = sum(abs(b1[m] - actual[m]) for m in O.TEST_MONTHS) / 9
    prev = {m: b1[m] for m in O.TEST_MONTHS}      # B1 = last month's published YoY
    hits = {mod: sum(direction_hit(preds[m][mod]["yoy"], actual[m], prev[m]) for m in O.TEST_MONTHS) for mod in MODELS}
    hits["B1"] = sum(direction_hit(b1[m], actual[m], prev[m]) for m in O.TEST_MONTHS)
    poll_m = sorted(poll)
    mae_poll = {mod: sum(abs(preds[m][mod]["yoy"] - actual[m]) for m in poll_m) / len(poll_m) for mod in MODELS}
    mae_poll["poll"] = sum(abs(poll[m] - actual[m]) for m in poll_m) / len(poll_m)
    hits_poll = sum(direction_hit(poll[m], actual[m], prev[m]) for m in poll_m)
    go = mae["c"] < mae["B1"] and mae["c"] < mae["a"]
    inside = sum(r["c_inside_range"] for r in rows)

    if bugfix and LOCK.exists():
        stamp = json.loads(LOCK.read_text())["scored_at_utc"][:19].replace(":", "")
        for f in ("replay.csv", "scoreboard.md", "tavily_attribution.csv"):
            if (RES / f).exists():
                shutil.copy(RES / f, RES / f"{Path(f).stem}_before_bugfix_{stamp}{Path(f).suffix}")
    with (RES / "replay.csv").open("w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(rows[0]))
        wr.writeheader()
        for r in rows:
            wr.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})
    with (RES / "tavily_attribution.csv").open("w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=["month", "pred_without_tavily", "pred_with_tavily", "coverage_without",
                                            "coverage_with", "actual_yoy", "miss_without", "miss_with",
                                            "tavily_calls", "credits"])
        wr.writeheader()
        for m in O.TEST_MONTHS:
            calls, cr = credits_for(m)
            wr.writerow({"month": m, "pred_without_tavily": round(preds[m]["b"]["yoy"], 4),
                         "pred_with_tavily": round(preds[m]["c"]["yoy"], 4),
                         "coverage_without": round(preds[m]["b"]["coverage_observed"], 4),
                         "coverage_with": round(preds[m]["c"]["coverage_observed"], 4), "actual_yoy": actual[m],
                         "miss_without": round(miss["b"][m], 4), "miss_with": round(miss["c"][m], 4),
                         "tavily_calls": calls, "credits": cr})
    names = {"a": "(a) Trend only (= B2)", "b": "(b) Government spine only", "c": "(c) Spine + Tavily evidence",
             "c_strict": "(c-strict) Spine + official observed series", "B1": "B1 last month's rate"}
    lines = ["# Replay scoreboard (Jan–Sep 2026)", "",
             f"Scored once on {datetime.now(timezone.utc).isoformat()[:19]} UTC against MoSPI's published YoY. "
             "Rules: `docs/preregistration.md`.", "",
             "| Method | Mean absolute miss (pp) | Direction right (of 9) |", "|---|---|---|"]
    for k in ["a", "b", "c", "c_strict", "B1"]:
        lines.append(f"| {names[k]} | {mae[k]:.3f} | {hits[k]} |")
    lines += ["", f"Economists' poll, on its {len(poll_m)} dated months: poll {mae_poll['poll']:.3f} pp "
                  f"(direction {hits_poll} of {len(poll_m)}); on the same months (c) {mae_poll['c']:.3f}, "
                  f"(b) {mae_poll['b']:.3f}, (a) {mae_poll['a']:.3f}.", "",
              f"**{'GO' if go else 'NO-GO'}** (rule: (c) must beat B1 and (a) on mean absolute miss).", "",
              f"80% range (leave-one-out from replay misses): actual inside the range in **{inside} of 9** months.",
              "", "| Month | Actual | (a) | (b) | (c) | (c-strict) | B1 | Poll | (c) range | Inside | Coverage (b → c) |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['month']} | {r['actual_yoy']:.2f} | {r['a_trend_pred']:.2f} | {r['b_spine_pred']:.2f} | "
                     f"{r['c_tavily_pred']:.2f} | {r['c_strict_pred']:.2f} | {r['b1_pred']:.2f} | "
                     f"{('%.2f' % r['poll_pred']) if r['poll_pred'] != '' else '–'} | "
                     f"{r['c_range_low']:.2f}–{r['c_range_high']:.2f} | {'yes' if r['c_inside_range'] else 'no'} | "
                     f"{r['b_coverage_observed']:.0%} → {r['c_coverage_observed']:.0%} |")
    (RES / "scoreboard.md").write_text("\n".join(lines) + "\n")
    lock = {"scored_at_utc": datetime.now(timezone.utc).isoformat(),
            "preregistration_sha256": hashlib.sha256(prereg).hexdigest(),
            "mae": mae, "mae_poll_months": mae_poll, "direction_hits": hits, "go": go, "inside_range": inside,
            "bugfix": bugfix}
    if bugfix:
        hist = json.loads(LOCK.read_text()).get("history", []) + [json.loads(LOCK.read_text())]
        lock["history"] = hist
    LOCK.write_text(json.dumps(lock, indent=1))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
