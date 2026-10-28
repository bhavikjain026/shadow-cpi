#!/usr/bin/env python3
"""Positive demo of timelock.extract_as_of: a page whose as-of copy exists (label: demo, n=1). Budget 'asof-demo'
in config/budget.json (5 Tavily credits, shared with tools/asof_demo_r196.py); no Nemotron call.

    python tools/asof_demo_served.py           # lists the candidates from saved files; sends nothing
    python tools/asof_demo_served.py --live    # CDX lookups to pick the page, then one extract_as_of (1 credit)

The page is picked by a rule fixed before any call (committed with this script):
  1. Cases from benchmarks/timelock34/cases.jsonl (the date test and the finance check), in case-id order: letter,
     then number (C1..C14, E1..E20); results in their saved order; a URL already seen in an earlier case is skipped.
  2. Candidate: Tavily's or the page's date is before the cutoff, and the saved Wayback capture dates include one on or
     before the cutoff and one after it.
  3. For each candidate in that order, a live Wayback CDX lookup (logged direct download, at most MAX_LOOKUPS): the page
     is the one where the latest capture on or before the cutoff has a later capture with a different digest.
  4. extract_as_of runs on that page once. If it does not serve a Wayback copy, the result is saved as it is and no
     second page is tried.

Marker, fixed before the run: dates written in the text that fall after the cutoff (the three date patterns of
timelock.dates). Expected for a served copy: some in the live Extract, none in the as-of copy. Writes
results/asof_demo_served.json: request_id, hashes, capture time, provenance.
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from asof_demo_r196 import BUDGET, EXTRACT, ExtractOnly, LoggedWayback, check_budget, estimate  # noqa: E402
from timelock import extract_as_of  # noqa: E402
from timelock.asof import _ts_date, _ts_time  # noqa: E402
from timelock.dates import _DATES  # noqa: E402

CASES = ROOT / "benchmarks" / "timelock34" / "cases.jsonl"
OUT = ROOT / "results" / "asof_demo_served.json"
LABEL = "demo, n=1"
MAX_LOOKUPS = 25


def case_key(c):
    m = re.match(r"([A-Za-z]+)(\d+)$", c["id"])
    return (m[1], int(m[2])) if m else (c["id"], 0)


def candidates(path=CASES):
    """(case, result) pairs meeting rule 2, in rule-1 order."""
    cases = sorted((json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()),
                   key=case_key)
    seen, out = set(), []
    for c in cases:
        cut = c["cutoff"]
        for r in c["results"]:
            if r["url"] in seen:
                continue
            seen.add(r["url"])
            dated_before = any(d and d[:10] < cut for d in (r.get("published_date"), r.get("page_date")))
            caps = r.get("wayback_captures") or []
            if dated_before and any(d <= cut for d in caps) and any(d > cut for d in caps):
                out.append((c, r))
    return out


def digest_changed(captures, cutoff):
    """Rule 3 on a CDX list [(timestamp, digest)]: the latest capture on or before the cutoff, and a later capture with
    a different digest. (pre_ts, later_ts) or None."""
    before = [(t, d) for t, d in captures or [] if _ts_date(t) <= cutoff]
    if not before:
        return None
    t0, d0 = before[-1]
    later = next((t for t, d in captures if t > t0 and d != d0), None)
    return (t0, later) if later else None


def post_cutoff_dates(text, cutoff):
    """The marker: distinct ISO dates written in the text that are after the cutoff."""
    found = set()
    for pat, mk in _DATES:
        for m in re.finditer(pat, text or ""):
            try:
                iso = mk(m).isoformat()
            except ValueError:
                continue
            if iso > cutoff:
                found.add(iso)
    return sorted(found)


def pick(archive, cands, max_lookups=MAX_LOOKUPS):
    """The first candidate passing rule 3, its CDX evidence, and the lookups made."""
    tried = []
    for c, r in cands[:max_lookups]:
        caps = archive.captures(r["url"])
        hit = digest_changed(caps, c["cutoff"])
        tried.append({"case": c["id"], "url": r["url"], "captures": None if caps is None else len(caps),
                      "passes": bool(hit)})
        if hit:
            return c, r, hit, tried
    return None, None, None, tried


def main(argv):
    cands = candidates()
    s, cap = check_budget()
    print(f"{BUDGET}: {len(cands)} candidates by rules 1-2; estimate {estimate()} Tavily credit(s), budget {s} of {cap}")
    for c, r in cands[:5]:
        print(f"  {c['id']} cutoff {c['cutoff']} {r['url']}")
    if "--live" not in argv:
        print("Plan only: no call sent. Add --live to run it.")
        return None
    from shadow_cpi.budget import Budgeted
    from shadow_cpi.recorder import Recorder
    from shadow_cpi.tavily import Tavily
    archive = LoggedWayback(Recorder())
    c, r, hit, tried = pick(archive, cands)
    out = {"label": LABEL, "run_utc": datetime.now(timezone.utc).isoformat(), "rule": __doc__.split("Marker")[0].strip(),
           "cdx_lookups": tried, "tavily_credits": 0, "nemotron_calls": 0}
    if c is None:
        out["result"] = f"no candidate passed rule 3 in {len(tried)} CDX lookups; no Extract sent"
        OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(out["result"])
        return out
    tav = Budgeted(Tavily(recorder=Recorder()), [BUDGET])
    client = ExtractOnly(tav)
    cut = c["cutoff"]
    got = extract_as_of(client, r["url"], cut, published_date=r.get("published_date"), archive=archive, **EXTRACT)
    live = client.extract([r["url"]], **EXTRACT)       # the same request: served from the cache, 0 credits
    live_text = (live.get("results") or [{}])[0].get("raw_content") or ""
    out.update({"case": c["id"], "dataset": c["dataset"], "url": r["url"], "cutoff": cut,
                "tavily_date": r.get("published_date"), "saved_page_date": r.get("page_date"),
                "cdx_pre_cutoff_capture": _ts_time(hit[0]), "cdx_later_different_capture": _ts_time(hit[1]),
                "marker": "dates written in the text after the cutoff",
                "live": {"request_id": got["request_id"], "text_sha256": got["live_sha256"], "chars": len(live_text),
                         "post_cutoff_dates": post_cutoff_dates(live_text, cut)},
                "as_of": {"provenance": got["provenance"], "text_sha256": got["text_sha256"],
                          "chars": None if got["text"] is None else len(got["text"]),
                          "post_cutoff_dates": None if got["text"] is None else post_cutoff_dates(got["text"], cut)},
                "evidence": got["evidence"], "tavily_credits": tav.used})
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("case", "url", "cutoff", "live", "as_of", "tavily_credits")}, indent=1))
    print(f"-> {OUT.relative_to(ROOT)}")
    return out


if __name__ == "__main__":
    main(sys.argv[1:])
