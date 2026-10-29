"""Leak demo: the saved data (results/leak_demo.json) agrees with the results files, the page shows it with no API
call, and live mode is off by default and runs only through the credit guard. Live calls use fakes."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from shadow_cpi import leak_live as LL  # noqa: E402
from shadow_cpi import live_run as L  # noqa: E402
from shadow_cpi.recorder import Recorder  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / "results" / "leak_demo.json").read_text())
FR = json.loads((ROOT / "results" / "field_report.json").read_text())


@pytest.fixture(autouse=True)
def no_keys(monkeypatch):
    monkeypatch.chdir(ROOT)
    for k in ("SCPI_TAVILY_API_KEY", "SCPI_NEBIUS_API_KEY", "RUN_LIVE_ENABLED"):
        monkeypatch.delenv(k, raising=False)


def page(session=None):
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    for k, v in (session or {}).items():
        at.session_state[k] = v
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def text(at):
    parts = [m.value for m in at.markdown] + [c.value for c in at.caption] + [e.value for e in at.error]
    parts += [i.value for i in at.info] + [w.value for w in at.warning] + [s.value for s in at.success]
    parts += [t.value for t in at.title] + [h.value for h in at.subheader]
    return "\n".join(str(p) for p in parts)


def text_without(at):
    """Captions, titles, headings and alerts (the text we write); result headlines are a third party's."""
    parts = [c.value for c in at.caption] + [t.value for t in at.title] + [h.value for h in at.subheader]
    parts += [e.value for e in at.error] + [i.value for i in at.info] + [w.value for w in at.warning]
    return "\n".join(str(p) for p in parts) + "\n"


def shown_ids(at):
    """The recommended examples' IDs, from the 'How these examples were picked' caption."""
    import re
    return re.search(r"Cases that qualify: ([A-Z0-9, ]+)", text(at)).group(1).split(", ")


# ---------- the saved data ----------
def test_34_cases_with_both_searches_and_no_key_in_any_body():
    assert sum(c["test"] == "date" for c in DATA["cases"]) == FR["date_test"]["first_pass"]["arms"]["A"]["cases"]
    assert sum(c["test"] == "finance" for c in DATA["cases"]) == FR["finance"]["first_pass"]["all_14"]["events"]
    for c in DATA["cases"]:
        for side in ("open", "locked"):
            body = c[side]["request"]
            assert not {k.lower() for k in body} & {"api_key", "authorization"}
            assert body["query"] == c["query"]
            assert body.get("filter_by_published_date") is (side == "locked")
            assert ("start_date" in body and "end_date" in body) is (side == "locked")


def test_per_case_labels_give_the_field_report_totals():
    for t, arm, n in (("date", "A", FR["date_test"]["after_retry"]["arms"]["A"]["leak_cases"]),
                      ("finance", "N", FR["finance"]["after_retry"]["all_14"]["arms"]["N"]["confirmed_events"])):
        cs = [c for c in DATA["cases"] if c["test"] == t]
        assert sum(any(r["leak"] for r in c["open"]["results"]) for c in cs) == n
        assert not any(r["leak"] for c in cs for r in c["locked"]["results"])


def test_three_examples_each_leak_open_and_none_locked():
    by_id = {c["id"]: c for c in DATA["cases"]}
    assert len(DATA["examples"]) == 3
    for cid in DATA["examples"]:
        c = by_id[cid]
        assert any(r["leak"] and r["days_after_cutoff"] > 0 and r["quote"] for r in c["open"]["results"])
        assert not any(r["leak"] for r in c["locked"]["results"])


