#!/usr/bin/env python3
"""Smoke test for the forced model migration (v2/PREREGISTRATION.md Amendment G), at most 4 Nebius calls.

    python tools/smoke_model_migration.py

Each replacement model is called once with one of our real JSON-schema requests, rebuilt by Nemotron.chat_json from a
cached request to the original model on the same page: the gatekeeper prompt for nvidia/Nemotron-3_5-Lightning, the
line-citing price-events prompt for nvidia/Nemotron-3.5-Super-VL. The call date is set to 2026-11-09 IST so the dated
map picks the replacement; a fresh cache makes sure the request reaches Nebius. Reports: was the schema request
accepted (HTTP 200 on the first try, no fallback to JSON mode), is the output valid against the schema, and the answer
next to the original model's cached answer. Writes results/model_migration_smoke.json. Logs to the flight recorder.
"""
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from shadow_cpi.http import ApiError, request_json  # noqa: E402
from shadow_cpi.nemotron import Nemotron, _attach_lines  # noqa: E402
from shadow_cpi.recorder import LOG_FILE, Recorder  # noqa: E402
from shadow_cpi.verify import split_lines  # noqa: E402

CAP = 4
SWITCH = datetime(2026, 11, 8, 18, 30, tzinfo=timezone.utc)          # 2026-11-09 00:00 IST
CACHE = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "cache" / "nebius"
CASES = [("gatekeeper", "d60e288b3cc1df5d682042d5a232b85df0b9ce79f5e270d431e68719a55f9260"),
         ("line-citing (price events)", "d1558eb9bd905e19c62375e778cf8c20cfe246b4de3031f07d096e79a023c92e")]
OUT = ROOT / "results" / "model_migration_smoke.json"


class Capped:
    """The real transport, refusing a 5th call; records each attempt's status and response_format type."""
    def __init__(self):
        self.attempts = []

    def __call__(self, method, url, key, body, timeout):
        if len(self.attempts) >= CAP:
            raise SystemExit(f"cap of {CAP} Nebius calls reached")
        a = {"model": body.get("model"), "response_format": (body.get("response_format") or {}).get("type")}
        self.attempts.append(a)
        try:
            resp = request_json(method, url, key, body, timeout)
            a["status"] = 200
            return resp
        except ApiError as e:
            a["status"] = e.status
            raise


def main():
    t = Capped()
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        nem = Nemotron(recorder=Recorder(cache_dir=tmp, log_file=LOG_FILE), transport=t, clock=lambda: SWITCH)
        for job, key in CASES:
            cached = json.loads((CACHE / f"{key}.json").read_text(encoding="utf-8"))
            req = cached["request"]
            schema = req["response_format"]["json_schema"]["schema"]
            system, user = req["messages"][0]["content"], req["messages"][1]["content"]
            before = len(t.attempts)
            row = {"job": job, "original_model": req["model"], "cached_request": key,
                   "original_answer": json.loads(cached["response"]["choices"][0]["message"]["content"])}
            try:
                out, cid = nem.chat_json(req["model"], system, user, schema, max_tokens=req["max_tokens"],
                                         tag="smoke:model-migration")
                row.update(call=cid, answer=out)
                try:
                    jsonschema.validate(out, schema)
                    row["schema_valid"], row["schema_error"] = True, ""
                except jsonschema.ValidationError as e:
                    row["schema_valid"], row["schema_error"] = False, e.message[:300]
            except (ApiError, ValueError) as e:
                row.update(answer=None, schema_valid=False, error=f"{type(e).__name__}: {str(e)[:300]}")
            row["attempts"] = t.attempts[before:]
            row["replacement_model"] = row["attempts"][0]["model"] if row["attempts"] else None
            row["schema_request_accepted"] = bool(row["attempts"]) and row["attempts"][0]["status"] == 200 \
                and row["attempts"][0]["response_format"] == "json_schema"
            if job.startswith("line") and row.get("answer"):
                page = user.split("PAGE:\n", 1)[1]
                lines = [l.split(": ", 1)[1] if ": " in l else l for l in page.splitlines()]
                for side in ("answer", "original_answer"):
                    row[f"{side}_cited_lines"] = [
                        {"line": f.get("line"), "verified": f["verified"], "quote": f["quote"][:200]}
                        for f in _attach_lines([dict(x) for x in row[side].get("events", [])], lines, "new_price")]
            rows.append(row)
    res = {"run_utc": datetime.now(timezone.utc).isoformat(), "call_date_used": "2026-11-09 IST (clock set)",
           "nebius_calls_sent": len(t.attempts), "cap": CAP, "cases": rows}
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
