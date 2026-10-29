"""Every app page loads with the REAL results files (no sample data), and Home shows numbers from those files.
No API call is made: 'Run live' is tested with live_run.gate / run_live replaced by fakes."""
import json
import re
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PAGES = ["leak_demo", "try_it", "home", "evidence", "replay", "live_build", "radar", "field_report", "custody", "as_of", "research", "tavily_trace", "flight_recorder", "archive",
         "brief"]
LOCK = json.loads((ROOT / "results" / "score_lock.json").read_text())
AUDIT = json.loads((ROOT / "results" / "app" / "audit_summary.json").read_text())


@pytest.fixture(autouse=True)
def no_keys(monkeypatch):
    monkeypatch.chdir(ROOT)
    monkeypatch.setenv("SHADOW_CPI_NO_ANIMATION", "1")
    for k in ("SCPI_TAVILY_API_KEY", "SCPI_NEBIUS_API_KEY", "SHADOW_CPI_DATA_DIR", "RUN_LIVE_ENABLED"):
        monkeypatch.delenv(k, raising=False)


def load(page, session=None):
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    for k, v in (session or {}).items():
        at.session_state[k] = v
    at.run()
    if page != "leak_demo":                         # the default page
        at.switch_page(f"app_pages/{page}.py")
        at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def all_text(at):
    parts = [m.value for m in at.markdown] + [w.value for w in at.warning] + [t.value for t in at.title]
    parts += [h.value for h in at.subheader] + [m.label for m in at.metric] + [str(m.value) for m in at.metric]
    parts += [i.value for i in at.info] + [c.value for c in at.caption]
    return "\n".join(str(p) for p in parts)


@pytest.mark.parametrize("page", PAGES)
def test_page_loads_with_real_files_and_no_sample(page):
    text = all_text(load(page))
    assert "SAMPLE" not in text and "sample data" not in text.lower()


def test_no_sample_files_left():
    assert not (ROOT / "data" / "sample").exists()


def test_home_call_slot_scoreboard_and_audit():
    at = load("home")
    text = all_text(at)
    assert "Experimental nowcast" in text
    if not (ROOT / "sealed" / "2026-10.json").exists():
        if (ROOT / "results" / "nowcast_2026-10.json").exists():           # built, not sealed yet
            assert "Built but not sealed yet: sealing on 29 Oct." in [w.value for w in at.warning]
        else:
            assert "sealing on 29 Oct" in [m.value for m in at.metric]
    assert "P(headline ≥ 6.0%)" in text
    assert "Official October 2026 CPI in" in text and "Thu 12 Nov 2026, 4:00 PM IST" in text
    board = next(d.value for d in at.dataframe if "Average miss (percentage points)" in d.value.columns)
    assert list(board["Average miss (percentage points)"])[:5] == [f"{LOCK['mae'][k]:.3f}"
                                                                   for k in ("c", "a", "b", "c_strict", "B1")]
    assert list(board["Method"])[:5] == ["Shadow CPI", "Trend only", "Government prices only",
                                         "Shadow CPI, official series only", "Repeat last month"]
    assert "Economists' poll (its 6 dated months)" in list(board["Method"])
    assert ("Pass/fail rule (set before scoring): beat 'repeat last month' and 'trend only' → passed" in text)
    assert "Tavily searches the web, with dates locked, for price evidence → Nemotron on Nebius Token Factory" in text
    assert (f"Over Jan–Sep 2026: Shadow CPI missed by {LOCK['mae']['c']:.3f} percentage points on average. On the 6 "
            f"months with a published economists' poll: Shadow CPI {LOCK['mae_poll_months']['c']:.3f} vs poll "
            f"{LOCK['mae_poll_months']['poll']:.3f} (about a tie).") in text
    assert "GO" not in [w for line in text.splitlines() if not line.startswith("Codes") for w in line.split()]
    assert "after_scoring_changes.md" in text
    assert f"{AUDIT['events_checked']} events checked" in text
    assert "9 of 29" in text and "14 of 29" in text


