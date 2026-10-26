"""Replay a saved run (v2/replay.py): a cache miss is refused before anything is sent; no cache -> clean stop."""
import json

import pytest

from shadow_cpi.budget import CacheMiss
from shadow_cpi.recorder import request_hash
from v2 import ledger as LG
from v2 import replay as RP


def test_replay_recorder_serves_hits_and_refuses_misses(tmp_path):
    rec = RP.ReplayRecorder(tmp_path / "cache", tmp_path / "log.jsonl", tmp_path / "history.jsonl")
    body = {"query": "q", "include_usage": True}
    p = tmp_path / "cache" / "tavily" / f"{request_hash('tavily', '/search', body)}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"response": {"results": [], "usage": {"credits": 1}}}))
    sent = []
    resp, _ = rec.call("tavily", "/search", body, lambda: sent.append(1))
    assert resp["results"] == [] and sent == []
    with pytest.raises(CacheMiss):
        rec.call("tavily", "/search", {**body, "query": "other"}, lambda: sent.append(1))
    assert sent == []


def test_no_cache_stops_cleanly_and_leaves_the_ledger_alone(tmp_path):
    before = LG.LEDGER.read_bytes()
    r = RP.replay("2026-09", cache=tmp_path / "empty")
    assert not r["pass"] and "no cache" in r["error"] and r["sent"] == 0 and r["credits"] == 0
    assert LG.LEDGER.read_bytes() == before and not (tmp_path / "empty").exists()   # no folder created


def test_differences_catch_a_changed_needle():
    run = json.loads((LG.ROOT / "run_2026-09_basket.json").read_text())
    fp = RP.fingerprint(run)
    assert RP.differences(fp, fp) == []
    moved = {**fp, "needle": [fp["needle"][0], fp["needle"][1] + 0.01]}
    assert RP.differences(moved, fp) == ["needle"]


def test_claim_level_change_is_a_difference():
    run = json.loads((LG.ROOT / "run_2026-09_basket.json").read_text())
    fp = RP.fingerprint(run)
    claims = list(fp["claims"])
    claims[0] = claims[0][:4] + (0.123,) + claims[0][5:]
    assert RP.differences({**fp, "claims": claims}, fp) == ["claims"]
