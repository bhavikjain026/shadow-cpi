"""Leak demo: the saved data (results/leak_demo.json) agrees with the results files, the page shows it with no API
call, and live mode is off by default and runs only through the credit guard. Live calls use fakes."""
import json
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
    assert "Leak demo" in t and (f"examples chosen for clarity; all {len(DATA['cases'])} in the picker and the "
                                 "totals below") in t
    s, d = DATA["totals"]["strictness"], DATA["totals"]["date"]
    assert f"**{s['missed']} of {s['quotes']}**" in t
    assert len(at.selectbox[0].options) == 1 + len(DATA["cases"])
    assert len(at.error) >= 3                      # each example highlights its leaking result
    assert "days after the cutoff" in t and "Live mode is off" in t
    table = at.table[0].value
    assert table.iloc[0, 1].startswith(f"{d['open']['first']} of {d['cases']}")


def test_picker_shows_one_case():
    at = page()
    cid = DATA["cases"][-1]["id"]
    at.selectbox[0].set_value(cid).run()
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
    assert list(df.columns) == ["Finding", "Number", "File"] and len(df) == 6


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


# ---------- ui-polish: summary line, default examples, text badges ----------
def test_summary_line_at_top_reads_the_results_file():
    at = page()
    d, s = DATA["totals"]["date"], DATA["totals"]["strictness"]
    first = at.markdown[0].value
    assert (f"No time lock: {d['open']['retry']}/{d['cases']} cases leaked (after retry). Tavily time lock: "
            f"{d['locked']['retry']}/{d['cases']}. Cost: {s['missed']} of {s['quotes']} known-good quotes missed."
            ) in first and "(#all-cases)" in first


def test_default_examples_start_rbi_then_petrol_and_drop_m7():
    at = page()
    default = at.selectbox[0].options[0]
    assert default.startswith("Examples: R1, F3") and "M7" not in default
    assert any(o.startswith("M7") for o in at.selectbox[0].options)          # still in the picker
    assert "names both the case's item and its state" in text(at)


def test_every_result_has_a_text_badge():
    at = page()
    lines = [m.value for m in at.markdown if "Tavily published_date" in m.value] + [e.value for e in at.error]
    assert lines and all(any(b in x for b in ("[LEAK]", "[OK]", "[UNCHECKED]")) for x in lines)
    assert all(":red-badge[LEAK]" in e.value for e in at.error)
