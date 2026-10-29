"""timelock/feedback.py and check_leaks(report_to_tavily=...): payload shape, dry run by default, no send without the
flag, own request_ids only. No network: the POST is a recording stand-in."""
import importlib.util
import inspect
import json
from pathlib import Path

import pytest

from timelock import build_feedback, own_request_ids, reason_for, report_leaks, send_feedback

ROOT = Path(__file__).resolve().parent.parent
CUT, RID = "2026-04-29", "req-own-1"
LEAK = {"url": "https://example.org/news/2026/10/13/story", "published_date": "2026-10-13"}
SAFE = {"url": "https://example.org/news/2026/04/01/story", "published_date": "2026-04-01"}


class Post:
    def __init__(self):
        self.calls = []

    def __call__(self, payload, key):
        self.calls.append((payload, key))
        return {"success": True, "feedback_id": "f1"}


def load_server():
    spec = importlib.util.spec_from_file_location("timelock_mcp_server_fb", ROOT / "mcp" / "server.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_payload_shape_uses_url_or_id_and_the_documented_fields():
    p = build_feedback(RID, LEAK, "after the cutoff")
    assert p == {"request_id": RID, "urls_scores": [{"url": LEAK["url"], "comment": "after the cutoff"}]}
    assert build_feedback(RID, {**LEAK, "id": "a3f9"}, "x")["urls_scores"][0] == {"id": "a3f9", "comment": "x"}
    assert len(build_feedback(RID, LEAK, "y" * 5000)["urls_scores"][0]["comment"]) == 2000
    with pytest.raises(ValueError):
        build_feedback("", LEAK, "x")
    with pytest.raises(ValueError):
        build_feedback(RID, {}, "x")


def test_reason_names_the_dates_and_whether_an_end_date_was_sent():
    assert reason_for(LEAK, CUT) == ("published_date 2026-10-13; url date 2026-10-13: after the cutoff 2026-04-29 "
                                     "(this request sent no end_date)")
    assert reason_for(LEAK, CUT, end_date=CUT).endswith("after the requested end_date 2026-04-29")
    assert "no archive copy on or before the cutoff 2026-04-29" in reason_for(LEAK, CUT, captures=[])
    assert "earliest archive copy 2026-06-01" in reason_for(LEAK, CUT, captures=["2026-06-01"])


def test_dry_run_is_the_default_and_sends_nothing():
    post = Post()
    out = send_feedback(RID, LEAK, "r", own_request_ids={RID}, api_key="k", post=post)
    assert out["dry_run"] is True and out["payload"]["request_id"] == RID and post.calls == []


def test_real_send_only_for_own_request_ids_and_never_returns_the_key():
    post = Post()
    out = send_feedback(RID, LEAK, "r", dry_run=False, own_request_ids={RID}, api_key="SECRET", post=post)
    assert out["sent"] is True and len(post.calls) == 1 and post.calls[0][1] == "SECRET"
    assert "SECRET" not in json.dumps(out)
    other = send_feedback("someone-else", LEAK, "r", dry_run=False, own_request_ids={RID}, api_key="k", post=post)
    assert other["sent"] is False and other["skipped"] == "not_our_request" and len(post.calls) == 1
    assert send_feedback(RID, LEAK, "r", dry_run=False, api_key="k", post=post)["skipped"] == "not_our_request"


def test_failures_are_returned_not_raised(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    assert "no Tavily key" in send_feedback(RID, LEAK, "r", dry_run=False, own_request_ids={RID})["error"]

    def boom(payload, key):
        raise OSError("down")
    out = send_feedback(RID, LEAK, "r", dry_run=False, own_request_ids={RID}, api_key="k", post=boom)
    assert out["sent"] is False and out["error"].startswith("OSError")


def test_report_leaks_covers_only_flagged_results_of_own_requests():
    out = report_leaks([SAFE, LEAK, {"url": "https://example.org/undated"}], CUT, RID, own_request_ids={RID})
    assert len(out) == 1 and out[0]["payload"]["urls_scores"][0]["url"] == LEAK["url"]      # dry run by default
    foreign = report_leaks([LEAK], CUT, "not-ours", own_request_ids={RID})
    assert foreign == [{"sent": False, "skipped": "not_our_request", "url": LEAK["url"]}]


def test_own_request_ids_reads_the_receipts_file(tmp_path):
    f = tmp_path / "r.json"
    f.write_text(json.dumps({"rows": [{"request_id": "a"}, {"request_id": None}, {"request_id": "b"}]}))
    assert own_request_ids(f) == {"a", "b"}
    real = own_request_ids(ROOT / "results" / "call_receipts.json")
    assert real and None not in real


def test_mcp_check_leaks_sends_nothing_without_the_flag(monkeypatch):
    server = load_server()
    post = Post()
    monkeypatch.setattr("timelock.feedback._post", post)
    monkeypatch.setenv("TAVILY_API_KEY", "k")
    server.OWN_REQUEST_IDS.add(RID)
    body = json.dumps({"request_id": RID, "results": [LEAK, SAFE]})
    out = server.check_leaks(body, CUT)
    assert "feedback" not in out and out["counts"]["leak"] == 1 and post.calls == []
    assert inspect.signature(server.check_leaks).parameters["report_to_tavily"].default is False


def test_mcp_check_leaks_with_flag_reports_leaks_of_own_requests_only(monkeypatch):
    server = load_server()
    post = Post()
    monkeypatch.setattr(server, "report_leaks", lambda rs, c, rid, **kw: report_leaks(
        rs, c, rid, post=post, api_key="k", **kw))
    server.OWN_REQUEST_IDS.add(RID)
    out = server.check_leaks(json.dumps({"request_id": RID, "results": [LEAK, SAFE]}), CUT, report_to_tavily=True)
    assert [f["sent"] for f in out["feedback"]] == [True] and len(post.calls) == 1
    assert post.calls[0][0]["request_id"] == RID
    foreign = server.check_leaks(json.dumps({"request_id": "not-ours", "results": [LEAK]}), CUT, report_to_tavily=True)
    assert foreign["feedback"][0]["skipped"] == "not_our_request" and len(post.calls) == 1
    none = server.check_leaks(json.dumps([LEAK]), CUT, report_to_tavily=True)          # no request_id at all
    assert none["feedback"][0]["skipped"] == "not_our_request" and len(post.calls) == 1
