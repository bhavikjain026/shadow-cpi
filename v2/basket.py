#!/usr/bin/env python3
"""v2 issue 2: the Live build for the whole basket, one month (default September 2026, cutoff 29 Sep).

    python -m v2.basket                 # may spend credits (hard cap 'v2-issue2' in config/budget.json)
    python -m v2.basket --cache-only    # 0 credits

Order of evidence (Amendment A: each item has one source and moves once):
1. Government price spine (DoCA) for the spine foods: the measured change x the 2025 pass-through factor.
2. Official observed series, cut at the cutoff (v1's cutoff-aware code, from the cache): IBJA gold and silver,
   IOCL LPG, PPAC petrol.
3. Announced price changes for items with neither (electricity, rail fares, mobile tariffs, medicines, school fees):
   search proposes -> Nano reads -> Extract verifies (v2.pipeline); geography by Amendment A rule 2; one event per
   item x place x month (median change, earliest effective date).
Everything else stays on its trend. Each verified item moves the needle (v2.needle) and fills the treemap.
"""
import calendar
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import build_nowcast as BN  # noqa: E402
from shadow_cpi import evidence as E  # noqa: E402
from shadow_cpi import official as O  # noqa: E402
from shadow_cpi import predict as P  # noqa: E402
from shadow_cpi.budget import Budgeted, spent  # noqa: E402
from shadow_cpi.nemotron import Nemotron  # noqa: E402
from shadow_cpi.recorder import Recorder  # noqa: E402
from shadow_cpi.settings import models  # noqa: E402
from shadow_cpi.tavily import Tavily  # noqa: E402
from v2 import ledger as LG  # noqa: E402
from v2 import pipeline as PL  # noqa: E402
from v2 import rules as R  # noqa: E402
from v2.needle import path  # noqa: E402
from v2.treemap import layout  # noqa: E402

BUDGET = "v2-issue2"
EVENT_KINDS = ["electricity", "rail", "mobile", "medicine", "school_fee"]
OBSERVED = [("gold", "13.2.1.1.1.01", "IBJA daily gold rates"), ("silver", "13.2.1.1.1.02", "IBJA daily silver rates"),
            ("lpg", "04.5.2.2.1.01", "IOCL domestic LPG price list"), ("petrol", "07.2.2.2.1.01", "PPAC Delhi petrol")]


def name_of(meta, code):
    return meta.get(code, {}).get("name", code)


def spine_cards(inp, month, meta):
    cards = []
    for food, code in E.SPINE_FOODS.items():
        f = inp["factors"][food]
        if not f.get("use_spine"):
            continue
        ch, n = E.spine_change(inp["spine"], food, month)
        ok = ch is not None
        cards.append({"kind": "spine", "cpi_code": code, "name": name_of(meta, code), "status":
                      "verified" if ok else "rejected", "reason": "verified" if ok else "no spine prices for both months",
                      "source": "government price spine (DoCA monthly averages)", "change": f["factor"] * ch if ok else None,
                      "raw_change": ch, "detail": f"{n} zones; 2025 pass-through factor {f['factor']:.3f}",
                      "mode": "level", "weight_share": 1.0})
    return cards


def observed_cards(row, notes, month, meta, factors):
    cards = []
    for key, code, src in OBSERVED:
        ch = row.get(f"{key}_item_change")
        ob = notes["observed"].get(key, {})
        ok = ch is not None
        why = "verified"
        if not ok:
            why = ("IOCL list saved before the cutoff (an LPG gap)" if ob.get("gap") else
                   f"too few days ({ob.get('days_now')}/{ob.get('days_prev')})" if "days_now" in ob else "no data")
        detail = (f"{ob.get('days_now')} days to the cutoff vs {ob.get('days_prev')} last month"
                  if "days_now" in ob and ob.get("days_now") is not None else "price in force by the cutoff")
        cards.append({"kind": "observed", "cpi_code": code, "name": name_of(meta, code), "status":
                      "verified" if ok else "rejected", "reason": why, "source": src, "change": ch,
                      "raw_change": ob.get("change"), "detail": f"{detail}; factor {factors[key]['factor']:.3f}",
                      "mode": "level", "weight_share": 1.0})
    return cards


