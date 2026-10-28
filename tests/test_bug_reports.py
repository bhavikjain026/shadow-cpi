"""Feedback as bug reports (tools/build_bug_reports.py): every report has the four parts; counts come from files."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import build_bug_reports as BR  # noqa: E402


def test_reports_have_all_parts_and_cover_the_asked_topics():
    out = json.loads(BR.OUT.read_text())
    reps = out["reports"] + out["nebius"]
    assert all(all(r[k] for k in ("did", "happened", "expected", "fix", "evidence")) for r in reps)
    titles = " ".join(r["title"].lower() for r in reps)
    for t in ("auto_parameters", "last-modified", "map", "scanned pdf", "/usage", "nano"):
        assert t in titles


def test_field_notes_are_tagged_feature_requests_then_observations():
    reps = json.loads(BR.OUT.read_text())["reports"]
    assert [r["section"] for r in reps] == ["observation"] * 2 + ["feature"] * 2 + ["observation"] * 3
    assert [r["tag"] for r in reps] == ["unexplained", "doc gap", "documented behaviour", "documented behaviour",
                                       "unexplained", "doc gap", "doc gap"]
    t = [r["title"] for r in reps[:3]]
    assert "past month" in t[0] and "explicit dates" in t[1] and "as-of" in t[2]
    doc = BR.DOC.read_text()
    assert doc.startswith("# Tavily field notes / repro kit")
    assert doc.index("## Feature requests") < doc.index("## Observations")
    assert "bug" not in doc.lower().replace("bug_reports", "")
    assert all(r["to"] == "Tavily" for r in reps)


def test_top_three_carry_counts_and_request_ids():
    reps = json.loads(BR.OUT.read_text())["reports"]
    n, with_id, ids = BR.request_ids("arm_T_*.json")
    assert 0 < with_id <= n and ids[0] in reps[0]["evidence"]
    assert BR.request_ids("arm_Td_*.json")[2][0] in reps[1]["evidence"]
    ex = json.loads((ROOT / "results/timelock34_second_review.json").read_text())["finance_filtered"]["example"]
    rid, sha = BR.r196_receipt(ex)
    assert rid in reps[2]["evidence"] and sha[:16] in reps[2]["evidence"]
    ap = json.loads((ROOT / "results/field_report.json").read_text())["auto_parameters"]
    assert f"{ap['no_dates']['results_dated_oct_2026']} of {ap['no_dates']['results']}" in reps[0]["evidence"]
    td_n, td_dates = BR.echo_dates("arm_Td_*.json")
    assert td_n == ap["with_dates"]["searches"] and f"{td_dates} of {td_n} echoes" in reps[1]["happened"]


def test_counts_trace_to_sources():
    lag = BR.date_lag()
    assert 0 <= lag["over_7_days"] <= lag["tavily_later"] <= lag["with_both_dates"]
    assert str(json.loads((ROOT / "results/prompt_t/dairy_followup_2026-10-21.json").read_text())["gokul_adv_chars"]) \
        in BR.DOC.read_text()


def test_build_writes_both_files_with_every_report(tmp_path, monkeypatch):
    monkeypatch.setattr(BR, "OUT", tmp_path / "b.json")
    monkeypatch.setattr(BR, "DOC", tmp_path / "b.md")
    reps = BR.build()
    assert json.loads((tmp_path / "b.json").read_text())["reports"] == reps
    assert all(r["title"] in (tmp_path / "b.md").read_text() for r in reps)


def test_date_lag_counts_distinct_pages():
    rows = json.loads((ROOT / "results" / "date_field_test.json").read_text())["rows"]
    urls = {r["url"] for row in rows for a in ("A", "B", "C") for r in row["arms"].get(a, {}).get("results", [])
            if r.get("tavily_date") and r.get("page_date")}
    assert BR.date_lag()["with_both_dates"] == len(urls)