def test_home_opens_on_saved_run_without_calls(monkeypatch):
    from shadow_cpi import live_run as L
    monkeypatch.setattr(L, "run_live", lambda *a, **k: pytest.fail("no live call on load"))
    saved = json.loads((ROOT / "results" / "app" / "saved_run.json").read_text())
    assert saved["label"] in all_text(load("home"))


def _click_run(at):
    next(b for b in at.button if b.label.startswith("Run live")).click().run()
    assert not at.exception and not at.error
    return all_text(at)


def test_run_live_off_by_default_shows_saved_run_and_makes_no_calls(monkeypatch):
    from shadow_cpi import live_run as L
    monkeypatch.setenv("SCPI_TAVILY_API_KEY", "test-not-a-key")
    monkeypatch.setenv("SCPI_NEBIUS_API_KEY", "test-not-a-key")
    monkeypatch.setattr(L, "run_live", lambda *a, **k: pytest.fail("switch is off: no run"))
    monkeypatch.setattr(L, "usage_remaining", lambda *a, **k: pytest.fail("switch is off: no /usage call"))
    text = _click_run(load("home"))
    assert "Live runs open on 1 Dec (judging period). Showing the saved run." in text and "Saved run" in text


def test_run_live_without_keys_shows_saved_run_and_message(monkeypatch):
    from shadow_cpi import live_run as L
    monkeypatch.setenv("RUN_LIVE_ENABLED", "1")
    monkeypatch.setattr(L, "run_live", lambda *a, **k: pytest.fail("must not run without keys"))
    text = _click_run(load("home"))
    assert "switched off" in text and "Saved run" in text


def test_run_live_usage_failure_or_low_balance_shows_saved_run(monkeypatch):
    from shadow_cpi import live_run as L
    monkeypatch.setenv("RUN_LIVE_ENABLED", "1")
    monkeypatch.setenv("SCPI_TAVILY_API_KEY", "test-not-a-key")
    monkeypatch.setenv("SCPI_NEBIUS_API_KEY", "test-not-a-key")
    monkeypatch.setattr(L, "credits_left", lambda *a, **k: 1000)
    monkeypatch.setattr(L, "run_live", lambda *a, **k: pytest.fail("refused run must not start"))
    monkeypatch.setattr(L, "usage_remaining", lambda *a, **k: (None, "Tavily's usage check failed (URLError)"))
    text = _click_run(load("home"))
    assert "usage check failed" in text and "Saved run" in text
    monkeypatch.setattr(L, "usage_remaining", lambda *a, **k: (120, ""))
    text = _click_run(load("home"))
    assert "fewer than 400 credits" in text and "Saved run" in text


def test_run_live_session_cap_shows_saved_run(monkeypatch):
    from shadow_cpi import live_run as L
    monkeypatch.setenv("RUN_LIVE_ENABLED", "1")
    monkeypatch.setenv("SCPI_TAVILY_API_KEY", "test-not-a-key")
    monkeypatch.setenv("SCPI_NEBIUS_API_KEY", "test-not-a-key")
    monkeypatch.setattr(L, "run_live", lambda *a, **k: pytest.fail("cap must stop the run"))
    text = _click_run(load("home", {"live_runs": 3}))
    assert "3 live runs" in text and "Saved run" in text


def test_run_live_failure_never_shows_an_error(monkeypatch):
    from shadow_cpi import live_run as L
    monkeypatch.setattr(L, "gate", lambda n, **k: (True, ""))
    monkeypatch.setattr(L, "keys", lambda: ("t", "n"))

    def boom(*a, **k):
        raise TimeoutError("network")
    monkeypatch.setattr(L, "run_live", boom)
    text = _click_run(load("home"))
    assert "could not finish (TimeoutError)" in text and "Saved run" in text


def test_run_live_success_shows_receipt(monkeypatch):
    from shadow_cpi import live_run as L
    monkeypatch.setattr(L, "gate", lambda n, **k: (True, ""))
    monkeypatch.setattr(L, "keys", lambda: ("t", "n"))
    fake = {"label": "Live run test", "events": [], "stopped": "",
            "receipt": {"tavily_calls": 2, "nemotron_calls": 1, "credits": 2, "seconds": 3}}
    monkeypatch.setattr(L, "run_live", lambda *a, **k: fake)
    text = _click_run(load("home"))
    assert "Live run test" in text and "Receipt: Tavily calls 2" in text


