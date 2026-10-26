"""The CPI needle for the Live build page. Uses v1's frozen maths (shadow_cpi.cpi_math, official 2024 weights) without
changing it: index levels combined with the weights, year-on-year last, each carved item moving only its own weight.

changes = {cpi_code: (mode, value)}: mode 'level' replaces the item's trend with the measured change (spine and
official series, as v1 model (c)); mode 'add' adds the change to the item's own trend (announced price changes)."""
from shadow_cpi import cpi_math as M
from shadow_cpi import official as O
from shadow_cpi import predict as P


def yoy(month, changes, inp):
    """CPI year-on-year for `month` with the items in `changes` carved out; everything else on trend."""
    s, w = inp["series"], inp["weights"]
    prev = M.add_months(month, -1)
    hist = lambda code: {k: v for k, v in s[code].items() if k <= prev}      # noqa: E731 - nothing from `month` on
    groups = O.codes_at("group", w)
    carved = {}
    for code in changes:
        carved.setdefault(O.parent_code(code, "group"), {})[code] = w[code]
    comps_prev = M.build_components(prev, s, {g: w[g] for g in groups}, carved)
    trend = {g: M.trend_change(hist(g), month) for g in groups}
    trend.update({c: M.trend_change(hist(c), month) for c in changes})
    moved = {c: (v if mode == "level" else trend[c] + v) for c, (mode, v) in changes.items()}
    head, _ = M.predict_headline(comps_prev, moved, trend)
    level0 = M.aggregate({c: v[0] for c, v in comps_prev.items()}, {c: v[1] for c, v in comps_prev.items()})
    return M.yoy(s[O.HEADLINE][prev] * head / level0, s[O.HEADLINE][M.add_months(month, -12)])


def path(month, steps, inp=None):
    """Needle after each step. steps: [(cpi_code, mode, value)] in the order evidence arrives. Returns
    (start, [yoy after step 1, after step 2, ...]); start = every item on trend (v1 'trend only')."""
    inp = inp or P.load_inputs()
    start = P.predict_month(month, "a", inp)["yoy"]
    changes, out = {}, []
    for code, mode, value in steps:
        changes[code] = (mode, value)
        out.append(yoy(month, dict(changes), inp))
    return start, out


def jumps(month, steps, inp=None):
    """Display only (docs/after_scoring_changes.md, 2026-10-27): each step's jump, in pp = needle(steps 1..k) -
    needle(steps 1..k-1 with item k carved out on its own trend, no change). A step whose evidence equals the item's
    own trend jumps exactly 0. The jumps do not sum to end - start: the rest is carving items out of their groups
    (each measured item follows its own trend, not its group's), shown separately. Changes no needle value."""
    inp = inp or P.load_inputs()
    changes, out = {}, []
    for code, mode, value in steps:
        base = yoy(month, {**changes, code: ("add", 0.0)}, inp)
        changes[code] = (mode, value)
        out.append(yoy(month, dict(changes), inp) - base)
    return out


def trend_only(month, inp=None):
    """v1 model (a), 'trend only', for reference."""
    return P.predict_month(month, "a", inp or P.load_inputs())["yoy"]
