"""tools/sync_doc_numbers.py: README and Devpost are rendered from templates that type no number. Offline, no calls."""
import re
import shutil
from datetime import date
from pathlib import Path

import pytest

from tools import sync_doc_numbers as S

ROOT = Path(__file__).resolve().parent.parent
ST = {"calls": 1234, "cached": 1, "credits": 900, "spent_before_ledger": 160, "plan_limit": 1000,
      "addon_credits": 3125, "inside": 3, "total": 4, "undated": 0, "median_latency_s": 3.96}
# names that contain digits but are not numbers
NAMES = ("SHA-256", "v1", "v2")
BANNED = (r"\bfirst\b(?! commit\b)",                  # "first commit" is the eligibility line
          r"beats economists", r"\bno leaks\b", r"every page through Tavily", r"scores itself",
          r"\bused by\b", r"\b3 of 10\b")


def prose(text):
    """The template with code blocks, inline code, link targets, HTML comments and digit-bearing names removed."""
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"`[^`]*`", "", text)
    text = re.sub(r"\]\([^)]*\)", "]", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = S.PLACEHOLDER.sub("", text)
    text = re.sub(r"^\s*\d+\. ", "", text, flags=re.M)      # numbered-list markers
    for n in NAMES:
        text = text.replace(n, "")
    return text


@pytest.fixture(scope="module")
def values():
    return S.facts(ST, date(2026, 10, 25))


ALL_TEMPLATES = [*S.TEMPLATES.values(), *S.BLOCKS.values()]


@pytest.mark.parametrize("tmpl", ALL_TEMPLATES)
def test_templates_type_no_number(tmpl):
    typed = [(i + 1, line) for i, line in enumerate(prose((ROOT / tmpl).read_text()).splitlines())
             if re.search(r"\d", line)]
    assert typed == [], f"{tmpl} types a number; use a {{{{key}}}} from facts(): {typed}"


@pytest.mark.parametrize("tmpl", ALL_TEMPLATES)
def test_templates_avoid_banned_phrases(tmpl):
    text = (ROOT / tmpl).read_text()
    hits = [b for b in BANNED if re.search(b, text, re.I)]
    assert hits == []


def test_every_key_resolves(values):
    for tmpl in S.TEMPLATES.values():
        out = S.render((ROOT / tmpl).read_text(), values)
        assert "{{" not in out and "None" not in prose(out)


def test_readme_top_keeps_checks_apart(values):
    """The headline table: date test and finance check in separate rows, never summed, initial pass in a footnote."""
    out = S.render((ROOT / "docs/templates/README.md").read_text(), values)
    top = out.split("## Time-locked search leakage")[0]
    v = {k: int(values[k]) for k in ("dt_cases", "fin_events", "dt_dated_retry", "fin_dated_retry",
                                     "dt_nodates_retry", "fin_nodates_retry")}
    assert f"| Date test ({v['dt_cases']} cases) | **{v['dt_nodates_retry']} of {v['dt_cases']}** |" in top
    assert f"| {v['fin_dated_retry']} of {v['fin_events']} |" in top
    total = v["dt_cases"] + v["fin_events"]
    for summed in (v["dt_dated_retry"] + v["fin_dated_retry"], v["dt_nodates_retry"] + v["fin_nodates_retry"]):
        assert not re.search(rf"\b{summed} (of|/) {total}\b", out)
    details = top.split("<details>")[1].split("</details>")[0]
    assert values["dt_leak_rule"] in details and values["fin_leak_rule"] in details and "Initial pass" in details
    rr = S.load("results/retry_reconciliation.json")["retry_runs"]
    assert (f"On the initial pass, {rr['finance']['failed_urls']} finance-check archive lookups (and "
            f"{rr['date']['failed_urls']} in the date test) failed") in " ".join(details.split())
    assert (f"rises from {values['fin_nodates']} to {values['fin_nodates_retry']} of {v['fin_events']}"
            in " ".join(details.split()))
    assert "The cost." in top and values["ex_row"] in top


def test_drift_phrase_reads_the_drift_file():
    as_of = date(2026, 10, 27)
    assert S.drift_phrase({"runs": []}, as_of) == "no drift run is committed yet, as of 27 Oct 2026"
    assert S.drift_phrase(None, as_of) == "no drift run is committed yet, as of 27 Oct 2026"
    run = lambda d, k, c, ok=True: {"ist_date": d, "checked": k, "changed": c, "complete": ok}   # noqa: E731
    one = {"runs": [run("2026-10-27", 12, 2)]}
    assert S.drift_phrase(one, as_of) == "2 of 12 radar pages had changed since they were saved (one run, 27 Oct 2026 IST)"
    many = {"runs": [run("2026-10-27", 12, 2), run("2026-10-28", 10, 1, ok=False), run("2026-10-29", 12, 3)]}
    assert S.drift_phrase(many, as_of) == (
        "3 runs committed (27 Oct 2026 to 29 Oct 2026 IST), 34 page checks, 6 changes found; in the latest run, "
        "3 of 12 radar pages had changed since they were saved; 1 of the runs stopped incomplete")


def test_feedback_summary_only_restates_filed_reports(values):
    """Every filed report gets one row whose text, fix and evidence are copied from results/bug_reports.json."""
    br = S.load("results/bug_reports.json")
    rows = values["feedback_summary_rows"].splitlines()
    assert len(rows) == len(br["reports"])
    for r in br["reports"]:
        (row,) = [x for x in rows if r["title"] in x]
        assert r["happened"] in row and r["fix"] in row
        assert re.search(r"`([^`]+)`", row.split(" | ")[-2]).group(1) in r["evidence"]


def test_missing_key_stops(values):
    with pytest.raises(SystemExit, match="no_such_key"):
        S.render("{{no_such_key}}", values)


def test_devpost_short_description_fits(values):
    out = S.render((ROOT / "docs/templates/devpost.md").read_text(), values)
    short = re.search(r"<!-- short:start -->(.*?)<!-- short:end -->", out, re.S).group(1)
    assert len(short.split()) <= 140


def test_sync_renders_with_as_of_label_and_is_idempotent(tmp_path, values):
    for rel in [*S.TEMPLATES.values(), *S.BLOCKS.values(), *S.BLOCKS]:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, tmp_path / rel)
    (tmp_path / "FEEDBACK_NOTES.md").write_text(S.render_block((ROOT / "FEEDBACK_NOTES.md").read_text(),
                                                               S.BLOCKS["FEEDBACK_NOTES.md"], "stale"))
    assert S.sync(ST, date(2026, 10, 25), root=tmp_path, values=values) == ["README.md", "docs/devpost_draft.md",
                                                                             "FEEDBACK_NOTES.md"]
    readme = (tmp_path / "README.md").read_text().replace("\n", " ")
    assert "as of 25 Oct 2026" in readme and "1,234 calls sent, 900 credits used" in readme
    assert "75% of dated" in readme and "median latency 4.0 s" in readme
    assert readme.startswith("<!-- Generated by tools/sync_doc_numbers.py")
    assert S.sync(ST, date(2026, 10, 25), root=tmp_path, values=values) == []


def test_leak_rules_are_quoted_whole(values):
    for key, rel in (("dt_leak_rule", "v2/DATE_TEST_PREREG.md"), ("fin_leak_rule", "v2/FINANCE_PREREG.md")):
        rule = values[key]
        assert rule in " ".join((ROOT / rel).read_text().split())             # verbatim, modulo line breaks
        assert "no capture on or before the cutoff" in rule and rule.endswith(("cutoff.", "cutoff)."))
    for doc in ("README.md", "docs/devpost_draft.md"):
        text = " ".join((ROOT / doc).read_text().split())
        assert values["dt_leak_rule"] in text and values["fin_leak_rule"] in text


def test_numbers_come_from_the_results_files(values):
    import json
    sl = json.loads((ROOT / "results/score_lock.json").read_text())
    assert values["mae_c"] == f"{sl['mae']['c']:.3f}" and values["inside"] == str(sl["inside_range"])
    fr = json.loads((ROOT / "results/field_report.json").read_text())
    assert values["dt_nodates"] == str(fr["date_test"]["first_pass"]["arms"]["A"]["leak_cases"])
