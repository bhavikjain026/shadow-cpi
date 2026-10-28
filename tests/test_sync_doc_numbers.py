"""tools/sync_doc_numbers.py: README and Devpost are rendered from templates that type no number. Offline, no calls."""
import re
import shutil
from datetime import date, datetime
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
    """The headline table: the pre-registered initial pass is the primary count, date test and finance check in
    separate rows, never summed (on either pass); the update after the archive retry follows, explained in a footnote."""
    out = S.render((ROOT / "docs/templates/README.md").read_text(), values)
    top = out.split("## Time-locked search leakage")[0]
    v = {k: int(values[k]) for k in ("dt_cases", "fin_events", "dt_nodates", "dt_dated", "fin_nodates", "fin_dated",
                                     "dt_dated_retry", "fin_dated_retry", "dt_nodates_retry", "fin_nodates_retry",
                                     "rr_dt_failed")}
    assert "| Leaks, measured (pre-registered initial pass) |" in top
    assert (f"| Date test ({v['dt_cases']} cases) | **{v['dt_nodates']} of {v['dt_cases']}** "
            f"(Wilson {values['dt_nodates_w']}) | **{v['dt_dated']} of {v['dt_cases']}** (Wilson {values['dt_dated_w']}) |"
            in top)
    assert (f"| {v['fin_nodates']} of {v['fin_events']} ({values['fin_nodates_w']}) | {v['fin_dated']} of "
            f"{v['fin_events']} ({values['fin_dated_w']}) |" in top)
    assert (f"{v['dt_nodates_retry']} of {v['dt_cases']} with no dates (Wilson {values['dt_nodates_retry_w']}) after "
            f"retrying the {v['rr_dt_failed']} archive lookups that had failed") in " ".join(top.split())
    total = v["dt_cases"] + v["fin_events"]
    for summed in (v["dt_dated"] + v["fin_dated"], v["dt_nodates"] + v["fin_nodates"],
                   v["dt_dated_retry"] + v["fin_dated_retry"], v["dt_nodates_retry"] + v["fin_nodates_retry"]):
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
    pg = lambda q, n: {"changed": True, "quote_present": q, "number_changed": n}   # noqa: E731
    fields = {"runs": [{**run("2026-10-28", 62, 3), "pages": [pg(True, "no"), pg(False, "yes"), pg(False, "unknown")]}]}
    assert S.drift_phrase(fields, as_of) == (
        "3 of 62 radar pages had changed since they were saved; cited quote still present on 1 of 3; "
        "cited number changed on 1 of 3 (one run, 28 Oct 2026 IST)")
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
                                                                             "docs/gallery/README.md",
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


def test_620_of_659_always_carries_its_date():
    """Every doc that states the auto_parameters count also says when it was measured (read from the arm T files)
    and, in README and Devpost, what the 27 Oct re-check showed. The video script is hand-typed, so it is checked here."""
    v = S.facts(ST, date(2026, 10, 27))
    count = re.compile(r"620 of 659|620/659")
    assert (v["auto_oct"], v["auto_results"]) == ("620", "659")
    for doc in ("README.md", "docs/devpost_draft.md"):     # rendered from the template; sync --check ties the file
        paras = [p for p in S.render((ROOT / S.TEMPLATES[doc]).read_text(), v).split("\n\n") if count.search(p)]
        assert paras, doc
        assert all(v["auto_note"] in " ".join(p.split()) for p in paras), doc
        assert sum(len(count.findall(p)) for p in paras) == sum(p.count(v["auto_note"]) for p in paras), doc
    shots = [l for l in (ROOT / "docs/video_script.md").read_text().splitlines() if count.search(l)]
    day = " ".join(v["auto_date"].split()[:2])
    assert shots and all(f"auto_parameters, {day}: 620/659" in l for l in shots)
    spoken = datetime.strptime(v["auto_date"], "%d %b %Y")          # the voice-over says it aloud: "22 October"
    voice = [l for l in shots if "six hundred twenty of six hundred fifty-nine" in l]
    assert voice and all(f"when we tested on {spoken.day} {spoken:%B}, six hundred twenty of" in l for l in voice)


def test_devpost_opens_with_the_finding_and_the_reuse(values):
    """The Devpost headline: two lines, at most 40 words, the measured date-test counts and what a Tavily user can reuse."""
    out = S.render((ROOT / "docs/templates/devpost.md").read_text(), values)
    lines = re.search(r"<!-- headline:start -->(.*?)<!-- headline:end -->", out, re.S).group(1).strip().splitlines()
    assert len(lines) == 2 and len(" ".join(lines).split()) <= 40
    first, update = lines[0].split("Update:")
    assert "pre-registered" in first
    assert f"no dates, {values['dt_nodates']} of {values['dt_cases']}" in first
    assert f"`filter_by_published_date`, {values['dt_dated']} of {values['dt_cases']}" in first
    assert f"{values['dt_nodates_retry']} of {values['dt_cases']} after retrying" in update
    assert all(w in lines[1] for w in ("timelocked_search", "extract_as_of", "Colab"))


def test_gallery_images_and_captions():
    """docs/gallery: four 1600x900 PNGs, each shown in the captions file; the R196 caption matches the asof demo."""
    from PIL import Image
    readme = (ROOT / "docs/gallery/README.md").read_text()
    pngs = sorted((ROOT / "docs/gallery").glob("*.png"))
    assert len(pngs) == 4
    for p in pngs:
        assert Image.open(p).size == (1600, 900), p.name
        assert f"]({p.name})" in readme, p.name
    demo = S.load("results/asof_demo_r196.json")
    assert f"**{demo['as_of']['provenance']['reason']}**" in readme


