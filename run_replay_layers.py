#!/usr/bin/env python3
"""Replay layers that do not need the spine, for test months: event layer (target month + last 10 days of the
previous month, applied by effective date), IBJA gold/silver, IOCL LPG and PPAC petrol, with the fixed 2025
pass-through factors from config/passthrough.json.

    python run_replay_layers.py 2026-01              # one month
    python run_replay_layers.py 2026-01 2026-02 ...  # several, in order

Hard caps (config/budget.json): 'replay-layers' (whole step) and 'replay-layers-month/<month>' (each month); the
IBJA/IOCL/PPAC fetches also charge 'ibja-iocl'. TEST MONTHS: results are recorded, never used to change any
parameter, filter or factor, and NOT scored against official CPI here.
"""
import csv
import json
import re
import sys
import time

from shadow_cpi import cpi_math as M
from shadow_cpi import evidence as E
from shadow_cpi import official as O
from shadow_cpi.budget import BudgetExceeded, Budgeted, spent
from shadow_cpi.nemotron import Nemotron
from shadow_cpi.recorder import Recorder, read_log
from shadow_cpi.tavily import Tavily

OUT_CSV = O.ROOT / "results" / "replay_layers.csv"
PPAC_URL = "https://ppac.gov.in/archives/impnews"
PPAC_ROW = re.compile(r"RSP of Petrol in Delhi as per IOCL outlet as on (\d{1,2})-(\w+)-(\d{4}), Rs\. ([\d.]+)/ltr")


def cached_page(url_part, tag, cache_dir=None, log_file=None):
    """Text of an already-fetched page (from the Tavily cache, via the flight recorder). Defaults: cache/, logs/."""
    from pathlib import Path
    cache_dir = Path(cache_dir or O.ROOT / "cache")
    for e in reversed(read_log(log_file) if log_file else read_log()):
        if e.get("tag") == tag and e["endpoint"] == "/extract":
            p = cache_dir / "tavily" / f"{e['cache_key']}.json"
            if not p.exists():
                continue
            resp = json.loads(p.read_text())["response"]
            for p in resp["results"]:
                if url_part in p["url"]:
                    return p["raw_content"]
    return ""


def ppac_petrol(text):
    """{iso_date: (price, exact line)} for Delhi petrol (IOCL outlet) from PPAC's 'Important news' archive."""
    out = {}
    for m in PPAC_ROW.finditer(text):
        dd, mon, yy, price = m.groups()
        iso = f"{yy}-{E.MONTHS_EN.index(mon) + 1:02d}-{int(dd):02d}"
        out[iso] = (float(price), m.group(0))
    return out


def month_avg(daily, month):
    v = [p for d, (p, _) in daily.items() if d.startswith(month)]
    return (sum(v) / len(v), len(v)) if v else (None, 0)


def cached_lpg_petrol(cache_dir=None, log_file=None):
    """(IOCL LPG revisions, PPAC Delhi petrol {date: (price, line)}, IOCL list retrieved_at) from the Tavily cache.
    Also used by build_nowcast.py. Defaults: cache/ and logs/flight_recorder.jsonl."""
    from pathlib import Path
    cache_dir = Path(cache_dir or O.ROOT / "cache")
    kw = {"cache_dir": cache_dir, "log_file": log_file}
    lpg_rev = E.parse_iocl_lpg(cached_page("iocl.com/indane-14Kg", "p2-history", **kw)
                               or cached_page("iocl.com/indane-14Kg", "observed:lpg extract", **kw))
    petrol = ppac_petrol(cached_page("ppac.gov.in", "observed:petrol extract", **kw))
    iocl_at = ""
    for e in read_log(log_file) if log_file else read_log():
        if e["endpoint"] == "/extract" and "iocl.com/indane-14Kg" in json.dumps(e.get("params")) and not e["cached"]:
            p = cache_dir / "tavily" / f"{e['cache_key']}.json"      # the first fetch only; missing = unknown date
            iocl_at = json.loads(p.read_text())["retrieved_at"] if p.exists() else ""
            break
    return lpg_rev, petrol, iocl_at


IOCL_RETRIEVED = ""


