"""Leak checker (shadow_cpi/leakcheck.py): safe / date_flag / leak; undated pages are flagged, not rejected."""
import runpy
from pathlib import Path

from shadow_cpi.leakcheck import DATE_FLAG, LEAK, SAFE, check_result, check_results

CUT = "2026-10-06"


def test_labels():
    assert check_result({"url": "https://x.in/a", "published_date": "2026-10-03"}, CUT) == SAFE
    assert check_result({"url": "https://x.in/a", "published_date": "2026-10-07"}, CUT) == LEAK
    assert check_result({"url": "https://x.in/a", "published_date": "Wed, 07 Oct 2026 10:00:00 GMT"}, CUT) == LEAK
    assert check_result({"url": "https://x.in/2026/10/07/a"}, CUT) == LEAK                      # date in the address
    assert check_result({"url": "https://x.in/a"}, CUT) == DATE_FLAG                             # undated: flagged
    assert check_result({"url": "https://x.in/a"}, CUT, page_date="2026-10-01") == SAFE
    assert check_result({"url": "https://x.in/a", "published_date": "2026-10-02"}, CUT, page_date="2026-10-09") == LEAK


def test_wayback_capture_before_the_cutoff_turns_a_late_date_into_a_flag():
    r = {"url": "https://x.in/a", "published_date": "2026-10-09"}
    assert check_result(r, CUT, captures=["2026-09-30", "2026-10-10"]) == DATE_FLAG
    assert check_result(r, CUT, captures=["2026-10-10"]) == LEAK


def test_cutoff_day_is_safe_and_counts():
    assert check_result({"url": "u", "published_date": CUT}, CUT) == SAFE
    counts, labelled = check_results([{"url": "u", "published_date": "2026-10-07"}, {"url": "u"}], CUT)
    assert counts == {SAFE: 0, DATE_FLAG: 1, LEAK: 1} and len(labelled) == 2


def test_example_runs(capsys):
    runpy.run_path(str(Path(__file__).resolve().parent.parent / "examples" / "leakcheck_example.py"))
    assert "{'safe': 1, 'date_flag': 1, 'leak': 1}" in capsys.readouterr().out
