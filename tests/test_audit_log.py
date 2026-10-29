import json
import re
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import audit_log  # noqa: E402
import verify_audit_log as vfy  # noqa: E402

DAYS = ["2026-10-28", "2026-10-29"]
KEY_SHAPED = re.compile(r"(tvly-[A-Za-z0-9_-]{8,}|sk-[A-Za-z0-9]{16,}|eyJ[A-Za-z0-9_-]{20,}|"
                        r"(api[_-]?key|token|secret|bearer)\s*[=:]\s*\S{8,})", re.I)
ALLOWED = set(audit_log.FIELDS) | {"prev_hash", "entry_hash"}


def _synthetic(tmp_path, n=5):
    (tmp_path / "results").mkdir()
    (tmp_path / "logs").mkdir()
    led, rec = [], []
    for i in range(n):
        t = f"2026-10-28T01:00:0{i}+00:00"
        rec.append({"id": f"c{i}", "time": t, "service": "tavily", "endpoint": "/search",
                    "params": {"query": f"q{i}"}, "cached": False, "n_results": 1 if i else 0,
                    "n_failed": 0 if i else 1, "credits": 1})
        led.append({"time": t, "call_id": f"c{i}", "endpoint": "/search", "credits": 1,
                    "request_id": f"r{i}", "response_sha256": "ab" * 32})
    (tmp_path / "results" / "credit_ledger.jsonl").write_text("".join(json.dumps(x) + "\n" for x in led))
    (tmp_path / "logs" / "flight_recorder.jsonl").write_text("".join(json.dumps(x) + "\n" for x in rec))
    audit_log.build("2026-10-28", tmp_path)
    return tmp_path / "results" / "audit_log" / "2026-10-28.jsonl"


def test_synthetic_chain_and_status(tmp_path):
    log = _synthetic(tmp_path)
    assert vfy.verify(log)[0]
    first = json.loads(log.read_text().splitlines()[0])
    assert first["status"] == "failed" and first["prev_hash"] == audit_log.GENESIS


def test_edit_detected(tmp_path):
    log = _synthetic(tmp_path)
    lines = log.read_text().splitlines()
    e = json.loads(lines[2]); e["credits"] = 0
    lines[2] = json.dumps(e)
    log.write_text("\n".join(lines) + "\n")
    ok, msg = vfy.verify(log)
    assert not ok and msg.startswith("entry 3")


def test_removal_detected(tmp_path):
    log = _synthetic(tmp_path)
    lines = log.read_text().splitlines()
    del lines[1]
    log.write_text("\n".join(lines) + "\n")
    ok, msg = vfy.verify(log)
    assert not ok and msg.startswith("entry 2")


def test_tail_removal_detected(tmp_path):
    log = _synthetic(tmp_path)
    lines = log.read_text().splitlines()
    log.write_text("\n".join(lines[:-1]) + "\n")
    ok, msg = vfy.verify(log)
    assert not ok and "head mismatch" in msg


def test_entry_hash_recomputable_with_editing_and_rehash_caught(tmp_path):
    # Re-hashing one edited entry still breaks the next entry's prev_hash.
    log = _synthetic(tmp_path)
    lines = [json.loads(x) for x in log.read_text().splitlines()]
    lines[1]["credits"] = 99
    lines[1]["entry_hash"] = audit_log.entry_hash(lines[1])
    log.write_text("".join(audit_log.canonical(e) + "\n" for e in lines))
    ok, msg = vfy.verify(log)
    assert not ok and msg.startswith("entry 3")


@pytest.mark.parametrize("day", DAYS)
def test_committed_logs_verify(day):
    ok, msg = vfy.verify(ROOT / "results" / "audit_log" / f"{day}.jsonl")
    assert ok, msg


@pytest.mark.parametrize("day", DAYS)
def test_committed_logs_have_ots_stub(day):
    assert (ROOT / "results" / "audit_log" / f"{day}.head.ots").exists()


@pytest.mark.parametrize("day", DAYS)
def test_no_page_text_or_keys(day):
    for line in (ROOT / "results" / "audit_log" / f"{day}.jsonl").read_text().splitlines():
        e = json.loads(line)
        assert set(e) <= ALLOWED
        assert len(line) < 5000
        assert not KEY_SHAPED.search(line), line[:200]
        assert e["response_sha256"] is None or re.fullmatch(r"[0-9a-f]{64}", e["response_sha256"])
