"""timelock/langchain.py and mcp check_leaks: fake clients and inline data only, no network, no key."""
import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from timelock import TimeLockError
from tests.test_timelock_mcp import load_server

ROOT = Path(__file__).resolve().parent.parent
CUT = "2026-10-06"
RESPONSE = {"request_id": "r1", "results": [
    {"url": "https://a.in/news/2026/10/05/preview", "title": "ta", "content": "ca", "published_date": "2026-10-05",
     "raw_content": "full text"},
    {"url": "https://b.in/leaky", "title": "tb", "content": "cb", "published_date": "2026-10-08"},
    {"url": "https://c.in/undated", "title": "tc", "content": "cc"}]}


class Fake:
    def __init__(self, response):
        self.response, self.sent = response, []

    def search(self, query, **params):
        self.sent.append({"query": query, **params})
        return self.response


def test_importing_timelock_does_not_import_langchain():
    code = ("import sys; sys.modules['langchain_core'] = None; import timelock; "
            "assert 'timelock.langchain' not in sys.modules; print('ok')")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 0 and out.stdout.strip() == "ok", out.stderr


def test_missing_langchain_gives_a_clear_import_error(monkeypatch):
    monkeypatch.delitem(sys.modules, "timelock.langchain", raising=False)
    monkeypatch.setitem(sys.modules, "langchain_core", None)               # None makes the import fail
    monkeypatch.setitem(sys.modules, "langchain_core.tools", None)
    with pytest.raises(ImportError, match=r'pip install "timelock\[langchain\]"'):
        importlib.import_module("timelock.langchain")


class TestTool:
    @pytest.fixture
    def mod(self):
        pytest.importorskip("langchain_core")
        return importlib.import_module("timelock.langchain")

    def test_delegates_and_returns_only_safe_results(self, mod):
        fake = Fake(RESPONSE)
        tool = mod.TimeLockedTavilySearch(cutoff=CUT, client=fake, topic="news", max_results=3)
        out = tool.invoke({"query": "q"})
        assert fake.sent[0] == {"query": "q", "start_date": "2026-09-07", "end_date": CUT,
                                "filter_by_published_date": True, "topic": "news", "max_results": 3,
                                "search_depth": "basic", "include_published_date": True}
        assert out["counts"] == {"safe": 1, "date_flag": 1, "leak": 1} and out["window"] == ["2026-09-07", CUT]
        assert [r["url"] for r in out["results"]] == ["https://a.in/news/2026/10/05/preview"]
        assert "raw_content" not in out["results"][0] and out["request_id"] == "r1"
        assert "leaky" not in json.dumps(out) and "undated" not in json.dumps(out)
        json.dumps(out)

    def test_cutoff_is_required_and_checked(self, mod):
        with pytest.raises(Exception):
            mod.TimeLockedTavilySearch(client=Fake(RESPONSE))
        with pytest.raises(TimeLockError, match="ISO date"):
            mod.TimeLockedTavilySearch(cutoff="yesterday", client=Fake(RESPONSE)).invoke({"query": "q"})

    @pytest.mark.parametrize("name,value", [("time_range", "week"), ("days", 3), ("auto_parameters", True)])
    def test_refuses_what_the_core_refuses(self, mod, name, value):
        fake = Fake(RESPONSE)
        with pytest.raises(TimeLockError, match=name):
            mod.TimeLockedTavilySearch(cutoff=CUT, client=fake, **{name: value})
        tool = mod.TimeLockedTavilySearch(cutoff=CUT, client=fake)
        with pytest.raises(TimeLockError, match=name):
            tool.invoke({"query": "q", name: value})
        assert fake.sent == []                                             # refused before any call

    def test_end_date_past_the_cutoff_is_refused_and_narrowing_is_not(self, mod):
        fake = Fake(RESPONSE)
        tool = mod.TimeLockedTavilySearch(cutoff=CUT, client=fake)
        with pytest.raises(TimeLockError):
            tool.invoke({"query": "q", "end_date": "2026-10-07"})
        assert fake.sent == []
        tool.invoke({"query": "q", "start_date": "2026-10-01", "end_date": "2026-10-05"})
        assert (fake.sent[0]["start_date"], fake.sent[0]["end_date"]) == ("2026-10-01", "2026-10-05")


def test_check_leaks_on_mixed_dated_and_undated_results():
    server = load_server()
    results = RESPONSE["results"] + [{"url": "https://d.in/old", "published_date": "Tue, 29 Sep 2026 10:00:00 GMT"},
                                     {"url": "https://e.in/2026/10/09/x", "published_date": None},
                                     {"title": "no url, no date"}]
    out = server.check_leaks(json.dumps({"results": results}), CUT)
    assert out["checked"] == 6 and out["counts"] == {"safe": 2, "date_flag": 2, "leak": 2}
    assert out["undated"] == 2
    assert [(x["url"], x["published_date"], x["url_date"]) for x in out["leaks"]] == [
        ("https://b.in/leaky", "2026-10-08", None), ("https://e.in/2026/10/09/x", None, "2026-10-09")]
    assert out["re_read"] == ["https://b.in/leaky", "https://c.in/undated", "https://e.in/2026/10/09/x"]
    assert out["cutoff"] == CUT
    assert server.check_leaks(json.dumps(results), CUT) == out              # a bare list works too
    json.dumps(out)


def test_check_leaks_uses_a_page_date_and_rejects_bad_input():
    server = load_server()
    out = server.check_leaks(json.dumps([{"url": "https://a.in/p", "published_date": "2026-10-01",
                                          "page_date": "2026-10-10"}]), CUT)
    assert out["counts"]["leak"] == 1 and out["leaks"][0]["page_date"] == "2026-10-10"
    clean = server.check_leaks("[]", CUT)
    assert clean["counts"] == {"safe": 0, "date_flag": 0, "leak": 0} and clean["re_read"] == []
    for bad in ("not json", '"text"', "[1, 2]", '{"results": 5}'):
        with pytest.raises(ValueError):
            server.check_leaks(bad, CUT)
    with pytest.raises(TimeLockError):
        server.check_leaks("[]", "06/10/2026")
