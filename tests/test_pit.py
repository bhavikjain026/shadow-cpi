"""Time-locked search (shadow_cpi/pit): saved Tavily responses only, no network, placeholder key."""
import json
from pathlib import Path

import pytest

from shadow_cpi import pit
from shadow_cpi.recorder import Recorder, read_log, response_sha256
from shadow_cpi.tavily import Tavily

FIX = Path(__file__).resolve().parent / "fixtures" / "pit"


def saved(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))["response"]


def client(tmp_path, response):
    sent = []

    def transport(method, url, key, body, timeout):
        sent.append(body)
        return response

    rec = Recorder(tmp_path / "cache", tmp_path / "flight.jsonl")
    return Tavily(api_key="placeholder-not-a-key", recorder=rec, transport=transport), sent


def test_window_is_always_sent_and_cannot_be_moved(tmp_path):
    tav, sent = client(tmp_path, saved("search_dated_window_F3.json"))
    pit.pit_search("petrol diesel price hike India May 2026", "2026-05-29", tavily=tav, topic="news", max_results=3)
    body = sent[0]
    assert body["start_date"] == "2026-05-01" and body["end_date"] == "2026-05-29"
    assert body["filter_by_published_date"] is True and body["include_usage"] is True
    for k in pit.LOCKED:
        with pytest.raises(pit.TimeLockError):
            pit.pit_search("q", "2026-05-29", tavily=tav, **{k: "x"})
    with pytest.raises(pit.TimeLockError):
        pit.window_for("2026-05-29", start="2026-06-01")


def test_saved_dated_response_matches_readme_example(tmp_path):
    resp = saved("search_dated_window_F3.json")
    tav, _ = client(tmp_path, resp)
    r = pit.pit_search("petrol diesel price hike India May 2026", "2026-05-29", tavily=tav, topic="news",
                       max_results=3)
    assert r["counts"] == {"safe": 3, "date_flag": 0, "leak": 0} and len(r["kept"]) == 3
    assert r["request_id"] == resp["request_id"] == "607ab443-9bc5-43fd-ac5f-31d4618b8c82"
    assert r["response_sha256"] == response_sha256(resp)
    assert r["credits"] == resp["usage"]["credits"] and r["response_time"] == resp["response_time"]
    log = read_log(tmp_path / "flight.jsonl")
    assert log[-1]["request_id"] == r["request_id"] and log[-1]["response_sha256"] == r["response_sha256"]
    assert log[-1]["params"]["filter_by_published_date"] is True


def test_post_cutoff_result_is_dropped_even_if_the_filter_lets_it_through(tmp_path):
    # the same case's no-dates response holds a 21 Sep page (a confirmed leak in the date test): replayed as if
    # Tavily had returned it inside the lock, check_result must still drop it
    tav, _ = client(tmp_path, saved("search_no_dates_F3.json"))
    r = pit.pit_search("petrol diesel price hike India May 2026", "2026-05-29", tavily=tav)
    assert r["counts"]["leak"] == 1 and all(x["pit_label"] != "leak" for x in r["kept"])
    assert "hindustantimes.com" in r["leaks"][0]["url"]


def test_undated_is_flagged_not_kept_and_page_date_can_reveal_a_leak(tmp_path):
    resp = {"results": [{"url": "https://x.in/a"}, {"url": "https://x.in/b", "published_date": "2026-05-10"}],
            "usage": {"credits": 0}, "request_id": "r1"}
    tav, _ = client(tmp_path, resp)
    r = pit.pit_search("q", "2026-05-29", tavily=tav, page_dates={"https://x.in/b": "2026-06-02"})
    assert r["counts"] == {"safe": 0, "date_flag": 1, "leak": 1} and r["kept"] == []
    assert r["credits"] == 0                    # include_usage can read 0 below Tavily's threshold


def test_reexports():
    assert pit.check_result({"url": "u", "published_date": "2026-05-30"}, "2026-05-29") == pit.LEAK
    assert callable(pit.as_of) and pit.as_of("2026-09-15")["month"] == "2026-09"
