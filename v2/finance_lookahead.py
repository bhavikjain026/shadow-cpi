#!/usr/bin/env python3
"""Finance look-ahead check (v2/FINANCE_PREREG.md, Amendment 1): replaying the day before a scheduled financial
event, does a Tavily search with no dates return pages that state the outcome, and do start/end dates +
filter_by_published_date stop that? Exploratory: it changes no scored verdict.

    python -m v2.finance_lookahead     # runs once (cap 'finance-lookahead', 60) -> results/finance_lookahead.json + .md

Two arms per event, same neutral query, run close together in a seeded random order: N no dates; D start_date =
cutoff - 29 days, end_date = cutoff, filter_by_published_date. Outcome judged from the search title + snippet only.
Labels: confirmed leak (states the outcome + Wayback: no capture by the cutoff, first capture after it, Tavily's or
the address's date after it); snippet leak (states the outcome + a post-cutoff date, not Wayback-confirmed); date flag
(post-cutoff date, outcome not stated). Reuses the date-test harness (Wayback CDX, Wilson, exact McNemar).
"""
import json
import random
import re
import statistics
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from shadow_cpi.budget import BudgetExceeded  # noqa: E402
from shadow_cpi.recorder import provenance  # noqa: E402
from shadow_cpi.tavily import iso_date  # noqa: E402
from v2 import date_test as DT  # noqa: E402

SEED = 20261022
OUT = ROOT / "results" / "finance_lookahead.json"
BUDGET = "finance-lookahead"
FLAGGED = {"C4": "date from the board-meeting notice; no official outcome filing found"}
# (id, kind, name, event date, quarter) -- the list fixed in v2/FINANCE_PREREG.md (Amendment 1, 14 events)
EVENTS = [("R1", "rbi", "RBI", "2026-02-06", None), ("R2", "rbi", "RBI", "2026-04-08", None),
          ("R3", "rbi", "RBI", "2026-06-05", None), ("R4", "rbi", "RBI", "2026-08-05", None),
          ("R5", "rbi", "RBI", "2026-10-07", None),
          ("C1", "company", "TCS", "2026-07-09", 1), ("C2", "company", "Reliance Industries", "2026-07-17", 1),
          ("C3", "company", "HDFC Bank", "2026-07-18", 1), ("C4", "company", "ICICI Bank", "2026-07-18", 1),
          ("C5", "company", "Infosys", "2026-07-23", 1), ("C6", "company", "TCS", "2026-10-08", 2),
          ("C7", "company", "HDFC Bank", "2026-10-17", 2), ("C8", "company", "ICICI Bank", "2026-10-17", 2),
          ("C9", "company", "Infosys", "2026-10-23", 2)]
BASE = {"topic": "news", "search_depth": "basic", "max_results": 5, "include_published_date": True}
NAMES = {"RBI": ["rbi", "reserve bank"], "TCS": ["tcs", "tata consultancy"], "Reliance Industries": ["reliance", "ril"],
         "HDFC Bank": ["hdfc bank"], "ICICI Bank": ["icici bank", "icici"], "Infosys": ["infosys"]}
QUARTER = {1: [r"\bq1\s*fy\s*'?27\b", r"\bq1\s*fy\s*2027\b", r"quarter ended (on )?(30 june|june 30),? 2026",
               r"june quarter", r"april[- ]june (quarter|2026)"],
           2: [r"\bq2\s*fy\s*'?27\b", r"\bq2\s*fy\s*2027\b", r"quarter ended (on )?(30 september|september 30),? 2026",
               r"september quarter", r"july[- ]september (quarter|2026)"]}
FIGURE = re.compile(r"(₹|rs\.?\s*\d|inr\s*\d|\d[\d,.]*\s*(crore|cr\b|bn|billion|lakh))|\d+(\.\d+)?\s*(%|per ?cent)", re.I)
RESULT_WORD = re.compile(r"\b(profit|revenue|income|pat|earnings)\b", re.I)
DECISION = re.compile(r"\b(unchanged|kept|keeps|held|holds|hike[ds]?|hiked|raise[ds]?|raised|cut[s]?|reduce[ds]?|"
                      r"reduced|increase[ds]?|increased)\b", re.I)
