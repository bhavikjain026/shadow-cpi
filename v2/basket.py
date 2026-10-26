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
BUDGETS = [BUDGET, "v2-amendB"]                  # Amendment B re-run: at most 30 more credits
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


def event_cards(tav, nem, nano, month, items_cfg, meta, ledger=None):
    """Proposed pages per kind, verified, with Amendment A use; and the moving events (one per kind x place)."""
    seen, cards, moving = set(), [], []
    for kind in EVENT_KINDS:
        cfg = items_cfg[kind]
        queries = [(lang, cfg["queries"][lang]) for lang in cfg.get("langs", ["en"]) if lang in cfg["queries"]]
        kc = PL.propose(tav, nem, nano, queries, month, f"v2:basket {kind}", seen)
        PL.fetch_and_verify(tav, nem, nano, kc, month, cfg["match"], None, None, kind, f"v2:basket {kind}",
                            super_model=models()["mid"])
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
        PL.ledger_rows(kc, month, cfg["cpi_code"], name_of(meta, cfg["cpi_code"]), kind, "", nano, ledger)
        for where, cls in groups.items():
            sources = [{"published": c["published"], "change": cl["change"], "effective_date": cl["effective_date"],
                        "read_by": cl.get("read_by"), "url": c["url"]} for cl, _, c in cls]
            change, eff, share = merge(sources, month)
            weight = cls[0][1]
            moving.append({"kind": "event", "cpi_code": cfg["cpi_code"], "event_kind": kind, "where": where,
                           "change": change, "effective_date": eff, "share_of_month": share, "weight_share": weight,
                           "applied": change * share * weight, "mode": "add", "n_sources": len(cls),
                           "sources": sources, "urls": sorted({c["url"] for _, _, c in cls})})
        cards += kc
    return cards, moving


def merge(sources, month):
    """One event per item x place x month (v1 Amendment 3 d): median change, earliest effective date, day share."""
    change = statistics.median(x["change"] for x in sources)
    eff = min(x["effective_date"] for x in sources)
    days = calendar.monthrange(int(month[:4]), int(month[5:]))[1]
    return change, eff, (days - int(eff[8:]) + 1) / days


def stages(timeline, start):
    """Issue 8, 'What Tavily adds': the needle with the government spine only, then + official series read with
    Tavily Extract, then + announced price changes found with Tavily Search."""
    def last(kinds):
        vals = [t["yoy_after"] for t in timeline if t["kind"] in kinds]
        return vals[-1] if vals else None
    spine = last({"spine"}) or start
    series = last({"spine", "observed"}) or spine
    events = timeline[-1]["yoy_after"] if timeline else series
    return [{"label": "Trend + government spine (no web evidence)", "yoy": spine},
            {"label": "+ official series via Tavily Extract (IBJA, IOCL, PPAC)", "yoy": series},
            {"label": "+ announced price changes via Tavily Search", "yoy": events}]


def time_machine(month, item_cards, moving, inp, meta, total, client, ledger=None):
    """Issue 3: for each day of the month up to the cutoff, the needle from evidence published by that day only.
    Official series: daily rows up to the day (v1's cutoff-aware code). Events: pages published by the day. The spine
    is a monthly average with no daily prices, so it enters only on the cutoff day."""
    from datetime import date, timedelta
    from v2.needle import yoy
    w, cut = inp["weights"], R.cutoff(month)
    spine = [c for c in item_cards if c["kind"] == "spine" and c["status"] == "verified"]
    rows, d = [], date.fromisoformat(f"{month}-01")
    ledger = [r for r in LG.read(ledger) if r["month"] == month]
    while d.isoformat() <= cut:
        day = d.isoformat()
        inp_d, notes_d, _ = BN.gather(month, day, Budgeted(client, BUDGETS, cache_only=True))
        changes, measured = {}, 0.0
        if day == cut:
            for c in spine:
                changes[c["cpi_code"]] = ("level", c["change"])
                measured += w[c["cpi_code"]]
        for c in observed_cards(inp_d["observed"][month], notes_d, month, meta, inp["factors"]):
            if c["status"] == "verified":
                changes[c["cpi_code"]] = ("level", c["change"])
                measured += w[c["cpi_code"]]
        for m in moving:
            src = [x for x in m["sources"] if x["published"] <= day]
            if src:
                ch, _, share = merge(src, month)
                changes[m["cpi_code"]] = ("add", changes.get(m["cpi_code"], ("add", 0.0))[1] + ch * share * m["weight_share"])
                measured += w[m["cpi_code"]] * m["weight_share"]
        rows.append({"date": day, "yoy": yoy(month, changes, inp) if changes else P.predict_month(month, "a", inp)["yoy"],
                     "measured": measured / total, "n_items": len(changes),
                     "n_ledger_records": sum(r["published_date"] <= day for r in ledger)})
        d += timedelta(days=1)
    return rows


def basket_tiles(inp, meta, measured_codes):
    w = inp["weights"]
    groups = []
    for g in O.codes_at("group", w):
        items = [{"code": c, "name": name_of(meta, c), "weight": w[c]} for c in measured_codes
                 if O.parent_code(c, "group") == g]
        groups.append({"code": g, "name": name_of(meta, g), "weight": w[g], "items": items})
    return layout(groups)


def run(month="2026-09", cache_only=False, rec=None, keys=(None, None), out_dir=None, ledger=None):
    """keys = (Tavily, Nebius) keys, None = from the environment; v2.replay passes placeholders with a recorder that
    refuses any call not in the cache, and a scratch out_dir and ledger so committed files are left alone."""
    rec = rec or Recorder()
    client = Tavily(api_key=keys[0], recorder=rec)
    tav = Budgeted(client, BUDGETS, cache_only=cache_only)
    nem, nano = Nemotron(api_key=keys[1], recorder=rec), models()["small"]
    cut = R.cutoff(month)
    # official observed series cut at the cutoff (v1's code, cache only: the replay months are all cached)
    inp, notes, missing = BN.gather(month, cut, Budgeted(client, BUDGETS, cache_only=True))
    meta = inp["meta"]
    item_cards = spine_cards(inp, month, meta) + observed_cards(inp["observed"][month], notes, month, meta,
                                                                inp["factors"])
    ev_cards, moving = event_cards(tav, nem, nano, month, E.load_items()["events"], meta, ledger)
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
           "stages": stages(timeline, start), "time_machine": time_machine(month, item_cards, moving, inp, meta, total,
                                                                          client, ledger),
           "credits_budget": BUDGET, "credits_spent": spent(BUDGET),
           "credits_by_budget": {b: spent(b) for b in BUDGETS}}
    p = Path(out_dir or LG.ROOT) / f"run_{month}_basket.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float))
    return out, p


if __name__ == "__main__":
    o, p = run(cache_only="--cache-only" in sys.argv)
    ev = [cl for c in o["cards"] for cl in c["claims"] if "status" in cl]
    print(f"items: {sum(c['status'] == 'verified' for c in o['item_cards'])} of {len(o['item_cards'])} verified; "
          f"event pages {len(o['cards'])}, claims checked {len(ev)}, verified {sum(cl['status'] == 'verified' for cl in ev)}, "
          f"moving {len(o['moving_events'])}; measured {o['measured_share']:.1%}; needle {o['needle']}; "
          f"v1 (c) {o['v1']['c']:.3f}; official {o['official']}; credits {o['credits_by_budget']}")