def test_tavily_trace_page_shows_calls_funnel_failures():
    at = load("tavily_trace")
    t = json.loads((ROOT / "results" / "app" / "tavily_trace_2026-03.json").read_text())
    assert str(t["n_calls"]) in [m.value for m in at.metric]
    text = all_text(at)
    stage = lambda x: x.replace("the (c) prediction", "the forecast")                     # noqa: E731
    assert all(stage(f["stage"]) in text and str(f["n"]) in text for f in t["funnel"])
    assert "(c) prediction" not in text and "Annex 5.3d" not in "\n".join(c.value for c in at.main.caption)
    sources = next(e for e in at.expander if e.label == "Sources")
    assert "Annex 5.3d" in sources.markdown[0].value and "f00bd45" in sources.markdown[0].value
    man = json.loads((ROOT / "manifests" / "2026-03.json").read_text())
    assert man["counts"]["events_verified"] == 0
    why = next(c.value for c in at.caption if c.value.startswith("Why price events verified is 0"))
    top = max((d for d in man["dropped"] if d["reason"].startswith("event:")), key=lambda d: d["count"])
    assert f"none of the {man['counts']['events_extracted']} candidate events" in why
    assert f"{top['reason'].removeprefix('event: ')} ({top['count']})" in why
    calls, failures = (at.dataframe[i].value for i in range(2))
    assert len(calls) == t["n_calls"] and len(failures) == len(t["failures"])
    assert any("0 addresses" in r for r in failures["Result"]) and any("image" in r for r in failures["Result"])


def test_replay_scoreboard_matches_score_lock():
    at = load("replay")
    board = at.dataframe[0].value
    assert list(board["Average miss (percentage points)"])[:5] == [f"{LOCK['mae'][k]:.3f}"
                                                                   for k in ("c", "a", "b", "c_strict", "B1")]
    text = all_text(at)
    assert "never used to tune anything" not in text
    assert (f"Rules were pre-registered, with one disclosed post-scoring correction "
            f"({LOCK['history'][-1]['mae']['c']:.3f} → {LOCK['mae']['c']:.3f}): a logged bug fix found by an "
            "independent audit; we show the scores before and after.") in text
    assert "frozen before scoring" not in text


def test_field_report_chart_defaults_to_the_preregistered_initial_pass():
    """The Field Report chart opens on the pre-registered initial pass (the primary count); the retry is the update."""
    at = load("field_report")
    radio = at.radio[0]
    assert list(radio.options) == ["Pre-registered initial pass", "After retrying the failed Wayback archive lookups"]
    assert radio.value == "Pre-registered initial pass"
    a = json.loads((ROOT / "results" / "field_report.json").read_text())["date_test"]["first_pass"]["arms"]["A"]
    assert f"no dates {a['leak_cases']} of {a['cases']}" in all_text(at)


def test_field_report_cost_of_correctness_reads_the_leakage_rows():
    rows = json.loads((ROOT / "results" / "field_report.json").read_text())["leakage"]["rows"]
    dt = {(x["run"], x["setting"]): x for x in rows if x["check"].startswith("Date test")}
    o, l1, l2 = (dt[("first pass", "no dates")], dt[("first pass", "+ filter_by_published_date")],
                 dt[("after logged retry", "+ filter_by_published_date")])
    at = load("field_report")
    assert "Cost of correctness" in [h.value for h in at.subheader]
    cards = {m.label: (m.value, m.proto.delta) for m in at.metric}
    assert cards["Credits per search: no dates → time lock"][0] == f"{o['credits_per_call']:.2f} → {l1['credits_per_call']:.2f}"
    assert cards["Median latency: no dates → time lock"][0] == f"{o['median_latency_s']:.1f} s → {l1['median_latency_s']:.1f} s"
    lost = cards["Valid evidence the time-locked search didn't return"]
    assert lost == (f"{l1['valid_total'] - l1['valid_kept']}/{l1['valid_total']}",
                    f"{l2['valid_total'] - l2['valid_kept']}/{l2['valid_total']} after retrying the failed Wayback "
                    "archive lookups")
    assert lost[0] == "12/40" and lost[1].startswith("20/48")
    assert any("pre-registered initial pass" in c.value for c in at.caption)


