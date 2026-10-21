"""Every app page loads with the REAL results files (no sample data), and Home shows numbers from those files.
No API call is made: 'Run live' is tested with live_run.gate / run_live replaced by fakes."""
import json
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PAGES = ["home", "evidence", "replay", "tavily_trace", "flight_recorder", "archive", "brief"]
LOCK = json.loads((ROOT / "results" / "score_lock.json").read_text())
AUDIT = json.loads((ROOT / "results" / "app" / "audit_summary.json").read_text())


@pytest.fixture(autouse=True)
def no_keys(monkeypatch):
    monkeypatch.chdir(ROOT)
    for k in ("SCPI_TAVILY_API_KEY", "SCPI_NEBIUS_API_KEY", "SHADOW_CPI_DATA_DIR", "RUN_LIVE_ENABLED"):
        monkeypatch.delenv(k, raising=False)


def load(page, session=None):
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    for k, v in (session or {}).items():
        at.session_state[k] = v
    at.run()
    if page != "home":
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
        assert "sealing on 29 Oct" in [m.value for m in at.metric]
    assert "P(headline ≥ 6.0%)" in text
    assert "Official October 2026 CPI in" in text and "Thu 12 Nov 2026, 4:00 PM IST" in text
    board = at.dataframe[0].value
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
    assert "fewer than 150 credits" in text and "Saved run" in text


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
    funnel, calls, failures = (at.dataframe[i].value for i in range(3))
    assert len(funnel) == len(t["funnel"]) and len(calls) == t["n_calls"] and len(failures) == len(t["failures"])
    assert any("0 addresses" in r for r in failures["Result"]) and any("image" in r for r in failures["Result"])


def test_replay_scoreboard_matches_score_lock():
    at = load("replay")
    board = at.dataframe[0].value
    assert list(board["Average miss (percentage points)"])[:5] == [f"{LOCK['mae'][k]:.3f}"
                                                                   for k in ("c", "a", "b", "c_strict", "B1")]
    text = all_text(at)
    assert "never used to tune anything" not in text
    assert ("Rules were frozen before scoring. After scoring we made only logged bug fixes, found by an independent "
            "audit, and we show the scores before and after.") in text


def test_saved_run_shows_window_replay_date_searches_credits():
    s = json.loads((ROOT / "results" / "app" / "saved_run.json").read_text())
    text = all_text(load("home"))
    assert f"Evidence window {s['evidence_window'][0]} to {s['evidence_window'][1]}" in text
    assert f"replayed from saved results on {s['replayed_on']}" in text
    assert f"{s['n_searches']} searches" in text and f"{s['credits']} credits when first run" in text
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
