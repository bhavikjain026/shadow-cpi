#!/usr/bin/env python3
"""Prompt 2 - evidence engine for one month.

    python run_evidence.py 2026-03 --estimate     # credit estimate only
    python run_evidence.py 2026-03                # run (cached calls are free); stops BEFORE the cap is passed

Writes config/passthrough.json, data/evidence/<month>.json (+ _trace.json) and manifests/<month>.json.
"""
import json
import sys
import time

from shadow_cpi import cpi_math as M
from shadow_cpi import evidence as E
from shadow_cpi import official as O
from shadow_cpi.nemotron import Nemotron
from shadow_cpi.recorder import Recorder, read_log
from shadow_cpi.tavily import Tavily

PT_MONTHS = [f"2025-{m:02d}" for m in range(2, 13)]   # 2025 only (Jan 2025 has no official MoM)
MIN_DAYS = 5                                 # an IBJA monthly average needs at least 5 trading days


def estimate(items, events):
    """Upper bound: each search 1 credit + extract of the top 6 pages (2 credits)."""
    per_search = 1 + 2
    quotes = len(items) * 2 * per_search
    ev = sum(len(c.get("langs", ["en", "hi"])) for c in events.values()) * per_search
    return {"quotes, target month": quotes, "quotes, previous month (for matching)": quotes,
            "events, target month": ev, "events, last 10 days of previous month": ev}


def food_passthrough(series):
    """Foods: official item (or sub-class) MoM vs the spine's MoM (geometric mean over centres), 2025 only."""
    spine = E.load_spine()
    out = {}
    for food, code in E.SPINE_FOODS.items():
        if not spine:
            out[food] = {"factor": None, "note": "pending: needs the government spine (data/spine.csv)"}
            continue
        obs = {m: E.spine_change(spine, food, m)[0] for m in PT_MONTHS}
        off = {m: M.mom(series[code], m) for m in PT_MONTHS}
        f, n, used = E.fit_passthrough(off, {m: v for m, v in obs.items() if v is not None}, PT_MONTHS)
        out[food] = {"factor": f, "n_months": n, "months": used, "cpi_item": code,
                     "observed": "Dept of Consumer Affairs retail prices (spine), centres present in both months"}
    return out


def passthrough(series, ibja, lpg_rev):
    out = {"_fitted_on": "2025 only (Feb-Dec 2025 MoM; official item index vs observed price)", "items": {}}
    for item, field, code in (("gold", "gold", "13.2.1.1.1.01"), ("silver", "silver", "13.2.1.1.1.02")):
        obs = {}
        for m in PT_MONTHS:
            a, na = E.monthly_average(ibja, field, m)
            b, nb = E.monthly_average(ibja, field, M.add_months(m, -1))
            if a and b and na >= MIN_DAYS and nb >= MIN_DAYS:
                obs[m] = a / b - 1
        off = {m: M.mom(series[code], m) for m in PT_MONTHS}
        f, n, used = E.fit_passthrough(off, obs, PT_MONTHS)
        out["items"][item] = {"factor": f, "n_months": n, "months": used, "observed": "IBJA 999 PM daily rates",
                              "cpi_item": code}
    obs = {m: E.lpg_monthly(lpg_rev, m) / E.lpg_monthly(lpg_rev, M.add_months(m, -1)) - 1 for m in PT_MONTHS}
    off = {m: M.mom(series["04.5.2.2.1.01"], m) for m in PT_MONTHS}
    f, n, used = E.fit_passthrough(off, obs, PT_MONTHS)
    out["items"]["lpg"] = {"factor": f, "n_months": n, "months": used, "cpi_item": "04.5.2.2.1.01",
                           "observed": "IOCL domestic 14.2 kg, 4-metro mean, day-weighted"}
    out["items"]["petrol"] = {"factor": 1.0, "n_months": 0, "cpi_item": "07.2.2.2.1.01",
                              "note": "not fitted: the official petrol index did not move in 2025; fixed at 1.0 in "
                                      "advance (the CPI item is the pump price)"}
    out["items"].update(food_passthrough(series))
    E.PASSTHROUGH_FILE.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def observed_rows(ibja, lpg_rev, month):
    """Rows for the manifest: every IBJA daily rate in the month, and the IOCL revisions in force in the month."""
    rows = {"gold": [], "silver": [], "lpg": []}
    for d, r in sorted(ibja.items()):
        if d.startswith(month):
            rows["gold"].append({"price": r["gold"], "unit": "Rs/10 g (999, PM)", "place": "India (IBJA)", "date": d,
                                 "line": r["line"], "url": r["url"]})
            rows["silver"].append({"price": r["silver"], "unit": "Rs/kg (999, PM)", "place": "India (IBJA)",
                                   "date": d, "line": r["line"], "url": r["url"]})
    in_force = [r for r in lpg_rev if r[0] <= month_end(month)]
    for eff, prices, line in [r for r in in_force if r[0] >= f"{month}-01"] or in_force[-1:]:
        for city, price in prices.items():
            rows["lpg"].append({"price": price, "unit": "Rs/cylinder (14.2 kg)", "place": city.title(), "date": eff,
                                "line": line, "url": E.IOCL_LPG_URL})
    return rows


