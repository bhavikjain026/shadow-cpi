"""Feedback as bug reports (tools/build_bug_reports.py): every report has the four parts; counts come from files."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import build_bug_reports as BR  # noqa: E402


def test_reports_have_all_parts_and_cover_the_asked_topics():
    reps = json.loads(BR.OUT.read_text())["reports"]
    assert all(all(r[k] for k in ("did", "happened", "expected", "fix", "evidence")) for r in reps)
    titles = " ".join(r["title"].lower() for r in reps)
    for t in ("auto_parameters", "published_date", "map", "scanned pdf", "/usage", "nano"):
        assert t in titles


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
