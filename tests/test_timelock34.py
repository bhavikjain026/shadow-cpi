"""benchmarks/timelock34: the dataset is rebuilt from the committed results, holds no page text, and the scorer
reproduces the experiments' own after-retry numbers. Offline, 0 credits."""
import json
import subprocess
import sys
from pathlib import Path

from benchmarks.timelock34 import build
from benchmarks.timelock34.score import date_checked, load_cases, recorded, score, wilson

ROOT = Path(__file__).resolve().parent.parent


def test_cases_file_is_up_to_date_and_has_34_cases():
    cases = load_cases()
    assert build.dumps(build.build()) == (ROOT / "benchmarks/timelock34/cases.jsonl").read_text(encoding="utf-8")
    assert [c["dataset"] for c in cases].count("date_test") == 20 and len(cases) == 34
    # M8/M9 and M11/M12: two price changes in the same state and month, so the same question and searches
    assert len({(c["question"], c["cutoff"]) for c in cases}) == 32


def test_no_page_text_only_short_quotes():
    for c in load_cases():
        for r in c["results"]:
            assert "content" not in r and "raw_content" not in r and "title" not in r
            assert len(r["quote"].split()) <= build.QUOTE_WORDS and r["leak"] in ("confirmed", "date_flag", "unknown")
        for name, body in c["requests"].items():
            assert "derived_from" in body or (body["query"] == c["question"] and name in c["receipts"])


def test_scorer_reproduces_the_after_retry_numbers():
    cases = load_cases()
    dt = json.loads((ROOT / "results/date_field_test_wayback_retry.json").read_text())["after"]["arms"]
    fin = json.loads((ROOT / "results/finance_lookahead_wayback_retry.json").read_text())["after"]["all"]["arms"]
    arms = [("date_test", "no_dates", dt["A"], "leak_cases"), ("date_test", "dates", dt["B"], "leak_cases"),
            ("date_test", "dates_filter", dt["C"], "leak_cases"), ("date_test", "dates_filter_page_date", dt["D"],
                                                                   "leak_cases"),
            ("finance", "no_dates", fin["N"], None), ("finance", "dates_filter", fin["D"], None)]
    for ds, arm, want, key in arms:
        got = score(recorded(arm, cases), cases)[ds]
        leaks = want[key] if key else want["confirmed"]["events"]
        assert got["leak_cases"] == leaks, (ds, arm)
        assert (got["valid_total"] - got["valid_kept"], got["valid_total"]) == (want["valid_lost"],
                                                                               want["valid_total"]), (ds, arm)
        assert got["unlabelled"] == 0


def test_any_search_function_and_unlabelled_urls():
    cases = load_cases()[:2]
    s = score(lambda q, cut: ["https://example.com/not-in-the-dataset"], cases)
    assert s["all"]["cases"] == 2 and s["all"]["unlabelled"] == 2 and s["all"]["leak_cases"] == 0
    assert s["all"]["wilson95"] == wilson(0, 2)
    assert score(lambda q, cut: None, cases)["all"]["cases"] == 0
    checked = score(date_checked(recorded("no_dates")))["all"]
    assert checked["leak_cases"] == 0 and checked["cases"] == 34          # timelock's date check alone


def test_cli_runs():
    out = subprocess.run([sys.executable, "benchmarks/timelock34/score.py"], cwd=ROOT, capture_output=True,
                         text=True, check=True).stdout
    assert "| no_dates | all | 20 of 34 |" in out
