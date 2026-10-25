"""Tavily field report (tools/build_field_report.py): every figure comes from the committed results files. Offline."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import build_field_report as FR  # noqa: E402


def test_four_arm_credits_come_from_the_ablation_results():
    saved = json.loads(FR.OUT.read_text(encoding="utf-8"))
    src = json.loads((ROOT / "results" / "v2_ablation.json").read_text())["arms"]
    assert {x["arm"]: x["real_new_credits"] for x in saved["four_arms"]["rows"]} == {k: a["new_credits"]
                                                                                      for k, a in src.items()}


def test_values_trace_to_their_sources():
    r = json.loads(FR.OUT.read_text(encoding="utf-8"))
    rt = json.loads((ROOT / "results" / "finance_lookahead_wayback_retry.json").read_text())
    assert r["finance"]["retry"]["recovered"] == rt["recovered"]
    assert r["exploratory"]["H"]["label"].startswith("exploratory, added after scoring")
    nd = r["auto_parameters"]["no_dates"]
    assert sum(nd["time_range"].values()) == nd["searches"]
    assert r["radar"]["runs"][0]["with_provenance"] == r["radar"]["runs"][0]["calls"]


def test_rebuild_is_deterministic_apart_from_the_date(tmp_path, monkeypatch):
    monkeypatch.setattr(FR, "OUT", tmp_path / "fr.json")
    a = FR.build()
    saved = json.loads((ROOT / "results" / "field_report.json").read_text())
    a.pop("built"); saved.pop("built")
    assert json.loads(json.dumps(a, default=float)) == saved
