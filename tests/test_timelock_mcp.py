"""mcp/server.py: the tool on saved responses (no key, no network); registration checked with a stand-in FastMCP
when the mcp package is not installed."""
import importlib.util
import inspect
import json
import sys
import types
from pathlib import Path

import pytest

from timelock import TimeLockError

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures" / "timelock"
Q, CUT = "RBI monetary policy repo rate decision October 2026", "2026-10-06"


def load_server():
    spec = importlib.util.spec_from_file_location("timelock_mcp_server", ROOT / "mcp" / "server.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Fake:
    def __init__(self, response):
        self.response, self.sent = response, []

    def search(self, query, **params):
        self.sent.append(params)
        return self.response


def test_tool_on_the_saved_rbi_response(monkeypatch):
    server = load_server()
    monkeypatch.setenv("TIMELOCK_REPLAY", str(FIX / "rbi_2026-10-06_locked.json"))
    out = server.search(Q, CUT, topic="news")
    assert out["counts"] == {"safe": 5, "date_flag": 0, "leak": 0}
    assert out["request_id"] == "5e7387cb-67c8-455d-931d-fab9b7523f49" and out["window"] == ["2026-09-07", CUT]
    assert all(r["title"] and r["content"] for r in out["results"])
    json.dumps(out)                                                       # MCP returns it as JSON


def test_leaks_and_undated_results_come_back_without_their_text():
    server = load_server()
    resp = json.loads((FIX / "rbi_2026-10-06_unlocked.json").read_text(encoding="utf-8"))["response"]
    resp = {**resp, "results": resp["results"] + [{"url": "https://x.in/undated", "title": "t", "content": "c"}]}
    fake = Fake(resp)
    out = server.run(fake, Q, CUT, topic="news", include_domains=None, include_raw_content=True)
    assert out["counts"] == {"safe": 2, "date_flag": 1, "leak": 3}
    for r in out["results"]:
        if r["status"] == "safe":
            assert r["url"] and r["content"] and "raw_content" not in r
        else:                                            # no text and no full URL: slugs can state the outcome
            assert set(r) == {"domain", "published_date", "url_date", "page_date", "status"} and r["domain"]
    assert not any("repo-rate" in json.dumps(r) for r in out["results"] if r["status"] == "leak")
    assert fake.sent[0]["include_raw_content"] is True and "include_domains" not in fake.sent[0]
    with pytest.raises(TimeLockError):
        server.run(fake, Q, CUT, end_date="2026-10-07")


def test_registered_with_fastmcp(monkeypatch):
    server = load_server()
    try:
        import mcp.server.fastmcp  # noqa: F401
    except ImportError:                                  # stand-in with the same tool() decorator shape
        reg = {}

        class FastMCP:
            def __init__(self, name):
                reg["name"] = name

            def tool(self, name=None):
                def deco(fn):
                    reg[name] = fn
                    return fn
                return deco
        fake = types.ModuleType("mcp.server.fastmcp")
        fake.FastMCP = FastMCP
        for m in ("mcp", "mcp.server"):
            monkeypatch.setitem(sys.modules, m, types.ModuleType(m))
        monkeypatch.setitem(sys.modules, "mcp.server.fastmcp", fake)
        server.build_server()
        assert reg == {"name": "timelock", "timelocked_search": server.search, "extract_as_of": server.as_of,
                       "check_leaks": server.check_leaks}
    else:
        assert server.build_server() is not None
    params = inspect.signature(server.search).parameters
    assert list(params)[:2] == ["query", "cutoff"] and all(p.annotation is not inspect._empty
                                                           for p in params.values())
    params = inspect.signature(server.as_of).parameters
    assert list(params)[:2] == ["url", "cutoff"] and all(p.annotation is not inspect._empty for p in params.values())
    params = inspect.signature(server.check_leaks).parameters
    assert list(params) == ["results_json", "cutoff", "report_to_tavily"] and all(p.annotation is not inspect._empty
                                                              for p in params.values())


def test_as_of_tool_on_fakes(monkeypatch):
    from tests.test_timelock_asof import CUT, LIVE_CHANGED, OLD_HTML, URL, FakeTavily, FakeWayback
    server = load_server()
    wb = FakeWayback([("20260707101500", "A"), ("20260709080000", "B")], {"20260707101500": OLD_HTML})
    out = server.run_as_of(FakeTavily(LIVE_CHANGED), URL, CUT, max_chars=10, archive=wb)
    assert out["provenance"]["source"] == "wayback_asof" and out["text"] == "TCS Q1 pre" and out["truncated"]
    refused = server.run_as_of(FakeTavily(LIVE_CHANGED), URL, CUT, archive=FakeWayback([("20260709080000", "B")]))
    assert refused["text"] is None and refused["provenance"]["reason"] == "no as-of copy"
    json.dumps(out)
    monkeypatch.setenv("TIMELOCK_REPLAY", str(FIX / "rbi_2026-10-06_locked.json"))
    with pytest.raises(ValueError, match="live Tavily key"):
        server.as_of(URL, CUT)


@pytest.mark.parametrize("call,code,field", [
    (lambda s: s.search(Q, "06/10/2026"), "invalid_date", "cutoff"),
    (lambda s: s.search(Q, "20261006"), "invalid_date", "cutoff"),
    (lambda s: s.search(Q, "2026-02-30"), "invalid_date", "cutoff"),
    (lambda s: s.search(Q, CUT, start_date="last week"), "invalid_date", "start_date"),
    (lambda s: s.search(Q, CUT, end_date="2026-10-07"), "end_date_after_cutoff", "end_date"),
    (lambda s: s.search(Q, CUT, start_date="2026-10-02", end_date="2026-10-01"), "start_date_after_end_date",
     "start_date"),
    (lambda s: s.as_of("https://x.example/a", "yesterday"), "invalid_date", "cutoff"),
    (lambda s: s.check_leaks("[]", "2026-13-01"), "invalid_date", "cutoff"),
])
def test_bad_dates_come_back_as_a_structured_error_and_no_call_is_made(monkeypatch, call, code, field):
    server = load_server()
    monkeypatch.setattr(server, "client", lambda: pytest.fail("a refused call must not reach the client"))
    out = call(server)
    assert set(out) == {"error"} and out["error"]["code"] == code and out["error"]["field"] == field
    assert out["error"]["message"]
    if code == "invalid_date":
        assert out["error"]["expected"] == "YYYY-MM-DD"
    json.dumps(out)


def test_tool_descriptions_say_what_is_refused_and_why():
    server = load_server()
    for text in (server.search.__doc__, server.as_of.__doc__, server.check_leaks.__doc__):
        assert "Refused" in text or "Nothing is refused" in text
    doc = server.search.__doc__
    for phrase in ("end_date_after_cutoff", "invalid_date", "time_range", "auto_parameters", "slug", "UTC"):
        assert phrase in doc
    assert "no as-of copy" in server.as_of.__doc__ and "status 200" in server.as_of.__doc__