# ---------- the page ----------
def test_home_is_the_leak_demo_with_examples_and_totals():
    at = page()
    t = text(at)
    assert (f"examples chosen for clarity; all {len(DATA['cases'])} in the picker and the "
                                 "totals below") in t
    s, d = DATA["totals"]["strictness"], DATA["totals"]["date"]
    assert f"**{s['missed']} of {s['quotes']}**" in t
    assert list(at.selectbox[0].options) == [f"Recommended examples ({len(shown_ids(at))})",
                                             f"All {len(DATA['cases'])} cases"]
    leaks = [m.value for m in at.markdown if m.value.startswith(":red-badge[LEAK]")]
    assert len(leaks) >= 3                         # each example highlights its leaking result
    assert "days after the cutoff" in t and "Everything above is saved results. For a live search" in t
    table = at.table[0].value
    assert table.iloc[0, 1].startswith(f"{d['open']['first']} of {d['cases']}")


def test_picker_shows_one_case():
    at = page()
    cid = DATA["cases"][-1]["id"]
    at.selectbox[0].set_value(f"All {len(DATA['cases'])} cases").run()
    assert len(at.selectbox[1].options) == len(DATA["cases"])
    at.selectbox[1].set_value(cid).run()
    assert not at.exception
    assert sum(cid in h.value for h in at.markdown if h.value.startswith("####")) == 1


def test_live_without_keys_never_calls(monkeypatch):
    monkeypatch.setenv("RUN_LIVE_ENABLED", "1")
    monkeypatch.setattr(LL, "run_pair", lambda *a, **k: pytest.fail("no key: no run"))
    at = page()
    at.text_input[0].set_value("RBI repo rate decision")
    at.button[0].click().run()
    assert "switched off" in text(at)


def test_live_runs_through_the_gate_and_labels_only_flag_or_safe(monkeypatch):
    monkeypatch.setenv("RUN_LIVE_ENABLED", "1")
    monkeypatch.setenv("SCPI_TAVILY_API_KEY", "test-not-a-key")
    seen = {}
    monkeypatch.setattr(L, "gate", lambda n, **k: (seen.update(k) or True, ""))
    side = {"request": {"query": "q"}, "credits": 1, "latency_s": 0.5, "request_id": "r",
            "results": [{"url": "https://a.example/x", "title": "A", "published_date": "2026-01-02", "label": "safe"},
                        {"url": "https://b.example/y", "title": "B", "published_date": None, "label": "date flag"}]}
    monkeypatch.setattr(LL, "run_pair", lambda *a, **k: {"question": "q", "cutoff": "2026-03-01",
                                                          "open": side, "locked": side})
    at = page()
    at.text_input[0].set_value("RBI repo rate decision")
    at.button[0].click().run()
    assert seen.get("tavily_only") is True and at.session_state["live_runs"] == 1
    labels = [w.value for w in at.warning] + [s.value for s in at.success]
    assert any("date flag" in x for x in labels) and any("safe" in x for x in labels)
    assert not any("leak" in x.lower() for x in labels)


def test_field_report_starts_with_six_findings():
    at = page()
    at.switch_page("app_pages/field_report.py")
    at.run()
    assert not at.exception
    df = at.table[0].value
    assert list(df.columns) == ["Finding", "Number"] and len(df) == 6
    (src,) = [e for e in at.expander if e.label == "Sources"]          # the files, in one expander
    files = " ".join(m.value for m in src.markdown)
    assert "results/field_report.json" in files and "results/leakcheck_exact_match.json" in files


# ---------- live mode, offline ----------
def fake_transport(calls):
    def t(method, url, token, body, timeout):
        calls.append(body)
        return {"results": [{"url": "https://a.example/1", "title": "before", "published_date": "2026-02-01"},
                            {"url": "https://a.example/2", "title": "after", "published_date": "Tue, 10 Mar 2026 "
                                                                                                 "10:00:00 GMT"},
                            {"url": "https://a.example/3", "title": "undated"}],
                "usage": {"credits": 1}, "request_id": "rid", "response_time": 0.7}
    return t


