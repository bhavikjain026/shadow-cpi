#!/usr/bin/env python3
"""Live demo for the video: one past price change, end to end, under its own cap (budget 'demo-live' in
config/budget.json).

    python tools/demo_live.py            # prints the plan and the credit estimate; sends nothing (0 credits)
    python tools/demo_live.py --live     # one time-locked Tavily Search, Extract, Nemotron Nano gate, Super citation

The case is the date test's frozen case E8 (v2/date_test_cases.json): its query and cutoff, searched with
shadow_cpi.pit (start_date/end_date + filter_by_published_date; results after the cutoff dropped). The top results
the lock keeps are read with Tavily Extract, one at a time, until Nemotron Nano says the page states a price change and
Nemotron Super cites a line that code verifies (the line is copied from the Extract output and the number checked in
it). Prints the Token Factory endpoint host, both model IDs, Tavily's request_id and response hash, and the verified
line. Never prints a key. Every call goes through the Recorder (cache + flight recorder) and the credit ledger.
"""
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shadow_cpi.budget import BudgetExceeded, call_cost, cap_of, load_budget, read_ledger, spent  # noqa: E402
from shadow_cpi.evidence import GATE_QUESTION, GATE_SCHEMA, GATE_SYSTEM  # noqa: E402
from shadow_cpi.pit import pit_search  # noqa: E402
from shadow_cpi.verify import price_in_line  # noqa: E402

BUDGET = "demo-live"
CASE_ID = "E8"
EXTRACT_TOP = 3                                   # at most this many kept results are read
SEARCH = {"topic": "news", "search_depth": "basic", "max_results": 5, "include_published_date": True}
TAG = "demo-live"


def load_case(case_id=CASE_ID, path=ROOT / "v2" / "date_test_cases.json"):
    return next(c for c in json.loads(Path(path).read_text(encoding="utf-8"))["cases"] if c["id"] == case_id)


def estimate():
    """Upper bound in Tavily credits: one search plus one single-URL extract per result read."""
    return call_cost("/search", SEARCH) + EXTRACT_TOP * call_cost("/extract", {"urls": ["x"]})


def check_budget(cfg=None, ledger_path=None):
    """Refuse before any call if the estimate would take 'demo-live' past its cap. Returns (spent, cap)."""
    cfg = cfg or load_budget()
    ledger = read_ledger(ledger_path) if ledger_path else read_ledger()
    s, cap = spent(BUDGET, ledger), cap_of(BUDGET, cfg)
    if s + estimate() > cap:
        raise BudgetExceeded(f"budget '{BUDGET}': {s} spent + {estimate()} estimated > cap {cap}")
    return s, cap


def verified_line(events):
    """The first event whose cited line exists and holds its number (new price, or the % change)."""
    for e in events:
        if not e.get("verified") or not e.get("quote"):
            continue
        if e.get("new_price") is not None or (e.get("pct_change") is not None
                                              and price_in_line(e["pct_change"], e["quote"])):
            return e
    return None


def run(case, tav, nem, roles, host, out=print):
    """The demo. `tav` is a Budgeted Tavily client, `nem` a Nemotron client, `roles` config/models.json."""
    nano, sup = roles["small"], roles["mid"]
    out(f"Token Factory endpoint host: {host}")
    out(f"Nemotron Nano (gate): {nano}")
    out(f"Nemotron Super (line citation): {sup}")
    out(f"Case {case['id']}: {case['query']!r}, cutoff {case['cutoff']}")
    res = pit_search(case["query"], case["cutoff"], tavily=tav, tag=TAG, **SEARCH)
    out(f"Tavily search, window {res['window'][0]} to {res['window'][1]}, filter_by_published_date=true")
    out(f"  request_id {res['request_id']}")
    out(f"  response SHA-256 {res['response_sha256']}")
    out(f"  {len(res['kept'])} kept, {len(res['flagged'])} undated (not trusted), {len(res['leaks'])} after the cutoff "
        "(dropped)")
    found = {"host": host, "nano": nano, "super": sup, "request_id": res["request_id"],
             "response_sha256": res["response_sha256"], "url": None, "gate": None, "line": None, "event": None}
    for r in res["kept"][:EXTRACT_TOP]:
        resp, ecid = tav.extract([r["url"]], tag=TAG, parent=res["call_id"])
        text = (resp["results"][0].get("raw_content") or "") if resp["results"] else ""
        out(f"Extract {r['url']} ({r.get('published_date') or 'undated'}): {len(text):,} characters")
        if not text:
            continue
        gate, _ = nem.chat_json(nano, GATE_SYSTEM, GATE_QUESTION + text[:6000], GATE_SCHEMA, max_tokens=20, tag=TAG,
                                parent=ecid)
        out(f"  Nano gate: {gate.get('answer')}")
        if gate.get("answer") != "yes":
            continue
        events, _ = nem.price_events(sup, text, tag=TAG, parent=ecid)
        e = verified_line(events)
        if e:
            found.update(url=r["url"], gate=gate.get("answer"), line=e["quote"], event=e)
            out(f"  Super cited a line; code checked the number is in it: VERIFIED\n  \"{e['quote']}\"")
            return found
        out("  Super cited no line that holds its number")
    out("No verified line in the pages read")
    return found


def main(argv):
    case = load_case()
    s, cap = check_budget()
    print(f"demo-live: case {case['id']} ({case['query']}, cutoff {case['cutoff']}); estimate {estimate()} Tavily "
          f"credits, budget '{BUDGET}' {s} of {cap} spent")
    if "--live" not in argv:
        print("Plan only: no call sent. Add --live to run it (needs both keys in .env).")
        return None
    from shadow_cpi.budget import Budgeted
    from shadow_cpi.nemotron import Nemotron
    from shadow_cpi.settings import NEBIUS_BASE, models
    from shadow_cpi.tavily import Tavily
    tav = Budgeted(Tavily(), [BUDGET])
    nem = Nemotron(base=NEBIUS_BASE)
    found = run(case, tav, nem, models(), urlparse(NEBIUS_BASE).netloc)
    print(f"Tavily credits used: {tav.used}")
    return found


if __name__ == "__main__":
    main(sys.argv[1:])