def test_field_report_r196_chain_reads_the_demo_files():
    a = json.loads((ROOT / "results" / "asof_demo_r196.json").read_text())
    served = json.loads((ROOT / "results" / "asof_demo_served.json").read_text())
    at = load("field_report")
    assert "Why date filters aren't enough: a page edited after the cutoff" in [h.value for h in at.subheader]
    html = next(h.proto.body for h in at.get("html") if 'class="r196"' in h.proto.body)
    day = lambda d: f"{int(d[8:10])} {__import__('datetime').date.fromisoformat(d[:10]):%b}"    # noqa: E731
    steps = re.findall(r'<span class="k">(\d) · ([^<]+)</span><span class="v">([^<]+)</span><span class="c">([^<]+)', html)
    assert steps == [("1", "Tavily date", day(a["evidence"]["tavily_date"]), "passes the search filter"),
                     ("2", "Cutoff", day(a["cutoff"]), "the question is asked as of this day"),
                     ("3", "Page edited", day(a["evidence"]["page_date"]),
                      "now links the actual result, and live Extract returns it"),
                     ("4", "extract_as_of", "refuses the page", f"no archive copy on/before {day(a['cutoff'])}")]
    line = next(c.value for c in at.caption if c.value.startswith("The page: "))
    assert "TCS results preview" in line and f"case {served['case']}" in line and "results/asof_demo_served.json" in line


def test_field_report_chart_labels_every_bar_and_marks_zero():
    src = (ROOT / "app_pages" / "field_report.py").read_text()
    assert '"Label": f"{pct(x[\'leak_rate\'])} ({x[\'leaks\']}/{x[\'n\']})"' in src
    assert 'transform_filter("datum.zero === 0")' in src and "mark_text(" in src
    at = load("field_report")
    spec = json.loads(at.get("vega_lite_chart")[0].proto.spec)
    marks = [l["mark"]["type"] if isinstance(l["mark"], dict) else l["mark"] for l in spec["layer"]]
    assert marks.count("text") == 1 and marks.count("tick") == 2


def test_saved_run_shows_window_replay_date_searches_credits():
    s = json.loads((ROOT / "results" / "app" / "saved_run.json").read_text())
    text = all_text(load("home"))
    assert f"Evidence window {s['evidence_window'][0]} to {s['evidence_window'][1]}" in text
    assert f"replayed from saved results on {s['replayed_on']}" in text
    assert f"{s['n_searches']} searches" in text and f"{s['credits']} credits when originally run" in text
    assert "Searches run" not in text


def test_evidence_defaults_to_march_and_explains_cut_2():
    at = load("evidence")
    assert at.selectbox[0].value == "2026-03"
    assert "cut 2" not in all_text(at)                         # March has the web quotes
    at.selectbox[0].set_value("2026-09").run()
    assert "replay months other than March skipped web price quotes" in all_text(at)


def test_trace_names_the_numbers_used():
    text = all_text(load("tavily_trace"))
    assert "Onion (01.1.7.4.1.01)" in text and "Silver jewellery (13.2.1.1.1.02)" in text


def test_example_brief_for_september_is_labelled():
    at = load("brief")
    assert at.selectbox[0].value == "2026-09"
    text = all_text(at)
    assert "Example from replay month — not a forecast" in text
    assert not at.error                                        # it states coverage and the range


def test_evidence_month_switch_and_filters():
    at = load("evidence")
    for opt in ("News pages", "Official series (IBJA, IOCL, PPAC)", "All"):
        at.radio[0].set_value(opt).run()
        assert not at.exception


@pytest.mark.parametrize("month", ["2026-03", "2026-04", "2026-09"])
def test_evidence_quote_count_matches_the_table(month):
    at = load("evidence")
    at.selectbox[0].set_value(month).run()
    table = at.dataframe[0].value
    text = all_text(at)
    assert f"Price quotes listed above: **{len(table)}**" in text or f"Price quotes listed above: {len(table)}" in text
    assert "quotes verified" not in text


