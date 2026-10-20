"""Load every app page with the SAMPLE data and check it renders without errors (no API calls, no keys)."""
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PAGES = ["home", "evidence", "replay", "flight_recorder", "archive", "brief"]


@pytest.fixture(autouse=True)
def sample_data(monkeypatch):
    monkeypatch.delenv("SHADOW_CPI_DATA_DIR", raising=False)
    monkeypatch.chdir(ROOT)


def load(page):
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30)
    at.run()
    if page != "home":
        at.switch_page(f"app_pages/{page}.py")
        at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def all_text(at):
    parts = [m.value for m in at.markdown] + [w.value for w in at.warning] + [t.value for t in at.title]
    parts += [h.value for h in at.subheader] + [m.label for m in at.metric]
    return "\n".join(str(p) for p in parts)


@pytest.mark.parametrize("page", PAGES)
def test_page_loads_with_sample_data(page):
    at = load(page)
    assert "SAMPLE DATA" in all_text(at)


def test_home_shows_nowcast_range_and_seal():
    at = load("home")
    text = all_text(at)
    assert "experimental nowcast" in text
    assert "5.31%" in [m.value for m in at.metric]
    assert "4.86% to 5.82%" in text
    assert "8 of 9" in text
    assert "PASS" in " ".join(s.value for s in at.success)


@pytest.mark.parametrize("label, expect", [("Try to prove this wrong", "Range unchanged"),
                                           ("Run now", "live scans left today")])
def test_home_buttons_show_cached_result(label, expect):
    at = load("home")
    next(b for b in at.button if b.label == label).click().run()
    assert not at.exception
    text = all_text(at)
    assert expect in text
    assert "Live" in " ".join(i.value for i in at.info)
    assert "Receipt: Tavily calls" in " ".join(c.value for c in at.caption)


def test_evidence_month_switch_and_source_filter():
    at = load("evidence")
    at.selectbox[0].set_value("2026-09").run()
    at.radio[0].set_value("Tavily (web)").run()
    assert not at.exception


def test_flight_recorder_item_trace():
    at = load("flight_recorder")
    at.selectbox[0].set_value("event:milk").run()
    assert not at.exception
    assert "chase:milk" in "\n".join(c.value for c in at.code)


def test_replay_scoreboard_has_all_methods():
    at = load("replay")
    board = at.dataframe[0].value
    assert list(board["Method"]) == ["(a) Trend only", "(b) Government price spine only",
                                     "(c) Spine + Tavily evidence", "B1 (last month's rate)", "Economists' poll"]
