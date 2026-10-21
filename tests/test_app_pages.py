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
    assert list(board["Mean miss (pp)"])[:5] == [f"{LOCK['mae'][k]:.3f}" for k in ("a", "b", "c", "c_strict", "B1")]
    assert "Economists' poll (its 6 dated months)" in list(board["Method"])
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
    board = load("replay").dataframe[0].value
    assert list(board["Mean absolute miss"])[:5] == [f"{LOCK['mae'][k]:.3f} pp"
                                                     for k in ("a", "b", "c", "c_strict", "B1")]


def test_evidence_month_switch():
    at = load("evidence")
    at.selectbox[0].set_value("2026-03").run()
    at.radio[0].set_value("Tavily (web)").run()
    assert not at.exception