def test_evidence_links_lines_items_and_spine():
    at = load("evidence")
    at.selectbox[0].set_value("2026-09").run()
    quotes, events = at.dataframe[0].value, at.dataframe[2].value
    assert list(quotes.columns[:2]) == ["Item", "Source"] and list(events.columns[:2]) == ["Item", "Source"]
    assert all(i[:1].isupper() for i in quotes["Item"]) and all(i[:1].isupper() for i in events["Item"])
    assert any(l.startswith("Gold 999, ₹") and l.endswith("per 10 g (IBJA daily rate)") for l in quotes["Line"])
    assert not any(str(l).lstrip().startswith("#") for df in at.dataframe for col in ("Line", "Exact line")
                   if col in df.value for l in df.value[col])
    spine = next(d.value for d in at.dataframe if "Centre" in d.value)
    assert "Days" not in spine.columns
    assert "Units as printed by DoCA; eggs and milk are labelled Rs./Kg. by the source." in all_text(at)


def test_replay_chart_toggle_and_miss_wording():
    at = load("replay")
    assert at.checkbox[0].label == "Show other methods" and at.checkbox[0].value is False
    text = all_text(at)
    assert "percentage points too low" in text or "percentage points too high" in text
    assert "missed by -" not in text
    at.checkbox[0].check().run()
    assert not at.exception


def test_flight_recorder_defaults_to_a_verified_event_chain():
    at = load("flight_recorder")
    chains = json.loads((ROOT / "results" / "app" / "event_chains.json").read_text())
    picked = chains[at.selectbox[0].value]
    assert (picked["month"], picked["item"]) == ("2026-09", "electricity")
    assert "read the page with this event" in at.code[0].value


def test_home_scan_table_has_source_column():
    at = load("home")
    scan = at.dataframe[-1].value
    assert list(scan.columns[:2]) == ["Item", "Source"]
    assert not any(str(l).startswith("#") for l in scan["Exact line"])


def test_flight_recorder_labels_credits_against_the_ledger():
    from shadow_cpi.budget import account_spent, load_budget, read_ledger
    at = load("flight_recorder")
    billed = account_spent(load_budget(), read_ledger())
    assert any(f"by Tavily's per-call counts (ledger total {billed:,})" in c.value for c in at.caption)


def test_live_build_streams_cards_and_moves_the_needle():
    run = json.loads((ROOT / "v2" / "evidence" / "run_2026-09_basket.json").read_text(encoding="utf-8"))
    at = load("live_build")
    assert [m.value for m in at.metric][:2] == [f"{run['needle']['end']:.3f}%",
                                                f"{run['measured_share']:.1%} of the basket"]
    text = all_text(at)
    assert f"Final: **{run['needle']['end']:.3f}%**" in text and "not a forecast" in text
    at.radio[0].set_value("April 2026, milk tracer (Madhya Pradesh)").run()
    tr = json.loads((ROOT / "v2" / "evidence" / "run_2026-04_milk_madhya-pradesh.json").read_text(encoding="utf-8"))
    assert not at.exception and [m.value for m in at.metric] == [f"{tr['needle']['end']:.3f}%"]


def test_v2_panels_on_live_build_and_home():
    from app_pages.v2_panels import TIME_LABEL
    run = json.loads((ROOT / "v2" / "evidence" / "run_2026-09_basket.json").read_text(encoding="utf-8"))
    at = load("live_build")
    text = all_text(at)
    assert "What Tavily adds" in text and "Time machine" in text and TIME_LABEL in text
    assert at.select_slider[0].value == run["cutoff"]
    at.select_slider[0].set_value("2026-09-01").run()
    assert not at.exception
    first = run["time_machine"][0]
    assert f"{first['yoy']:.3f}%" in [m.value for m in at.metric]
    home = all_text(load("home"))
    assert "What Tavily adds (v2, September 2026)" in home and "development data" in home


