"""The arithmetic of Shadow CPI. Plain code, no AI.

Rules (from the maths review):
1. Combine index LEVELS with the official weights; never average percentage changes.
2. Year-on-year is computed only at the very end, at full precision (no rounding on the way).
3. A tracked item moves only its own weight; the rest of its subgroup ("residual") follows the trend.

Data shapes:
  series:  {code: {"YYYY-MM": index_level}}
  weights: {code: weight}  (any scale; normalised internally)
"""
from statistics import mean


# ---------- months ----------
def add_months(month, n):
    y, m = map(int, month.split("-"))
    k = y * 12 + (m - 1) + n
    return f"{k // 12:04d}-{k % 12 + 1:02d}"


def mom(series_code, month):
    """Month-on-month change of one series, or None if a level is missing."""
    a, b = series_code.get(month), series_code.get(add_months(month, -1))
    return None if a is None or b is None else a / b - 1


# ---------- aggregation ----------
def aggregate(levels, weights):
    """Weighted arithmetic mean of index levels (fixed-weight, Laspeyres-type)."""
    codes = [c for c in weights if c in levels]
    tw = sum(weights[c] for c in codes)
    if tw <= 0:
        raise ValueError("no weighted components available")
    return sum(weights[c] * levels[c] for c in codes) / tw


def yoy(level_now, level_12m_ago):
    return (level_now / level_12m_ago - 1) * 100


def residual_level(subgroup_level, subgroup_weight, item_levels, item_weights):
    """Index level of 'the rest of the subgroup' after carving out tracked items."""
    w_items = sum(item_weights.values())
    w_res = subgroup_weight - w_items
    if w_res <= 1e-12:
        return None, 0.0
    lvl = (subgroup_weight * subgroup_level - sum(item_weights[i] * item_levels[i] for i in item_weights)) / w_res
    return lvl, w_res


def build_components(month, series, subgroup_weights, item_weights_by_subgroup):
    """For a month, return {component_code: (level, weight)} where tracked items are separate components
    and each subgroup keeps only its residual weight. item_weights_by_subgroup: {subgroup: {item: weight}}."""
    comps = {}
    for sg, w_sg in subgroup_weights.items():
        lvl_sg = series.get(sg, {}).get(month)
        if lvl_sg is None:
            continue
        items = {i: w for i, w in item_weights_by_subgroup.get(sg, {}).items()
                 if series.get(i, {}).get(month) is not None}
        if items:
            item_lvls = {i: series[i][month] for i in items}
            res_lvl, w_res = residual_level(lvl_sg, w_sg, item_lvls, items)
            for i, w in items.items():
                comps[i] = (item_lvls[i], w)
            if res_lvl is not None:
                comps[sg + "#residual"] = (res_lvl, w_res)
        else:
            comps[sg] = (lvl_sg, w_sg)
    return comps


def predict_headline(prev_components, changes, trend_changes):
    """prev_components: {code: (level_last_month, weight)}.
    changes: {code: predicted change} from evidence (spine / Tavily), e.g. 0.04.
    trend_changes: {code: change} fallback for anything without evidence.
    Returns (predicted_headline_level, {code: (predicted_level, weight, source)})."""
    out = {}
    for code, (lvl, w) in prev_components.items():
        base = code.split("#")[0]
        if code in changes and changes[code] is not None:
            ch, src = changes[code], "observed"
        else:
            ch = trend_changes.get(code, trend_changes.get(base, 0.0)) or 0.0
            src = "carried"
        out[code] = (lvl * (1 + ch), w, src)
    head = aggregate({c: v[0] for c, v in out.items()}, {c: v[1] for c, v in out.items()})
    return head, out


def coverage(pred_components):
    """Share of total weight that is observed vs carried."""
    tw = sum(v[1] for v in pred_components.values())
    obs = sum(v[1] for v in pred_components.values() if v[2] == "observed")
    return {"observed": obs / tw, "carried": 1 - obs / tw}


def contributions_yoy(levels_now, levels_12m, weights):
    """Percentage-point contribution of each component to headline YoY inflation.
    contribution_i = w_i * (I_i,now - I_i,12m) / sum_j(w_j * I_j,12m) * 100. Sums to headline YoY."""
    codes = [c for c in weights if c in levels_now and c in levels_12m]
    denom = sum(weights[c] * levels_12m[c] for c in codes)
    return {c: weights[c] * (levels_now[c] - levels_12m[c]) / denom * 100 for c in codes}


# ---------- baselines ----------
def b1_last_yoy(headline_series, month):
    """B1: repeat last month's YoY."""
    prev = add_months(month, -1)
    return yoy(headline_series[prev], headline_series[add_months(prev, -12)])


def trend_change(series_code, month, seasonal_weight=0.5, base_year="2025"):
    """B2 trend for one component: average MoM of the last 3 months + 0.5 x (same month last year's MoM
    minus the base year's average MoM). The 0.5 is fixed in advance, never tuned on test months."""
    last3 = [mom(series_code, add_months(month, -k)) for k in (1, 2, 3)]
    last3 = [x for x in last3 if x is not None]
    if not last3:
        return 0.0
    drift = mean(last3)
    m12 = mom(series_code, add_months(month, -12))
    base = [mom(series_code, f"{base_year}-{mm:02d}") for mm in range(1, 13)]
    base = [x for x in base if x is not None]
    if m12 is None or not base:
        return drift
    return drift + seasonal_weight * (m12 - mean(base))