def test_run_pair_two_searches_labels_and_caps(tmp_path):
    calls = []
    rec = Recorder(cache_dir=tmp_path / "cache", log_file=tmp_path / "log.jsonl", use_cache=False)
    out = LL.run_pair("test-not-a-key", "  RBI   repo rate ", "2026-03-01",
                      now=datetime(2026, 12, 2, tzinfo=timezone.utc), path=tmp_path / "runs.jsonl",
                      transport=fake_transport(calls), recorder=rec, ledger_path=tmp_path / "ledger.jsonl")
    assert [c["filter_by_published_date"] for c in calls] == [False, True]
    assert calls[1]["start_date"] == "2026-01-31" and calls[1]["end_date"] == "2026-03-01"
    assert all(c["max_results"] == 5 and c["search_depth"] == "basic" and c["query"] == "RBI repo rate" for c in calls)
    assert [r["label"] for r in out["open"]["results"]] == ["safe", "date flag", "date flag"]
    assert out["open"]["credits"] == 1 and out["locked"]["credits"] == 1
    assert len((tmp_path / "runs.jsonl").read_text().splitlines()) == 1
    assert len((tmp_path / "ledger.jsonl").read_text().splitlines()) == 2
    with pytest.raises(ValueError):
        LL.run_pair("k", "   ", "2026-03-01", path=tmp_path / "runs.jsonl", transport=fake_transport([]),
                    recorder=rec, ledger_path=tmp_path / "ledger.jsonl")


def test_gate_tavily_only_needs_only_the_tavily_key(monkeypatch, tmp_path):
    monkeypatch.setenv("RUN_LIVE_ENABLED", "1")
    led = [{"credits": 0, "budgets": []}]
    ok, msg = L.gate(0, path=tmp_path / "r.jsonl", ledger=led, tavily_only=True, usage_fetch=lambda: {})
    assert not ok and "no API keys" in msg
    monkeypatch.setenv("SCPI_TAVILY_API_KEY", "test-not-a-key")
    fetch = lambda: {"account": {"plan_limit": 1000, "plan_usage": 0}}  # noqa: E731
    assert L.gate(0, path=tmp_path / "r.jsonl", ledger=led, tavily_only=True, usage_fetch=fetch) == (True, "")
    assert not L.gate(3, path=tmp_path / "r.jsonl", ledger=led, tavily_only=True, usage_fetch=fetch)[0]
    assert not L.gate(0, path=tmp_path / "r.jsonl", ledger=led, usage_fetch=fetch)[0]      # Home still needs both


def test_web_titles_cannot_inject_markdown():
    import importlib.util
    src = (ROOT / "app_pages" / "leak_demo.py").read_text()
    ns = {}
    exec(src[src.index("def link("):src.index("def case_title(")], ns)
    out = ns["link"]("Price ![x](https://t.example/p.png) [a]", "https://a.example/x(1) y")
    assert "![" not in out.replace("\\!\\[", "") and out.endswith("(<https://a.example/x(1)%20y>)")


# ---------- ui-polish / look: hero row, default examples, text badges ----------
def test_cost_card_is_the_date_tests_own_field_not_check_e():
    """Card (c) shows the date test's valid evidence dropped (locked arm C, initial pass), not check E's known-good
    quotes missed (those stay in the totals section)."""
    c = json.loads((ROOT / "results" / "date_field_test.json").read_text())["metrics"]["arms"]["C"]
    s = DATA["totals"]["strictness"]
    cost = page().metric[2]
    assert cost.label == "Cost of correctness" and cost.value == f"{c['valid_lost']} of {c['valid_total']}"
    assert "initial pass" in cost.delta and "check E" not in cost.delta
    assert "C" == __import__("tools.build_leak_demo", fromlist=["TESTS"]).TESTS["date"]["locked"]


