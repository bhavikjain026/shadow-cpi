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
    assert {r["run"] for r in rows if r["check"].startswith("Finance")} == {"first pass", "after logged retry"}
    p = json.loads((ROOT / FR.LEAKCHECKS["P"]).read_text())["metrics"]
    prows = [r for r in rows if r["check"].startswith("Check P")]
    assert [(r["n"], r["leaks"]) for r in prows] == [(m["with_text"], m["later_content"]) for m in p.values()]
    e = json.loads((ROOT / FR.LEAKCHECKS["E"]).read_text())
    (erow,) = [r for r in rows if r["check"].startswith("Check E")]
    assert (erow["n"], erow["leaks"], erow["valid_kept"]) == (e["metrics"]["run"], None,
                                                               e["metrics"]["shares"]["found before cutoff"]["x"])
    assert f"{e['metrics']['shares']['found only without dates']['x']} of {e['metrics']['run']}" in erow["caveats"]
    assert not any(r.get("placeholder") for r in rows)


def test_check_e_dates_are_read_from_the_saved_undated_responses():
    e = json.loads((ROOT / FR.LEAKCHECKS["E"]).read_text())
    d = FR.check_e_dates(e)
    assert d["quotes"] == e["metrics"]["shares"]["found only without dates"]["x"]
    assert d["after_cutoff"] + d["on_or_before_cutoff"] + d["undated_or_missing"] == d["quotes"]
    fake = {"cases": [{"id": "Q", "cutoff": "2026-05-29", "outcome": "found only without dates",
                       "searches": {"undated": {"results": [{"source_page": True,
                                                             "published_date": "Sat, 30 May 2026 10:00:00 GMT"}]}}}]}
    assert FR.check_e_dates(fake)["after_cutoff"] == 1
    fake["cases"][0]["searches"]["undated"]["results"].insert(0, {"source_page": True, "published_date": "2026-05-01"})
    assert FR.check_e_dates(fake)["after_cutoff"] == 1           # any copy dated after the cutoff counts


def test_receipt_credits_match_the_ledger(built):
    from shadow_cpi.budget import spent
    rc = built["receipt"]
    for x in rc["per_verified_quote"]:
        assert x["credits"] == sum(spent(b) for b in x["budgets"])
    assert sum(e["calls"] for e in rc["by_endpoint"]) == rc["total"]["calls"]
    assert all(e["p95_latency_s"] >= e["median_latency_s"] for e in rc["by_endpoint"])
    assert FR.p95(list(range(1, 21))) == pytest.approx(19.05) and FR.median([1, 2, 3, 4]) == 2.5 and FR.p95([3.0]) == 3.0
    exp = {x["experiment"]: 0 for x in rc["by_experiment"]}
    for x in rc["by_experiment"]:
        exp[x["experiment"]] += x["credits"]
    assert all(c == spent(e) for e, c in exp.items() if e != "reconcile")


def test_date_test_no_dates_row_reads_like_the_finance_rows(built):
    rows = [r for r in built["leakage"]["rows"] if r["setting"] == "no dates"]
    assert [(r["check"].split(" (")[0], r["run"]) for r in rows] == [
        ("Date test", "first pass"), ("Date test", "after logged retry"),
        ("Replication", "first pass"), ("Replication", "after logged retry"),     # its own group, never merged
        ("Finance check", "first pass"), ("Finance check", "after logged retry")]
    dt = json.loads((ROOT / "results" / "date_field_test.json").read_text())["metrics"]["arms"]["A"]
    assert (rows[0]["leaks"], rows[0]["n"]) == (dt["leak_cases"], dt["cases"])


def test_four_arm_table_shows_every_column_and_others_keep_the_default():
    from streamlit.testing.v1 import AppTest
    from app_pages.common import MAX_COLS
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=90)
    at.run()
    at.switch_page("app_pages/field_report.py")
    at.run()
    assert not at.exception
    arms = [d for d in at.dataframe if "Searches written by" in d.value.columns]
    assert len(arms) == 1
    order = list(arms[0].proto.column_order)
    assert order == list(arms[0].value.columns) and len(order) == 8
    others = [d for d in at.dataframe if "Searches written by" not in d.value.columns]
    assert all(len(d.proto.column_order) <= MAX_COLS for d in others)
