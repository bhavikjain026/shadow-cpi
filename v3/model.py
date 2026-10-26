"""v3 (experimental, beside v1): two methods fixed in v3/PREREG.md. Plain code, no AI, nothing fitted.

- v3a (primary): item = trend + w x (measured - trend), w by tier (official 1.0, corroborated 0.7, single source 0.4).
  Official series already have w = 1.0, so only news events change: each event's applied change is multiplied by its
  w and the inputs go to v1's unchanged predict_month(month, "c", ...).
- v3b (secondary): equal-weight average of the predicted headline LEVELS of v1's (a), (b) and (c); YoY last.
- Range: split conformal, half-width = the 8th smallest of the method's 9 Jan-Sep 2026 absolute misses.
- P(headline >= 6.0%): normal with mean = prediction and sigma = half-width / z_0.90.
v1's code is called, never copied or edited.
"""
import copy
import math
from statistics import NormalDist

from shadow_cpi import cpi_math as M
from shadow_cpi import official as O
from shadow_cpi import predict as P
from shadow_cpi.live_range import THRESHOLD

W = {"verified": 1.0, "corroborated": 0.7, "single source": 0.4}
ALPHA = 0.2
Z90 = NormalDist().inv_cdf(0.90)
METHODS = ("v3a", "v3b")
LABEL = "calibrated on Jan-Sep 2026; tested on Oct and Nov"


def tier(event):
    """A news event's tier. Official series are 'verified' and are never events (v3/PREREG.md section 2)."""
    return "corroborated" if event.get("confirmed_by_2_sources") else "single source"


def weighted_inputs(month, inp):
    """A copy of the inputs with each of the month's events' applied_change multiplied by its tier's w."""
    out = dict(inp)
    out["events"] = dict(inp["events"])
    evs = copy.deepcopy(inp["events"].get(month, []))
    for e in evs:
        e["v3_tier"] = tier(e)
        e["v3_w"] = W[e["v3_tier"]]
        e["applied_change"] = e["v3_w"] * e["applied_change"]
    out["events"][month] = evs
    return out


def v3a(month, inp):
    pred = P.predict_month(month, "c", weighted_inputs(month, inp))
    return {"yoy": pred["yoy"], "level": pred["level"], "evidence": pred["evidence"],
            "events": [{"item": e["item"], "tier": tier(e), "w": W[tier(e)], "applied_change_v1": e["applied_change"],
                        "applied_change_v3": W[tier(e)] * e["applied_change"]}
                       for e in inp["events"].get(month, [])]}


def v3b(month, inp, members=None):
    """Mean of the three members' predicted levels, then YoY against the published headline 12 months earlier."""
    members = members or {m: P.predict_month(month, m, inp) for m in ("a", "b", "c")}
    level = sum(members[m]["level"] for m in ("a", "b", "c")) / 3
    base = inp["series"][O.HEADLINE][M.add_months(month, -12)]
    return {"yoy": M.yoy(level, base), "level": level,
            "members": {m: {"yoy": members[m]["yoy"], "level": members[m]["level"]} for m in ("a", "b", "c")}}


def predict(month, inp):
    """{'v3a': ..., 'v3b': ..., 'v1_c': v1's (c) yoy from the same inputs} for one month."""
    members = {m: P.predict_month(month, m, inp) for m in ("a", "b", "c")}
    return {"v3a": v3a(month, inp), "v3b": v3b(month, inp, members), "v1_c": members["c"]["yoy"]}


def conformal_half_width(abs_misses, alpha=ALPHA):
    """Split conformal: the ceil((n+1)(1-alpha))-th smallest absolute miss; None if that rank exceeds n."""
    xs = sorted(abs_misses)
    k = math.ceil((len(xs) + 1) * (1 - alpha))
    return xs[k - 1] if k <= len(xs) else None


def p_at_least(pred, half, threshold=THRESHOLD):
    return 1 - NormalDist(pred, half / Z90).cdf(threshold)


def calibration(inp, months=O.TEST_MONTHS):
    """Jan-Sep 2026: each method's prediction, miss and |miss| against the published YoY, and the half-width."""
    pub = inp["published"][O.HEADLINE]
    rows = {m: predict(m, inp) for m in months}
    out = {}
    for meth in METHODS:
        per = {m: {"pred": rows[m][meth]["yoy"], "official": pub[m], "miss": rows[m][meth]["yoy"] - pub[m]}
               for m in months}
        half = conformal_half_width([abs(r["miss"]) for r in per.values()])
        out[meth] = {"months": per, "half_width": half, "n": len(per),
                     "rank": math.ceil((len(per) + 1) * (1 - ALPHA)),
                     "mean_abs_miss": sum(abs(r["miss"]) for r in per.values()) / len(per)}
    out["v1_c"] = {m: rows[m]["v1_c"] for m in months}
    return out


def with_range(pred, half):
    if half is None:
        return {"yoy": pred, "range_low": None, "range_high": None, "half_width": None,
                "p_headline_ge_6": None, "note": "unbounded at 80% with this n"}
    return {"yoy": pred, "range_low": pred - half, "range_high": pred + half, "half_width": half,
            "width": 2 * half, "range_level": 1 - ALPHA, "p_headline_ge_6": p_at_least(pred, half)}
