"""X-Project-ID: shadow-cpi goes on Tavily calls only, and never touches the cache key. Fakes only, 0 credits."""
import io
import json
import urllib.request

from shadow_cpi import http as H
from shadow_cpi.recorder import Recorder, request_hash
from shadow_cpi.tavily import Tavily


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def capture(monkeypatch):
    seen = []

    def fake_urlopen(req, timeout):
        seen.append({k.lower(): v for k, v in req.header_items()})
        return Resp(b'{"results": []}')

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return seen


def test_header_is_sent_to_tavily_and_not_to_other_hosts(monkeypatch):
    seen = capture(monkeypatch)
    H.request_json("POST", "https://api.tavily.com/search", "k", {"query": "q"})
    H.request_json("POST", "https://api.tokenfactory.nebius.com/v1/chat/completions", "k", {"model": "m"})
    assert seen[0]["x-project-id"] == "shadow-cpi" and seen[0]["authorization"] == "Bearer k"
    assert "x-project-id" not in seen[1]


def test_cache_key_ignores_headers(monkeypatch, tmp_path):
    seen = capture(monkeypatch)
    rec = Recorder(tmp_path / "cache", tmp_path / "log.jsonl")
    tav = Tavily(api_key="k", recorder=rec)
    tav.search("RBI repo rate", max_results=1)
    assert seen[0]["x-project-id"] == "shadow-cpi"
    body = {"query": "RBI repo rate", "max_results": 1, "search_depth": "basic", "include_usage": True}
    key = request_hash("tavily", "/search", body)                         # body only: no header in the key
    assert (tmp_path / "cache" / "tavily" / f"{key}.json").exists()
    assert json.loads((tmp_path / "log.jsonl").read_text().splitlines()[0])["cache_key"] == key
    tav.search("RBI repo rate", max_results=1)                            # served from the cache: no second call
    assert len(seen) == 1