def test_video_reuse_shot():
    """The reuse shot: one sentence of voice-over, at most ten words on screen, and the script still fits 2:50."""
    rows = [[c.strip() for c in l.strip().strip("|").split("|")]
            for l in (ROOT / "docs/video_script.md").read_text().splitlines() if re.match(r"\| \d:\d\d-", l)]
    shot = next(r for r in rows if "extract_as_of" in r[1])
    assert shot[2] == '"Take the time lock, the as-of reader, or run our leak check with your own Tavily key."'
    assert all(w in shot[1] for w in ("timelocked_search", "Open in Colab"))
    assert len(shot[3].strip('"').replace("·", " ").split()) <= 10
    m, s = rows[-1][0].split("-")[1].split(":")
    assert int(m) * 60 + int(s) <= 170


def test_no_doc_calls_the_preregistered_result_a_sensitivity():
    """The pre-registered initial pass is the primary result everywhere; nothing labels it a sensitivity."""
    docs = [*S.TEMPLATES, *S.TEMPLATES.values(), "docs/video_script.md", "tools/sync_doc_numbers.py",
            "app_pages/leak_demo.py", "app_pages/field_report.py"]
    hits = [d for d in docs if re.search(r"sensitivity", (ROOT / d).read_text(), re.I)]
    assert hits == []


def test_check_p_flagged_pages_split_exactly(values):
    """README: the flagged pages are stated as the sum of their four outcomes, later content included."""
    n = {k: int(values[k]) for k in ("p_flagged", "p_later", "p_furniture", "p_benign", "p_unclear")}
    assert n["p_flagged"] == n["p_later"] + n["p_furniture"] + n["p_benign"] + n["p_unclear"]
    out = " ".join(S.render((ROOT / "docs/templates/README.md").read_text(), values).split())
    assert (f"{n['p_flagged']} pages held a later date somewhere in the text, mostly as page furniture; each has one "
            f"outcome: {n['p_later']} later content (the page just counted), {n['p_furniture']} in date bars, sidebars "
            f"and related links, {n['p_benign']} benign, {n['p_unclear']} unclear.") in out


def test_replay_score_names_its_post_scoring_correction(values):
    import json
    sl = json.loads((ROOT / "results/score_lock.json").read_text())
    assert values["mae_c_before"] == f"{sl['history'][-1]['mae']['c']:.3f}" != values["mae_c"]
    phrase = (f"pre-registered, with one disclosed post-scoring correction ({values['mae_c_before']} → "
              f"{values['mae_c']}")
    for tmpl in ("docs/templates/README.md", "docs/templates/devpost.md"):
        out = " ".join(S.render((ROOT / tmpl).read_text(), values).split())
        assert phrase in out and "frozen before scoring" not in out, tmpl


def test_valid_evidence_lost_always_says_which_pass(values):
    """Every 'x of 40' valid-evidence count names the initial pass (the after-retry total differs)."""
    for tmpl in [*S.TEMPLATES.values()]:
        out = " ".join(S.render((ROOT / tmpl).read_text(), values).split())
        for k in ("dt_lost_filter", "dt_lost_pagecheck"):
            for m in re.finditer(rf"\b{values[k]} of (the date test's )?{values['dt_valid_total']}\b", out):
                assert "initial pass" in out[m.start():m.end() + 160], (tmpl, out[m.start():m.end() + 160])


def test_python_requirement_line(values):
    import json
    assert values["python_min"] == "3.10"
    assert values["python_tested"] == json.loads((ROOT / "results/python_env.json").read_text())["python"]
    out = S.render((ROOT / "docs/templates/README.md").read_text(), values)
    assert f"Python {values['python_min']}+ (tested on {values['python_tested']})." in out


SPOKEN = {**dict(enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
                           "fifteen sixteen seventeen eighteen nineteen twenty".split())), 40: "forty"}


def test_video_leak_shot_matches_the_results(values):
    """The video script is hand-typed: its leak shot leads with the pre-registered initial pass, gives the retry as
    the update, and labels the valid-evidence cost with its pass; every count matches the results files."""
    v = {k: int(values[k]) for k in ("dt_cases", "dt_nodates", "dt_dated", "dt_nodates_retry", "rr_dt_failed",
                                     "dt_lost_filter", "dt_valid_total")}
    shot = next(l for l in (ROOT / "docs/video_script.md").read_text().splitlines() if "Field Report leak table" in l)
    w = {k: SPOKEN[n] for k, n in v.items()}
    assert (f"With no dates, {w['dt_nodates']} of {w['dt_cases']} searches met our confirmed-leak rule; "
            f"{w['dt_nodates_retry']} after we retried {w['rr_dt_failed']} archive lookups that had failed.") in shot
    assert f"published-date filter: {w['dt_dated']} of {w['dt_cases']}." in shot
    assert (f"The cost, on the initial pass: the filter dropped {w['dt_lost_filter']} of {w['dt_valid_total']} "
            "pieces of valid evidence.") in shot
    lo, hi = (values["dt_nodates_w"].replace("–", "-"), values["dt_dated_w"].replace("–", "-"))
    assert (f'"{v["dt_nodates"]}/{v["dt_cases"]} → {v["dt_dated"]}/{v["dt_cases"]}, pre-registered '
            f'(95%: {lo} → {hi})"') in shot
    assert f'"Update: {v["dt_nodates_retry"]}/{v["dt_cases"]} after retrying {v["rr_dt_failed"]} failed' in shot
    assert f'"Cost: {v["dt_lost_filter"]}/{v["dt_valid_total"]} valid evidence dropped (initial pass)"' in shot
