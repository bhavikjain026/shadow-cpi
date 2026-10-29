"""tools/evidence_tiers.py: tiers and case-level bounds come from the saved results; the best case is the headline."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))
import evidence_tiers as ET  # noqa: E402


def res(label, captures=("2026-01-01",), tavily_date="2026-01-01"):
    return {"label": label, "captures": None if captures is None else list(captures), "tavily_date": tavily_date}


def test_tiers_map_labels_as_the_headline_stores_them():
    assert [ET.tier(res(x)) for x in "PLFU"] == ["archived", "leak", "unknown", "unknown"]


def test_counts_split_unknown_and_count_undated():
    rows = [res("P"), res("L"), res("U", captures=None), res("U", captures=[]), res("F", captures=[], tavily_date=None),
            res("U", captures=["2026-02-01"])]
    c = ET.counts(rows)
    assert (c["results"], c["archived"], c["leak"], c["unknown"]) == (6, 1, 1, 4)
    assert c["unknown_lookup_failed"] == 1 and c["unknown_no_capture"] == 2 and c["unknown_capture_unconfirmed"] == 1
    assert c["unknown_with_date_flag"] == 1 and c["undated"] == 1
    assert c["unknown_lookup_failed"] + c["unknown_no_capture"] + c["unknown_capture_unconfirmed"] == c["unknown"]


def test_case_bounds_best_is_leak_only_worst_adds_any_unknown():
    cases = [[res("L")], [res("P"), res("U", captures=[])], [res("P")], [res("F", captures=[])]]
    b = ET.case_bounds(cases)
    assert (b["best_case"]["k"], b["worst_case"]["k"], b["best_case"]["n"]) == (1, 3, 4)
    lo, hi = b["worst_case"]["wilson95"]
    assert 0 <= lo <= 3 / 4 <= hi <= 1


@pytest.fixture(scope="module")
def built():
    return ET.build()


def test_best_case_equals_the_headline_pooled_count(built):
    head = json.loads((ROOT / "results/replication.json").read_text())["pooled"]["price"]["arms"]
    for a in ("A", "C"):
        assert built["arms"][a]["pooled"]["best_case"]["k"] == head[a]["leak_cases"]
        assert built["arms"][a]["pooled"]["best_case"]["n"] == head[a]["cases"]


def test_worst_case_is_never_below_best_and_tiers_sum(built):
    for a in ("A", "C"):
        for x in [built["arms"][a]["pooled"], *built["arms"][a]["by_source"].values()]:
            assert x["archived"] + x["leak"] + x["unknown"] == x["results"]
            assert x["best_case"]["k"] <= x["worst_case"]["k"] <= x["worst_case"]["n"]


def test_saved_file_matches_a_fresh_build(built):
    assert json.loads((ROOT / "results/evidence_tiers.json").read_text()) == json.loads(json.dumps(built))


def test_field_report_carries_the_block_and_label():
    fr = json.loads((ROOT / "results/field_report.json").read_text())["evidence_tiers"]
    assert fr["label"].startswith("exploratory, added after scoring") and "not a new result" in fr["label"]


def test_after_retry_tiers_sum_keep_the_leak_floor_and_only_resolve_failed_lookups(built):
    for a in ("A", "C"):
        x, y = built["arms"][a]["pooled"], built["arms"][a]["after_retry"]["pooled"]
        assert y["archived"] + y["leak"] + y["unknown"] == y["results"] == x["results"]
        assert y["unknown_lookup_failed"] == 0 and y["leak"] >= x["leak"] and y["archived"] >= x["archived"]
        assert y["best_case"]["k"] <= y["worst_case"]["k"] <= x["worst_case"]["k"]


def test_retried_changes_only_failed_lookups():
    ok = {"url": "https://x.test/a", "captures": ["2026-01-01"], "tavily_date": "2026-01-01", "label": "P"}
    failed = {**ok, "captures": None, "label": "U"}
    rec = {"https://x.test/a": ["2026-01-01"]}
    assert ET.retried(ok, "2026-02-01", rec) is ok
    assert ET.retried(failed, "2026-02-01", rec)["label"] == "P"
    assert ET.retried(failed, "2026-02-01", {}) is failed


def test_page_block_leads_with_coverage_and_carries_the_bound_caption():
    src = (ROOT / "app_pages/field_report.py").read_text()
    assert src.index("**Coverage, initial pass**") < src.index("The worst case assumes every unverified result leaked.")
    assert "That is a mathematical bound, not an estimate" in src and "**Coverage, after retry**" in src
    assert "it is unverified, not leaked" in src


def test_readme_and_devpost_carry_the_coverage_line_from_the_json_and_no_worst_case_count():
    c = json.loads((ROOT / "results/evidence_tiers.json").read_text())["arms"]["C"]["pooled"]
    line = (f"confirmed {c['archived']} of {c['results']} time-locked results as published before the cutoff and none after it")
    for f in ("README.md", "docs/devpost_draft.md"):
        text = " ".join((ROOT / f).read_text().split())
        assert line in text and f"the other {c['unknown']} could not be checked" in text
        assert f"{c['worst_case']['k']} of {c['worst_case']['n']} cases" not in text
