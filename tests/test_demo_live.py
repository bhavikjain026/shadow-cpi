"""tools/demo_live.py on fake Tavily and Nemotron transports: no key, no network, 0 credits."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import demo_live as D  # noqa: E402

from shadow_cpi.budget import BudgetExceeded, Budgeted, load_budget  # noqa: E402
from shadow_cpi.nemotron import Nemotron  # noqa: E402
from shadow_cpi.recorder import Recorder  # noqa: E402
from shadow_cpi.tavily import Tavily  # noqa: E402

KEY = "tvly-NOT-A-REAL-KEY-0000"
ROLES = {"small": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B", "mid": "nvidia/nemotron-3-super-120b-a12b"}
LINE = "The JKERC approved a 6.83 percent hike in electricity tariff from 1 September 2026."
PAGE = "Jammu and Kashmir power tariff\n" + LINE + "\nRead more about the order."


def tavily_transport(results, sent):
    def fake(method, url, key, body, timeout):
        sent.append((url.rsplit("/", 1)[-1], body))
        if url.endswith("/search"):
            return {"request_id": "rid-demo-1", "results": results, "response_time": 1.2, "usage": {"credits": 1}}
        return {"results": [{"url": body["urls"][0], "raw_content": PAGE}], "failed_results": [],
                "usage": {"credits": 1}}
    return fake


def nebius_transport(gate="yes", line=2, pct=6.83):
    def fake(method, url, key, body, timeout):
        if body["response_format"]["json_schema"]["schema"]["required"] == ["answer"]:
            content = {"answer": gate}
        else:
            content = {"events": [{"item_or_service": "electricity", "seller_or_authority": "JKERC",
                                   "region": "Jammu and Kashmir", "old_price": None, "new_price": None,
                                   "pct_change": pct, "unit": None, "announced_date": None,
                                   "effective_date": "2026-09-01", "line": line}]}
        return {"choices": [{"message": {"content": json.dumps(content)}}]}
    return fake


def clients(tmp_path, results, gate="yes", line=2, pct=6.83, cfg=None):
    rec = Recorder(tmp_path / "cache", tmp_path / "log.jsonl")
    sent = []
    tav = Tavily(api_key=KEY, recorder=rec, transport=tavily_transport(results, sent))
    cfg = cfg or {**load_budget(), "spent_before_ledger": 0}
    btav = Budgeted(tav, [D.BUDGET], cfg=cfg, ledger_path=tmp_path / "ledger.jsonl")
    nem = Nemotron(api_key="nb-NOT-A-REAL-KEY", recorder=rec, transport=nebius_transport(gate, line, pct))
    return btav, nem, sent


RESULTS = [{"url": "https://example.com/jk-tariff", "title": "J&K tariff", "published_date": "2026-09-02"},
           {"url": "https://example.com/later", "title": "later", "published_date": "2026-10-05"}]


def test_end_to_end_prints_host_models_receipt_and_verified_line(tmp_path):
    tav, nem, sent = clients(tmp_path, RESULTS)
    lines = []
    found = D.run(D.load_case(), tav, nem, ROLES, "api.tokenfactory.nebius.com", out=lines.append)
    text = "\n".join(lines)
    assert "api.tokenfactory.nebius.com" in text and ROLES["small"] in text and ROLES["mid"] in text
    assert "request_id rid-demo-1" in text and found["response_sha256"] in text
    assert found["line"] == LINE and LINE in text and "VERIFIED" in text
    assert KEY not in text and "nb-NOT-A-REAL-KEY" not in text
    search = sent[0][1]
    assert search["filter_by_published_date"] is True and search["end_date"] == "2026-09-29"
    assert search["query"] == D.load_case()["query"]
    assert [e for e, _ in sent] == ["search", "extract"]           # the post-cutoff result is never read
    assert tav.used == 2 <= D.estimate() <= load_budget()["caps"][D.BUDGET]


def test_cap_is_its_own_budget_of_ten():
    assert load_budget()["caps"][D.BUDGET] == 10 and D.estimate() <= 10


def test_refuses_before_any_call_when_the_estimate_passes_the_cap(tmp_path):
    led = tmp_path / "ledger.jsonl"
    led.write_text(json.dumps({"time": "t", "call_id": "x", "endpoint": "/search", "credits": 8,
                               "budgets": [D.BUDGET]}) + "\n")
    with pytest.raises(BudgetExceeded, match="demo-live"):
        D.check_budget(ledger_path=led)


def test_gate_no_and_unverified_line_give_no_line(tmp_path):
    tav, nem, _ = clients(tmp_path, RESULTS[:1], gate="no")
    assert D.run(D.load_case(), tav, nem, ROLES, "h", out=lambda s: None)["line"] is None
    tav, nem, _ = clients(tmp_path / "b", RESULTS[:1], pct=9.99)          # the number is not in the cited line
    assert D.run(D.load_case(), tav, nem, ROLES, "h", out=lambda s: None)["line"] is None


def test_plan_mode_sends_nothing(monkeypatch, capsys):
    import shadow_cpi.tavily as T
    monkeypatch.setattr(T, "Tavily", lambda *a, **k: pytest.fail("no client may be built without --live"))
    assert D.main([]) is None
    assert "no call sent" in capsys.readouterr().out
