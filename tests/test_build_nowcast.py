"""build_nowcast.py (the October builder) and Amendment 2 (shadow_cpi/live_range.py)."""
import json

import pytest

from shadow_cpi import live_range as L
from shadow_cpi import predict as P
from shadow_cpi.settings import ROOT

CACHED = (ROOT / "cache" / "tavily").exists() and (ROOT / "logs" / "flight_recorder.jsonl").exists()
SCORED = json.loads((ROOT / "results" / "replay_predictions.json").read_text())


@pytest.mark.skipif(not CACHED, reason="needs the local Tavily cache (git-ignored)")
def test_builder_reproduces_scored_march_exactly():
    import build_nowcast as B
    out = B.build("2026-03", "2026-03-31", cache_only=True)
    assert out["headline_yoy"] == SCORED["2026-03"]["c"]["yoy"]          # exact, no tolerance


@pytest.mark.skipif(not CACHED, reason="needs the local Tavily cache (git-ignored)")
def test_builder_calls_the_scored_predictor(monkeypatch):
    import build_nowcast as B
    calls = []
    real = P.predict_month
    monkeypatch.setattr(P, "predict_month", lambda m, mod, inp: calls.append((m, mod)) or real(m, mod, inp))
    B.build("2026-03", "2026-03-31", cache_only=True)
    assert ("2026-03", "c") in calls


def test_builder_refuses_live_run_on_a_test_month():
    import build_nowcast as B
    with pytest.raises(SystemExit):
        B.build("2026-03", "2026-03-31", cache_only=False)


def test_percentile_matches_the_preregistered_one():
    from tools.score_replay import percentile
    xs = [-0.38, -0.31, -0.2, -0.19, -0.17, -0.02, -0.01, 0.11, 0.26]
    for q in (0.1, 0.8, 0.9):
        assert L.percentile(xs, q) == percentile(xs, q)


def test_live_range_symmetric_80th_percentile_of_abs_miss():
    misses = [-0.38, -0.31, -0.2, -0.19, -0.17, -0.02, -0.01, 0.11, 0.26]
    r = L.live_range(5.0, misses)
    half = L.percentile([abs(m) for m in misses], 0.8)
    assert r["low"] == pytest.approx(5.0 - half) and r["high"] == pytest.approx(5.0 + half)
    assert not r["floor_applied"]
    assert r["p_headline_ge_6"] < 0.01 and L.live_range(6.0, misses)["p_headline_ge_6"] == pytest.approx(0.5)


def test_live_range_floor_is_the_preregistered_width():
    misses = [-0.5, -0.5, -0.1, 0.0, 0.1, 0.1, 0.2, 0.7, 0.9]    # 2 x p80 |miss| < q90 - q10
    r = L.live_range(5.0, misses)
    assert r["floor_applied"]
    assert r["width"] == pytest.approx(r["preregistered_range"]["width"])


def test_live_range_skeptic_widens_50_percent():
    misses = [-0.38, -0.31, -0.2, -0.19, -0.17, -0.02, -0.01, 0.11, 0.26]
    assert L.live_range(5.0, misses, 2)["half_width"] == pytest.approx(1.5 * L.live_range(5.0, misses)["half_width"])