def observed_layers(month, row, ibja, lpg_rev, petrol, factors, iocl_retrieved, window_end=None):
    """IBJA gold/silver, IOCL LPG and PPAC petrol changes for `month` (fills `row`, returns `observed`). Also used by
    build_nowcast.py. window_end: last day the evidence may cover (default: month end); Amendment 1 (a) records an
    LPG gap when IOCL's list was retrieved before it."""
    prev = M.add_months(month, -1)
    observed = {}
    for item in ("gold", "silver"):
        a, na = E.monthly_average(ibja, item, month)
        b, nb = E.monthly_average(ibja, item, prev)
        ok = a and b and na >= 5 and nb >= 5
        ch = a / b - 1 if ok else None
        observed[item] = {"avg_now": a, "days_now": na, "avg_prev": b, "days_prev": nb, "change": ch}
        row.update({f"{item}_obs_change": ch, f"{item}_days": f"{na}/{nb}", f"{item}_factor": factors[item]["factor"],
                    f"{item}_item_change": None if ch is None else ch * factors[item]["factor"]})
    gap = (window_end or E.month_window(month)[1]) > iocl_retrieved[:10]      # Amendment 1 (a): months IOCL's list cannot cover
    lpg_ch = None if gap else E.lpg_monthly(lpg_rev, month) / E.lpg_monthly(lpg_rev, prev) - 1
    observed["lpg"] = {"avg_now": E.lpg_monthly(lpg_rev, month), "avg_prev": E.lpg_monthly(lpg_rev, prev),
                       "change": lpg_ch, "gap": gap, "iocl_list_retrieved_at": iocl_retrieved}
    row.update({"lpg_obs_change": lpg_ch, "lpg_factor": factors["lpg"]["factor"], "lpg_gap": gap,
                "lpg_item_change": None if lpg_ch is None else lpg_ch * factors["lpg"]["factor"]})
    a, na = month_avg(petrol, month)
    b, nb = month_avg(petrol, prev)
    p_ch = a / b - 1 if a and b else None
    observed["petrol"] = {"avg_now": a, "days_now": na, "avg_prev": b, "days_prev": nb, "change": p_ch,
                          "note": "PPAC daily Delhi rows exist only from 15 May 2026"}
    row.update({"petrol_obs_change": p_ch, "petrol_days": f"{na}/{nb}", "petrol_factor": factors["petrol"]["factor"],
                "petrol_item_change": None if p_ch is None else p_ch * factors["petrol"]["factor"]})
    return observed


def run_month(month, tav_all, nem, ibja, lpg_rev, petrol, factors, cfg):
    extra = [a.split("=", 1)[1] for a in sys.argv if a.startswith("--budget=")]
    tav = tav_all.charge("replay-layers", f"replay-layers-month/{month}", *extra)
    t0 = time.time()
    events, estats, etrace = E.collect_events(tav, nem, month, cfg["events"])
    row = {"month": month, "events_verified": len(events)}
    observed = observed_layers(month, row, ibja, lpg_rev, petrol, factors, IOCL_RETRIEVED)
    row["events"] = "; ".join(f"{e['kind']} {e.get('region') or ''} {e['change'] * 100:+.2f}% from {e['effective_date']} "
                              f"(prorated {e['change_prorated'] * 100:+.2f}%)" for e in events)
    row["credits"] = spent(f"replay-layers-month/{month}")
    rows = {"gold": [], "silver": [], "lpg": []}
    for d, r in sorted(ibja.items()):
        if d.startswith(month):
            rows["gold"].append({"price": r["gold"], "unit": "Rs/10 g (999, PM)", "place": "India (IBJA)", "date": d,
                                 "line": r["line"], "url": r["url"]})
            rows["silver"].append({"price": r["silver"], "unit": "Rs/kg (999, PM)", "place": "India (IBJA)",
                                   "date": d, "line": r["line"], "url": r["url"]})
    in_force = [r for r in lpg_rev if r[0] <= E.month_window(month)[1]]
    for eff, prices, line in [r for r in in_force if r[0] >= f"{month}-01"] or in_force[-1:]:
        for city, price in prices.items():
            rows["lpg"].append({"price": price, "unit": "Rs/cylinder (14.2 kg)", "place": city.title(), "date": eff,
                                "line": line, "url": E.IOCL_LPG_URL})
    rows["petrol"] = [{"price": p, "unit": "Rs/litre", "place": "Delhi (IOCL outlet)", "date": d, "line": line,
                       "url": PPAC_URL} for d, (p, line) in sorted(petrol.items()) if d.startswith(month)]
    for k in rows:
        observed[k]["rows"] = rows[k]
    empty_q = {"drops": {}, "leak_drops": 0, "by_lang": {}, "queries": []}
    detail = {"test_month": True, "scored": False, "layers": "events + observed (no spine, no quotes)",
              "observed": {k: {x: y for x, y in v.items() if x != "rows"} for k, v in observed.items()},
              "passthrough": {k: factors[k]["factor"] for k in ("gold", "silver", "lpg", "petrol")},
              "event_stats": {k: v for k, v in estats.items() if k != "queries"},
              "event_search_window": {"pre_days": E.EVENT_PRE_DAYS, "applied_by": "effective date inside the month"},
              "credits_this_month": row["credits"], "budgets": tav.budgets, "seconds": round(time.time() - t0)}
    man = E.build_manifest(month, [], empty_q, events, estats, observed, [], detail)
    old = E.MANIFEST_DIR / f"{month}.json"
    if old.exists():                      # this step rewrites events only: keep quotes already in the manifest
        prev = json.loads(old.read_text())
        key = lambda q: (q.get("item"), q.get("url"), q.get("line"), q.get("date"))     # noqa: E731
        new = {key(q) for q in man["quotes"]}
        man["quotes"] = [q for q in prev.get("quotes", []) if key(q) not in new] + man["quotes"]
        if "quotes_restored_from" in prev.get("detail", {}):
            man["detail"]["quotes_restored_from"] = prev["detail"]["quotes_restored_from"]
    E.write_manifest(month, man)
    (E.EVIDENCE_DIR / f"{month}_trace.json").write_text(json.dumps({"events": etrace}, ensure_ascii=False, indent=1),
                                                         encoding="utf-8")
    return row


