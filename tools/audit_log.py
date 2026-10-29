"""Build a tamper-evident daily audit log of API calls.

Reads results/credit_ledger.jsonl (credits, request ids, response hashes) and,
when present, logs/flight_recorder.jsonl (every call incl. cached/failed ones).
Writes results/audit_log/<date>.jsonl, a hash chain, and <date>.head.

Day boundary: a "day" is an IST calendar day (Asia/Kolkata, UTC+05:30, no DST),
00:00:00 to 23:59:59 IST. Call times are stored in UTC and assigned to a day by
converting to IST. The builder refuses a day that has not ended in IST; with
--partial it writes <date>.partial.jsonl/.partial.head instead, which are never
stamped or committed (gitignored).

Entries carry metadata only: no page text, no prompts, no keys. A visitor-entered
question (the Try it page) is logged as "visitor query" plus the SHA-256 of its
text; our own pipeline queries stay readable. No cap or truncation is applied.

    python tools/audit_log.py 2026-10-28 [--partial] [--root DIR] [--recorder PATH]
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

GENESIS = "0" * 64
IST = timezone(timedelta(hours=5, minutes=30), "IST")  # Asia/Kolkata; India has no DST
VISITOR_TAG_PREFIXES = ("live:try it",)  # calls whose query text a visitor typed
VISITOR_QUERY = "visitor query"
FIELDS = ("time", "service", "endpoint", "request_id", "query", "query_sha256", "urls",
          "status", "cached", "credits", "response_sha256")


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def entry_hash(entry):
    """SHA-256 of the canonical JSON of the entry, excluding entry_hash itself."""
    body = {k: v for k, v in entry.items() if k != "entry_hash"}
    return hashlib.sha256(canonical(body).encode()).hexdigest()


def ist_day(timestamp):
    """The IST calendar date (YYYY-MM-DD) of an ISO-8601 timestamp (UTC if naive)."""
    t = datetime.fromisoformat(timestamp)
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t.astimezone(IST).date().isoformat()


def day_has_ended(day, now=None):
    end = datetime.fromisoformat(day).replace(tzinfo=IST) + timedelta(days=1)
    return (now or datetime.now(timezone.utc)) >= end


def _read(path, day):
    if not path or not Path(path).exists():
        return []
    out = []
    for line in Path(path).read_text().splitlines():
        if line.strip():
            d = json.loads(line)
            if ist_day(d["time"]) == day:
                out.append(d)
    return out


def _query(rec, params):
    q = params.get("query")
    if q is not None and str(rec.get("tag") or "").startswith(VISITOR_TAG_PREFIXES):
        return VISITOR_QUERY, hashlib.sha256(str(q).encode()).hexdigest()
    return q, None


def _status(rec):
    if "n_results" not in rec or "n_failed" not in rec:
        return "unrecorded"
    if rec["n_failed"] == 0:
        return "ok"
    return "failed" if rec["n_results"] == 0 else "partial"


def build_entries(day, ledger_path, recorder_path):
    ledger = {d["call_id"]: d for d in _read(ledger_path, day)}
    rows = []
    seen = set()
    for r in _read(recorder_path, day):
        seen.add(r["id"])
        p = r.get("params") or {}
        led = ledger.get(r["id"], {})
        query, query_sha = _query(r, p)
        credits = led.get("credits", r.get("credits"))
        rows.append({
            "time": r["time"], "service": r["service"], "endpoint": r["endpoint"],
            "request_id": led.get("request_id") or r.get("request_id"),
            "query": query, "query_sha256": query_sha,
            "urls": p.get("urls") or ([p["url"]] if p.get("url") else None),
            "status": _status(r), "cached": bool(r.get("cached")),
            "credits": credits,
            "response_sha256": led.get("response_sha256") or r.get("response_sha256"),
        })
    for cid, led in ledger.items():  # ledger-only calls (no recorder available)
        if cid in seen:
            continue
        rows.append({
            "time": led["time"], "service": "tavily", "endpoint": led["endpoint"],
            "request_id": led.get("request_id"), "query": None, "query_sha256": None,
            "urls": None,
            "status": "unrecorded", "cached": False, "credits": led.get("credits"),
            "response_sha256": led.get("response_sha256"),
        })
    rows.sort(key=lambda e: (e["time"], e["endpoint"], e["request_id"] or ""))
    return rows


def chain(rows):
    prev, out = GENESIS, []
    for row in rows:
        e = dict(row)
        e["prev_hash"] = prev
        e["entry_hash"] = entry_hash(e)
        prev = e["entry_hash"]
        out.append(e)
    return out, prev


def build(day, root=".", recorder=None, partial=False, now=None):
    if not partial and not day_has_ended(day, now):
        raise SystemExit(f"refusing to build {day}: that IST day has not ended yet "
                         "(use --partial for an unstamped <date>.partial.jsonl)")
    root = Path(root)
    rec = Path(recorder) if recorder else root / "logs" / "flight_recorder.jsonl"
    entries, head = chain(build_entries(day, root / "results" / "credit_ledger.jsonl", rec))
    outdir = root / "results" / "audit_log"
    outdir.mkdir(parents=True, exist_ok=True)
    stem = f"{day}.partial" if partial else day
    (outdir / f"{stem}.jsonl").write_text("".join(canonical(e) + "\n" for e in entries))
    (outdir / f"{stem}.head").write_text(head + "\n")
    return len(entries), head


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("day")
    ap.add_argument("--partial", action="store_true",
                    help="allow a day still in progress; writes <date>.partial.jsonl, never stamp or commit it")
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--recorder")
    a = ap.parse_args(argv)
    n, head = build(a.day, a.root, a.recorder, a.partial)
    print(f"{a.day}: {n} entries, head {head}")


if __name__ == "__main__":
    sys.exit(main())
