"""Prompt 3 predictor: carve-out aggregation of index LEVELS (docs/preregistration.md). Plain code, no AI.

predict_month(month, model, inp) -> dict with the predicted YoY and its parts. Models: 'a' trend only, 'b' spine only,
'c' spine + Tavily evidence, 'c_strict' spine + official observed series (no news events).
Nothing here reads an official figure for the target month: official data up to month-1 only.
"""
import csv
import json

from . import cpi_math as M
from . import official as O
from .evidence import SPINE_FOODS, load_spine, spine_change
from .settings import ROOT

GOLD, SILVER, LPG, PETROL = "13.2.1.1.1.01", "13.2.1.1.1.02", "04.5.2.2.1.01", "07.2.2.2.1.01"
EVENT_ITEMS = {"electricity", "rail", "mobile", "medicine", "school_fee", "fuel"}   # milk: observed via spine; gst: never


def load_inputs():
    series, weights, published, meta = O.load_tidy()
    factors = json.loads((ROOT / "config" / "passthrough.json").read_text())["items"]
    observed = {r["month"]: r for r in csv.DictReader((ROOT / "results" / "replay_layers.csv").open())}
    events = {}
    for m in O.TEST_MONTHS:
        p = ROOT / "manifests" / f"{m}.json"
        events[m] = json.loads(p.read_text())["events"] if p.exists() else []
    return {"series": series, "weights": weights, "published": published, "meta": meta, "factors": factors,
            "observed": observed, "events": events, "spine": load_spine()}


def _num(x):
    return None if x in (None, "", "None") else float(x)


def evidence_changes(month, model, inp):
    """{code: (change, source)} for carved components; the model decides which evidence is used."""
    out = {}
    if model in ("b", "c", "c_strict"):
        for food, code in SPINE_FOODS.items():
            f = inp["factors"][food]
            if not f.get("use_spine"):
                continue
            ch, _ = spine_change(inp["spine"], food, month)
            out[code] = (None if ch is None else f["factor"] * ch, "spine")
    if model in ("c", "c_strict"):
        row = inp["observed"].get(month, {})
        for code, key in ((GOLD, "gold"), (SILVER, "silver"), (LPG, "lpg")):
            ch = _num(row.get(f"{key}_item_change"))
            out[code] = (ch, "observed")
        p = _num(row.get("petrol_item_change"))
        out[PETROL] = (p, "observed")
    if model == "c":
        for e in inp["events"].get(month, []):
            if e["item"] not in EVENT_ITEMS or not e.get("cpi_code"):
                continue
            if e["item"] == "fuel" and out.get(PETROL, (None,))[0] is not None:
                continue                                  # PPAC covers the month: fuel events not used
            code = e["cpi_code"]
            prev = out.get(code)
            add = e["applied_change"]
            out[code] = ((prev[0] if prev and prev[0] is not None else 0.0) + add, "event+trend")
    return out


def predict_month(month, model, inp):
    s, w = inp["series"], inp["weights"]
    prev = M.add_months(month, -1)
    hist = lambda code: {k: v for k, v in s[code].items() if k <= prev}      # noqa: E731 - no data from `month` on
    groups = O.codes_at("group", w)
    ev = evidence_changes(month, model, inp)
    carved = {}
    for code in ev:
        carved.setdefault(O.parent_code(code, "group"), {})[code] = w[code]
    comps_prev = M.build_components(prev, s, {g: w[g] for g in groups}, carved)
    trend = {g: M.trend_change(hist(g), month) for g in groups}
    trend.update({c: M.trend_change(hist(c), month) for c in ev})
    changes = {}
    for code, (ch, src) in ev.items():
        if src == "event+trend":
            changes[code] = trend[code] + ch                # events add to the item's own trend
        elif ch is not None:
            changes[code] = ch
    head, pred = M.predict_headline(comps_prev, changes, trend)
    base = M.aggregate({c: v[0] for c, v in comps_prev.items()}, {c: v[1] for c, v in comps_prev.items()})
    level = s[O.HEADLINE][prev] * head / base           # anchored to the published headline of month-1
    yoy = M.yoy(level, s[O.HEADLINE][M.add_months(month, -12)])
    # contributions to predicted YoY by division (pp), and to the predicted month-on-month change (for the skeptic)
    comps_12 = M.build_components(M.add_months(month, -12), s, {g: w[g] for g in groups}, carved)
    now = {c: v[0] for c, v in pred.items()}
    ago = {c: v[0] for c, v in comps_12.items()}
    wts = {c: v[1] for c, v in pred.items()}
    contrib = M.contributions_yoy(now, ago, wts)
    by_div = {}
    for c, pp in contrib.items():
        by_div[c[:2]] = by_div.get(c[:2], 0.0) + pp
    denom = sum(v[1] * v[0] for v in comps_prev.values())
    mom_pp = {c: wts[c] * (now[c] - comps_prev[c][0]) / denom * 100 for c in pred}
    cov = M.coverage(pred)
    return {"month": month, "model": model, "yoy": yoy, "level": level, "coverage_observed": cov["observed"],
            "evidence": {c: {"change": changes.get(c), "source": ev[c][1]} for c in ev},
            "contrib_division_pp": by_div, "mom_pp": mom_pp}