@pytest.mark.parametrize("page", ["home", "replay"])
def test_v1_vs_v2_table_reads_the_v2_locks(page):
    sc = json.loads((ROOT / "results" / "v2_score_lock.json").read_text())
    rc = json.loads((ROOT / "results" / "v2_recall_lock.json").read_text())
    at = load(page)
    assert "**v2 (experimental, stricter rules)**" in [m.value for m in at.markdown]
    df = next(d.value for d in at.dataframe if "v2" in d.value.columns)
    cells = dict(zip(df["Measure"], df["v2"]))
    assert cells["Average miss (percentage points)"] == f"{sc['v2']['mae']:.3f}"
    assert cells[f"Known price changes found directly (of {rc['total']})"] == str(rc["v2_found"])
    assert "Nano" in cells["Verified claims, by model"] and "not like-for-like" in all_text(at).lower()


def test_research_page_wording():
    text = all_text(load("research"))
    assert "Research tool, not investment advice." in text and "Designed for" in text and "used by" not in text.lower()


def test_home_shows_v3_beside_v1_labelled_experimental():
    at = load("home")
    text = all_text(at)
    subs = [h.value for h in at.subheader]
    assert any(s.startswith("Experimental v3, beside v1") for s in subs)
    v1_at = next(i for i, s in enumerate(subs) if s.endswith(" call"))
    assert subs.index(next(s for s in subs if s.startswith("Experimental v3"))) == v1_at + 1   # right under v1
    assert any(e.label == "Jan–Sep 2026: retrospective, not a test" for e in at.expander)
    assert "v3/PREREG.md" in " ".join(c.value for c in at.caption) or "v3/PREREG.md" in text


def test_every_page_has_a_purpose_line():
    import re
    from app_pages.common import PAGE_GUIDES
    titles = set()
    for f in (ROOT / "app_pages").glob("*.py"):
        titles.update(re.findall(r'^header\("([^"]+)"', f.read_text(encoding="utf-8"), re.M))
    assert titles | {"Leak demo"} == set(PAGE_GUIDES) and len(titles) == 14   # Leak demo opens with brand(), no header()
    at = load("leak_demo")
    assert PAGE_GUIDES["Leak demo"] in [c.value for c in at.caption]


def test_sidebar_page_guide_lists_all_15_pages_with_link_and_description():
    from app_pages.common import PAGE_GUIDES
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    guide = [e for e in at.sidebar.expander if e.label == "Page guide"]
    assert len(guide) == 1 and not guide[0].proto.expanded
    assert guide[0].proto.icon == ":material/menu_book:"
    captions = [c.value for c in guide[0].caption]
    assert captions == list(dict.fromkeys(captions)) and len(captions) == 15 and set(captions) == set(PAGE_GUIDES.values())
    kids = list(guide[0].children.values())
    links = [k for k in kids if k.type == "page_link"]
    assert len(links) == 15 and all(k.proto.page_script_hash or k.proto.page for k in links)
    assert [k.type for k in kids] == ["page_link", "caption"] * 15                  # each link followed by its line
    assert [k.proto.label for k in links][:5] == ["Leak demo", "Field Report", "Try it: search the past",
                                              "October forecast", "Radar"]   # nav order
    assert not [e for e in at.main.expander if e.label == "Page guide"]            # no second copy in the main area


@pytest.mark.parametrize("page", PAGES)
def test_no_page_renders_a_bare_none(page):
    """A bare expression statement (a conditional that calls a function, say) is printed by Streamlit's magic; its
    None is drawn as the code text `None`. No page may render a text element that is only None."""
    at = load(page)
    texts = [m.value for m in at.markdown] + [c.value for c in at.caption] + [t.value for t in at.text]
    assert [t for t in texts if str(t).strip().strip("`") in ("None", "null")] == []


def test_pages_have_no_bare_expression_statements():
    """The same fault, found in the source: only calls and docstrings may stand alone as a statement."""
    import ast
    bad = []
    for f in sorted((ROOT / "app_pages").glob("*.py")) + [ROOT / "app.py"]:
        for n in ast.walk(ast.parse(f.read_text())):
            if (isinstance(n, ast.Expr) and not isinstance(n.value, (ast.Call, ast.Await, ast.Yield, ast.YieldFrom))
                    and not (isinstance(n.value, ast.Constant) and isinstance(n.value.value, str))):
                bad.append(f"{f.name}:{n.lineno}")
    assert bad == []


