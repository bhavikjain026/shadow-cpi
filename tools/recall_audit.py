#!/usr/bin/env python3
"""Recall audit of the event layer on 2025 (the calibration year; tuning allowed here, never on 2026).

    python tools/recall_audit.py run  <label>    # run the event layer on the audit months (hard cap 'recall-audit')
    python tools/recall_audit.py score <label>   # recall vs the reference list + why each miss was dropped

The reference list (REFERENCE) was built from news BEFORE running the layer: results/recall_reference_search.json
(+ IOCL's official LPG price list for R1).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from shadow_cpi import evidence as E  # noqa: E402
from shadow_cpi.budget import BudgetExceeded, Budgeted  # noqa: E402
from shadow_cpi.nemotron import Nemotron  # noqa: E402
from shadow_cpi.recorder import Recorder, read_log  # noqa: E402
from shadow_cpi.tavily import Tavily, best_date  # noqa: E402

MONTHS = ["2025-09", "2025-04", "2025-05"]        # September first: GST is the last kind searched in a month
REFERENCE = [
    {"id": "R1", "month": "2025-04", "kind": "lpg", "effective": "2025-04-08", "what": "Domestic LPG +Rs 50 (803 -> 853)",
     "keys": ["lpg", "cylinder", "एलपीजी", "सिलेंडर"], "evidence": "https://iocl.com/indane-14Kg-nonsubsid-previous-price"},
    {"id": "R2", "month": "2025-04", "kind": "milk", "effective": "2025-04-30", "what": "Mother Dairy milk +Rs 2/litre",
     "keys": ["mother dairy", "मदर डेयरी"], "evidence": "https://www.instagram.com/p/DJFCkYGoK05"},
    {"id": "R3", "month": "2025-05", "kind": "milk", "effective": "2025-05-01", "what": "Amul milk +Rs 2/litre",
     "keys": ["amul", "अमूल"], "evidence": "https://agrimoon.com/why-amuls-%E2%82%B92-hike-reflects-more-than-just-market-forces"},
    {"id": "R4", "month": "2025-09", "kind": "gst", "effective": "2025-09-22", "what": "GST two-slab rate cuts",
     "keys": ["gst", "जीएसटी"], "evidence": "https://www.thehindu.com/news/national/gst-20-implementation-a-festival-of-savings-first-step-towards-economic-self-reliance-pm/article70074409.ece"},
]
OUT = ROOT / "results" / "recall_audit"


def run(label, cache_only=False):
    cfg = E.load_items()
    events = {k: v for k, v in cfg["events"].items() if k != "fuel"}   # petrol did not move in 2025
    rec = Recorder()
    tav, nem = Budgeted(Tavily(recorder=rec), ["recall-audit"], cache_only=cache_only), Nemotron(recorder=rec)
    OUT.mkdir(parents=True, exist_ok=True)
    for m in MONTHS:
        try:
            kept, stats, trace = E.collect_events(tav, nem, m, events)
        except BudgetExceeded as e:
            print(f"STOPPED at {m}: {e}")
            break
        (OUT / f"{label}_{m}.json").write_text(json.dumps(
            {"kept": kept, "stats": {k: v for k, v in stats.items() if k != "_month"}, "trace": trace},
            ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        print(f"{m}: {len(kept)} events kept; credits so far {tav.used}", flush=True)


def search_dispositions(month, kind):
    """For every search the layer ran for this kind and month: each result, its date and what happened to it."""
    start = E.search_window(month, E.EVENT_PRE_DAYS)[0]
    out = []
    for e in read_log():
        if e.get("tag") != f"event:{kind} search" or e["endpoint"] != "/search":
            continue
        p = e["params"]
        if not (start <= p.get("start_date", "") <= E.month_window(month)[1]):
            continue
        resp = json.loads((ROOT / "cache" / "tavily" / f"{e['cache_key']}.json").read_text())["response"]
        inside = 0
        for r in resp.get("results", []):
            d, src = best_date(r)
            ok = bool(d) and p["start_date"] <= d <= p["end_date"]
            inside += ok
            out.append({"query": p["query"], "window": (p["start_date"], p["end_date"]), "url": r["url"],
                        "title": r.get("title", ""), "content": r.get("content", ""), "date": d, "date_source": src,
                        "published_date": r.get("published_date"),
                        "fate": ("page has no date" if not d else "dated outside the window" if not ok
                                 else "extracted (top 6)" if inside <= E.EXTRACT_TOP else "not extracted (beyond top 6)")})
    return out


def score(label):
    rows = []
    for ref in REFERENCE:
        f = OUT / f"{label}_{ref['month']}.json"
        if not f.exists():
            rows.append({**ref, "found": False, "why": "month not run"})
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        hit = [e for e in d["kept"] if e["kind"] == ref["kind"] and abs(int(e["effective_date"][8:]) -
               int(ref["effective"][8:])) <= 2 and e["effective_date"][:7] == ref["effective"][:7]]
        if hit:
            rows.append({**ref, "found": True, "why": "kept", "url": hit[0]["url"]})
            continue
        low = lambda t: (t or "").lower()                      # noqa: E731
        traced = [t for t in d["trace"] if t.get("kind") == ref["kind"] and
                  any(k in low(t.get("line")) + low(t.get("item_or_service")) + low(t.get("seller_or_authority"))
                      for k in ref["keys"])]
        if traced:
            verdicts = sorted({t["verdict"] for t in traced})
            rows.append({**ref, "found": False, "why": "extracted but dropped: " + "; ".join(verdicts),
                         "examples": traced[:3]})
            continue
        disp = [r for r in search_dispositions(ref["month"], ref["kind"])
                if any(k in low(r["title"]) + low(r["content"]) + low(r["url"]) for k in ref["keys"])]
        if disp:
            fates = sorted({r["fate"] for r in disp})
            rows.append({**ref, "found": False, "why": "in search results but: " + "; ".join(fates),
                         "examples": disp[:4]})
        else:
            rows.append({**ref, "found": False, "why": "not in any search result"})
    found = sum(r["found"] for r in rows)
    (OUT / f"{label}_score.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"recall {found} of {len(rows)}")
    for r in rows:
        print(f"  {r['id']} {r['what']:38s} {'FOUND' if r['found'] else 'missed'}: {r['why']}")
    return rows


if __name__ == "__main__":
    if sys.argv[1] == "run":
        run(sys.argv[2], cache_only="--cache-only" in sys.argv)
    else:
        score(sys.argv[2])
