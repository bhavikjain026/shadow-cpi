#!/usr/bin/env python3
"""Network retry of FAILED Wayback CDX lookups only (logged; no Tavily call, no credits).

    python tools/wayback_retry.py finance   # results/finance_lookahead.json -> results/finance_lookahead_wayback_retry.json
    python tools/wayback_retry.py date      # results/date_field_test.json   -> results/date_field_test_wayback_retry.json

Only URLs whose lookup failed (captures None) are retried: 3 tries, 5 s apart, same CDX query and the same labelling
rules otherwise. The original result files are not changed: the pre-registered metric stays the primary result; this
writes before/after metrics side by side, labelled as a network retry.
"""
import copy
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from shadow_cpi.recorder import Recorder  # noqa: E402
from v2 import date_test as DT  # noqa: E402
from v2 import finance_lookahead as F  # noqa: E402

TRIES, WAIT = 3, 5


def results(out):
    return [r for row in out["rows"] for a in row["arms"].values() for r in a.get("results", [])]


def retry(rec, urls, tag):
    got, attempts = {}, {}
    for u in urls:
        for k in range(1, TRIES + 1):
            attempts[u] = k
            caps = DT.wayback(rec, u, tag=f"{tag} wayback retry {k}")
            if caps is not None:
                got[u] = caps
                break
            if k < TRIES:
                time.sleep(WAIT)
    return got, attempts


def relabel(test, out):
    for row in out["rows"]:
        for a in row["arms"].values():
            for r in a.get("results", []):
                if test == "finance":
                    r["label"] = F.label(row, r)
                else:
                    r["label"] = DT.label(row["cutoff"], r["captures"], r["tavily_date"], DT.url_date(r["url"]),
                                          r["page_date"])


def metrics(test, out):
    if test == "finance":
        return {"all": F.metrics(out), "without_C4": F.metrics(out, drop=("C4",))}
    return DT.metrics(out)


def main(test):
    src = F.OUT if test == "finance" else DT.OUT
    dst = src.with_name(src.stem + "_wayback_retry.json")
    if dst.exists():
        raise SystemExit(f"{dst} exists: the network retry runs once")
    out = json.loads(src.read_text(encoding="utf-8"))
    failed = sorted({r["url"] for r in results(out) if r["captures"] is None})
    got, attempts = retry(Recorder(), failed, test)
    after = copy.deepcopy(out)
    for r in results(after):
        if r["url"] in got:
            r["captures"] = got[r["url"]]
    relabel(test, after)
    rec = {"label": "NETWORK RETRY of failed Wayback lookups (logged); the pre-registered result in "
                    f"{src.name} stays primary", "run_utc": datetime.now(timezone.utc).isoformat(),
           "rule": f"only lookups that failed; {TRIES} tries, {WAIT} s apart; same CDX query and labels",
           "failed_urls": len(failed), "recovered": len(got), "still_failed": len(failed) - len(got),
           "tries_used": attempts, "before": out["metrics"], "after": metrics(test, after),
           "recovered_captures": got}
    dst.write_text(json.dumps(rec, ensure_ascii=False, indent=1))
    print(f"{test}: {len(failed)} failed lookups retried, {len(got)} recovered, {len(failed) - len(got)} still failed "
          f"-> {dst.name}")


if __name__ == "__main__":
    main(sys.argv[1])
