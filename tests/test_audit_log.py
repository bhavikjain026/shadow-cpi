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

DAYS = ["2026-10-28"]
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


# ---- IST day boundary, partial guard, visitor privacy, no truncation ----
from datetime import datetime, timezone  # noqa: E402


def _rec(i, t, tag="x", query="q"):
    return {"id": f"c{i}", "time": t, "service": "tavily", "endpoint": "/search",
            "params": {"query": query}, "cached": False, "n_results": 1, "n_failed": 0,
            "credits": 1, "tag": tag}


def _root(tmp_path, recs):
    (tmp_path / "results").mkdir(exist_ok=True)
    (tmp_path / "logs").mkdir(exist_ok=True)
    (tmp_path / "results" / "credit_ledger.jsonl").write_text("")
    (tmp_path / "logs" / "flight_recorder.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs))
    return tmp_path


AFTER = datetime(2026, 11, 1, tzinfo=timezone.utc)


def test_day_boundary_is_ist(tmp_path):
    recs = [_rec(0, "2026-10-27T18:29:59+00:00"),   # 23:59:59 IST on the 27th
            _rec(1, "2026-10-27T18:30:00+00:00"),   # 00:00:00 IST on the 28th
            _rec(2, "2026-10-28T18:29:59+00:00"),   # 23:59:59 IST on the 28th
            _rec(3, "2026-10-28T18:30:00+00:00")]   # 00:00:00 IST on the 29th
    root = _root(tmp_path, recs)
    n, _ = audit_log.build("2026-10-28", root, now=AFTER)
    got = [json.loads(x)["time"] for x in (root / "results/audit_log/2026-10-28.jsonl").read_text().splitlines()]
    assert n == 2 and got == ["2026-10-27T18:30:00+00:00", "2026-10-28T18:29:59+00:00"]


def test_refuses_unfinished_day_unless_partial(tmp_path):
    root = _root(tmp_path, [_rec(0, "2026-10-28T10:00:00+00:00")])
    now = datetime(2026, 10, 28, 18, 29, tzinfo=timezone.utc)  # 23:59 IST: still the 28th
    with pytest.raises(SystemExit):
        audit_log.build("2026-10-28", root, now=now)
    assert not (root / "results/audit_log/2026-10-28.jsonl").exists()
    audit_log.build("2026-10-28", root, partial=True, now=now)
    out = root / "results/audit_log"
    assert (out / "2026-10-28.partial.jsonl").exists() and not (out / "2026-10-28.jsonl").exists()
    assert vfy.verify(out / "2026-10-28.partial.jsonl")[0]
    audit_log.build("2026-10-28", root, now=datetime(2026, 10, 28, 18, 30, tzinfo=timezone.utc))
    assert (out / "2026-10-28.jsonl").exists()


def test_visitor_query_hidden_ours_readable(tmp_path):
    secret = "my private question about Priya's salary"
    recs = [_rec(0, "2026-10-28T10:00:00+00:00", tag="live:try it open", query=secret),
            _rec(1, "2026-10-28T10:00:01+00:00", tag="live:try it locked", query=secret),
            _rec(2, "2026-10-28T10:00:02+00:00", tag="item:onion quotes", query="onion price Delhi")]
    root = _root(tmp_path, recs)
    audit_log.build("2026-10-28", root, now=AFTER)
    text = (root / "results/audit_log/2026-10-28.jsonl").read_text()
    assert "Priya" not in text and secret not in text
    e = [json.loads(x) for x in text.splitlines()]
    import hashlib
    assert e[0]["query"] == e[1]["query"] == "visitor query"
    assert e[0]["query_sha256"] == hashlib.sha256(secret.encode()).hexdigest()
    assert e[2]["query"] == "onion price Delhi" and e[2]["query_sha256"] is None


def test_no_truncation_beyond_3000(tmp_path):
    recs = [_rec(i, "2026-10-28T10:00:00+00:00") for i in range(3500)]
    root = _root(tmp_path, recs)
    n, _ = audit_log.build("2026-10-28", root, now=AFTER)
    assert n == 3500
    assert len((root / "results/audit_log/2026-10-28.jsonl").read_text().splitlines()) == 3500


def test_committed_log_has_no_visitor_text():
    for line in (ROOT / "results/audit_log/2026-10-28.jsonl").read_text().splitlines():
        e = json.loads(line)
        if e["query_sha256"]:
            assert e["query"] == "visitor query"