def month_end(month):
    return E.month_window(month)[1]


def main():
    month = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "2026-03"
    prev = M.add_months(month, -1)
    cfg = E.load_items()
    est = estimate(cfg["quote_items"], cfg["events"])
    print(f"Credit estimate for {month} (upper bound, cached calls are free): {est} = {sum(est.values())}; "
          f"hard caps in config/budget.json")
    if "--estimate" in sys.argv:
        return
    rec = Recorder()
    tav = E.Budgeted(Tavily(recorder=rec), [f"live-month/{month}"])
    nem = Nemotron(recorder=rec)
    t0 = time.time()
    series, _, _, _ = O.load_tidy()

    try:
        ibja, ibja_used, ibja_failed = E.ibja_daily(tav, O.month_range("2025-01", month))
        lpg_resp, _ = tav.extract([E.IOCL_LPG_URL, "https://www.goodreturns.in/petrol-price-in-new-delhi.html"],
                                  extract_depth="advanced", tag="observed:lpg extract")
        lpg_rev = E.parse_iocl_lpg(next(p["raw_content"] for p in lpg_resp["results"] if "iocl" in p["url"]))
        pt = passthrough(series, ibja, lpg_rev)

        observed = {}
        for item in ("gold", "silver"):
            a, na = E.monthly_average(ibja, item, month)
            b, nb = E.monthly_average(ibja, item, prev)
            observed[item] = {"avg_now": a, "days_now": na, "avg_prev": b, "days_prev": nb,
                              "change": (a / b - 1) if a and b else None, "source": "IBJA daily bullion report PDFs"}
        observed["lpg"] = {"avg_now": E.lpg_monthly(lpg_rev, month), "avg_prev": E.lpg_monthly(lpg_rev, prev),
                           "source": E.IOCL_LPG_URL}
        observed["lpg"]["change"] = observed["lpg"]["avg_now"] / observed["lpg"]["avg_prev"] - 1
        rows = observed_rows(ibja, lpg_rev, month)
        for k in rows:
            observed[k]["rows"] = rows[k]

        spine = E.load_spine()
        spine_out, spine_rows = {}, E.spine_rows(month)
        for food in E.SPINE_FOODS:
            ch, n = E.spine_change(spine, food, month) if spine else (None, 0)
            spine_out[food] = {"change": ch, "n_centres": n, "tier": "strict"} if ch is not None else \
                {"change": None, "note": "spine not loaded yet (data/spine.csv)"}

        quotes, qstats, qtrace = E.collect_quotes(tav, nem, month, E.quote_items_for(month, cfg))
        prev_quotes, pstats, ptrace = E.collect_quotes(tav, nem, prev, E.quote_items_for(month, cfg))
        events, estats, etrace = E.collect_events(tav, nem, month, cfg["events"])
    except E.BudgetExceeded as e:
        print(f"\nSTOPPED before spending more: {e}. Ask the owner before continuing.")
        sys.exit(2)

    spine_prices = {(i, c): p for (i, c, m), p in spine.items() if m == prev}
    matched = {}
    for item in cfg["quote_items"]:
        ch, used = E.match_change(item, quotes, prev_quotes, spine_prices)
        matched[item] = {"change": ch, "matched_cities": used, "n_quotes": sum(q["item"] == item for q in quotes)}

    detail = {"observed": {k: {x: y for x, y in v.items() if x != "rows"} for k, v in observed.items()},
              "passthrough_file": "config/passthrough.json", "spine": spine_out, "matched": matched,
              "quote_stats": {k: v for k, v in qstats.items() if k != "queries"},
              "event_stats": {k: v for k, v in estats.items() if k != "queries"},
              "prev_month_quotes": prev_quotes, "prev_month_quote_stats": {k: v for k, v in pstats.items() if k != "queries"},
              "event_search_window": {"pre_days": E.EVENT_PRE_DAYS, "applied_by": "effective date inside the month"},
              "ibja_reports_used": ibja_used, "ibja_reports_failed": ibja_failed,
              "tavily_params": {"topic": "news", "search_depth": "basic", "max_results": E.SEARCH_N,
                                "include_domains_mode": "prefer", "exclude_domains": ["mospi.gov.in"],
                                "extract_top": E.EXTRACT_TOP, "chunks_per_source": 5},
              "credits_this_run": tav.used, "budgets": tav.budgets,
              "seconds": round(time.time() - t0)}
    manifest = E.build_manifest(month, quotes, qstats, events, estats, observed, spine_rows, detail)
    E.write_manifest(month, manifest)
    E.EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    (E.EVIDENCE_DIR / f"{month}_trace.json").write_text(json.dumps(
        {"quotes": qtrace, "prev_quotes": ptrace, "events": etrace}, ensure_ascii=False, indent=1), encoding="utf-8")
    old = E.EVIDENCE_DIR / f"{month}.json"
    if old.exists():
        old.unlink()          # superseded by manifests/<month>.json (one file per month, in the app's schema)
    print(f"done in {time.time() - t0:.0f}s; Tavily credits this run {tav.used} (budgets {tav.budgets})")


if __name__ == "__main__":
    main()