PCT = re.compile(r"\d+(\.\d+)?\s*(%|per ?cent)", re.I)


def event(e):
    eid, kind, name, day, q = e
    cutoff = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
    d = date.fromisoformat(day)
    query = (f"RBI monetary policy repo rate decision {d:%B %Y}" if kind == "rbi"
             else f"{name} Q{q} FY27 quarterly results")
    return {"id": eid, "kind": kind, "name": name, "event_date": day, "cutoff": cutoff, "quarter": q, "query": query,
            "flag": FLAGGED.get(eid, "")}


def arm_params(arm, ev):
    p = dict(BASE)
    if arm == "N":
        p["filter_by_published_date"] = False
    else:
        start = (date.fromisoformat(ev["cutoff"]) - timedelta(days=29)).isoformat()
        p.update(start_date=start, end_date=ev["cutoff"], filter_by_published_date=True)
    return p


def names(ev, text):
    t = text.lower()
    return any(re.search(rf"\b{re.escape(w)}\b", t) for w in NAMES[ev["name"]])


def states_outcome(ev, text):
    """Pre-registered rule, title + snippet only."""
    t = text or ""
    if ev["kind"] == "rbi":
        return bool(re.search(r"repo", t, re.I) and DECISION.search(t) and PCT.search(t))
    return bool(names(ev, t) and any(re.search(p, t, re.I) for p in QUARTER[ev["quarter"]])
                and RESULT_WORD.search(t) and FIGURE.search(t))


def label(ev, r):
    """confirmed / snippet / flag / valid / none, from the outcome rule, the date signals and Wayback captures."""
    cut = ev["cutoff"]
    post = any(d and d > cut for d in (r["tavily_date"], r["url_date"]))
    cap = r["captures"] or []
    outcome = states_outcome(ev, f"{r['title']} {r['content']}")
    if outcome and post and cap and cap[0] > cut:
        return "confirmed"
    if outcome and post:
        return "snippet"
    if post:
        return "flag"
    if cap and cap[0] <= cut and names(ev, f"{r['title']} {r['content']}"):
        return "valid"
    return "none"


def own_month(ev, r):
    """RBI only: the result names the event's own month (a page about another meeting can state an outcome too)."""
    if ev["kind"] != "rbi":
        return True
    return f"{date.fromisoformat(ev['event_date']):%B}".lower() in f"{r['title']} {r['content']}".lower()


def run(tav, rec, events=None, seed=SEED):
    """tav: a Budgeted Tavily client (cap 'finance-lookahead'). Returns the result dict (written by main)."""
    evs = [event(e) for e in (events or EVENTS)]
    rng = random.Random(seed)
    rows, skipped = [], []
    for ev in evs:
        order = ["N", "D"]
        rng.shuffle(order)
        arms = {}
        for arm in order:
            try:
                resp, sid = tav.search(ev["query"], **arm_params(arm, ev), tag=f"finance {ev['id']} {arm}")
            except BudgetExceeded as e:
                skipped.append({"event": ev["id"], "arm": arm, "why": str(e)})
                continue
            arms[arm] = {"order": order.index(arm), "call": sid, "credits": (resp.get("usage") or {}).get("credits", 0),
                         "response_time": resp.get("response_time"), **provenance(resp),
                         "results": [{"url": r["url"], "title": r.get("title") or "", "content": r.get("content") or "",
                                      "tavily_date": iso_date(r.get("published_date")) or None,
                                      "url_date": DT.url_date(r["url"])} for r in resp.get("results", [])]}
        rows.append({**ev, "arms": arms})
    urls = list(dict.fromkeys(r["url"] for row in rows for a in row["arms"].values() for r in a["results"]))
    captures = {u: DT.wayback(rec, u, tag="finance wayback") for u in urls}
    for row in rows:
        for a in row["arms"].values():
            for r in a["results"]:
                r["captures"] = captures.get(r["url"])
                r["states_outcome"] = states_outcome(row, f"{r['title']} {r['content']}")
                r["label"] = label(row, r)
    return {"rows": rows, "skipped": skipped, "seed": seed}


