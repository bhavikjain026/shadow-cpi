"""The CPI needle for the Live build page: 'trend only' for the month, then the same with one verified item carved
out and moved by its evidence. Uses v1's frozen maths (shadow_cpi.cpi_math, official weights) without changing it:
index levels combined with the 2024-series weights, year-on-year last, the item moving only its own weight."""
from shadow_cpi import cpi_math as M
from shadow_cpi import official as O
from shadow_cpi import predict as P
from shadow_cpi.event_rules import state_share


def _yoy(month, cpi_code, applied, inp):
    s, w = inp["series"], inp["weights"]
    prev = M.add_months(month, -1)
    hist = lambda code: {k: v for k, v in s[code].items() if k <= prev}      # noqa: E731 - nothing from `month` on
    groups = O.codes_at("group", w)
    carved = {O.parent_code(cpi_code, "group"): {cpi_code: w[cpi_code]}}
    comps_prev = M.build_components(prev, s, {g: w[g] for g in groups}, carved)
    trend = {g: M.trend_change(hist(g), month) for g in groups}
    trend[cpi_code] = M.trend_change(hist(cpi_code), month)
    head, _ = M.predict_headline(comps_prev, {cpi_code: trend[cpi_code] + applied}, trend)
    level0 = M.aggregate({c: v[0] for c, v in comps_prev.items()}, {c: v[1] for c, v in comps_prev.items()})
    return M.yoy(s[O.HEADLINE][prev] * head / level0, s[O.HEADLINE][M.add_months(month, -12)])


def needle(month, cpi_code, change, share_of_month, state, inp=None):
    """(before, after, applied): CPI year-on-year with the item carved out on its own trend, then with the verified
    change added. applied = change x share of the month x the state's share of the item's all-India weight
    (official Annex 5.3d). The difference between the two is the evidence's effect alone."""
    inp = inp or P.load_inputs()
    applied = change * share_of_month * state_share(cpi_code, {state})
    return _yoy(month, cpi_code, 0.0, inp), _yoy(month, cpi_code, applied, inp), applied


def trend_only(month, inp=None):
    """v1 model (a), 'trend only', for reference."""
    return P.predict_month(month, "a", inp or P.load_inputs())["yoy"]
