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