def test_default_examples_follow_the_rule_f3_first_r1_out():
    ok = ("confirmed pre-cutoff", "valid")
    want = [c["id"] for c in DATA["cases"] if any(r["leak"] for r in c["open"]["results"])
            and c["locked"]["results"] and all(r["label"].startswith(ok) for r in c["locked"]["results"])]
    at = page()
    ids = shown_ids(at)
    assert at.selectbox[0].value == f"Recommended examples ({len(ids)})"
    assert ids[0] == "F3" and sorted(ids) == sorted(want) and "R1" not in ids
    assert not any("F3" in o for o in at.selectbox[0].options)            # no case IDs in the dropdown's labels
    assert len(at.tabs) == (len(ids) - 1 if len(ids) > 2 else 0)           # F3 is the case shown above the cards
    at.selectbox[0].set_value(f"All {len(DATA['cases'])} cases").run()
    every = at.selectbox[1].options
    assert any(o.endswith(" · R1") for o in every) and any(o.endswith(" · M7") for o in every)
    assert "RBI decision · Feb 2026 · R1" in every                         # human label built from the case


def test_card_metadata_is_short_and_finance_page_dates_said_once():
    t = text(at := page())
    assert ":gray-badge[Tavily: 21 Sep 2026] :gray-badge[Page: 21 Sep 2026] :gray-badge[Wayback: confirmed leak]" in t
    assert "not read in this test" not in t
    if any(by.startswith("R") for by in shown_ids(at)):
        assert t.count("Page dates not read in the finance check.") == 1


def test_every_result_has_a_text_badge():
    at = page()
    vals = [m.value for m in at.markdown]
    rows = [i for i, v in enumerate(vals) if v.startswith(":gray-badge[Tavily: ")]      # each card's chip row
    assert rows and all(vals[i - 1].startswith((":red-badge[LEAK]", ":green-badge[OK]", ":gray-badge[UNCHECKED]"))
                        for i in rows)
    assert all(vals[i - 1].startswith(":red-badge[LEAK]") for i in rows if "days after the cutoff" in vals[i])


# ---------- first screen: brand header ----------
def test_brand_header_leads_the_first_screen():
    from app_pages import common as C
    at = page()
    assert [t.value for t in at.title] == [C.TITLE_CLAIM] == [C.BRAND_LINE]   # the claim is the page's only H1
    md = [m.value for m in at.markdown]
    assert md.index(C.EYEBROW) < md.index(C.SUBHEAD)                          # eyebrow, H1, subhead, then the cards
    assert C.EYEBROW == "Nebius x NVIDIA Global AI Hackathon · Built on Tavily"
    assert len(C.SUBHEAD.split(". ")) == 1 and len(at.metric) == 3 and all(m.help for m in at.metric)
    banned = ("first", "beats economists", "no leaks", "scores itself", "used by", "sensitivity", "eliminates",
              "guarantees", "fixed it in every case", "every page through Tavily")
    ours = "\n".join(m.value for m in at.markdown if not m.value.startswith(":"))     # not third-party headlines
    shown = (text_without(at) + ours + " " + " ".join(m.help for m in at.metric)).lower()
    assert not [b for b in banned if re.search(rf"\b{re.escape(b)}\b", shown)]
    assert "0 of 34" not in shown and "20 of 34" not in shown
    links = [b.proto.label for b in at.get("link_button")]
    assert links == ["GitHub"] and at.get("link_button")[0].proto.url == C.GITHUB_URL
    assert [p.proto.label for p in at.main.get("page_link")][:1] == ["Field Report"]


def test_video_button_shows_only_when_its_url_is_set(monkeypatch):
    from app_pages import common as C
    monkeypatch.setattr(C, "VIDEO_URL", "https://example.com/video")
    links = {b.proto.label: b.proto.url for b in page().get("link_button")}
    assert links == {"GitHub": C.GITHUB_URL, "Watch the video": "https://example.com/video"}


def test_sidebar_brand_is_keyed_and_moved_above_the_links_by_css():
    css = (ROOT / "app_pages" / "style.css").read_text()
    assert '[data-testid="stLayoutWrapper"]:has(> .st-key-sidebar-brand) { order: -2;' in css
    assert '[data-testid="stSidebarNav"] { order: -1; }' in css
    at = page()
    assert at.sidebar.markdown[0].value == "**Shadow CPI**"


