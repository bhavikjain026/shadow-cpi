#!/usr/bin/env python3
"""v2 issue 14: build Jan-Sep 2026 under the cutoff rule and Amendments A-D, then score ONCE against the
pre-registered rule (v2/PREREGISTRATION.md) and show v2 beside v1.

    python -m v2.score            # scores once; refuses if results/v2_score_lock.json exists (cap 'v2-issue14', 250)

Per month: the government spine items, the official series cut at the cutoff (v1's code), and announced price changes
from the Amendment C query set (v2.events; the issue 4 run's cache is reused, missing months are completed), verified
under Amendments A-D, one event per item x place x month. Range = prediction +- 0.284 (Amendment D). Direction is
scored with v1's pre-registered rule against B1.
"""
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import build_nowcast as BN  # noqa: E402
from shadow_cpi import official as O  # noqa: E402
from shadow_cpi import predict as P  # noqa: E402
from shadow_cpi.budget import Budgeted, spent  # noqa: E402
from shadow_cpi.nemotron import Nemotron  # noqa: E402
from shadow_cpi.recorder import Recorder  # noqa: E402
from shadow_cpi.settings import models  # noqa: E402
from shadow_cpi.tavily import Tavily  # noqa: E402
from tools.score_replay import direction_hit  # noqa: E402
from v2 import kinds as K  # noqa: E402
from v2 import recall as RC  # noqa: E402
from v2 import rules as R  # noqa: E402
from v2.basket import merge, observed_cards, spine_cards  # noqa: E402
from v2.events import run_month  # noqa: E402
from v2.needle import path  # noqa: E402

BUDGET = "v2-issue14"
LOCK = ROOT / "results" / "v2_score_lock.json"
MONTHS = [f"2026-{m:02d}" for m in range(1, 10)]
HALF_WIDTH = 0.284                     # Amendment D: v1's live-month half-width
SCOPE_KIND = {"diesel": "fuel", "rail": "rail", "mobile": "mobile", "bus": "bus", "electricity": "electricity"}


def moving_events(cards, month):
    """Verified claims whose item events may move (Amendment A rule 1), placed by rule 2, merged per item x place."""
    groups, uses = {}, {}
    for c in cards:
        for cl in c["claims"]:
            if cl.get("status") != "verified":
                continue
            kind = cl.get("kind")
            if K.KINDS.get(kind, {}).get("role") != "moves":
                cl["use"] = f"context: {kind} has another source (Amendment A)" if kind else "context: no kind"
                continue
            sc, weight, where, why = R.geography(SCOPE_KIND[kind], cl["line"], cl.get("region") or "",
                                                 cl.get("seller") or "", f"{c['title']} {cl.get('context', '')}",
                                                 K.KINDS[kind]["cpi"], extra_states=cl.get("states"))
            if sc == "context":
                cl["use"] = f"context: {why}"
                continue
            cl["use"] = f"moves CPI ({sc}: {where})"
            groups.setdefault((kind, where), []).append((cl, weight, c))
    out = []
    for (kind, where), cls in groups.items():
        sources = [{"published": c["published"], "change": cl["change"], "effective_date": cl["effective_date"],
                    "read_by": cl.get("read_by"), "url": c["url"]} for cl, _, c in cls]
        change, eff, share = merge(sources, month)
        out.append({"kind": "event", "event_kind": kind, "cpi_code": K.KINDS[kind]["cpi"], "where": where,
                    "change": change, "effective_date": eff, "share_of_month": share, "weight_share": cls[0][1],
                    "applied": change * share * cls[0][1], "sources": sources})
    return out


def measured(weights, items):
    """Amendment D, rule 4: full weight for spine/official items; an event counts its item weight x its share."""
    total = sum(weights[g] for g in O.codes_at("group", weights))
    seen = {}
    for code, share in items:
        seen[code] = min(1.0, seen.get(code, 0.0) + share)
    return sum(weights[c] * s for c, s in seen.items()) / total


def v1_measured(month, weights):
    """v1 (c) recomputed under v2's definition: spine and official items in full, events by their state share."""
    pred = json.loads((ROOT / "results" / "replay_predictions.json").read_text())[month]["c"]["evidence"]
    events = json.loads((ROOT / "manifests" / f"{month}.json").read_text())["events"]
    items = [(c, 1.0) for c, v in pred.items() if v["change"] is not None and v["source"] in ("spine", "observed")]
    items += [(e["cpi_code"], e.get("weight", 1.0)) for e in events if e.get("cpi_code") in pred
              and pred[e["cpi_code"]]["source"] == "event+trend"]
    return measured(weights, items)