def metrics(out, drop=()):
    rows = [r for r in out["rows"] if r["id"] not in drop]
    n = len(rows)
    kept = {a: {row["id"]: row["arms"].get(a, {}).get("results", []) for row in rows} for a in ("N", "D")}
    valid = {row["id"]: {r["url"] for a in kept for r in kept[a][row["id"]] if r["label"] == "valid"} for row in rows}
    res = {}
    for a in ("N", "D"):
        res_a = {}
        for lab in ("confirmed", "snippet", "flag"):
            res_a[lab] = {"results": sum(r["label"] == lab for i in kept[a] for r in kept[a][i]),
                          "events": sum(any(r["label"] == lab for r in kept[a][i]) for i in kept[a])}
        by_id = {row["id"]: row for row in rows}
        strict = {i: [r for r in kept[a][i] if r["label"] == "snippet" and own_month(by_id[i], r)] for i in kept[a]}
        res_a["snippet_own_month"] = {"results": sum(len(v) for v in strict.values()),
                                      "events": sum(bool(v) for v in strict.values())}
        calls = [row["arms"][a] for row in rows if a in row["arms"]]
        times = [c["response_time"] for c in calls if c.get("response_time") is not None]
        res_a.update(events=n, confirmed_wilson95=DT.wilson(res_a["confirmed"]["events"], n),
                     snippet_wilson95=DT.wilson(res_a["snippet"]["events"], n),
                     snippet_own_month_wilson95=DT.wilson(res_a["snippet_own_month"]["events"], n),
                     results=sum(len(v) for v in kept[a].values()),
                     valid_lost=sum(len(valid[i] - {r["url"] for r in kept[a][i]}) for i in valid),
                     valid_total=sum(len(v) for v in valid.values()),
                     undated=sum(r["tavily_date"] is None for i in kept[a] for r in kept[a][i]),
                     wayback_failed=sum(r["captures"] is None for i in kept[a] for r in kept[a][i]),
                     credits=sum(c["credits"] for c in calls),
                     median_latency_s=statistics.median(times) if times else None)
        res[a] = res_a
    out_m = {"events": n, "dropped": list(drop), "arms": res}
    for lab in ("confirmed", "snippet"):
        yes = {a: {i for i in kept[a] if any(r["label"] == lab for r in kept[a][i])} for a in ("N", "D")}
        b, c = len(yes["N"] - yes["D"]), len(yes["D"] - yes["N"])
        out_m[f"mcnemar_{lab}"] = {"N_only": b, "D_only": c, "p_exact": DT.mcnemar_exact(b, c),
                                   "role": "pre-registered (metric 3)" if lab == "confirmed" else "descriptive"}
    return out_m