# ---------- review fixes ----------
def test_v3_panel_never_says_sealed_unless_the_bundle_files_and_the_tag_exist(monkeypatch, tmp_path):
    from app_pages import v3_panel as V
    from app_pages import common as C
    (tmp_path / "sealed").mkdir()
    monkeypatch.setattr(C, "ROOT", tmp_path)
    monkeypatch.setattr(V, "_tag_exists", lambda tag: False)
    assert V.v3_sealed("2026-10") is False
    (tmp_path / "sealed/2026-10.v3.json").write_text("{}")
    (tmp_path / "sealed/2026-10.bundle.sha256").write_text("x")
    assert V.v3_sealed("2026-10") is False                       # files but no tag
    monkeypatch.setattr(V, "_tag_exists", lambda tag: tag == "seal-2026-10-bundle")
    assert V.v3_sealed("2026-10") is True
    (tmp_path / "sealed/2026-10.v3.json").unlink()
    assert V.v3_sealed("2026-10") is False                       # tag but no v3 file


def test_home_v3_panel_says_it_was_not_sealed_for_october():
    from app_pages import v3_panel as V
    assert not (ROOT / "sealed/2026-10.v3.json").exists()        # the real state this test describes
    at = load("home")
    text = all_text(at) + " " + " ".join(c.value for c in at.caption)
    assert V.NOT_SEALED in text
    assert "sealed right after v1" not in text and "Sealed with v1 in one hash bundle" not in text
    assert "docs/after_scoring_changes.md" in text


def test_tagline_is_the_same_in_the_app_and_both_templates():
    from app_pages import common as C
    for rel in ("docs/templates/README.md", "docs/templates/devpost.md", "README.md", "docs/devpost_draft.md"):
        text = " ".join((ROOT / rel).read_text().split())
        assert C.TAGLINE in text, rel
        assert "searches the past without cheating" not in text, rel
    assert "Prize focus: Best Use of Tavily. Also entering: Best Apps & Agents track." in (
        ROOT / "docs/devpost_draft.md").read_text()
    assert "The judged version will be the git tag" in (ROOT / "docs/devpost_draft.md").read_text()


def test_leak_demo_caption_and_box_and_the_two_new_captions():
    at = load("leak_demo")
    text = " ".join(c.value for c in at.caption) + " " + " ".join(m.value for m in at.markdown)
    leak = json.loads((ROOT / "results/leak_demo.json").read_text())
    f3 = next(c for c in leak["cases"] if c["id"] == "F3")
    all_ok = all(r["label"].startswith(("confirmed pre-cutoff", "valid")) for r in f3["locked"]["results"])
    assert ("every result was dated before it (and Wayback confirmed it)." in text) == all_ok
    assert "every result was dated before it" in text and "every result is from before it" not in text
    c = json.loads((ROOT / "results/replication.json").read_text())["pooled"]["price"]["arms"]["C"]
    from app_pages.common import wilson95
    lo, hi = wilson95(c["leak_cases"], c["cases"])
    assert f"we detected none in {c['cases']} cases (95% interval {lo:.0%}–{hi:.0%})".replace("%–", "–") in text
    fr = load("field_report")
    assert any(x.value.startswith("This compares who writes the search (query planning)") for x in fr.caption)
    ev = load("evidence")
    assert any(x.value == "Showing the selected month; October's live events are on Radar." for x in ev.caption)


def test_field_report_has_a_closed_exploratory_analyses_block_that_reads_the_results():
    at = load("field_report")
    assert not at.exception
    ex = [e for e in at.expander if e.label == "Exploratory analyses"]
    assert len(ex) == 1
    fd = json.loads((ROOT / "results" / "filter_drops.json").read_text())
    shown = " ".join(m.value for m in ex[0].markdown) + " ".join(c.value for c in ex[0].caption)
    assert f"{fd['not_returned']} of {fd['valid_total']}" in shown and fd["label"].capitalize() in shown
