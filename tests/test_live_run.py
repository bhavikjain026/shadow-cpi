"""'Run live' caps (shadow_cpi/live_run.py), with mocked calls only: no key, no network, no credit."""
import json
from datetime import datetime, timezone

import pytest

from shadow_cpi import live_run as L
from shadow_cpi.budget import load_budget

NOW = datetime(2026, 10, 22, 10, 0, tzinfo=timezone.utc)
REAL_USAGE = L.usage_remaining                 # kept before the fixture swaps in a fake
CFG = load_budget()


@pytest.fixture(autouse=True)
def switched_on_no_network(monkeypatch):
    """Gate tests run with the switch ON and a fake /usage (plenty left); no test may reach Tavily."""
    monkeypatch.setenv("RUN_LIVE_ENABLED", "1")
    monkeypatch.setattr(L, "usage_remaining", lambda key, fetch=None: (1000, ""))
    monkeypatch.setattr("shadow_cpi.tavily.Tavily.usage", lambda self, tag=None: pytest.fail("network call"))


def ledger(spent_total=0, live=0):
    out = [{"credits": spent_total, "budgets": ["x"]}]
    return out + ([{"credits": live, "budgets": ["run-now", "run-now-scan/2026-10-22#1"]}] if live else [])


def test_limits_are_the_owner_caps():
    lim = L.limits(CFG)
    assert (lim["per_session"], lim["per_day"], lim["credit_floor"], lim["usage_floor"]) == (3, 8, 100, 150)


def test_allowed_with_keys_and_room(tmp_path):
    assert L.gate(0, NOW, tmp_path / "runs.jsonl", CFG, ledger(500), have_keys=True) == (True, "")


def test_no_keys_never_runs(tmp_path):
    ok, msg = L.gate(0, NOW, tmp_path / "runs.jsonl", CFG, ledger(0), have_keys=False)
    assert not ok and "switched off" in msg


def test_session_cap_3(tmp_path):
    ok, msg = L.gate(3, NOW, tmp_path / "runs.jsonl", CFG, ledger(0), have_keys=True)
    assert not ok and "3 live runs" in msg
    assert L.gate(2, NOW, tmp_path / "runs.jsonl", CFG, ledger(0), have_keys=True)[0]


def test_day_cap_8_for_the_whole_app(tmp_path):
    p = tmp_path / "runs.jsonl"
    p.write_text("".join(json.dumps({"day": "2026-10-22", "n": i}) + "\n" for i in range(7)))
    assert L.gate(0, NOW, p, CFG, ledger(0), have_keys=True)[0]                 # 7 used: the 8th may run
    p.write_text(p.read_text() + json.dumps({"day": "2026-10-22", "n": 8}) + "\n"
                 + json.dumps({"day": "2026-10-21", "n": 1}) + "\n")
    ok, msg = L.gate(0, NOW, p, CFG, ledger(0), have_keys=True)
    assert not ok and "8 live runs" in msg
    assert L.gate(0, datetime(2026, 10, 23, tzinfo=timezone.utc), p, CFG, ledger(0), have_keys=True)[0]


def test_credit_floor_100(tmp_path):
    from shadow_cpi.budget import account_limit
    room = account_limit(CFG) - CFG["spent_before_ledger"] - 100 - 8   # balance minus one scan cap = exactly 100
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


def test_switch_off_by_default_makes_no_calls(tmp_path, monkeypatch):
    monkeypatch.delenv("RUN_LIVE_ENABLED")
    monkeypatch.setattr(L, "usage_remaining", lambda *a, **k: pytest.fail("no /usage call when off"))
    ok, msg = L.gate(0, NOW, tmp_path / "r", CFG, ledger(0), have_keys=True)
    assert not ok and msg == "Live runs open on 1 Dec (judging period). Showing the saved run."
    for v in ("0", "false", "off", ""):
        monkeypatch.setenv("RUN_LIVE_ENABLED", v)
        assert not L.enabled()
    for v in ("1", "true", "YES", "on"):
        monkeypatch.setenv("RUN_LIVE_ENABLED", v)
        assert L.enabled()


USAGE = {"key": {"usage": 596, "limit": None}, "account": {"current_plan": "x", "plan_usage": 596, "plan_limit": 1500,
                                                          "paygo_usage": 0, "paygo_limit": None}}


def test_usage_remaining_reads_account_limit_minus_usage():
    assert REAL_USAGE("k", fetch=lambda: USAGE) == (904, "")


@pytest.mark.parametrize("resp, why", [({"key": {"usage": 5, "limit": None}}, "no credit limit"),
                                       ({"account": {"plan_usage": 5, "plan_limit": None}}, "no credit limit"),
                                       ({}, "no credit limit"), (None, "no credit limit")])