def report(out):
    pct = lambda x: "—" if x is None else f"{x:.0%}"  # noqa: E731
    L = ["# Finance look-ahead check", "",
         f"Run {out['built_utc'][:16]} UTC by `python -m v2.finance_lookahead`, pre-registered in "
         "`v2/FINANCE_PREREG.md` (with Amendment 1). **Exploratory**: it changes no scored verdict. Outcomes judged "
         "from search titles and snippets only. Arms: **N** no dates; **D** start/end dates (the 30 days to the "
         "cutoff) + `filter_by_published_date`. Cutoff = the day before each event.", ""]
    for key, title in (("all", "All 14 events"), ("without_C4", f"13 events, without C4 ({FLAGGED['C4']})")):
        m = out["metrics"][key]
        L += [f"## {title}", "",
              "| Arm | Confirmed-leak events (Wilson 95%) | Snippet-leak events, RBI own month (Wilson 95%) "
              "[loose] | Date-flag events | Confirmed / snippet (own month) [loose] / date-flag results | Valid evidence "
              "lost | Undated | Credits | Median latency |",
              "|---|---|---|---|---|---|---|---|---|"]
        for a, r in m["arms"].items():
            c, s = r["confirmed_wilson95"], r["snippet_own_month_wilson95"]
            L.append(f"| {a} | {r['confirmed']['events']} of {r['events']} ({pct(c[0])}–{pct(c[1])}) | "
                     f"{r['snippet_own_month']['events']} of {r['events']} ({pct(s[0])}–{pct(s[1])}) "
                     f"[{r['snippet']['events']}] | {r['flag']['events']} | "
                     f"{r['confirmed']['results']} / {r['snippet_own_month']['results']} [{r['snippet']['results']}] / "
                     f"{r['flag']['results']} of "
                     f"{r['results']} | {r['valid_lost']} of {r['valid_total']} | {r['undated']} | {r['credits']} | "
                     f"{'—' if r['median_latency_s'] is None else f'{r['median_latency_s']:.2f} s'} |")
        for lab in ("confirmed", "snippet"):
            mc = m[f"mcnemar_{lab}"]
            L.append(f"\nN vs D, exact McNemar on {lab}-leak events ({mc['role']}): only in N {mc['N_only']}, only "
                     f"in D {mc['D_only']}, p = {mc['p_exact']:.4f}.")
        L.append("")
    L += ["**Confirmed leak** = states the outcome, and the Wayback Machine has no copy on or before the cutoff, its "
          "first copy is after it, and Tavily's or the address's date is after it. **Snippet leak** = states the "
          "outcome with a post-cutoff date, not Wayback-confirmed (reported separately, never counted as confirmed). "
          "**Date flag** = a post-cutoff date on a result that does not state the outcome. With 13–14 events the "
          "intervals are wide.",
          "",
          "**Snippet figures:** for the RBI events the primary count uses only pages that name the event's own month "
          "(a page about another meeting can also state a repo-rate outcome); the loose count, in brackets, is the "
          "pre-registered rule as written. Company events are the same in both.",
          "",
          "**Valid evidence lost** = results that are Wayback-confirmed from on or before the cutoff and name the RBI "
          "or the company, found by either arm, that this arm did not return."]
    retry = OUT.with_name(OUT.stem + "_wayback_retry.json")
    if retry.exists():
        rt = json.loads(retry.read_text(encoding="utf-8"))
        L += ["", "## Network retry of failed Wayback lookups (logged; the results above stay primary)", "",
              f"{rt['run_utc'][:16]} UTC, `tools/wayback_retry.py finance`: {rt['failed_urls']} failed lookups retried "
              f"({rt['rule']}); {rt['recovered']} recovered, {rt['still_failed']} still failed.", "",
              "| Events | Arm | Confirmed-leak events before → after | Snippet-leak events (loose) before → after | "
              "Valid evidence lost before → after |", "|---|---|---|---|---|"]
        for key, title in (("all", "14"), ("without_C4", "13")):
            for a in ("N", "D"):
                b, f = rt["before"][key]["arms"][a], rt["after"][key]["arms"][a]
                L.append(f"| {title} | {a} | {b['confirmed']['events']} → {f['confirmed']['events']} | "
                         f"{b['snippet']['events']} → {f['snippet']['events']} | {b['valid_lost']} of "
                         f"{b['valid_total']} → {f['valid_lost']} of {f['valid_total']} |")
    if out["skipped"]:
        L += ["", "**Incomplete:** the credit cap stopped some calls (listed in results/finance_lookahead.json)."]
    return "\n".join(L) + "\n"


def main():
    if "--report" in sys.argv:                     # offline: rewrite the .md from the saved rows (0 credits)
        out = json.loads(OUT.read_text(encoding="utf-8"))
        out["metrics"] = {"all": metrics(out), "without_C4": metrics(out, drop=("C4",))}
        OUT.with_suffix(".md").write_text(report(out))
        return
    if OUT.exists():
        raise SystemExit(f"{OUT} exists: the finance check runs once")
    from shadow_cpi.budget import Budgeted, usage_check
    from shadow_cpi.recorder import Recorder
    from shadow_cpi.tavily import Tavily
    rec = Recorder()
    tav = Budgeted(Tavily(recorder=rec), [BUDGET])
    out = run(tav, rec)
    out["built_utc"] = datetime.now(timezone.utc).isoformat()
    out["metrics"] = {"all": metrics(out), "without_C4": metrics(out, drop=("C4",))}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    OUT.with_suffix(".md").write_text(report(out))
    print(OUT.with_suffix(".md").read_text())
    print(usage_check(tav.tav)[1])


if __name__ == "__main__":
    main()
