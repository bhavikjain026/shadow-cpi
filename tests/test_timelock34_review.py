"""benchmarks/timelock34/compare_review.py: the second review joins our labels row by row, holds no page text, and
the committed results file and docs match what the script computes. Offline, 0 credits."""
import json
from pathlib import Path

import pytest

from benchmarks.timelock34 import compare_review as CR
from benchmarks.timelock34.score import load_cases

ROOT = Path(__file__).resolve().parent.parent


def test_results_file_is_up_to_date():
    assert CR.dumps(CR.build()) == CR.OUT.read_text(encoding="utf-8")


def test_join_checks_case_and_url_in_order():
    cases, review = load_cases(), CR.load_review()
    assert len(CR.join(cases, review)) == 283
    swapped = [dict(r) for r in review]
    swapped[0]["url"], swapped[1]["url"] = swapped[1]["url"], swapped[0]["url"]
    with pytest.raises(ValueError, match="R001"):
        CR.join(cases, swapped)
    with pytest.raises(ValueError, match="282 rows"):
        CR.join(cases, review[:-1])


def test_short_quotes_only():
    for row in CR.load_review():
        assert len(row["evidence_quote"].split()) < 25
        assert row["label"] in ("LEAK", "SAFE", "UNCLEAR")


def test_kappa_by_hand():
    k = CR.kappa([(True, True)] * 2 + [(False, False)] * 2)
    assert (k["agreement"], k["kappa"]) == (1.0, 1.0)
    k = CR.kappa([(True, True), (True, False), (False, True), (False, False)])
    assert (k["agreement"], k["kappa"]) == (0.5, 0.0)


def test_headline_numbers():
    rep = json.loads(CR.OUT.read_text(encoding="utf-8"))
    assert (rep["decided"], rep["unclear"], rep["rows"]) == (137, 146, 283)
    a = rep["agreement"]
    assert f"{a['confirmed_or_date_flag']['agreement']:.1%}" == "89.1%" and f"{a['confirmed_or_date_flag']['kappa']:.2f}" == "0.76"
    assert f"{a['confirmed']['agreement']:.1%}" == "75.9%" and f"{a['confirmed']['kappa']:.2f}" == "0.36"
    t = {(x["dataset"], x["setting"]): x for x in rep["tasks"]}
    assert (t["date_test", "no_dates"]["reviewer_leak"], t["date_test", "no_dates"]["ours_confirmed"]) == (4, 10)
    assert (t["finance", "no_dates"]["reviewer_leak"], t["finance", "no_dates"]["ours_confirmed"]) == (14, 10)
    assert (t["finance", "dates_filter"]["reviewer_leak"], t["finance", "dates_filter"]["ours_confirmed"]) == (1, 0)
    ff = rep["finance_filtered"]
    assert (ff["searches_with_result_dated_after_cutoff"], ff["searches"], ff["reviewer_leak_pages"]) == (0, 14, 1)
    assert ff["example"]["row_id"] == "R196" and ff["example"]["our_published_date"] < ff["example"]["cutoff"]


def test_docs_match_the_results_file_and_never_say_no_leaks():
    rep = json.loads(CR.OUT.read_text(encoding="utf-8"))
    ff = rep["finance_filtered"]
    count = f"{ff['searches_with_result_dated_after_cutoff']} of {ff['searches']} filtered searches"
    unclear = f"{rep['unclear']} of {rep['rows']} rows stayed unclear"
    for doc in ("benchmarks/timelock34/DATASHEET.md", "README.md", "docs/devpost_draft.md"):
        text = " ".join((ROOT / doc).read_text(encoding="utf-8").split())
        assert count in text and "returned a result dated after the cutoff" in text, doc
        assert unclear in text and "post-hoc AI-assisted review (ChatGPT agent)" in text, doc
        assert "independent reviewer" not in text.lower(), doc
        assert "no leaks" not in text.lower(), doc
    ds = (ROOT / "benchmarks/timelock34/DATASHEET.md").read_text(encoding="utf-8")
    assert f"decided {rep['decided']} of {rep['rows']} rows" in " ".join(ds.split())
    ct = rep["crosstab"]["date_test"]
    assert f"called SAFE ({ct['confirmed/SAFE'] + ct['date_flag/SAFE']})" in ds
    assert f"{rep['crosstab']['finance']['unknown/LEAK']} rows with no date signal" in ds


def test_datasheet_tables_match_the_results_file():
    rep = json.loads(CR.OUT.read_text(encoding="utf-8"))
    ds = (ROOT / "benchmarks/timelock34/DATASHEET.md").read_text(encoding="utf-8")
    for key, lab in (("confirmed_or_date_flag", "`confirmed` or `date_flag`"), ("confirmed", "`confirmed` only")):
        a = rep["agreement"][key]
        assert f"| {lab} | {a['agreement']:.1%} | {a['kappa']:.2f} |" in ds
    t = {(x["dataset"], x["setting"]): x for x in rep["tasks"]}
    for (d, s), lab in ((("date_test", "no_dates"), "| date test | `no_dates` |"),
                        (("finance", "no_dates"), "| finance | `no_dates` |"),
                        (("finance", "dates_filter"), "| finance | `dates_filter` |")):
        assert f"{lab} {t[d, s]['reviewer_leak']} | {t[d, s]['ours_confirmed']} |" in ds
    assert all(t[("date_test", s)]["reviewer_leak"] == t[("date_test", s)]["ours_confirmed"] == 0
               for s in ("dates", "dates_filter", "dates_filter_page_date"))


def test_join_checks_the_cutoff_and_kappa_is_none_when_undefined():
    cases, review = load_cases(), [dict(r) for r in CR.load_review()]
    review[0]["cutoff"] = "2026-01-01"
    with pytest.raises(ValueError, match="R001"):
        CR.join(cases, review)
    assert CR.kappa([])["kappa"] is None and CR.kappa([(True, True)] * 3)["kappa"] is None
