#!/usr/bin/env python3
"""Run each repro/ script once with OUR key, under the 'repro-kit' budget, and log every call to the credit ledger.

    python tools/run_repro.py            # prints the plan and the worst-case credits; sends nothing (0 credits)
    python tools/run_repro.py --live     # runs the seven scripts once each; writes results/repro_run.json

The key is read from SCPI_TAVILY_API_KEY (environment, or .env here or in the main checkout) and handed to the scripts
as TAVILY_API_KEY; it is never printed. Each script's worst case is its MAX_CREDITS; the run stops before a script
whose worst case would take 'repro-kit' (or the account) past its cap. 0 Nemotron calls.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shadow_cpi.budget import LEDGER, BudgetExceeded, account_limit, account_spent, cap_of, load_budget, read_ledger, spent  # noqa: E402

BUDGET = "repro-kit"
OUT = ROOT / "results" / "repro_run.json"
SCRIPTS = ("auto_parameters_time_range", "auto_parameters_echo_dates", "extract_no_asof", "published_vs_modified",
           "map_empty", "scanned_pdf_extract", "usage_lag")


def worst_case(script):
    """The MAX_CREDITS a script declares (its own estimate may be lower)."""
    return int(re.search(r"^MAX_CREDITS = (\d+)", (ROOT / "repro" / f"{script}.py").read_text(), re.M).group(1))


def find_key():
    if os.environ.get("SCPI_TAVILY_API_KEY"):
        return os.environ["SCPI_TAVILY_API_KEY"]
    for env in (ROOT / ".env", ROOT.parent / "shadow-cpi" / ".env"):
        if env.exists():
            for line in env.read_text().splitlines():
                if line.startswith("SCPI_TAVILY_API_KEY="):
                    return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit("No SCPI_TAVILY_API_KEY in the environment or .env. Nothing was sent.")


def check(cost, cfg=None, ledger=None):
    """Refuse before a script runs if its worst case would pass the 'repro-kit' cap or the account limit."""
    cfg = cfg or load_budget()
    ledger = read_ledger() if ledger is None else ledger
    s, cap = spent(BUDGET, ledger), cap_of(BUDGET, cfg)
    if s + cost > cap:
        raise BudgetExceeded(f"budget '{BUDGET}': {s} spent + {cost} worst case > cap {cap}")
    total, limit = account_spent(cfg, ledger), account_limit(cfg) - cfg["reserve"]
    if total + cost > limit:
        raise BudgetExceeded(f"account: {total} spent + {cost} > {limit}")


def ledger_rows(receipts, script, now=None):
    """One credit-ledger row per call a script made (format of shadow_cpi.budget.Budgeted._write)."""
    now = now or datetime.now(timezone.utc).isoformat()
    return [{"time": now, "call_id": hashlib.sha256(f"{script}:{r['request_id']}:{r['response_sha256']}".encode()).hexdigest()[:12],
             "endpoint": r["endpoint"], "credits": r["credits"], "real_spent": r["credits"],
             "original_cost": r["credits"], "budgets": [BUDGET], "request_id": r["request_id"],
             "response_time": r.get("response_time"), "response_sha256": r["response_sha256"]}
            for r in receipts if r["endpoint"] != "/usage"]          # GET /usage is free; the ledger holds billed calls


def run_one(script, key):
    with tempfile.TemporaryDirectory() as d:
        receipt = Path(d) / "receipt.jsonl"
        env = {**os.environ, "TAVILY_API_KEY": key, "REPRO_RECEIPT": str(receipt)}
        p = subprocess.run([sys.executable, str(ROOT / "repro" / f"{script}.py")], env=env, capture_output=True,
                           text=True, timeout=300)
        receipts = [json.loads(l) for l in receipt.read_text().splitlines()] if receipt.exists() else []
    out = (p.stdout + p.stderr).replace(key, "[key]")
    return p.returncode, out, receipts


def main(live=False, out=print):
    cfg = load_budget()
    plan = {s: worst_case(s) for s in SCRIPTS}
    out(f"repro-kit: cap {cap_of(BUDGET, cfg)}, spent {spent(BUDGET, read_ledger())}; worst case if all run: {sum(plan.values())}")
    for s, c in plan.items():
        out(f"  {s}: up to {c} credits")
    if not live:
        out("dry run: nothing sent (use --live)")
        return None
    key, runs, used = find_key(), [], 0
    for s, c in plan.items():
        try:
            check(c)
        except BudgetExceeded as e:
            out(f"STOP before {s}: {e}")
            runs.append({"script": s, "skipped": str(e)})
            break
        code, text, receipts = run_one(s, key)
        rows = ledger_rows(receipts, s)
        with LEDGER.open("a", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        got = sum(r["credits"] for r in rows)
        receipts = [r for r in receipts if r["endpoint"] != "/usage"]
        used += got
        runs.append({"script": s, "exit_code": code, "credits": got, "request_ids": [r["request_id"] for r in receipts],
                     "output": text})
        out(f"{s}: exit {code}, {got} credits, request ids {[r['request_id'] for r in receipts]}")
    OUT.write_text(json.dumps({"date": datetime.now(timezone.utc).date().isoformat(), "budget": BUDGET,
                               "credits_used": used, "runs": runs}, indent=1, ensure_ascii=False) + "\n")
    out(f"credits used: {used} of {cap_of(BUDGET, cfg)}; log: {OUT.relative_to(ROOT)}")
    return used


if __name__ == "__main__":
    main(live="--live" in sys.argv)
