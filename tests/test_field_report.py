"""Tavily field report (tools/build_field_report.py): every figure comes from the results files. Offline. Each test
builds fresh into a temporary file, so new data (e.g. another radar run) never breaks it."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import build_field_report as FR  # noqa: E402


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    FR.OUT = tmp_path_factory.mktemp("fr") / "field_report.json"
    try:
        return FR.build()
    finally:
        FR.OUT = ROOT / "results" / "field_report.json"


def test_four_arm_credits_come_from_the_ablation_results(built):
    src = json.loads((ROOT / "results" / "v2_ablation.json").read_text())["arms"]
    assert {x["arm"]: x["real_new_credits"] for x in built["four_arms"]["rows"]} == {k: a["new_credits"]
                                                                                      for k, a in src.items()}


def test_values_trace_to_their_sources(built):
    from shadow_cpi.budget import load_budget
    rt = json.loads((ROOT / "results" / "finance_lookahead_wayback_retry.json").read_text())
    assert built["finance"]["retry"]["recovered"] == rt["recovered"]
    assert built["exploratory"]["H"]["label"].startswith("exploratory, added after scoring")
    nd = built["auto_parameters"]["no_dates"]
    assert sum(nd["time_range"].values()) == nd["searches"]
    radar = json.loads((ROOT / "v2" / "radar" / "radar_2026-10.json").read_text())
    assert len(built["radar"]["runs"]) == len(radar["runs"])
    assert built["radar"]["cap"] == load_budget()["caps"]["radar-2026-10"]
    assert all(r["with_provenance"] == r["calls"] for r in built["radar"]["runs"])


def test_leakage_table_reads_the_date_and_finance_results(built):
    rows = built["leakage"]["rows"]
    dt = json.loads((ROOT / "results" / "date_field_test.json").read_text())["metrics"]["arms"]
    first = [r for r in rows if r["check"].startswith("Date test") and r["run"] == "first pass"]
    assert [r["leaks"] for r in first] == [dt[a]["leak_cases"] for a in "ABCD"]
    assert [r["valid_kept"] for r in first] == [dt[a]["valid_total"] - dt[a]["valid_lost"] for a in "ABCD"]
    assert {r["run"] for r in rows if r["check"].startswith("Finance")} == {"first pass", "after retry"}
    for chk in ("P", "E"):                       # placeholders until their results files exist
        mine = [r for r in rows if r["check"] == f"Check {chk}"]
        assert mine and (mine[0].get("placeholder") or (ROOT / FR.PENDING_CHECKS[chk]).exists())


def test_receipt_credits_match_the_ledger(built):
    from shadow_cpi.budget import spent
    rc = built["receipt"]
    for x in rc["per_verified_quote"]:
        assert x["credits"] == sum(spent(b) for b in x["budgets"])
    assert sum(e["calls"] for e in rc["by_endpoint"]) == rc["total"]["calls"]
    assert all(e["p95_latency_s"] >= e["median_latency_s"] for e in rc["by_endpoint"])
    assert FR.p95([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]) == 10 and FR.median([1, 2, 3, 4]) == 2.5
