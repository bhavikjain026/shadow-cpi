"""The app's file readers match the real formats (baselines.csv, flight recorder log, seals)."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from app_pages import common as C  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def sample_data(monkeypatch):
    monkeypatch.delenv("SHADOW_CPI_DATA_DIR", raising=False)


def test_default_is_sample_and_switches_to_real(monkeypatch):
    assert C.is_sample()
    assert C.tag("x") == "x (SAMPLE)"
    monkeypatch.setenv("SHADOW_CPI_DATA_DIR", ".")
    assert C.data_dir() == ROOT
    assert not C.is_sample()
    assert C.tag("x") == "x"


def test_sample_baselines_have_real_columns():
    real = (ROOT / "results" / "baselines.csv").read_text(encoding="utf-8").splitlines()[0]
    sample = (C.SAMPLE_DIR / "results" / "baselines.csv").read_text(encoding="utf-8").splitlines()[0]
    assert sample == real


def test_sample_log_uses_recorder_keys():
    keys = {"id", "time", "service", "endpoint", "params", "cached", "latency_ms", "parent", "tag", "cache_key"}
    log = C.read_log()
    assert log and all(keys <= set(e) for e in log)
    expected = sum(e.get("credits") or 0 for e in log if e["service"] == "tavily" and not e["cached"])
    assert C.tavily_credits(log) == expected


def test_seals_verify_like_shadow_cpi_seal():
    from shadow_cpi import seal as S
    for m in C.months_with("sealed"):
        assert C.seal_status(m)[2]
        assert S.verify(m, seal_dir=C.SAMPLE_DIR / "sealed")


def test_seal_detects_tampering(tmp_path, monkeypatch):
    (tmp_path / "sealed").mkdir()
    for f in ("2026-10.json", "2026-10.sha256"):
        (tmp_path / "sealed" / f).write_bytes((C.SAMPLE_DIR / "sealed" / f).read_bytes())
    monkeypatch.setenv("SHADOW_CPI_DATA_DIR", str(tmp_path))
    assert C.seal_status("2026-10")[2]
    p = tmp_path / "sealed" / "2026-10.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    d["headline_yoy"] = 4.0
    p.write_text(json.dumps(d), encoding="utf-8")
    assert not C.seal_status("2026-10")[2]


def test_missing_files_return_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("SHADOW_CPI_DATA_DIR", str(tmp_path))
    assert C.read_json("results/nowcast_latest.json") is None
    assert C.read_csv("results/replay.csv") == []
    assert C.read_log() == []
    assert C.months_with("sealed") == []


def test_next_release_rolls_to_working_day():
    r = C.next_release(datetime(2026, 10, 20, tzinfo=timezone.utc))
    assert r["month"] == "2026-10" and r["likely"].isoformat() == "2026-11-12"
    r = C.next_release(datetime(2026, 11, 13, tzinfo=timezone.utc))
    assert r["month"] == "2026-11" and r["likely"].isoformat() == "2026-12-14"
    assert C.next_release(datetime(2026, 12, 15, tzinfo=timezone.utc)) is None
