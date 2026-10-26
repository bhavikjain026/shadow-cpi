"""Cache + Flight Recorder.

Every outside call (Tavily, Nebius) goes through here:
- the response is cached on disk, keyed by a hash of the request (never the API key),
  so re-running costs nothing;
- one line is appended to logs/flight_recorder.jsonl with time, service, endpoint,
  main parameters, result counts, credits used, latency, cache hit and parent call.
"""
import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .settings import ROOT

CACHE_DIR = ROOT / "cache"
LOG_FILE = ROOT / "logs" / "flight_recorder.jsonl"
SUMMARY_KEYS = ("query", "urls", "url", "topic", "start_date", "end_date", "language",
                "search_depth", "extract_depth", "include_domains", "exclude_domains",
                "filter_by_published_date", "instructions", "model")


def request_hash(service, endpoint, body):
    blob = json.dumps({"s": service, "e": endpoint, "b": body}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def response_sha256(response):
    """SHA-256 of a response: its JSON with sorted keys, no spaces, UTF-8 (Amendment F provenance)."""
    blob = json.dumps(response, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def provenance(response):
    """{'request_id', 'response_sha256'} for one response (request_id is Tavily's own, None if absent)."""
    rid = response.get("request_id") if isinstance(response, dict) else None
    return {"request_id": rid, "response_sha256": response_sha256(response)}


def _summary(body):
    out = {}
    for k in SUMMARY_KEYS:
        if k in body:
            v = body[k]
            if k == "urls" and isinstance(v, list):
                v = v[:20]
            out[k] = v
    return out


def _counts(response):
    c = {}
    if isinstance(response, dict):
        if isinstance(response.get("results"), list):
            c["n_results"] = len(response["results"])
        if isinstance(response.get("failed_results"), list):
            c["n_failed"] = len(response["failed_results"])
        usage = response.get("usage")
        if isinstance(usage, dict):
            c["credits"] = usage.get("credits")
    return c


class Recorder:
    def __init__(self, cache_dir=CACHE_DIR, log_file=LOG_FILE, use_cache=True):
        self.cache_dir = Path(cache_dir)
        self.log_file = Path(log_file)
        self.use_cache = use_cache
        self.history_log = self.log_file          # the flight recorder earlier runs wrote (v2.replay points it elsewhere)
        self.provenance = []                      # every call made through this recorder (Amendment F)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def _path(self, service, h):
        d = self.cache_dir / service
        d.mkdir(parents=True, exist_ok=True)
        return d / f"{h}.json"

    def call(self, service, endpoint, body, fn, parent=None, tag=None):
        """Return (response, call_id). fn() performs the real request if not cached."""
        h = request_hash(service, endpoint, body)
        path = self._path(service, h)
        call_id = uuid.uuid4().hex[:12]
        started = time.time()
        cached = False
        if self.use_cache and path.exists():
            response = json.loads(path.read_text(encoding="utf-8"))["response"]
            cached = True
        else:
            response = fn()
            path.write_text(json.dumps({
                "service": service, "endpoint": endpoint, "request": body, "response": response,
                "retrieved_at": datetime.now(timezone.utc).isoformat()}, ensure_ascii=False), encoding="utf-8")
        entry = {"id": call_id, "time": datetime.now(timezone.utc).isoformat(), "service": service,
                 "endpoint": endpoint, "params": _summary(body), "cached": cached,
                 "latency_ms": int((time.time() - started) * 1000), "parent": parent, "tag": tag,
                 "cache_key": h, **_counts(response), **provenance(response)}
        self.provenance.append({k: entry[k] for k in ("id", "service", "endpoint", "cached", "request_id",
                                                       "response_sha256")})
        with self.log_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return response, call_id


def read_log(log_file=LOG_FILE):
    p = Path(log_file)
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def credits_used(entries, include_cached=False):
    return sum((e.get("credits") or 0) for e in entries
               if e.get("service") == "tavily" and (include_cached or not e.get("cached")))
