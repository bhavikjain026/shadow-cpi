"""Account limit = plan + add-on credits; the reserve is kept for the seal runs (config/budget.json)."""
import json

import pytest

from shadow_cpi.budget import BudgetExceeded, Budgeted, account_limit, load_budget


class FakeTavily:
    rec = None


def cfg(**kw):
    return {"plan_limit": 1500, "addon_credits": 3125, "reserve": 150, "reserve_for": ["live-month", "skeptic"],
            "spent_before_ledger": 0, "caps": {"live-month": 120, "skeptic": 48, "prompt-t": 90}, **kw}


def write_ledger(path, total):
    path.write_text(json.dumps({"time": "t", "call_id": "x", "endpoint": "/search", "credits": total,
                                "budgets": ["other"]}) + "\n")


def test_account_limit_includes_addon_credits():
    assert account_limit(cfg()) == 4625
    assert account_limit({"plan_limit": 100}) == 100


def test_real_config_matches_the_billing_page():
    c = load_budget()
    assert (c["plan_limit"], c["addon_credits"], c["reserve"]) == (1500, 3125, 150)
    assert {"live-month", "nov-interim-scan", "skeptic"} <= set(c["reserve_for"])


def test_reserve_blocks_other_budgets_but_not_the_seal(tmp_path):
    led = tmp_path / "ledger.jsonl"
    write_ledger(led, 4625 - 150)                         # exactly the reserve left
    other = Budgeted(FakeTavily(), ["prompt-t"], cfg=cfg(), ledger_path=led)
    with pytest.raises(BudgetExceeded):
        other.check(1)
    Budgeted(FakeTavily(), ["live-month", "live-month/2026-10"], cfg=cfg(), ledger_path=led).check(1)
    Budgeted(FakeTavily(), ["skeptic", "skeptic/2026-10"], cfg=cfg(), ledger_path=led).check(1)


def test_nothing_past_the_account_limit_even_for_the_seal(tmp_path):
    led = tmp_path / "ledger.jsonl"
    write_ledger(led, 4625)
    with pytest.raises(BudgetExceeded):
        Budgeted(FakeTavily(), ["live-month"], cfg=cfg(), ledger_path=led).check(1)


def test_ledger_reconciles_to_the_billing_page():
    from shadow_cpi.budget import account_spent, read_ledger
    led = read_ledger()
    i = next(k for k, e in enumerate(led) if e["call_id"] == "reconcile-2026-10-22")
    assert account_spent(load_budget(), led[:i + 1]) == 681                  # matches the billing page that day
