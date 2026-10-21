"""'Run live' caps (shadow_cpi/live_run.py), with mocked calls only: no key, no network, no credit."""
import json
from datetime import datetime, timezone

import pytest

from shadow_cpi import live_run as L
from shadow_cpi.budget import load_budget

NOW = datetime(2026, 10, 22, 10, 0, tzinfo=timezone.utc)
CFG = load_budget()


def ledger(spent_total=0, live=0):
    out = [{"credits": spent_total, "budgets": ["x"]}]
    return out + ([{"credits": live, "budgets": ["run-now", "run-now-scan/2026-10-22#1"]}] if live else [])


def test_limits_are_the_owner_caps():
    assert (L.limits(CFG)["per_session"], L.limits(CFG)["per_day"], L.limits(CFG)["credit_floor"]) == (3, 15, 100)


def test_allowed_with_keys_and_room(tmp_path):
    assert L.gate(0, NOW, tmp_path / "runs.jsonl", CFG, ledger(500), have_keys=True) == (True, "")


def test_no_keys_never_runs(tmp_path):
    ok, msg = L.gate(0, NOW, tmp_path / "runs.jsonl", CFG, ledger(0), have_keys=False)
    assert not ok and "switched off" in msg


def test_session_cap_3(tmp_path):
    ok, msg = L.gate(3, NOW, tmp_path / "runs.jsonl", CFG, ledger(0), have_keys=True)
    assert not ok and "3 live runs" in msg
    assert L.gate(2, NOW, tmp_path / "runs.jsonl", CFG, ledger(0), have_keys=True)[0]


def test_day_cap_15_for_the_whole_app(tmp_path):
    p = tmp_path / "runs.jsonl"
    p.write_text("".join(json.dumps({"day": "2026-10-22", "n": i}) + "\n" for i in range(15))
                 + json.dumps({"day": "2026-10-21", "n": 1}) + "\n")
    ok, msg = L.gate(0, NOW, p, CFG, ledger(0), have_keys=True)
    assert not ok and "15 live runs" in msg
    assert L.gate(0, datetime(2026, 10, 23, tzinfo=timezone.utc), p, CFG, ledger(0), have_keys=True)[0]


def test_credit_floor_100(tmp_path):
    room = CFG["plan_limit"] - CFG["spent_before_ledger"] - 100 - 8   # balance minus one scan cap = exactly 100
    assert L.gate(0, NOW, tmp_path / "r", CFG, ledger(room), have_keys=True)[0]
    ok, msg = L.gate(0, NOW, tmp_path / "r", CFG, ledger(room + 1), have_keys=True)
    assert not ok and "floor of 100" in msg


def test_total_live_budget(tmp_path):
    ok, msg = L.gate(0, NOW, tmp_path / "r", CFG, ledger(0, live=115), have_keys=True)
    assert not ok and "live-run credit budget" in msg


def test_keys_only_from_environment(monkeypatch):
    for k in L.KEY_VARS:
        monkeypatch.delenv(k, raising=False)
    assert L.keys() is None
    monkeypatch.setenv("SCPI_TAVILY_API_KEY", "a")
    monkeypatch.setenv("SCPI_NEBIUS_API_KEY", "b")
    assert L.keys() == ("a", "b")


def test_run_live_with_mocked_calls_records_run_and_stays_in_window(tmp_path, monkeypatch):
    from shadow_cpi import evidence as E
    from shadow_cpi import recorder as R
    seen = []

    def fake_fetch(tav, nem, query, lang, start, end, job, stats, drop, seen_set):
        seen.append((start, end, job, lang))
        yield {"url": "https://example.in/a"}, "2026-10-20", "url", "Line one.\nAmul milk up Rs 2 across the country", "e1"
    monkeypatch.setattr(E, "fetch_pages", fake_fetch)
    monkeypatch.setattr("shadow_cpi.nemotron.Nemotron.price_events", lambda self, m, t, **k: ([], "n1"))
    monkeypatch.setattr(R, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(R, "LOG_FILE", tmp_path / "log.jsonl")
    monkeypatch.setattr(R.Recorder.__init__, "__defaults__", (tmp_path / "cache", tmp_path / "log.jsonl", True))
    out = L.run_live("t", "n", now=NOW, path=tmp_path / "runs.jsonl", cfg=CFG)
    assert L.runs_on("2026-10-22", tmp_path / "runs.jsonl") == 1
    assert seen and all(s == ("2026-10-15", "2026-10-22") for s, *_ in [(x[:2], x) for x in seen])
    assert all(lang == "en" for *_, lang in seen)
    assert out["live"] and out["events"] == [] and out["receipt"]["credits"] == 0
