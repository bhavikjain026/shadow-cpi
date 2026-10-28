"""docs/judging_ops.md: when a cap, key, balance or model fails during judging, the app shows the saved example or
saved run with a plain note, never an error box or a stack trace. Fake failing clients only, 0 credits."""
import json
import re
from pathlib import Path

import pytest

from shadow_cpi import try_it as T
from shadow_cpi.http import ApiError

ROOT = Path(__file__).resolve().parent.parent
KEY = "test-key-not-real"
st = pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402


class FailingClient:
    """A Budgeted-like client whose every call fails the way the real services do."""
    used = 0

    def __init__(self, exc):
        self.exc = exc

    def search(self, *a, **k):
        raise self.exc


FAILURES = [ApiError(432, "Tavily plan credit limit reached - upgrade or wait for the monthly reset"),
            ApiError(433, "Tavily pay-as-you-go limit reached"), ApiError(401, "Unauthorized"),
            ApiError(404, "model nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B has been retired"),
            TimeoutError("read timed out"), ApiError(0, "network error: down")]


@pytest.fixture
def app_env(monkeypatch):
    monkeypatch.chdir(ROOT)
    monkeypatch.setenv("SHADOW_CPI_NO_ANIMATION", "1")
    for k in ("SCPI_TAVILY_API_KEY", "SCPI_NEBIUS_API_KEY", "RUN_LIVE_ENABLED"):
        monkeypatch.delenv(k, raising=False)


def texts(at):
    parts = [m.value for m in at.markdown] + [c.value for c in at.caption] + [i.value for i in at.info]
    return "\n".join(parts + [w.value for w in at.warning])


def open_try_it(monkeypatch, run):
    monkeypatch.setattr(T, "setting", lambda name: KEY if name == "SCPI_TAVILY_API_KEY" else None)
    monkeypatch.setattr(T, "run", run)
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    at.run()
    at.switch_page("app_pages/try_it.py")
    at.run()
    at.text_input[0].set_value("petrol diesel price hike India May 2026")
    at.button[0].click()
    at.run()
    return at


@pytest.mark.parametrize("exc", FAILURES, ids=lambda e: type(e).__name__ + str(getattr(e, "status", "")))
def test_try_it_shows_the_saved_example_when_a_live_search_fails(app_env, monkeypatch, exc):
    def run(q, cut, runs):                                    # the real T.run, with a client that fails
        return T.run(q, cut, runs, key=KEY, tav=FailingClient(exc), st_store=T.Store([]),
                     ledger_path=Path("/nonexistent/ledger.jsonl"), usage_fetch=lambda: {
                         "account": {"plan_limit": 1000, "plan_usage": 0}})

    at = open_try_it(monkeypatch, run)
    assert not at.exception and not at.error
    t = texts(at)
    assert "Saved example, not a live run" in t and "Leak demo case F3" in t
    assert KEY not in t and "Traceback" not in t


@pytest.mark.parametrize("message", [
    "Today's 25 search credits for this page are used up (resets at 00:00 UTC).",
    "Live search is switched off on this copy of the app (no API key).",
    "Live search is paused: Tavily's usage check failed (ApiError).",
    "You have used this visit's 3 searches."])
def test_try_it_shows_the_saved_example_when_a_cap_or_key_refuses(app_env, monkeypatch, message):
    def refuse(q, cut, runs):
        raise T.Refused(message)

    at = open_try_it(monkeypatch, refuse)
    assert not at.exception and not at.error
    t = texts(at)
    assert message in t and "Saved example, not a live run" in t


def test_input_mistakes_stay_a_plain_warning_without_the_example(app_env, monkeypatch):
    def refuse(q, cut, runs):
        raise T.Refused("Type a question to start.")

    at = open_try_it(monkeypatch, refuse)
    assert not at.exception and not at.error
    assert "Type a question to start." in texts(at) and "Saved example, not a live run" not in texts(at)


@pytest.mark.parametrize("exc", FAILURES, ids=lambda e: type(e).__name__ + str(getattr(e, "status", "")))
def test_home_run_live_shows_the_saved_run_when_tavily_or_nemotron_fails(app_env, monkeypatch, exc):
    from shadow_cpi import live_run as L

    def fail(transport_exc):
        def transport(*a, **k):
            raise transport_exc
        return transport

    real = L.run_live
    monkeypatch.setattr(L, "gate", lambda n, **k: (True, ""))
    monkeypatch.setattr(L, "keys", lambda: (KEY, KEY))
    # the real run_live, with Tavily and Nebius both failing at the transport (key, cap, retired model, network)
    monkeypatch.setattr(L, "run_live", lambda *a, **k: real(*a, transport=fail(exc), nem_transport=fail(exc),
                                                            path=Path("/nonexistent/dir/live_runs.jsonl")))
    monkeypatch.setattr(L, "STATE_FILE", Path("/nonexistent/dir/live_runs.jsonl"))
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    at.run()
    at.switch_page("app_pages/home.py")
    at.run()
    run_btn = next(b for b in at.button if b.label.startswith("Run live"))
    run_btn.click()
    at.run()
    assert not at.exception and not at.error
    t = texts(at)
    assert "Saved run" in t and KEY not in t


def test_judging_ops_table_matches_the_budget_file():
    cfg = json.loads((ROOT / "config" / "budget.json").read_text())
    doc = (ROOT / "docs" / "judging_ops.md").read_text()
    rows = dict(re.findall(r"^\| `([\w.\-]+)` \| (\d+) \|", doc, re.M))
    assert len(rows) == 11
    for path, value in rows.items():
        node = cfg
        parts = path.split(".")
        if parts[0] == "caps":
            parts = ["caps", ".".join(parts[1:])]
        for p in parts:
            node = node[p]
        assert node == int(value), path
