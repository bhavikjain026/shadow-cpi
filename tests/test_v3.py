"""v3 (v3/PREREG.md): the two methods, the conformal range, the v1 input checks and the bundle seal.
Offline: saved inputs and throwaway git repos only. No API calls."""
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

import seal_month as SM
from shadow_cpi import official as O
from shadow_cpi import predict as P
from shadow_cpi import seal as S
from v3 import build as B
from v3 import model as V
from v3 import seal_bundle as SB

ROOT = Path(__file__).resolve().parent.parent
MONTH = "2026-10"
BEFORE = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def inp():
    return P.load_inputs()


# ---------- model ----------
def test_tier_weights_are_the_preregistered_ones():
    assert V.W == {"verified": 1.0, "corroborated": 0.7, "single source": 0.4}
    assert V.tier({"confirmed_by_2_sources": True}) == "corroborated"
    assert V.tier({"confirmed_by_2_sources": False}) == "single source"
    assert V.tier({}) == "single source"


def test_v3a_with_every_weight_one_is_v1_c(inp, monkeypatch):
    monkeypatch.setattr(V, "W", {k: 1.0 for k in V.W})
    for m in O.TEST_MONTHS:
        assert V.v3a(m, inp)["yoy"] == P.predict_month(m, "c", inp)["yoy"]


def test_v3a_scales_only_event_changes_and_leaves_inputs_alone(inp):
    before = json.dumps(inp["events"], sort_keys=True)
    m = "2026-09"                                         # one corroborated electricity event
    w = V.weighted_inputs(m, inp)
    (e,) = w["events"][m]
    (orig,) = inp["events"][m]
    assert e["v3_w"] == 0.7 and e["applied_change"] == pytest.approx(0.7 * orig["applied_change"])
    assert json.dumps(inp["events"], sort_keys=True) == before
    assert V.v3a("2026-01", inp)["yoy"] == P.predict_month("2026-01", "c", inp)["yoy"]   # no events: same as v1


def test_v3b_is_equal_weight_average_of_a_b_c(inp):
    m = "2026-05"
    got = V.v3b(m, inp)
    ys = [P.predict_month(m, k, inp)["yoy"] for k in ("a", "b", "c")]
    assert got["yoy"] == pytest.approx(sum(ys) / 3, abs=1e-12)


def test_v1_c_reproduces_scored_replay(inp):
    saved = json.loads((ROOT / "results" / "replay_predictions.json").read_text())
    cal = V.calibration(inp)
    assert cal["v1_c"] == {m: saved[m]["c"]["yoy"] for m in O.TEST_MONTHS}


def test_conformal_rank_and_unbounded():
    assert V.conformal_half_width(range(1, 10)) == 8           # n=9: ceil(10*0.8) = 8th smallest
    assert V.conformal_half_width([0.1, 0.2, 0.3]) is None      # n=3: rank 4 > n
    assert V.with_range(5.0, None)["range_low"] is None


def test_range_and_probability():
    r = V.with_range(5.5, 0.3)
    assert (r["range_low"], r["range_high"]) == pytest.approx((5.2, 5.8))
    assert V.p_at_least(6.0, 0.3) == pytest.approx(0.5)
    assert V.p_at_least(5.7, 0.3) == pytest.approx(0.1)       # 6.0 is the top of the 80% range


def test_retrospective_file_matches_code(inp):
    saved = json.loads((ROOT / "results" / "v3_retrospective.json").read_text())
    fresh = B.build_retro(inp)
    assert saved["label"] == "retrospective, not a test"
    for m in V.METHODS:
        assert saved["methods"][m]["half_width"] == fresh["methods"][m]["half_width"]


# ---------- throwaway repo: v1 sealed for real, then v3 ----------
def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    for f in ("data/cpi_tidy.csv", "config/models.json", "data/official_releases.csv"):
        (r / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / f, r / f)
    (r / SM.WEIGHTS_FILE).parent.mkdir(parents=True, exist_ok=True)
    (r / SM.WEIGHTS_FILE).write_bytes(b"fake weights file")
    (r / "manifests").mkdir()
    (r / "manifests" / f"{MONTH}.json").write_text('{"month": "2026-10"}', encoding="utf-8")
    (r / "results").mkdir()
    pred = {"target_month": MONTH, "headline_yoy": 5.31, "range_low": 5.0, "range_high": 5.6,
            "evidence_cutoff_utc": "2026-10-15T18:29:00+00:00"}   # past, so v1 seals
    (r / "results" / f"nowcast_{MONTH}.json").write_text(json.dumps(pred), encoding="utf-8")
    (r / "code.py").write_text("x = 1\n")
    git(r, "init", "-q")
    git(r, "config", "user.email", "test@example.com")
    git(r, "config", "user.name", "Test")
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", "fixture")
    SM.run(MONTH, root=r, out=lambda *_: None)                   # real v1 seal: commit + tag (push fails, no remote)
    return r


