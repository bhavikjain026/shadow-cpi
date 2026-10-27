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
        assert reg == {"name": "timelock", "timelocked_search": server.search}
    else:
        assert server.build_server() is not None
    params = inspect.signature(server.search).parameters
    assert list(params)[:2] == ["query", "cutoff"] and all(p.annotation is not inspect._empty
                                                           for p in params.values())