def test_use_it_block_matches_the_readme_example():
    """At most 4 lines; the timelocked_search and extract_as_of calls are the README's, modulo line breaks."""
    import re
    src = (ROOT / "app_pages" / "leak_demo.py").read_text()
    code = re.search(r'USE_IT = """(.*?)"""', src, re.S).group(1)
    assert len(code.splitlines()) <= 4
    readme = " ".join((ROOT / "README.md").read_text().split())
    for call in re.findall(r"(?:timelocked_search|extract_as_of)\(.*\)", code):
        assert " ".join(call.split()) in readme, call
    at = page()
    assert any(c.value == code for c in at.code)
    links = " ".join(m.value for m in at.markdown)
    assert "/tree/main/timelock)" in links and "colab-badge.svg" in links


def test_tab_labels_are_short():
    """tab_label() read from the page source (the page runs on import): short item, month, small grey case ID."""
    import ast
    from datetime import date
    src = (ROOT / "app_pages" / "leak_demo.py").read_text()
    tree = ast.parse(src)
    ns = {"date": date}
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "SHORT" or (
                isinstance(node, ast.FunctionDef) and node.name in ("tab_label", "case_id")):
            exec(compile(ast.Module([node], []), "leak_demo", "exec"), ns)
    by_id = {c["id"]: c for c in DATA["cases"]}
    labels = [ns["tab_label"](by_id[i]) for i in ("F3", "R2")]
    assert labels == ["Petrol hike · May 26 :gray[:small[F3]]", "RBI rate · Apr 26 :gray[:small[R2]]"]
    assert all(len(re.sub(r":gray\[:small\[\w+\]\]", "", l).strip()) <= 22 for l in labels)


def test_replication_line_reads_the_replication_file():
    """One short line under the update: the pre-registered replication's time-locked count (initial pass)."""
    c = json.loads((ROOT / "results" / "replication.json").read_text())["metrics"]["price"]["arms"]["C"]
    assert (f"Replication: {c['leak_cases']} of {c['cases']} more cases detected leaking with the time lock."
            in [x.value for x in page().caption])


def test_field_report_shows_the_replication_group_and_the_pooled_line():
    at = page()
    at.switch_page("app_pages/field_report.py")
    at.run()
    assert not at.exception
    rp = json.loads((ROOT / "results" / "field_report.json").read_text())["replication"]
    a, c = rp["first_pass"]["arms"]["A"], rp["first_pass"]["arms"]["C"]
    text = " ".join(m.value for m in at.markdown)
    assert (f"**Replication:** no dates {a['leak_cases']} of {a['cases']}" in text
            and f"{c['leak_cases']} of {c['cases']}" in text)
    pl = rp["pooled"]["arms"]["C"]
    assert "**Pilot + replication, date-test rule** (pre-registered secondary" in text
    assert f"Time lock (Tavily date filters) {pl['leak_cases']} of {pl['cases']}" in text
    cap = " ".join(x.value for x in at.caption)
    assert "Cache note (descriptive, not pre-registered)" in cap and "includes the reused pilot response" in cap


def test_benchmark_table_has_the_replication_row_apart_and_the_live_line_points_to_try_it():
    at = page()
    assert f"Pilot and finance check (the {len(DATA['cases'])}-case benchmark)" in [h.value for h in at.subheader]
    rp = json.loads((ROOT / "results/replication.json").read_text())
    a, c = rp["metrics"]["price"]["arms"]["A"], rp["metrics"]["price"]["arms"]["C"]
    df = at.table[0].value
    assert len(df) == 3 and df.iloc[2, 0].startswith("Replication (date-test rule")        # a row of its own
    assert df.iloc[2, 1].startswith(f"{a['leak_cases']} of {a['cases']}")
    assert df.iloc[2, 3].startswith(f"{c['leak_cases']} of {c['cases']}")
    assert df.iloc[0, 1].startswith(f"{DATA['totals']['date']['open']['first']} of {DATA['totals']['date']['cases']}")
    assert any(p.proto.page.endswith("try_it.py") or "try_it" in str(p.proto.page) for p in at.main.get("page_link"))