def fake_v3(repo, v1c=5.31):
    """A v3 file built by build_live with a fake gather, in the throwaway repo."""
    def gather(month, cutoff):
        return {}, []
    pred = {"v3a": {"yoy": 5.2, "events": []}, "v3b": {"yoy": 5.25, "members": {}}, "v1_c": v1c}
    retro = {"methods": {m: {"half_width": 0.3, "months": {"x": {"miss": 0.3}}} for m in V.METHODS}}
    orig = V.predict
    V.predict = lambda month, inp: pred
    try:
        out = B.build_live(MONTH, "2026-10-15", repo / "sealed" / f"{MONTH}.json", gather=gather, retro=retro,
                           root=repo)
    finally:
        V.predict = orig
    (repo / "results" / f"v3_nowcast_{MONTH}.json").write_text(json.dumps(out), encoding="utf-8")
    return out


def test_build_live_checks_inputs_against_v1_seal(repo):
    out = fake_v3(repo)
    assert out["inputs_match_v1"]["all_match"] and out["v3a"]["range_low"] == pytest.approx(4.9)
    with pytest.raises(B.Refuse, match="inputs differ"):
        fake_v3(repo, v1c=5.32)
    (repo / "manifests" / f"{MONTH}.json").write_text('{"month": "2026-10", "edited": 1}')
    with pytest.raises(B.Refuse, match="SHA-256"):
        fake_v3(repo)


def test_build_live_refuses_after_code_change(repo):
    (repo / "code.py").write_text("x = 2\n")
    git(repo, "commit", "-qam", "change code")
    with pytest.raises(B.Refuse, match="code changed"):
        fake_v3(repo)


def test_bundle_dry_run_then_real_seal(repo):
    fake_v3(repo)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "v3 file")
    with pytest.raises(SB.Refuse, match="v1 seal not found"):
        SB.run(MONTH, dry_run=True, root=repo, now=BEFORE, out=lambda *_: None)   # no v1 dry-run seal there
    digest = SB.run(MONTH, root=repo, now=BEFORE, out=lambda *_: None)
    assert SB.verify(MONTH, repo / "sealed")
    assert git(repo, "tag", "--list", f"seal-{MONTH}-bundle") and git(repo, "tag", "--list", f"seal-{MONTH}")
    assert S.verify(MONTH, repo / "sealed")                       # v1's own seal still verifies, untouched
    lines = (repo / "sealed" / f"{MONTH}.bundle.sha256").read_text().splitlines()
    assert [l.split("  ")[1] for l in lines] == [f"{MONTH}.json", f"{MONTH}.sha256", f"{MONTH}.v3.json"]
    assert len(digest) == 64
    with pytest.raises(SB.Refuse, match="never redone"):
        SB.run(MONTH, root=repo, now=BEFORE, out=lambda *_: None)
    (repo / "sealed" / f"{MONTH}.v3.json").write_text("{}")
    assert not SB.verify(MONTH, repo / "sealed")


def test_bundle_refuses_late_or_unmatched(repo):
    fake_v3(repo)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "v3 file")
    late = datetime(2026, 10, 29, 18, 30, tzinfo=timezone.utc)   # 00:00 IST on the 30th
    with pytest.raises(SB.Refuse, match="deadline"):
        SB.run(MONTH, root=repo, now=late, out=lambda *_: None)
    v3 = json.loads((repo / "results" / f"v3_nowcast_{MONTH}.json").read_text())
    v3["inputs_match_v1"]["v1_seal_sha256"] = "0" * 64
    (repo / "results" / f"v3_nowcast_{MONTH}.json").write_text(json.dumps(v3))
    git(repo, "commit", "-qam", "tamper")
    with pytest.raises(SB.Refuse, match="not built against this v1 seal"):
        SB.run(MONTH, root=repo, now=BEFORE, out=lambda *_: None)
