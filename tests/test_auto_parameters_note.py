"""House rule: every displayed mention of the auto_parameters no-dates count (results dated October 2026 of all results,
arm T) carries the qualifier "measured <date>; a one-query re-check on <date> did not show it", worded by
tools/build_bug_reports.auto_note() from the arm T files and the 27 Oct re-check. Checks the app pages, the docs and
templates (rendered), and the generated bug reports. Results artifacts (results/*.md) are not displayed docs."""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import build_bug_reports as BR  # noqa: E402

FR = json.loads((ROOT / "results" / "field_report.json").read_text())["auto_parameters"]["no_dates"]
OCT, ALL = FR["results_dated_oct_2026"], FR["results"]
COUNT = re.compile(rf"\b{OCT} of {ALL}\b|\b{OCT}/{ALL}\b|Of {ALL} results, {OCT}\b")
NOTE = BR.auto_note()
SPOKEN = "six hundred twenty of six hundred fifty-nine"


def blocks(text):
    """Paragraphs; each Markdown table row is its own block."""
    for para in re.split(r"\n\s*\n", text):
        rows = [l for l in para.splitlines() if l.lstrip().startswith("|")]
        yield from rows if rows else [" ".join(para.split())]


def missing(text):
    return [b[:160] for b in blocks(text) if len(COUNT.findall(b)) > b.count(NOTE)]


def test_the_note_is_the_one_the_readme_uses():
    assert NOTE == "measured 22 Oct 2026; a one-query re-check on 27 Oct 2026 did not show it"
    assert NOTE in (ROOT / "README.md").read_text() and NOTE in (ROOT / "docs/devpost_draft.md").read_text()


def test_every_doc_mention_carries_the_note():
    files = subprocess.run(["git", "ls-files", "*.md"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    files = [f for f in files if not f.startswith(("results/", "tests/", "logs/", "cache/"))]
    bad = {f: m for f in files if (m := missing((ROOT / f).read_text(encoding="utf-8")))}
    assert bad == {}


def test_templates_render_with_the_note():
    import sync_doc_numbers as S
    from datetime import date
    stats = {"calls": 1, "cached": 0, "credits": 1, "spent_before_ledger": 0, "plan_limit": 1, "addon_credits": 0,
             "inside": 1, "total": 1, "undated": 0, "median_latency_s": 1.0}      # run counts do not matter here
    v = S.facts(stats, date(2026, 10, 27))
    assert v["auto_note"] == NOTE
    for doc, tpl in [*S.TEMPLATES.items(), *S.BLOCKS.items()]:
        assert missing(S.render((ROOT / tpl).read_text(), v)) == [], doc


def test_bug_reports_json_carries_the_note():
    reports = json.loads((ROOT / "results" / "bug_reports.json").read_text())["reports"]
    assert missing("\n\n".join(str(v) for r in reports for v in r.values())) == []


def test_video_voice_over_says_the_recheck():
    lines = [l for l in (ROOT / "docs/video_script.md").read_text().splitlines() if SPOKEN in l]
    assert lines and all("a one-query re-check on 27 October did not show it" in l for l in lines)


def test_field_report_page_carries_the_note(monkeypatch):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest
    monkeypatch.chdir(ROOT)
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=90)
    at.run()
    at.switch_page("app_pages/field_report.py")
    at.run()
    assert not at.exception
    shown = [m.value for m in at.markdown] + [c.value for c in at.caption]
    assert any(COUNT.search(s) for s in shown)
    assert missing("\n\n".join(shown)) == []