def event_cards(tav, nem, nano, month, items_cfg, meta):
    """Proposed pages per kind, verified, with Amendment A use; and the moving events (one per kind x place)."""
    seen, cards, moving = set(), [], []
    for kind in EVENT_KINDS:
        cfg = items_cfg[kind]
        queries = [(lang, cfg["queries"][lang]) for lang in cfg.get("langs", ["en"]) if lang in cfg["queries"]]
        kc = PL.propose(tav, nem, nano, queries, month, f"v2:basket {kind}", seen)
        PL.fetch_and_verify(tav, nem, nano, kc, month, cfg["match"], None, None, kind, f"v2:basket {kind}")
        groups = {}
        for c in kc:
            c["kind"], c["cpi_code"] = kind, cfg["cpi_code"]
            for cl in c["claims"]:
                if cl.get("status") != "verified":
                    continue
                role, why = R.source_role(cfg["cpi_code"])
                if role == "context":
                    cl["use"] = f"context: {why}"
                    continue
                sc, weight, where, why = R.geography(kind, cl["line"], cl.get("region") or "", cl.get("seller") or "",
                                                     c["title"] + " " + cl.get("context", ""), cfg["cpi_code"])
                if sc == "context":
                    cl["use"] = f"context: {why}"
                    continue
                cl["use"] = f"moves CPI ({sc}: {where})"
                groups.setdefault(where, []).append((cl, weight, c))
        PL.ledger_rows(kc, month, cfg["cpi_code"], name_of(meta, cfg["cpi_code"]), kind, "", nano)
        for where, cls in groups.items():
            change = statistics.median(cl["change"] for cl, _, _ in cls)
            eff = min(cl["effective_date"] for cl, _, _ in cls)
            days = calendar.monthrange(int(month[:4]), int(month[5:]))[1]
            share = (days - int(eff[8:]) + 1) / days
            weight = cls[0][1]
            moving.append({"kind": "event", "cpi_code": cfg["cpi_code"], "event_kind": kind, "where": where,
                           "change": change, "effective_date": eff, "share_of_month": share, "weight_share": weight,
                           "applied": change * share * weight, "mode": "add", "n_sources": len(cls),
                           "urls": sorted({c["url"] for _, _, c in cls})})
        cards += kc
    return cards, moving


def basket_tiles(inp, meta, measured_codes):
    w = inp["weights"]
    groups = []
    for g in O.codes_at("group", w):
        items = [{"code": c, "name": name_of(meta, c), "weight": w[c]} for c in measured_codes
                 if O.parent_code(c, "group") == g]
        groups.append({"code": g, "name": name_of(meta, g), "weight": w[g], "items": items})
    return layout(groups)


def run(month="2026-09", cache_only=False):
    rec = Recorder()
    tav = Budgeted(Tavily(recorder=rec), [BUDGET], cache_only=cache_only)
    nem, nano = Nemotron(recorder=rec), models()["small"]
    cut = R.cutoff(month)
    # official observed series cut at the cutoff (v1's code, cache only: the replay months are all cached)
    inp, notes, missing = BN.gather(month, cut, Budgeted(Tavily(recorder=rec), [BUDGET], cache_only=True))
    meta = inp["meta"]
    item_cards = spine_cards(inp, month, meta) + observed_cards(inp["observed"][month], notes, month, meta,
                                                                inp["factors"])
    ev_cards, moving = event_cards(tav, nem, nano, month, E.load_items()["events"], meta)
    steps = [c for c in item_cards if c["status"] == "verified"]
    seq = [(c["cpi_code"], c["mode"], c["change"]) for c in steps] + [(m["cpi_code"], "add", m["applied"])
                                                                       for m in moving]
    start, after = path(month, seq, inp)
    w, total = inp["weights"], sum(inp["weights"][g] for g in O.codes_at("group", inp["weights"]))
    measured, timeline = 0.0, []
    for (code, mode, value), yoy_after, src in zip(seq, after, steps + moving):
        measured += w[code] * src.get("weight_share", 1.0)
        timeline.append({"cpi_code": code, "name": name_of(meta, code), "kind": src["kind"], "mode": mode,
                         "value": value, "yoy_after": yoy_after, "measured_after": measured / total,
                         "weight": w[code], "weight_share": src.get("weight_share", 1.0)})
    preds = json.loads((ROOT / "results" / "replay_predictions.json").read_text())
    out = {"month": month, "cutoff": cut, "window": list(R.window(month)), "built_utc":
           datetime.now(timezone.utc).isoformat(), "model_read": nano, "item_cards": item_cards, "cards": ev_cards,
           "moving_events": moving, "timeline": timeline, "needle": {"start": start, "end": after[-1] if after else start},
           "measured_share": measured / total, "tiles": basket_tiles(inp, meta, [c for c, _, _ in seq]),
           "v1": {"c": preds[month]["c"]["yoy"], "a": preds[month]["a"]["yoy"]},
           "official": inp["published"][O.HEADLINE][month], "notes": missing + [
               "The spine is DoCA's monthly average for the whole month, so it includes the 30th, one day after the "
               "cutoff (the file has no daily prices)."],
           "credits_budget": BUDGET, "credits_spent": spent(BUDGET)}
    p = LG.ROOT / f"run_{month}_basket.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float))
    return out, p


if __name__ == "__main__":
    o, p = run(cache_only="--cache-only" in sys.argv)
    ev = [cl for c in o["cards"] for cl in c["claims"] if "status" in cl]
    print(f"items: {sum(c['status'] == 'verified' for c in o['item_cards'])} of {len(o['item_cards'])} verified; "
          f"event pages {len(o['cards'])}, claims checked {len(ev)}, verified {sum(cl['status'] == 'verified' for cl in ev)}, "
          f"moving {len(o['moving_events'])}; measured {o['measured_share']:.1%}; needle {o['needle']}; "
          f"v1 (c) {o['v1']['c']:.3f}; official {o['official']}; credits ({BUDGET}) {o['credits_spent']}")