def main():
    months = [a for a in sys.argv[1:] if re.fullmatch(r"\d{4}-\d{2}", a)]
    if "--cache-only" in sys.argv:
        print("CACHE-ONLY: no Tavily call will be sent; anything not cached is skipped and recorded")
    if any(m not in E.REPLAY_MONTHS for m in months):
        raise SystemExit("replay layers are for test months 2026-01..2026-09 only")
    cfg = E.load_items()
    factors = json.loads(E.PASSTHROUGH_FILE.read_text())["items"]
    rec = Recorder()
    base = Budgeted(Tavily(recorder=rec), ["replay-layers"], cache_only="--cache-only" in sys.argv)
    nem = Nemotron(recorder=rec)
    try:
        ibja, _, ibja_failed = E.ibja_daily(base.charge("replay-layers", "ibja-iocl"),
                                            O.month_range("2025-01", max(months)))
    except BudgetExceeded as e:
        raise SystemExit(f"STOPPED: {e}")
    lpg_rev, petrol, iocl_at = cached_lpg_petrol()
    global IOCL_RETRIEVED
    IOCL_RETRIEVED = iocl_at
    existing = {}
    if OUT_CSV.exists():
        with OUT_CSV.open(encoding="utf-8") as f:
            existing = {r["month"]: r for r in csv.DictReader(f)}
    cols = ["month", "events_verified", "events", "gold_obs_change", "gold_days", "gold_factor", "gold_item_change",
            "silver_obs_change", "silver_days", "silver_factor", "silver_item_change", "lpg_obs_change", "lpg_factor",
            "lpg_item_change", "lpg_gap", "petrol_obs_change", "petrol_days", "petrol_factor", "petrol_item_change", "credits"]
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    for m in months:
        try:
            row = run_month(m, base, nem, ibja, lpg_rev, petrol, factors, cfg)
        except BudgetExceeded as e:
            print(f"STOPPED before spending more ({m}): {e}")
            break
        existing[m] = row
        print(f"{m}: {row['events_verified']} verified events; credits {row['credits']}; {row['events'] or 'no events'}",
              flush=True)
        with OUT_CSV.open("w", newline="", encoding="utf-8") as f:      # saved after every month
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            for k in sorted(existing):
                w.writerow({c: existing[k].get(c, "") for c in cols})
    print(f"IBJA reports failed: {len(ibja_failed)}; step total {spent('replay-layers')} of cap 400")


if __name__ == "__main__":
    main()
