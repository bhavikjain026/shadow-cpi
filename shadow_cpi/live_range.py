"""Amendment 2 (after scoring, live months only): the 80% range and P(headline >= 6.0%) for October and November 2026.
Plain code, no AI. See docs/frozen_rules.md (Amendment 2) and docs/after_scoring_changes.md.

The scored Jan-Sep results, and their leave-one-out ranges (5 of 9 inside), are not touched by this module.

- half-width = 80th percentile (linear interpolation) of |miss| over the 9 scored out-of-sample misses of (c);
- floor: the range is never narrower than the pre-registered one (q10/q90 of all 9 signed misses);
- range = prediction +/- half-width (symmetric);
- P(headline >= 6.0%) from the normal distribution whose central 80% is that range (sigma = half-width / z_0.90).
"""
import json
from statistics import NormalDist

from .settings import ROOT

LIVE_MONTHS = ("2026-10", "2026-11")
THRESHOLD = 6.0          # RBI's Q3 projection (owner, 2026-10-21)
Z90 = NormalDist().inv_cdf(0.90)


def percentile(xs, q):
    """Linear interpolation, as tools/score_replay.percentile (the pre-registered method)."""
    xs = sorted(xs)
    k = (len(xs) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def scored_misses(published, test_months):
    """{month: (c) prediction - published YoY} from the scored run (results/replay_predictions.json), unrounded."""
    preds = json.loads((ROOT / "results" / "replay_predictions.json").read_text())
    return {m: preds[m]["c"]["yoy"] - published[m] for m in test_months}


def live_range(pred, misses, skeptic_contrary=0):
    """Amendment 2 range for a live month. misses: the 9 scored misses of (c)."""
    vals = list(misses)
    q10, q90 = percentile(vals, 0.10), percentile(vals, 0.90)
    old_low, old_high = pred - q90, pred - q10
    half = percentile([abs(v) for v in vals], 0.80)
    floored = 2 * half < old_high - old_low
    if floored:
        half = (old_high - old_low) / 2
    if skeptic_contrary >= 2:                     # pre-registered skeptic rule, unchanged
        half *= 1.5
    sigma = half / Z90
    return {"low": pred - half, "high": pred + half, "half_width": half, "width": 2 * half,
            "method": "Amendment 2: prediction +/- 80th percentile of |miss| of (c) over the 9 scored months, "
                      "floor = pre-registered width",
            "floor_applied": floored, "skeptic_widened": skeptic_contrary >= 2,
            "preregistered_range": {"low": old_low, "high": old_high, "width": old_high - old_low},
            "p_headline_ge_6": 1 - NormalDist(pred, sigma).cdf(THRESHOLD),
            "p_method": f"normal with mean = prediction and sigma = half-width / {Z90:.4f} (its central 80% = the "
                        "range); threshold 6.0% = RBI's Q3 projection"}