def build_month(month, tav, nem, nano, sup, rec):
    cut = R.cutoff(month)
    inp, notes, _ = BN.gather(month, cut, Budgeted(Tavily(recorder=rec), [BUDGET], cache_only=True))
    meta = inp["meta"]
    items = [c for c in spine_cards(inp, month, meta) + observed_cards(inp["observed"][month], notes, month, meta,
                                                                       inp["factors"]) if c["status"] == "verified"]
    cards = run_month(month, tav, nem, nano, sup)
    moving = moving_events(cards, month)
    spine = [(c["cpi_code"], "level", c["change"]) for c in items if c["kind"] == "spine"]
    seq = [(c["cpi_code"], "level", c["change"]) for c in items] + [(m["cpi_code"], "add", m["applied"])
                                                                    for m in moving]
    start, after = path(month, seq, inp)
    _, spine_after = path(month, spine, inp)
    claims = [cl for c in cards for cl in c["claims"] if "status" in cl]
    return {"month": month, "cutoff": cut, "trend_only": start, "spine_only": spine_after[-1] if spine_after else start,
            "v2": after[-1] if after else start, "moving_events": moving,
            "measured": measured(inp["weights"], [(c["cpi_code"], 1.0) for c in items]
                                 + [(m["cpi_code"], m["weight_share"]) for m in moving]),
            "v1_measured": v1_measured(month, inp["weights"]),
            "claims": {s: sum(cl["status"] == s for cl in claims) for s in ("verified", "context", "rejected")},
            "verified_by_model": {m: sum(cl["status"] == "verified" and cl.get("read_by") == m for cl in claims)
                                  for m in (nano, sup)},
            "date_rejections": {f: sum(c.get("date_flag") == f for c in cards for _ in c["claims"])
                                for f in ("after cutoff", "edited after its date")},
            "recall_claims": [{**cl, "url": c["url"]} for c in cards for cl in c["claims"] if "status" in cl]}


def main():
    if LOCK.exists():
        raise SystemExit(f"v2 is already scored ({LOCK}). It is scored once; change nothing except logged bug fixes.")
    rec = Recorder()
    tav = Budgeted(Tavily(recorder=rec), [BUDGET])
    nem = Nemotron(recorder=rec)
    nano, sup = models()["small"], models()["mid"]
    months = []
    for m in MONTHS:
        months.append(build_month(m, tav, nem, nano, sup, rec))
        print(f"{m}: v2 {months[-1]['v2']:.3f}; credits {spent(BUDGET)}", flush=True)
    inp = P.load_inputs()
    pub = inp["published"][O.HEADLINE]
    base = {r["month"]: r for r in csv.DictReader((ROOT / "results" / "baselines.csv").open())}
    v1lock = json.loads((ROOT / "results" / "score_lock.json").read_text())
    rows, n = [], len(MONTHS)
    for b in months:
        m, act = b["month"], pub[b["month"]]
        b1 = float(base[m]["b1_pred"])
        rows.append({"month": m, "actual": act, "v2": b["v2"], "miss": b["v2"] - act,
                     "range": [b["v2"] - HALF_WIDTH, b["v2"] + HALF_WIDTH],
                     "inside": abs(b["v2"] - act) <= HALF_WIDTH, "direction_hit": direction_hit(b["v2"], act, b1),
                     "spine_only": b["spine_only"], "trend_only": b["trend_only"],
                     "measured": b["measured"], "v1_measured": b["v1_measured"],
                     "poll": float(base[m]["poll_pred"]) if base[m]["poll_pred"] else None})
    mae = sum(abs(r["miss"]) for r in rows) / n
    poll_rows = [r for r in rows if r["poll"] is not None]
    recall = RC.score({b["month"]: b["recall_claims"] for b in months})
    v2_found = sum(r["v2"] == "FOUND" for r in recall)
    out = {
        "scored_at_utc": datetime.now(timezone.utc).isoformat(),
        "rules": "v2/PREREGISTRATION.md with Amendments A-D",
        "v2": {"mae": mae, "direction_hits": sum(r["direction_hit"] for r in rows), "inside_range": sum(r["inside"]
                                                                                                        for r in rows),
               "mae_poll_months": sum(abs(r["miss"]) for r in poll_rows) / len(poll_rows),
               "recall_found": v2_found, "measured_sep": rows[-1]["measured"],
               "lift_sep": {"spine_only": rows[-1]["spine_only"], "with_all_evidence": rows[-1]["v2"]},
               "verified_by_model": {k: sum(b["verified_by_model"][k] for b in months) for k in (nano, sup)},
               "claims": {s: sum(b["claims"][s] for b in months) for s in ("verified", "context", "rejected")},
               "date_rejections": {f: sum(b["date_rejections"][f] for b in months)
                                   for f in ("after cutoff", "edited after its date")}},
        "v1": {"mae": v1lock["mae"]["c"], "direction_hits": v1lock["direction_hits"]["c"],
               "inside_range": v1lock["inside_range"], "mae_poll_months": v1lock["mae_poll_months"]["c"],
               "recall_found": sum(r["v1"] == "FOUND" for r in recall), "measured_sep": rows[-1]["v1_measured"]},
        "baselines": {"B1": v1lock["mae"]["B1"], "trend_only": v1lock["mae"]["a"],
                      "poll": v1lock["mae_poll_months"]["poll"]},
        "months": rows, "recall": recall, "month_builds": [{k: v for k, v in b.items() if k != "recall_claims"}
                                                           for b in months],
        "credits_budget": BUDGET, "credits_spent": spent(BUDGET)}
    out["pass_rule"] = mae < out["baselines"]["B1"] and mae < out["baselines"]["trend_only"]
    out["v2_better_than_v1"] = mae < out["v1"]["mae"] and v2_found > 9
    LOCK.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float))
    print(json.dumps({k: out[k] for k in ("v2", "v1", "baselines", "pass_rule", "v2_better_than_v1",
                                           "credits_spent")}, indent=1, default=float))


if __name__ == "__main__":
    main()
