"""Account limit = plan + add-on credits; the reserve is kept for the seal runs (config/budget.json)."""
import json

import pytest

from shadow_cpi.budget import BudgetExceeded, Budgeted, account_limit, load_budget


class FakeTavily:
    rec = None


def cfg(**kw):
    return {"plan_limit": 1000, "addon_credits": 3125, "reserve": 150, "reserve_for": ["live-month", "skeptic"],
            "spent_before_ledger": 0, "caps": {"live-month": 120, "skeptic": 48, "prompt-t": 90}, **kw}


def write_ledger(path, total):
    path.write_text(json.dumps({"time": "t", "call_id": "x", "endpoint": "/search", "credits": total,
                                "budgets": ["other"]}) + "\n")


def test_account_limit_includes_addon_credits():
    assert account_limit(cfg()) == 4125
    assert account_limit({"plan_limit": 100}) == 100


def test_real_config_matches_the_billing_page():
    c = load_budget()
    assert (c["plan_limit"], c["addon_credits"], c["reserve"]) == (1000, 3125, 150)   # lower figure (/usage)
    assert {"live-month", "nov-interim-scan", "skeptic"} <= set(c["reserve_for"])


def test_reserve_blocks_other_budgets_but_not_the_seal(tmp_path):
    led = tmp_path / "ledger.jsonl"
    write_ledger(led, 4125 - 150)                         # exactly the reserve left
    other = Budgeted(FakeTavily(), ["prompt-t"], cfg=cfg(), ledger_path=led)
    with pytest.raises(BudgetExceeded):
        other.check(1)
    Budgeted(FakeTavily(), ["live-month", "live-month/2026-10"], cfg=cfg(), ledger_path=led).check(1)
    Budgeted(FakeTavily(), ["skeptic", "skeptic/2026-10"], cfg=cfg(), ledger_path=led).check(1)


def test_nothing_past_the_account_limit_even_for_the_seal(tmp_path):
    led = tmp_path / "ledger.jsonl"
    write_ledger(led, 4125)
    with pytest.raises(BudgetExceeded):
        Budgeted(FakeTavily(), ["live-month"], cfg=cfg(), ledger_path=led).check(1)


def test_ledger_reconciles_to_the_billing_page():
    from shadow_cpi.budget import account_spent, read_ledger
    led = read_ledger()
    i = next(k for k, e in enumerate(led) if e["call_id"] == "reconcile-2026-10-22")
    assert account_spent(load_budget(), led[:i + 1]) == 681                  # matches the billing page that day


def test_credit_ledger_rows_carry_request_id_and_response_sha256(tmp_path):
    from shadow_cpi.recorder import Recorder, response_sha256
    from shadow_cpi.tavily import Tavily
    resp = {"request_id": "req-1", "results": [], "usage": {"credits": 1}}
    tav = Tavily(api_key="test", recorder=Recorder(cache_dir=tmp_path / "c", log_file=tmp_path / "l.jsonl"),
                 transport=lambda *a: resp)
    led = tmp_path / "ledger.jsonl"
    Budgeted(tav, ["prompt-t"], cfg=cfg(), ledger_path=led).search("q")
    row = json.loads(led.read_text())
    assert row["request_id"] == "req-1" and row["response_sha256"] == response_sha256(resp)


def test_usage_check_warns_only_above_ledger_plus_slack(tmp_path):
    from shadow_cpi.budget import usage_check

    class U:
        def __init__(self, plan, paygo=0):
            self.r = {"account": {"plan_usage": plan, "paygo_usage": paygo}}

        def usage(self, tag=None):
            return self.r
    led = [{"credits": 100, "budgets": ["x"]}]
    log = tmp_path / "u.jsonl"
    assert usage_check(U(120), cfg=cfg(), ledger=led, log=log)[0] is True          # lag allowance
    ok, msg = usage_check(U(131), cfg=cfg(), ledger=led, log=log)
    assert ok is False and "WARNING" in msg
    assert usage_check(U(50, paygo=1), cfg=cfg(), ledger=led, log=log)[0] is False  # any pay-as-you-go
    assert len(log.read_text().splitlines()) == 3 and "test" not in log.read_text()

    class Broken:
        def usage(self, tag=None):
            raise OSError("down")
    assert usage_check(Broken(), cfg=cfg(), ledger=led, log=log)[0] is None


def test_cached_auto_parameters_search_is_not_charged_but_keeps_its_original_cost(tmp_path):
    """Bug fix (logged, 2026-10-22): Budgeted added search_depth='basic' to auto_parameters searches, which Tavily.search
    does not send, so the cache check never matched and cached T+dates searches were charged again."""
    from shadow_cpi.budget import read_ledger, spent
    from shadow_cpi.recorder import Recorder
    from shadow_cpi.tavily import Tavily
    sent = []

    def transport(*a):
        sent.append(a)
        return {"request_id": f"req-{len(sent)}", "results": [], "usage": {"credits": 2}}
    tav = Tavily(api_key="test", recorder=Recorder(cache_dir=tmp_path / "c", log_file=tmp_path / "l.jsonl"),
                 transport=transport)
    led = tmp_path / "ledger.jsonl"
    b = Budgeted(tav, ["prompt-t"], cfg=cfg(), ledger_path=led)
    b.search("q", auto_parameters=True, max_results=8)
    b.search("q", auto_parameters=True, max_results=8)
    assert len(sent) == 1 and b.used == 2
    first, again = read_ledger(led)
    assert (first["real_spent"], first["original_cost"], first.get("cached")) == (2, 2, None)
    assert (again["credits"], again["real_spent"], again["original_cost"], again["cached"]) == (0, 0, 2, True)
    assert spent("prompt-t", path=led) == 2


def test_cached_rows_do_not_use_up_a_run_now_scan():
    from shadow_cpi.budget import run_now_allowed
    c = {"plans": {"cut5_run_now": {"scans_per_day": 1}}}
    led = [{"credits": 0, "cached": True, "budgets": ["run-now-scan/2026-12-01#1"]}]
    assert run_now_allowed("2026-12-01", led, c) == "run-now-scan/2026-12-01#1"


def test_fresh_client_sends_and_charges_even_when_a_cached_copy_exists(tmp_path):
    """Amendment R1 (radar): a recorder that does not read its cache must never pass a real call as a free cache hit."""
    from shadow_cpi.budget import read_ledger, spent
    from shadow_cpi.recorder import Recorder
    from shadow_cpi.tavily import Tavily
    sent = []

    def transport(*a):
        sent.append(a)
        return {"request_id": f"r{len(sent)}", "results": [], "usage": {"credits": 1}}
    led = tmp_path / "ledger.jsonl"
    cached = Budgeted(Tavily(api_key="t", recorder=Recorder(cache_dir=tmp_path / "c", log_file=tmp_path / "l"),
                             transport=transport), ["prompt-t"], cfg=cfg(), ledger_path=led)
    cached.search("q")                                                         # fills the cache, 1 credit
    fresh = Budgeted(Tavily(api_key="t", recorder=Recorder(cache_dir=tmp_path / "c", log_file=tmp_path / "l",
                                                           use_cache=False), transport=transport),
                     ["prompt-t"], cfg=cfg(), ledger_path=led)
    assert fresh.fresh
    fresh.search("q")
    assert len(sent) == 2 and spent("prompt-t", path=led) == 2 and not any(e.get("cached") for e in read_ledger(led))
