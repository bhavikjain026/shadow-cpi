"""timelock/ (standalone time-locked search): saved Tavily responses only, no network, no key."""
import io
import json
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

import timelock
from shadow_cpi.recorder import response_sha256 as recorder_sha256
from timelock import DATE_FLAG, LEAK, SAFE, Replay, TavilyHTTP, TimeLockError, timelocked_search

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures" / "timelock"
LOCKED_FIX, UNLOCKED_FIX = FIX / "rbi_2026-10-06_locked.json", FIX / "rbi_2026-10-06_unlocked.json"
Q, CUT = "RBI monetary policy repo rate decision October 2026", "2026-10-06"


class Fake:
    def __init__(self, response):
        self.response, self.sent = response, []

    def search(self, query, **params):
        self.sent.append({"query": query, **params})
        return self.response


def saved(path):
    return json.loads(path.read_text(encoding="utf-8"))["response"]


def test_window_is_always_sent_and_defaults_to_30_days():
    c = Fake({"results": []})
    timelocked_search(c, "q", CUT, topic="news")
    assert c.sent[0] == {"query": "q", "start_date": "2026-09-07", "end_date": CUT, "filter_by_published_date": True,
                         "topic": "news"}
    timelocked_search(c, "q", CUT, start_date="2026-10-01", end_date="2026-10-05", filter_by_published_date=True)
    assert (c.sent[1]["start_date"], c.sent[1]["end_date"]) == ("2026-10-01", "2026-10-05")   # narrowing is fine


@pytest.mark.parametrize("kw", [{"end_date": "2026-10-07"}, {"filter_by_published_date": False},
                                {"time_range": "week"}, {"days": 3}, {"auto_parameters": True},
                                {"start_date": "2026-10-07"}, {"end_date": "x"}])
def test_refuses_anything_that_moves_the_window_before_calling(kw):
    c = Fake({"results": []})
    with pytest.raises(TimeLockError):
        timelocked_search(c, "q", CUT, **kw)
    with pytest.raises(TimeLockError):
        timelocked_search(c, "q", "6 Oct 2026")
    assert c.sent == []


def test_saved_rbi_response_receipt_and_labels():
    results = timelocked_search(Replay(LOCKED_FIX), Q, CUT, topic="news", max_results=5, search_depth="basic",
                                include_published_date=True)
    resp = saved(LOCKED_FIX)
    assert results.counts == {SAFE: 5, DATE_FLAG: 0, LEAK: 0} and len(results.safe()) == 5
    assert results.request_id == resp["request_id"] == "5e7387cb-67c8-455d-931d-fab9b7523f49"
    assert results.response_sha256 == recorder_sha256(resp)            # same hash as the pipeline's Flight Recorder
    assert results.window == ["2026-09-07", CUT]
    r = results[0]
    assert r["published_date"] == "2026-10-05" and r["published_date_raw"] == "Mon, 05 Oct 2026 00:00:00 GMT"
    assert r["request_id"] == results.request_id and r["response_sha256"] == results.response_sha256
    assert r["page_date"] is None and r["status"] == SAFE


def test_post_cutoff_pages_are_leaks_even_if_the_filter_lets_them_through():
    # the same question searched with no dates (a real saved response): replayed as if it came back inside the
    # lock, the date check still marks the three pages dated 7 and 9 October as leaks
    results = timelocked_search(Fake(saved(UNLOCKED_FIX)), Q, CUT)
    assert results.counts == {SAFE: 2, DATE_FLAG: 0, LEAK: 3}
    assert sorted(r["published_date"] for r in results if r["status"] == LEAK) == ["2026-10-07", "2026-10-07",
                                                                                    "2026-10-09"]


def test_page_date_from_extracted_text_or_given():
    resp = {"request_id": "r1", "results": [
        {"url": "https://x.in/a", "published_date": "2026-10-01", "raw_content": "Updated: Oct 8, 2026 09:00 IST"},
        {"url": "https://x.in/b", "raw_content": "no date here"},
        {"url": "https://x.in/c"}]}
    results = timelocked_search(Fake(resp), "q", CUT, include_raw_content=True,
                                page_dates={"https://x.in/c": "2026-10-02"})
    assert [(r["page_date"], r["status"]) for r in results] == [("2026-10-08", LEAK), (None, DATE_FLAG),
                                                                ("2026-10-02", SAFE)]
    c = Fake(resp)
    with pytest.raises(TimeLockError):                       # '5 Oct 2026' would compare wrongly as a string
        timelocked_search(c, "q", CUT, page_dates={"https://x.in/c": "5 Oct 2026"})
    assert c.sent == []


def test_replay_refuses_a_request_it_did_not_record():
    with pytest.raises(ValueError, match="different request"):
        timelocked_search(Replay(LOCKED_FIX), Q, CUT, start_date="2026-10-01")
    with pytest.raises(ValueError, match="different request"):
        timelocked_search(Replay(LOCKED_FIX), "another question", CUT)
    with pytest.raises(ValueError, match="include_domains"):
        timelocked_search(Replay(LOCKED_FIX), Q, CUT, topic="news", max_results=5, search_depth="basic",
                          include_published_date=True, include_domains=["rbi.org.in"])


def test_live_client_sends_the_lock(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    with pytest.raises(ValueError):
        TavilyHTTP()
    seen = {}

    def urlopen(req, timeout):
        seen["url"], seen["body"] = req.full_url, json.loads(req.data)
        seen["auth"] = req.get_header("Authorization")
        return io.BytesIO(b'{"request_id": "r2", "results": []}')

    monkeypatch.setattr("timelock.clients.urllib.request.urlopen", urlopen)
    results = timelocked_search(TavilyHTTP("placeholder-not-a-key"), "q", CUT)
    assert seen["url"] == "https://api.tavily.com/search" and seen["auth"] == "Bearer placeholder-not-a-key"
    assert seen["body"]["end_date"] == CUT and seen["body"]["filter_by_published_date"] is True
    assert results.request_id == "r2" and list(results) == []


def test_example_runs_offline(capsys):
    runpy.run_path(str(ROOT / "examples" / "timelock_rbi.py"), run_name="__main__")
    out = capsys.readouterr().out
    assert "{'safe': 5, 'date_flag': 0, 'leak': 0} 5e7387cb-67c8-455d-931d-fab9b7523f49" in out


def test_standalone_no_pipeline_imports():
    code = "import sys, timelock; print(sorted(m for m in sys.modules if m.split('.')[0] in ('shadow_cpi', 'v2')))"
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    assert out.strip() == "[]"


def test_pipeline_names_are_the_same_objects():
    from shadow_cpi import leakcheck, pit
    from shadow_cpi.tavily import iso_date
    from v2.date_test import page_date
    assert leakcheck.check_result is pit.check_result is timelock.check_result
    assert pit.TimeLockError is TimeLockError and iso_date is timelock.iso_date and page_date is timelock.page_date


def test_readme_snippet_is_the_example():
    code = (ROOT / "examples" / "timelock_rbi.py").read_text(encoding="utf-8").split("\n", 1)[1].strip()
    readme = (ROOT / "docs" / "templates" / "README.md").read_text(encoding="utf-8")
    assert "```python\n" + code + "\n```" in readme