def test_usage_without_a_limit_fails_closed(resp, why):
    remaining, msg = REAL_USAGE("k", fetch=lambda: resp)
    assert remaining is None and why in msg


def test_usage_call_failure_fails_closed():
    from shadow_cpi.http import ApiError

    def fail():
        raise ApiError(401, "unauthorised")
    remaining, msg = REAL_USAGE("k", fetch=fail)
    assert remaining is None and "failed (ApiError)" in msg


def test_gate_refuses_when_usage_fails_or_balance_low(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "usage_remaining", REAL_USAGE)              # real parsing; fetch is mocked below

    def timeout():
        raise TimeoutError()
    ok, msg = L.gate(0, NOW, tmp_path / "r", CFG, ledger(0), have_keys=True,
                     usage_fetch=timeout)
    assert not ok and "usage check failed (TimeoutError)" in msg
    ok, msg = L.gate(0, NOW, tmp_path / "r", CFG, ledger(0), have_keys=True, usage_fetch=lambda: {"key": {}})
    assert not ok and "no credit limit" in msg
    low = {"account": {"plan_limit": 1500, "plan_usage": 1351}}                # 149 left
    ok, msg = L.gate(0, NOW, tmp_path / "r", CFG, ledger(0), have_keys=True, usage_fetch=lambda: low)
    assert not ok and "fewer than 150 credits" in msg
    edge = {"account": {"plan_limit": 1500, "plan_usage": 1350}}               # exactly 150 left
    assert L.gate(0, NOW, tmp_path / "r", CFG, ledger(0), have_keys=True, usage_fetch=lambda: edge) == (True, "")


def test_ledger_check_still_applies_when_usage_is_fine(tmp_path):
    from shadow_cpi.budget import account_limit
    ok, msg = L.gate(0, NOW, tmp_path / "r", CFG, ledger(account_limit(CFG)), have_keys=True)
    assert not ok and "floor of 100" in msg


def test_tavily_usage_is_a_fresh_get_with_the_same_key(tmp_path, monkeypatch):
    monkeypatch.undo()                                       # the real Tavily.usage, with a fake transport
    from shadow_cpi.recorder import Recorder
    from shadow_cpi.tavily import Tavily
    sent = []

    def transport(method, url, token, body, timeout):
        sent.append((method, url, token, body))
        return USAGE
    t = Tavily(api_key="the-key", recorder=Recorder(tmp_path / "c", tmp_path / "log.jsonl"), transport=transport)
    assert t.usage() == USAGE and t.usage() == USAGE           # second call is sent again, not cached
    assert [s[:2] for s in sent] == [("GET", t.base + "/usage")] * 2 and all(s[2] == "the-key" for s in sent)
    assert all(s[3] is None for s in sent)


class FakeSecrets:
    def __init__(self, data, exists=True, boom=False):
        self.data, self.exists, self.boom, self.writes = data, exists, boom, 0

    def load_if_toml_exists(self):
        if self.boom:
            raise RuntimeError("bad secrets file")
        return self.exists

    def get(self, k):
        return self.data.get(k)


@pytest.fixture
def fake_secrets(monkeypatch):
    import streamlit.runtime.secrets as S

    def use(**kw):
        fake = FakeSecrets(**kw)
        monkeypatch.setattr(S, "secrets_singleton", fake)
        return fake
    return use


def test_setting_env_first_then_streamlit_secret(monkeypatch, fake_secrets):
    pytest.importorskip("streamlit")
    fake_secrets(data={"SCPI_TAVILY_API_KEY": "from-secrets", "RUN_LIVE_ENABLED": "1", "nested": {"a": 1}})
    monkeypatch.setenv("SCPI_TAVILY_API_KEY", "from-env")
    assert L.setting("SCPI_TAVILY_API_KEY") == "from-env"
    monkeypatch.delenv("SCPI_TAVILY_API_KEY")
    assert L.setting("SCPI_TAVILY_API_KEY") == "from-secrets"
    monkeypatch.delenv("RUN_LIVE_ENABLED")
    assert L.enabled()                                       # RUN_LIVE_ENABLED = "1" as a secret turns it on
    assert L.setting("nested") is None and L.setting("missing") is None


def test_setting_without_secrets_or_with_a_broken_store_is_none(monkeypatch, fake_secrets):
    pytest.importorskip("streamlit")
    for k in ("RUN_LIVE_ENABLED", *L.KEY_VARS):          # other tests may have loaded .env into the process
        monkeypatch.delenv(k, raising=False)
    fake_secrets(data={"RUN_LIVE_ENABLED": "1"}, exists=False)
    assert L.setting("RUN_LIVE_ENABLED") is None and not L.enabled()
    fake_secrets(data={}, boom=True)
    assert L.setting("RUN_LIVE_ENABLED") is None and L.keys() is None
