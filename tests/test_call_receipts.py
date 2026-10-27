"""tools/build_call_receipts.py and its daily rebuild: the committed receipts cover every real call in the ledger, a
rebuild never rewrites an older call's response_time, and tools/radar_daily.sh rebuilds them before each commit.
Offline, 0 credits."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import build_call_receipts as BCR  # noqa: E402
from shadow_cpi.budget import read_ledger  # noqa: E402


def test_committed_receipts_cover_every_real_call_in_the_ledger():
    ledger = read_ledger()
    phantom = {c for e in ledger for c in e.get("phantom_of", [])}
    real = {e["call_id"] for e in ledger
            if e["endpoint"].startswith("/") and not e.get("cached") and e["call_id"] not in phantom}
    got = {r["call_id"] for r in json.loads(BCR.OUT.read_text(encoding="utf-8"))["rows"]}
    assert real == got, "rebuild: python tools/build_call_receipts.py && python tools/build_field_report.py"


def _call(i):
    return {"call_id": f"c{i}", "time": f"2026-10-2{i}T00:00:00+00:00", "endpoint": "/search", "credits": 1,
            "budgets": ["radar-2026-10"], "request_id": f"r{i}"}


def _save(cache, key, rt):
    (cache / "tavily").mkdir(parents=True, exist_ok=True)
    (cache / "tavily" / f"{key}.json").write_text(json.dumps({"response": {"response_time": rt}}))


def test_rebuild_is_append_only_for_response_time(tmp_path):
    log, cache, out = tmp_path / "log.jsonl", tmp_path / "cache", tmp_path / "receipts.json"
    log.write_text("\n".join(json.dumps({"id": f"c{i}", "service": "tavily", "cache_key": "same"}) for i in (1, 2)))
    _save(cache, "same", 1.5)
    BCR.build(log, cache, ledger=[_call(1)], out=out)
    _save(cache, "same", 9.0)                 # the same search again: the cache file now holds the later response
    r = BCR.build(log, cache, ledger=[_call(1), _call(2)], out=out)
    assert [x["response_time"] for x in r["rows"]] == [1.5, 9.0]
    assert json.loads(out.read_text())["rows"][0]["response_time"] == 1.5


def test_radar_daily_rebuilds_receipts_before_every_commit():
    sh = (ROOT / "tools/radar_daily.sh").read_text(encoding="utf-8")
    body = sh[sh.index("rebuild_receipts() {"):]
    assert "python tools/build_call_receipts.py && python tools/build_field_report.py" in body
    assert 'git checkout -- "${RECEIPT_FILES[@]}"' in body          # a failed rebuild leaves the tree clean
    commits = [m.start() for m in re.finditer(r"^\s*git commit ", sh, re.M)]
    calls = [m.start() for m in re.finditer(r"^\s*rebuild_receipts\b(?!\(\))", sh, re.M)]
    adds = [m.start() for m in re.finditer(r"^\s*(?:.*; )?add_side_files$", sh, re.M)]
    assert len(commits) == len(calls) == len(adds) == 2
    assert all(a < c < g for a, c, g in zip(adds, calls, commits))   # after the files are staged, before commit
