"""The app's file readers and the committed app snapshots (results/app/) match the real formats."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from app_pages import common as C  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def test_reads_the_repository_files():
    assert C.path("results/score_lock.json") == ROOT / "results" / "score_lock.json"
    assert C.read_json("results/score_lock.json")["mae"]


def test_flight_snapshot_keeps_recorder_keys_and_credits():
    log = C.read_log()
    keys = {"id", "time", "service", "endpoint", "params", "cached", "latency_ms", "parent", "tag"}
    assert log and all(keys <= set(e) for e in log)
    expected = sum(e.get("credits") or 0 for e in log if e["service"] == "tavily" and not e["cached"])
    assert C.tavily_credits(log) == expected


def test_audit_summary_matches_audit_files():
    a = C.read_json("results/app/audit_summary.json")
    assert a["events_checked"] == len(C.read_csv("audit/event_audit.csv"))
    assert (a["found_directly"], a["found_incl_official_series"], a["reference_changes"]) == (9, 14, 29)
    assert a["events_after_fixes"] == sum(len(json.loads(p.read_text())["events"])
                                          for p in (ROOT / "manifests").glob("2026-0*.json"))


def test_saved_run_is_the_latest_manifest():
    s = C.read_json("results/app/saved_run.json")
    man = json.loads((ROOT / "manifests" / f"{s['month']}.json").read_text())
    assert s["events"] == man["events"] and s["label"].startswith("Saved run")


def test_seal_detects_tampering(tmp_path, monkeypatch):
    from shadow_cpi import seal as S
    (tmp_path / "sealed").mkdir()
    payload = {"headline_yoy": 5.0, "range_low": 4.7, "range_high": 5.3}
    S.seal("2026-10", payload, seal_dir=tmp_path / "sealed")
    monkeypatch.setattr(C, "ROOT", tmp_path)
    assert C.seal_status("2026-10")[2]
    p = tmp_path / "sealed" / "2026-10.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    d["headline_yoy"] = 4.0
    p.write_text(json.dumps(d), encoding="utf-8")
    assert not C.seal_status("2026-10")[2]


def test_missing_files_return_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "ROOT", tmp_path)
    assert C.read_json("results/nowcast_latest.json") is None
    assert C.read_csv("results/replay.csv") == []
    assert C.read_log() == []
    assert C.months_with("sealed") == []


def test_next_release_rolls_to_working_day():
    r = C.next_release(datetime(2026, 10, 20, tzinfo=timezone.utc))
    assert r["month"] == "2026-10" and r["likely"].isoformat() == "2026-11-12"
    assert r["at"].hour == 16                                       # 4:00 PM IST
    r = C.next_release(datetime(2026, 11, 13, tzinfo=timezone.utc))
    assert r["month"] == "2026-11" and r["likely"].isoformat() == "2026-12-14"
    assert C.next_release(datetime(2026, 12, 15, tzinfo=timezone.utc)) is None
