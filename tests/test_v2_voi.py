"""Value of information (v2/voi.py): formula, search worth, stop rule, ledger join. Offline, no calls."""
import json

import pytest

from v2 import voi as V


def series(vals):
    return {f"2025-{i + 1:02d}": v for i, v in enumerate(vals)}


def test_voi_is_weight_times_sd_times_chance_from_2025_only():
    s = {"04.5.1.0.2.01": {**series([100, 102, 102, 102]), "2026-01": 150}}         # 2026 must be ignored
    st = V.item_stats(s, {"04.5.1.0.2.01": 2.0})
    e = st["electricity"]
    mom = [2.0, 0.0, 0.0]
    import statistics
    assert e["months"] == 3 and e["p_change"] == pytest.approx(1 / 3)
    assert e["voi_pp"] == pytest.approx(0.02 * statistics.stdev(mom) * (1 / 3))
    assert st["metro"]["voi_pp"] is None


def test_search_worth_sums_named_items():
    st = {"electricity": {"voi_pp": 0.02}, "milk": {"voi_pp": 0.01}, "bus": {"voi_pp": None}}
    assert V.search_worth("electricity tariff and milk price hike", st) == pytest.approx(0.03)
    assert V.search_worth("bus fare", st) is None and V.kinds_in("बिजली दूध") == ["electricity", "milk"]


def test_stop_rule():
    st = {"a": {"voi_pp": 0.02}, "b": {"voi_pp": 0.005}, "c": {"voi_pp": 0.001}}
    r = V.stop_rule(st)
    assert r["stop_after"] == 1 and [x["worth_searching"] for x in r["order"]] == [True, False, False]
    assert V.stop_rule({"a": {"voi_pp": 0.004}})["stop_after"] == 0                    # whole basket below 0.01 pp
    assert V.stop_rule({"a": {"voi_pp": 0.5}})["stop_after"] == 1


def test_credits_by_item_joins_ledger_to_queries():
    calls = [{"call_id": "s1", "sent": {"query": "milk and electricity hike"}}, {"call_id": "s2", "sent": {}}]
    led = [{"call_id": "s1", "endpoint": "/search", "credits": 2}, {"call_id": "x", "endpoint": "/extract", "credits": 1},
           {"call_id": "s2", "endpoint": "/search", "credits": 0}]
    assert V.credits_by_item(led, calls) == {"electricity": 1.0, "milk": 1.0, "not item-specific": 1}


def test_fresh_build_is_display_only(tmp_path, monkeypatch):
    monkeypatch.setattr(V, "OUT", tmp_path / "voi.json")
    d = V.build()
    assert "display only" in d["label"] and d["calibration_year"] == "2025"
    assert d["stop"]["total_pp"] == pytest.approx(sum(v["voi_pp"] for v in d["items"].values() if v["voi_pp"] is not None))


def test_words_match_whole_words_only():
    assert V.kinds_in("business news price hike") == [] and V.kinds_in("bus fare hike") == ["bus"]
    assert V.kinds_in("trail of evidence") == [] and V.kinds_in("बस किराया") == ["bus"]
