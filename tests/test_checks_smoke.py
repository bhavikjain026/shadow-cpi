"""Runs checks.py end to end against a fake network, to make sure the script itself has no bugs."""
import os
import urllib.request

import checks
from shadow_cpi.recorder import Recorder

PAGE = "Onion prices in Delhi rose to ₹56 per kg.\nदिल्ली में प्याज के दाम बढ़कर 56 रुपये प्रति किलो हो गए हैं।"


def fake(method, url, token, body, timeout):
    if url.endswith("/models"):
        return {"data": [{"id": "nvidia/Nemotron-Nano-X"}, {"id": "nvidia/nemotron-super-y"}, {"id": "other"}]}
    if url.endswith("/chat/completions"):
        if "price" in body["messages"][1]["content"] and "PAGE" in body["messages"][1]["content"]:
            return {"choices": [{"message": {"content": '{"quotes":[{"item":"onion","price":56,"unit":"kg",'
                    '"place":"Delhi","date":null,"line":1,'
                    '"retail_or_wholesale":"retail"}]}'}}]}
        return {"choices": [{"message": {"content": '{"ok": true, "n": 3}'}}]}
    if url.endswith("/extract"):
        return {"results": [{"url": u, "raw_content": PAGE + " onion 5.54"} for u in body["urls"]],
                "failed_results": [], "usage": {"credits": 1}}
    if url.endswith("/search"):
        return {"results": [{"url": "https://x/1", "published_date": "2026-03-05"},
                            {"url": "https://x/2", "published_date": "2026-03-20"}], "usage": {"credits": 1}}
    raise AssertionError(url)


def test_checks_runs(tmp_path, monkeypatch, capsys):
    os.environ["SCPI_TAVILY_API_KEY"] = "tvly-fake"
    os.environ["SCPI_NEBIUS_API_KEY"] = "neb-fake"
    monkeypatch.setattr(checks, "TRANSPORT", fake)
    monkeypatch.setattr(checks, "MODELS_FILE", tmp_path / "models.json")
    monkeypatch.setattr(checks, "Recorder", lambda: Recorder(tmp_path / "c", tmp_path / "l.jsonl"))
    monkeypatch.setattr(checks, "read_log", lambda: [])
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(OSError("offline")))
    checks.main()
    out = capsys.readouterr().out
    assert "[FAIL]" not in out, out
    assert "tvly-fake" not in out and "neb-fake" not in out
    assert "COPY EVERYTHING BELOW" in out
