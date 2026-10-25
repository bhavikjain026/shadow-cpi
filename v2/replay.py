#!/usr/bin/env python3
"""Replay a saved Live build run from the cache: no keys, no network, 0 credits.

    python -m v2.replay            # September 2026 basket; prints PASS/FAIL

Re-runs the whole Live build (v2.basket: search, Nemotron reading, Extract, quote check, maths, time machine) with
placeholder keys and a recorder that refuses any call not already in the cache, so nothing can be sent and nothing
can be spent. The rebuilt run goes to a scratch folder and is compared with the committed
v2/evidence/run_<month>_basket.json; the committed run file and the evidence ledger are left as they were.

Cache folder: $SCPI_REPLAY_CACHE, else replay_cache/ (a bundle shipped for judges, if present), else cache/.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from shadow_cpi.budget import CacheMiss  # noqa: E402
from shadow_cpi.recorder import Recorder, request_hash  # noqa: E402
from v2 import ledger as LG  # noqa: E402

PLACEHOLDER = "replay-no-key"
TOL = 1e-12


class ReplayRecorder(Recorder):
    """A Recorder that only serves the cache: a miss raises CacheMiss before anything is sent."""

    def call(self, service, endpoint, body, fn, parent=None, tag=None):
        if not self._path(service, request_hash(service, endpoint, body)).exists():
            raise CacheMiss(f"replay: {service} {endpoint} is not in the cache; nothing sent")
        return super().call(service, endpoint, body, fn, parent=parent, tag=tag)


def cache_dir():
    if os.environ.get("SCPI_REPLAY_CACHE"):
        return Path(os.environ["SCPI_REPLAY_CACHE"])
    bundle = ROOT / "replay_cache"
    return bundle if bundle.exists() else ROOT / "cache"


def refuse(*_a, **_k):
    raise CacheMiss("replay: network call refused")


def fingerprint(run):
    """What must match: every card's verdict, every verified quote, the needle path, coverage, time machine."""
    return {"item_cards": [(c["cpi_code"], c["status"]) for c in run["item_cards"]],
            "cards": [(c["url"], c["status"]) for c in run["cards"]],
            "verified_quotes": sorted((c["url"], cl["line"]) for c in run["cards"] for cl in c["claims"]
                                      if cl.get("status") == "verified"),
            "moving_events": [(m["cpi_code"], m["where"]) for m in run["moving_events"]],
            "needle": [run["needle"]["start"], run["needle"]["end"]], "measured_share": [run["measured_share"]],
            "timeline": [s["yoy_after"] for s in run["timeline"]],
            "time_machine": [r["yoy"] for r in run.get("time_machine", [])]}


def differences(a, b):
    out = []
    for k in a:
        x, y = a[k], b.get(k)
        if k in ("needle", "measured_share", "timeline", "time_machine"):
            same = len(x) == len(y) and all(abs(p - q) <= TOL for p, q in zip(x, y))
        else:
            same = x == y
        if not same:
            out.append(k)
    return out


def replay(month="2026-09", cache=None):
    """{'pass', 'month', 'calls', 'from_cache', 'sent', 'credits', 'differences', 'needle', 'committed_needle',
    'verified_quotes', 'error'}"""
    from v2 import basket as B
    cache = Path(cache or cache_dir())
    committed_path = LG.ROOT / f"run_{month}_basket.json"
    committed = json.loads(committed_path.read_text(encoding="utf-8"))
    res = {"month": month, "cache": str(cache), "pass": False, "error": None}
    committed_ledger = LG.LEDGER
    with tempfile.TemporaryDirectory() as tmp:
        rec = ReplayRecorder(cache, Path(tmp) / "flight_recorder.jsonl")
        scratch = Path(tmp) / "ledger.jsonl"            # the replay writes its ledger rows here, never to the real one
        scratch.write_bytes(committed_ledger.read_bytes() if committed_ledger.exists() else b"")
        n_before = len(LG.read(scratch))
        LG.LEDGER = scratch
        try:
            if not (cache / "tavily").exists():
                raise CacheMiss(f"no cache at {cache}")
            out, _ = B.run(month, cache_only=True, rec=rec, keys=(PLACEHOLDER, PLACEHOLDER), out_dir=tmp)
        except CacheMiss as e:
            out, res["error"] = None, str(e)
        finally:
            LG.LEDGER = committed_ledger
        res["ledger_rows_not_in_committed_ledger"] = len(LG.read(scratch)) - n_before
        log = [json.loads(line) for line in rec.log_file.read_text(encoding="utf-8").splitlines()] \
            if rec.log_file.exists() else []
    res.update({"calls": len(log), "from_cache": sum(e["cached"] for e in log),
                "sent": sum(not e["cached"] for e in log),
                "credits": sum((e.get("credits") or 0) for e in log if not e["cached"] and e["service"] == "tavily"),
                "committed_needle": committed["needle"]["end"]})
    if out is not None:
        res["differences"] = differences(fingerprint(out), fingerprint(committed))
        res["needle"] = out["needle"]["end"]
        res["verified_quotes"] = len(fingerprint(out)["verified_quotes"])
        res["pass"] = not res["differences"] and res["sent"] == 0 and not res["error"]
    return res


def main():
    r = replay(sys.argv[1] if len(sys.argv) > 1 else "2026-09")
    print(f"{'PASS' if r['pass'] else 'FAIL'}: replay of the {r['month']} Live build from {r['cache']}")
    print(f"  calls {r['calls']} (from cache {r['from_cache']}, sent {r['sent']}), credits {r['credits']}")
    if r["error"]:
        print(f"  stopped: {r['error']}")
    else:
        print(f"  needle {r['needle']:.6f}% vs committed {r['committed_needle']:.6f}%; verified quotes "
              f"{r['verified_quotes']}; differences: {', '.join(r['differences']) or 'none'}")
    return 0 if r["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
