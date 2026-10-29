"""Build a tamper-evident daily audit log of API calls.

Reads results/credit_ledger.jsonl (credits, request ids, response hashes) and,
when present, logs/flight_recorder.jsonl (every call incl. cached/failed ones).
Writes results/audit_log/<date>.jsonl, a hash chain, and <date>.head.

Entries carry metadata only: no page text, no prompts, no keys.

    python tools/audit_log.py 2026-10-28 [--root DIR] [--recorder PATH]
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

GENESIS = "0" * 64
FIELDS = ("time", "service", "endpoint", "request_id", "query", "urls",
          "status", "cached", "credits", "response_sha256")


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def entry_hash(entry):
    """SHA-256 of the canonical JSON of the entry, excluding entry_hash itself."""
    body = {k: v for k, v in entry.items() if k != "entry_hash"}
    return hashlib.sha256(canonical(body).encode()).hexdigest()


def _read(path, day):
    if not path or not Path(path).exists():
        return []
    out = []
    for line in Path(path).read_text().splitlines():
        if line.strip():
            d = json.loads(line)
            if str(d.get("time", "")).startswith(day):
                out.append(d)
    return out


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
        credits = led.get("credits", r.get("credits"))
        rows.append({
            "time": r["time"], "service": r["service"], "endpoint": r["endpoint"],
            "request_id": led.get("request_id") or r.get("request_id"),
            "query": p.get("query"),
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
            "request_id": led.get("request_id"), "query": None, "urls": None,
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


def build(day, root=".", recorder=None):
    root = Path(root)
    rec = Path(recorder) if recorder else root / "logs" / "flight_recorder.jsonl"
    entries, head = chain(build_entries(day, root / "results" / "credit_ledger.jsonl", rec))
    outdir = root / "results" / "audit_log"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / f"{day}.jsonl").write_text("".join(canonical(e) + "\n" for e in entries))
    (outdir / f"{day}.head").write_text(head + "\n")
    return len(entries), head


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("day")
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--recorder")
    a = ap.parse_args(argv)
    n, head = build(a.day, a.root, a.recorder)
    print(f"{a.day}: {n} entries, head {head}")


if __name__ == "__main__":
    sys.exit(main())
