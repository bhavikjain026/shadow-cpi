#!/usr/bin/env python3
"""Demo of timelock.extract_as_of on R196 (label: demo, n=1, not a measurement). Budget 'asof-demo' in
config/budget.json (5 Tavily credits); no Nemotron call.

    python tools/asof_demo_r196.py           # prints the plan and the estimate; sends nothing (0 credits)
    python tools/asof_demo_r196.py --live    # one Tavily Extract (1 credit), Wayback CDX + one capture (direct)

R196 is the TCS results preview from the finance check (results/timelock34_second_review.json, finance_filtered
.example): Tavily dated it 2026-07-07, the cutoff is 2026-07-08, and the page was later updated with a link to the
actual result. The question: does the live Extract contain the post-cutoff result link, and does the as-of copy not?

Marker, fixed before the run: the result headline the reviewer quoted, matched by RESULT_LINK below. Every call goes
through the Recorder: Tavily through the credit ledger, Wayback as a logged direct download (service 'direct', the
same exception as the date test's CDX lookups). Writes results/asof_demo_r196.json: request_id, hashes, capture time.
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shadow_cpi.budget import BudgetExceeded, call_cost, cap_of, load_budget, read_ledger, spent  # noqa: E402
from timelock import Wayback, extract_as_of  # noqa: E402

BUDGET = "asof-demo"
TAG = "asof-demo"
OUT = ROOT / "results" / "asof_demo_r196.json"
EXTRACT = {"extract_depth": "basic"}
RESULT_LINK = re.compile(r"Q1\s*FY\s*27\s+results?\W+net\s+profit\s+rises", re.I)
LABEL = "demo, n=1, not a measurement"


def case():
    ex = json.loads((ROOT / "results" / "timelock34_second_review.json").read_text(encoding="utf-8"))
    ex = ex["finance_filtered"]["example"]
    assert ex["row_id"] == "R196"
    return ex


def estimate():
    return call_cost("/extract", {"urls": ["x"], **EXTRACT})


def check_budget():
    s, cap = spent(BUDGET, read_ledger()), cap_of(BUDGET, load_budget())
    if s + estimate() > cap:
        raise BudgetExceeded(f"budget '{BUDGET}': {s} spent + {estimate()} estimated > cap {cap}")
    return s, cap


class LoggedWayback(Wayback):
    """Wayback through the Recorder (cache + flight recorder), service 'direct'."""

    def __init__(self, rec):
        super().__init__()
        self.rec = rec

    def _get(self, url):
        def get():
            final, text = Wayback._get(self, url)
            return {"final_url": final, "text": text}
        resp, _ = self.rec.call("direct", "GET", {"url": url}, get, tag=TAG)
        return resp["final_url"], resp["text"]


class ExtractOnly:
    """A Budgeted Tavily client with the .extract(urls, **kw) -> dict shape timelock expects."""

    def __init__(self, tav):
        self.tav = tav

    def extract(self, urls, **params):
        return self.tav.extract(urls, tag=TAG, **params)[0]


def hits(text):
    return [m.group(0) for m in RESULT_LINK.finditer(text or "")]


def main(argv):
    ex = case()
    s, cap = check_budget()
    print(f"{BUDGET}: R196 {ex['url']}\n  cutoff {ex['cutoff']}, Tavily date {ex['our_published_date']}; estimate "
          f"{estimate()} Tavily credit(s), budget {s} of {cap} spent")
    if "--live" not in argv:
        print("Plan only: no call sent. Add --live to run it.")
        return None
    from shadow_cpi.budget import Budgeted
    from shadow_cpi.recorder import Recorder
    from shadow_cpi.tavily import Tavily
    tav = Budgeted(Tavily(recorder=Recorder()), [BUDGET])
    client = ExtractOnly(tav)
    got = extract_as_of(client, ex["url"], ex["cutoff"], published_date=ex["our_published_date"],
                        archive=LoggedWayback(Recorder()), **EXTRACT)
    live = client.extract([ex["url"]], **EXTRACT)       # the same request: served from the cache, 0 credits
    live_text = (live.get("results") or [{}])[0].get("raw_content") or ""
    out = {"label": LABEL, "run_utc": datetime.now(timezone.utc).isoformat(), "row_id": ex["row_id"],
           "url": ex["url"], "cutoff": ex["cutoff"], "tavily_date": ex["our_published_date"],
           "marker": RESULT_LINK.pattern,
           "live": {"request_id": got["request_id"], "text_sha256": got["live_sha256"], "chars": len(live_text),
                    "result_link_hits": hits(live_text)},
           "as_of": {"provenance": got["provenance"], "text_sha256": got["text_sha256"],
                     "chars": None if got["text"] is None else len(got["text"]),
                     "result_link_hits": None if got["text"] is None else hits(got["text"])},
           "evidence": got["evidence"], "tavily_credits": tav.used, "nemotron_calls": 0}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("live", "as_of", "evidence", "tavily_credits")}, indent=1))
    print(f"-> {OUT.relative_to(ROOT)}")
    return out


if __name__ == "__main__":
    main(sys.argv[1:])
