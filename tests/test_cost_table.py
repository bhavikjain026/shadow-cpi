"""tools/build_cost_table.py: cost vs results by (search_depth, max_results), from a fake flight recorder and cache.
Offline, 0 credits."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import build_cost_table as CT  # noqa: E402


def write_call(cache, log, i, req, results, credits, cached=False, tag="v2:ablation A 2026-03", rt=1.5):
    key = f"k{i}"
    (cache / "tavily").mkdir(parents=True, exist_ok=True)
    (cache / "tavily" / f"{key}.json").write_text(json.dumps(
        {"service": "tavily", "endpoint": "/search", "request": req,
         "response": {"results": results, "response_time": rt}}))
    log.append({"id": f"id{i}", "service": "tavily", "endpoint": "/search", "cached": cached, "cache_key": key,
                "credits": credits, "tag": tag})


def test_groups_by_setting_counts_real_calls_only(tmp_path):
    cache, log = tmp_path / "cache", []
    dated, undated = {"published_date": "2026-03-02"}, {}
    write_call(cache, log, 1, {"search_depth": "basic", "max_results": 10}, [dated] * 8 + [undated] * 2, 1)
    write_call(cache, log, 2, {"search_depth": "basic", "max_results": 10}, [dated] * 6, 1, tag="radar:2026-10-26 x")
    write_call(cache, log, 3, {"search_depth": "basic", "max_results": 10}, [dated] * 9, 0, cached=True)  # cache hit
    write_call(cache, log, 4, {"search_depth": "advanced", "max_results": 8}, [dated] * 8, 2, tag="poll-2026-01")
    write_call(cache, log, 5, {"auto_parameters": True, "max_results": 10}, [dated] * 10, None)        # pre-ledger gap
    write_call(cache, log, 6, {"query": "x"}, [undated] * 5, 1)                                      # Tavily defaults
    lf = tmp_path / "log.jsonl"
    lf.write_text("\n".join(json.dumps(e) for e in log))
    out = CT.build(lf, cache, ledger=[{"call_id": "id5", "credits": 2}])
    rows = {(r["search_depth"], r["max_results"]): r for r in out["rows"]}
    assert set(rows) == {("basic", 10), ("advanced", 8), ("auto", 10), ("basic", 5)}
    b = rows[("basic", 10)]
    assert (b["calls"], b["credits"], b["results"]) == (2, 2, 16)
    assert b["fill_rate"] == 0.8 and b["dated_share"] == 14 / 16 and b["tasks"] == ["ablation", "radar"]
    assert rows[("auto", 10)]["credits"] == 2                       # filled from the ledger
    assert rows[("advanced", 8)]["credits_per_100_results"] == 25 and rows[("advanced", 8)]["tasks"] == ["poll"]
    assert out["credits_spent_building"] == 0


def test_committed_table_is_internally_consistent():
    out = json.loads((ROOT / "results" / "cost_vs_results.json").read_text())
    for r in out["rows"]:
        assert r["credits_per_call"] == r["credits"] / r["calls"]
        assert 0 <= r["fill_rate"] <= 1
