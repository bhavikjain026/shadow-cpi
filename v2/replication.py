#!/usr/bin/env python3
"""Replication of the date test (v2/REPLICATION_PREREG.md): new query-cutoff cases, arms A (no dates) and C
(start/end dates + filter_by_published_date), the pilots' leak rules applied by case type. Reuses the pilots' code
paths (v2/date_test.py, v2/finance_lookahead.py): query template, search parameters, Wayback CDX, labels, Wilson
and exact McNemar.

    python -m v2.replication --plan     # prints the sampled cases and the credit estimate (0 credits, no network)
    python -m v2.replication --freeze   # writes v2/replication_cases.json (0 credits, no network)
    python -m v2.replication            # runs once (cap 'replication', 200) -> results/replication.json + .md

Cutoff = the day before the event. Arm C's window is the 30 days ending at the cutoff (as the finance pilot). No
Extract (the pilot's arm D is not replicated) and no Nemotron: labels are code-only. The first pass is primary;
failed Wayback lookups are then retried once by the pilot's logged rule (tools/wayback_retry.py: 3 tries, 5 s apart)
and reported beside it.
"""
import copy
import json
import random
import re
import statistics
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from shadow_cpi.budget import BudgetExceeded, call_cost  # noqa: E402
from shadow_cpi.recorder import provenance  # noqa: E402
from shadow_cpi.tavily import iso_date  # noqa: E402
from v2 import date_test as DT  # noqa: E402
from v2 import finance_lookahead as F  # noqa: E402

SEED = 20261028
N_TARGET = 60
PERIOD = ("2026-01-01", "2026-09-30")          # event dates eligible
WINDOW_DAYS = 29                               # arm C: start_date = cutoff - 29 days, end_date = cutoff
SAME_EVENT_DAYS = 7
CASES = ROOT / "v2" / "replication_cases.json"
OUT = ROOT / "results" / "replication.json"
BUDGET = "replication"
REFERENCE = ROOT / "v2" / "recall_reference.json"
TIMELOCK34 = ROOT / "benchmarks" / "timelock34" / "cases.jsonl"
VERIFIED_GLOBS = ["v2/evidence/events_2026-0[1-9].json", "v2/ablation/arm_*_2026-0[1-9].json"]
FAMILY = {"petrol": "fuel", "diesel": "fuel"}
WORDS = {**DT.WORDS, "metro": "metro fare hike"}
TOPIC_WORDS = {**DT.TOPIC_WORDS, "metro": ["metro", "fare"]}
NATIONAL = ("india", "nationwide", "national")
ISO = re.compile(r"\d{4}-\d{2}-\d{2}")
RETRY_TRIES, RETRY_WAIT = 3, 5                 # tools/wayback_retry.py
ARMS = ("A", "C")
RULES = {"price": "date-test rule (v2/DATE_TEST_PREREG.md)", "finance": "finance rule (v2/FINANCE_PREREG.md)"}


# ---------- the case pool (pre-registered) ----------
def excluded():
    """(pilot ids, timelock34 ids): the date test's 20 and every timelock34 case (date test 20 + finance 14)."""
    pilot = {c["id"] for c in json.loads(DT.CASES.read_text(encoding="utf-8"))["cases"]}
    tl = {json.loads(line)["id"] for line in TIMELOCK34.read_text(encoding="utf-8").splitlines() if line.strip()}
    return pilot, tl


def in_period(d):
    return bool(d) and bool(ISO.fullmatch(d)) and PERIOD[0] <= d <= PERIOD[1]


def same_event(a, b):
    """Same kind, overlapping place (either national, or a state in common), and dates within 7 days (the same
    month when either has no day)."""
    if a["kind"] != b["kind"]:
        return False
    if a["states"] and b["states"] and not set(a["states"]) & set(b["states"]):
        return False
    if a.get("date") and b.get("date"):
        return abs((date.fromisoformat(a["date"]) - date.fromisoformat(b["date"])).days) <= SAME_EVENT_DAYS
    return a["month"] == b["month"]


def reference_rows():
    return [{"ref": r["id"], "kind": r["kind"], "states": r["states"], "date": r["date"], "month": r["month"]}
            for r in json.loads(REFERENCE.read_text(encoding="utf-8"))["changes"]]


def verified_records(root=ROOT):
    """Verified claims (card and claim both 'verified') with an ISO effective date in the period, a kind with a query
    template, and a place in India (states named, or a region naming India / nationwide / national)."""
    recs = []
    for pattern in VERIFIED_GLOBS:
        for f in sorted(root.glob(pattern)):
            for card in json.loads(f.read_text(encoding="utf-8")).get("cards") or []:
                if card.get("status") != "verified":
                    continue
                for cl in card.get("claims") or []:
                    kind = FAMILY.get(cl.get("kind"), cl.get("kind"))
                    d, states = cl.get("effective_date"), list(cl.get("states") or [])
                    india = bool(states) or any(w in (cl.get("region") or "").lower() for w in NATIONAL)
                    if cl.get("status") == "verified" and in_period(d) and kind in WORDS and india:
                        recs.append({"source": str(f.relative_to(root)), "url": card["url"], "kind": kind,
                                     "states": states, "date": d, "month": d[:7], "region": cl.get("region") or ""})
    return sorted(recs, key=lambda r: (r["date"], r["kind"], r["source"], r["url"], r["states"]))


def place(states):
    return ", ".join(DT.PLACE.get(s, s.title()) for s in states) or "India"


def price_case(cid, source, kind, states, day, **extra):
    cutoff = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
    return {"id": cid, "type": "price", "source": source, "kind": kind, "states": states, "event_date": day,
            "month": day[:7], "cutoff": cutoff,
            "query": f"{WORDS[kind]} {place(states)} {date.fromisoformat(day):%B %Y}", **extra}


def pool():
    """(eligible cases, dropped records with the reason), in a fixed order."""
    pilot, tl = excluded()
    ref = reference_rows()
    cases, dropped = [], []
    for r in ref:
        if r["ref"] in pilot or r["ref"] in tl:
            dropped.append({"source": "v2/recall_reference.json", "ref": r["ref"], "why": "pilot / timelock34 case"})
        elif not in_period(r["date"]):
            dropped.append({"source": "v2/recall_reference.json", "ref": r["ref"], "why": "no day-level date"})
        else:
            cases.append(price_case(f"RR-{r['ref']}", "v2/recall_reference.json", r["kind"], r["states"], r["date"],
                                    ref=r["ref"]))
    kept = []
    for rec in verified_records():
        hit = next((r for r in ref if same_event(rec, r)), None)
        dup = next((k for k in kept if same_event(rec, k)), None)
        if hit:
            dropped.append({**rec, "why": f"same event as recall reference {hit['ref']}"})
        elif dup:
            dropped.append({**rec, "why": f"same event as {dup['source']} {dup['date']} {dup['url']}"})
        else:
            kept.append(rec)
    for k, rec in enumerate(kept, 1):
        cases.append(price_case(f"VE{k:02d}", rec["source"], rec["kind"], rec["states"], rec["date"], url=rec["url"]))
    for e in F.EVENTS:
        ev = F.event(e)
        if ev["id"] in tl:
            dropped.append({"source": "v2/finance_lookahead.py EVENTS", "ref": ev["id"], "why": "timelock34 case"})
        elif in_period(ev["event_date"]):
            cases.append({**ev, "id": f"FE-{ev['id']}", "type": "finance", "source": "v2/FINANCE_PREREG.md",
                          "month": ev["event_date"][:7]})
    return cases, dropped


def sample(seed=SEED, cases=None):
    """All eligible cases if there are 60 or fewer, else 60 drawn with the seed; sorted by event date and id."""
    cases = sorted(cases if cases is not None else pool()[0], key=lambda c: (c["event_date"], c["id"]))
    if len(cases) > N_TARGET:
        cases = random.Random(seed).sample(cases, N_TARGET)
    return sorted(cases, key=lambda c: (c["event_date"], c["id"]))


# ---------- arms ----------
def arm_params(arm, c):
    p = dict(DT.BASE if c["type"] == "price" else F.BASE)
    if arm == "A":
        p["filter_by_published_date"] = False
    else:
        start = (date.fromisoformat(c["cutoff"]) - timedelta(days=WINDOW_DAYS)).isoformat()
        p.update(start_date=start, end_date=c["cutoff"], filter_by_published_date=True)
    return p


def credit_estimate(cases):
    return sum(call_cost("/search", arm_params(a, c)) for c in cases for a in ARMS)


# ---------- labels ----------
def label(c, r):
    if c["type"] == "price":
        return DT.label(c["cutoff"], r["captures"], r["tavily_date"], r["url_date"], None)
    return F.label(c, r)


def is_leak(c, r):
    return r["label"] == ("L" if c["type"] == "price" else "confirmed")


def is_flag(c, r):
    return r["label"] in (("F",) if c["type"] == "price" else ("snippet", "flag"))


def is_valid(c, r):
    if c["type"] == "finance":
        return r["label"] == "valid"
    return r["label"] == "P" and any(w in f"{r['title']} {r['content']}".lower() for w in TOPIC_WORDS[c["kind"]])


def relabel(rows):
    for row in rows:
        for a in row["arms"].values():
            for r in a["results"]:
                r["label"] = label(row, r)


# ---------- the run ----------
def run(tav, rec, cases, seed=SEED):
    """tav: a Budgeted Tavily client (cap 'replication'). Returns the rows (first pass, primary)."""
    rng = random.Random(seed + 1)
    rows, skipped = [], []
    for c in cases:
        order = list(ARMS)
        rng.shuffle(order)
        arms = {}
        for arm in order:
            try:
                resp, sid = tav.search(c["query"], **arm_params(arm, c), tag=f"replication {c['id']} {arm}")
            except BudgetExceeded as e:
                skipped.append({"case": c["id"], "arm": arm, "why": str(e)})
                continue
            arms[arm] = {"order": order.index(arm), "call": sid, "credits": (resp.get("usage") or {}).get("credits", 0),
                         "response_time": resp.get("response_time"), **provenance(resp),
                         "results": [{"url": r["url"], "title": r.get("title") or "", "content": r.get("content") or "",
                                      "tavily_date": iso_date(r.get("published_date")) or None,
                                      "url_date": DT.url_date(r["url"])} for r in resp.get("results", [])]}
        rows.append({**c, "arms": arms})
    urls = list(dict.fromkeys(r["url"] for row in rows for a in row["arms"].values() for r in a["results"]))
    captures = {u: DT.wayback(rec, u, tag="replication wayback") for u in urls}
    for row in rows:
        for a in row["arms"].values():
            for r in a["results"]:
                r["captures"] = captures.get(r["url"])
    relabel(rows)
    return {"rows": rows, "skipped": skipped, "seed": seed}


def wayback_retry(rec, out, sleep=time.sleep):
    """Retry pass (secondary): only the lookups that failed in the first pass, 3 tries, 5 s apart, same CDX query
    and labels. Returns a copy of `out` with recovered captures and labels recomputed, plus the log."""
    after = copy.deepcopy(out)
    failed = sorted({r["url"] for row in after["rows"] for a in row["arms"].values() for r in a["results"]
                     if r["captures"] is None})
    got = {}
    for u in failed:
        for k in range(1, RETRY_TRIES + 1):
            caps = DT.wayback(rec, u, tag=f"replication wayback retry {k}")
            if caps is not None:
                got[u] = caps
                break
            if k < RETRY_TRIES:
                sleep(RETRY_WAIT)
    for row in after["rows"]:
        for a in row["arms"].values():
            for r in a["results"]:
                if r["url"] in got:
                    r["captures"] = got[r["url"]]
    relabel(after["rows"])
    return after, {"rule": f"only lookups that failed; {RETRY_TRIES} tries, {RETRY_WAIT} s apart; same CDX query "
                           "and labels", "failed_urls": len(failed), "recovered": len(got),
                   "still_failed": len(failed) - len(got), "recovered_captures": got}


# ---------- metrics ----------
def metrics(out, kind, only=None, drop=()):
    """only: a case-id prefix (the sensitivity subset 'RR-', the 9 hand-built reference cases); drop: case ids left
    out (descriptive addendum only)."""
    rows = [r for r in out["rows"] if r["type"] == kind and (only is None or r["id"].startswith(only))
            and r["id"] not in drop]
    n = len(rows)
    kept = {a: {row["id"]: row["arms"].get(a, {}).get("results", []) for row in rows} for a in ARMS}
    by = {row["id"]: row for row in rows}
    valid = {i: {r["url"] for a in ARMS for r in kept[a][i] if is_valid(by[i], r)} for i in by}
    res, leak = {}, {}
    for a in ARMS:
        leak[a] = {i for i in by if any(is_leak(by[i], r) for r in kept[a][i])}
        calls = [row["arms"][a] for row in rows if a in row["arms"]]
        times = [c["response_time"] for c in calls if c.get("response_time") is not None]
        res[a] = {"leak_cases": len(leak[a]), "cases": n, "leak_case_wilson95": DT.wilson(len(leak[a]), n),
                  "leak_results": sum(is_leak(by[i], r) for i in by for r in kept[a][i]),
                  "flag_cases": sum(any(is_flag(by[i], r) for r in kept[a][i]) for i in by),
                  "results": sum(len(v) for v in kept[a].values()),
                  "valid_lost": sum(len(valid[i] - {r["url"] for r in kept[a][i]}) for i in by),
                  "valid_total": sum(len(v) for v in valid.values()),
                  "undated": sum(r["tavily_date"] is None for i in by for r in kept[a][i]),
                  "wayback_failed": sum(r["captures"] is None for i in by for r in kept[a][i]),
                  "credits": sum(c["credits"] for c in calls),
                  "median_latency_s": statistics.median(times) if times else None}
    b, c = len(leak["A"] - leak["C"]), len(leak["C"] - leak["A"])
    c_leaks = [{"case": i, "query": by[i]["query"], "cutoff": by[i]["cutoff"], "url": r["url"],
                "tavily_date": r["tavily_date"], "first_capture": (r["captures"] or [None])[0],
                "quote": f"{r['title']} — {r['content']}"[:300]}
               for i in sorted(leak["C"]) for r in kept["C"][i] if is_leak(by[i], r)]
    return {"rule": RULES[kind], "cases": n, "arms": res,
            "a_vs_c_mcnemar": {"A_only": b, "C_only": c, "p_exact": DT.mcnemar_exact(b, c)},
            "c_leaks": c_leaks, "leak_ids": {a: sorted(leak[a]) for a in ARMS}}


def all_metrics(out):
    return {k: metrics(out, k) for k in RULES}


def sensitivity(out):
    """Pre-registered sensitivity subset: the hand-built reference cases alone (date-test rule)."""
    return metrics(out, "price", only="RR-")


def pilot_leaks():
    """First-pass (primary) confirmed-leak case ids per arm in the two pilots, mapped to this test's A and C:
    date test A and C; finance N (as A) and D (as C)."""
    dt = json.loads(DT.OUT.read_text(encoding="utf-8"))
    fin = json.loads(F.OUT.read_text(encoding="utf-8"))
    price = {a: {row["id"] for row in dt["rows"] if any(r["label"] == "L" for r in row["arms"].get(a, {})
                                                       .get("results", []))} for a in ARMS}
    finance = {a: {row["id"] for row in fin["rows"] if any(r["label"] == "confirmed" for r in row["arms"]
                                                          .get(p, {}).get("results", []))}
               for a, p in (("A", "N"), ("C", "D"))}
    return {"price": (price, len(dt["rows"])), "finance": (finance, len(fin["rows"]))}


def pooled(m):
    """Secondary: pilot + replication per rule, never added across rules."""
    out = {}
    for kind, (leaks, n0) in pilot_leaks().items():
        r = m[kind]
        n = n0 + r["cases"]
        arms = {}
        for a in ARMS:
            x = len(leaks[a]) + r["arms"][a]["leak_cases"]
            arms[a] = {"leak_cases": x, "cases": n, "wilson95": DT.wilson(x, n)}
        b = len(leaks["A"] - leaks["C"]) + r["a_vs_c_mcnemar"]["A_only"]
        c = len(leaks["C"] - leaks["A"]) + r["a_vs_c_mcnemar"]["C_only"]
        out[kind] = {"rule": RULES[kind], "pilot_cases": n0, "replication_cases": r["cases"], "arms": arms,
                     "a_vs_c_mcnemar": {"A_only": b, "C_only": c, "p_exact": DT.mcnemar_exact(b, c)}}
    return out


# ---------- report ----------
def pct(x):
    return "—" if x is None else f"{x:.0%}"


def pval(p):
    """Four decimals, or scientific notation below 0.0001 (so a tiny p never prints as 0.0000)."""
    return f"{p:.4f}" if p >= 0.0001 else f"{p:.1e}"


def headline(m):
    lines = []
    for kind, r in m.items():
        if not r["cases"]:
            lines.append(f"- **{RULES[kind]}:** no eligible cases; nothing to report.")
            continue
        a, c = r["arms"]["A"], r["arms"]["C"]
        verdict = (f"arm C leaked in **{c['leak_cases']} of {c['cases']}** cases" if c["leak_cases"]
                   else f"arm C leaked in **0 of {c['cases']}** cases")
        lines.append(f"- **{RULES[kind]}:** arm A leaked in {a['leak_cases']} of {a['cases']} cases; {verdict}; "
                     f"exact McNemar p = {pval(r['a_vs_c_mcnemar']['p_exact'])}.")
        for x in r["c_leaks"]:
            lines.append(f"  - **C leak, {x['case']}** (cutoff {x['cutoff']}): {x['url']} — Tavily date "
                         f"{x['tavily_date']}, first Wayback copy {x['first_capture']}. Quote: \"{x['quote']}\"")
    return lines


def report(out):
    L = ["# Date test replication", "",
         f"Run {out['built_utc'][:16]} UTC by `python -m v2.replication`, pre-registered in "
         "`v2/REPLICATION_PREREG.md`. Arms: **A** no dates; **C** start/end dates (the 30 days to the cutoff) + "
         "`filter_by_published_date`. Cutoff = the day before each event. First Wayback pass = primary result.", "",
         "## Headline (first pass)", ""] + headline(out["metrics"])
    for kind, r in out["metrics"].items():
        if not r["cases"]:
            continue
        L += ["", f"## {r['rule']}: {r['cases']} cases", "",
              "| Arm | Cases with a confirmed leak (Wilson 95%) | Leak results | Date-flag cases | Valid evidence lost | "
              "Undated | Wayback failed | Credits | Median latency |", "|---|---|---|---|---|---|---|---|---|"]
        for a, x in r["arms"].items():
            lo, hi = x["leak_case_wilson95"]
            L.append(f"| {a} | {x['leak_cases']} of {x['cases']} ({pct(lo)}–{pct(hi)}) | {x['leak_results']} of "
                     f"{x['results']} | {x['flag_cases']} | {x['valid_lost']} of {x['valid_total']} | {x['undated']} "
                     f"| {x['wayback_failed']} | {x['credits']} | {DT.secs(x['median_latency_s'])} |")
        mc = r["a_vs_c_mcnemar"]
        L.append(f"\nA vs C, exact McNemar (paired by case): leaks only in A {mc['A_only']}, only in C "
                 f"{mc['C_only']}, p = {pval(mc['p_exact'])}.")
    s = out.get("sensitivity")
    if s and s["cases"]:
        L += ["", f"Sensitivity (pre-registered): the {s['cases']} hand-built reference cases alone: " + "; ".join(
            f"{a} {x['leak_cases']} of {x['cases']} ({pct(x['leak_case_wilson95'][0])}–"
            f"{pct(x['leak_case_wilson95'][1])})" for a, x in s["arms"].items())
            + f"; exact McNemar p = {pval(s['a_vs_c_mcnemar']['p_exact'])}."]
    rt = out.get("retry")
    if rt:
        L += ["", "## Wayback retry of failed lookups (secondary; the first pass above stays primary)", "",
              f"{rt['log']['failed_urls']} lookups failed in the first pass and were retried ({rt['log']['rule']}); "
              f"{rt['log']['recovered']} recovered, {rt['log']['still_failed']} still failed.", ""]
        for kind, r in rt["metrics"].items():
            if r["cases"]:
                L.append(f"- {r['rule']}: A {r['arms']['A']['leak_cases']} of {r['cases']}, C "
                         f"{r['arms']['C']['leak_cases']} of {r['cases']}; McNemar p = "
                         f"{pval(r['a_vs_c_mcnemar']['p_exact'])}; valid evidence lost A "
                         f"{r['arms']['A']['valid_lost']} of {r['arms']['A']['valid_total']}, C "
                         f"{r['arms']['C']['valid_lost']} of {r['arms']['C']['valid_total']}.")
    L += ["", "## Pilot + replication pooled (secondary; per rule, never added across rules; first passes)", ""]
    for kind, p in out["pooled"].items():
        L.append(f"- {p['rule']}: {p['pilot_cases']} pilot + {p['replication_cases']} replication cases. " + "; ".join(
            f"{a} {x['leak_cases']} of {x['cases']} ({pct(x['wilson95'][0])}–{pct(x['wilson95'][1])})"
            for a, x in p["arms"].items()) + f"; exact McNemar p = {pval(p['a_vs_c_mcnemar']['p_exact'])}.")
    if out["skipped"]:
        L += ["", "**Incomplete:** the credit cap stopped some calls (listed in results/replication.json)."]
    return "\n".join(L) + "\n"


# ---------- addendum (logged 2026-10-28, after the results; descriptive) ----------
def cache_reuse(out, ledger=None):
    """Searches served from the Recorder cache in this run (ledger rows charged to 'replication' with 'cached'), each
    with the earlier response it reused: the pilot's (same request_id as a date-test call) or this run's."""
    from shadow_cpi.budget import read_ledger
    led = ledger if ledger is not None else read_ledger()
    cached = {e["call_id"] for e in led if BUDGET in e["budgets"] and e.get("cached")}
    pilot = {a["request_id"]: f"date test {row['id']} arm {k}"
             for row in json.loads(DT.OUT.read_text(encoding="utf-8"))["rows"]
             for k, a in row["arms"].items() if a.get("request_id")}
    fresh = {a["request_id"]: f"{row['id']} arm {k}" for row in out["rows"] for k, a in row["arms"].items()
             if a.get("call") not in cached and a.get("request_id")}
    reuse = []
    for row in out["rows"]:
        for k, a in row["arms"].items():
            if a.get("call") in cached:
                rid = a.get("request_id")
                reuse.append({"case": row["id"], "arm": k, "call": a["call"], "request_id": rid,
                              "from_pilot": rid in pilot, "source": pilot.get(rid) or fresh.get(rid, "unknown"),
                              "leak": any(is_leak(row, r) for r in a["results"])})
    return reuse


def addendum(out, ledger=None):
    reuse = cache_reuse(out, ledger)
    if not reuse:
        return []
    pilot_ids = tuple(x["case"] for x in reuse if x["from_pilot"])
    all_ids = tuple(x["case"] for x in reuse)
    fmt = lambda r, a: (f"{r['arms'][a]['leak_cases']} of {r['cases']} ({pct(r['arms'][a]['leak_case_wilson95'][0])}–"  # noqa: E731
                        f"{pct(r['arms'][a]['leak_case_wilson95'][1])})")
    L = ["", "## Addendum: cache-served arm-A responses (logged 2026-10-28, after the results; descriptive, offline, "
             "0 credits; nothing above changes)", "",
         f"Every outside call goes through the Recorder cache. {len(reuse)} of the 44 searches were served from it, "
         "all in arm A (no dates: the same query and parameters as an earlier call). Arm C's searches were all fresh.",
         ""]
    for x in reuse:
        L.append(f"- **{x['case']} arm {x['arm']}** reused the response of {x['source']} (request {x['request_id']})"
                 + ("; that is the pilot's search of 22 Oct" if x["from_pilot"] else "; same run")
                 + f"; confirmed leak in this case: {'yes' if x['leak'] else 'no'}.")
    m3, m4 = metrics(out, "price", drop=pilot_ids), metrics(out, "price", drop=all_ids)
    L += ["", f"**Not pre-registered, descriptive.** Without the {len(pilot_ids)} cases that reused the pilot's "
              f"response ({', '.join(pilot_ids)}): A {fmt(m3, 'A')}, C {fmt(m3, 'C')}; exact McNemar p = "
              f"{pval(m3['a_vs_c_mcnemar']['p_exact'])}. Without all {len(all_ids)} cache-served cases: "
              f"A {fmt(m4, 'A')}, C {fmt(m4, 'C')}; exact McNemar p = {pval(m4['a_vs_c_mcnemar']['p_exact'])}."]
    reused_pilot = {x["source"] for x in reuse if x["from_pilot"]}
    leaks, _ = pilot_leaks()["price"]
    pc = sum(x["leak"] for x in reuse if x["from_pilot"])
    for src in sorted(reused_pilot):
        pid = src.split()[2]
        L += ["", f"**Pooled count:** the pooled arm-A count above ({out['pooled']['price']['arms']['A']['leak_cases']} "
                  f"of {out['pooled']['price']['arms']['A']['cases']}) includes the reused pilot response: {src} is "
                  f"{'one of the pilot' + chr(39) + 's confirmed-leak cases' if pid in leaks['A'] else 'a pilot case'}"
                  f", and the same response counts again in {pc} replication case{'s' if pc != 1 else ''} "
                  f"({', '.join(pilot_ids)}), with each case's own cutoff."]
    return L


# ---------- plan ----------
def plan_text(cases, dropped):
    from shadow_cpi.budget import load_budget, spent
    cfg = load_budget()
    cap = cfg["caps"].get(BUDGET)
    n_by = {k: sum(c["type"] == k for c in cases) for k in RULES}
    L = [f"Replication plan (seed {SEED}; target {N_TARGET}; eligible {len(cases)}"
         + ("; fewer than 60, so all are taken)" if len(cases) <= N_TARGET else ")"),
         f"Cases by rule: price (date-test rule) {n_by['price']}, finance (finance rule) {n_by['finance']}", ""]
    for c in cases:
        L.append(f"{c['id']:<8} {c['type']:<7} event {c['event_date']}  cutoff {c['cutoff']}  window "
                 f"{arm_params('C', c)['start_date']}..{c['cutoff']}  \"{c['query']}\"  [{c['source']}]")
    est = credit_estimate(cases)
    L += ["", f"Dropped records: {len(dropped)} (reasons in v2/replication_cases.json)",
          f"Credit estimate: {est} Tavily credits ({len(cases)} cases x 2 arms x 1 basic search); Extract 0; "
          "Wayback CDX = logged direct download, 0 credits; Nemotron 0.",
          f"Cap '{BUDGET}': {cap if cap is not None else 'NOT SET'} (spent so far {spent(BUDGET)}). "
          "This plan made 0 calls."]
    return "\n".join(L)


def main():
    cases_all, dropped = pool()
    cases = sample(cases=cases_all)
    if "--plan" in sys.argv:
        print(plan_text(cases, dropped))
        return
    if "--freeze" in sys.argv:
        CASES.write_text(json.dumps({"seed": SEED, "made_utc": datetime.now(timezone.utc).isoformat(),
                                     "eligible": len(cases_all), "cases": cases, "dropped": dropped},
                                    ensure_ascii=False, indent=1) + "\n")
        print(plan_text(cases, dropped))
        return
    if "--report" in sys.argv:                     # offline: rewrite the .md from the saved results (0 credits)
        out = json.loads(OUT.read_text(encoding="utf-8"))
        OUT.with_suffix(".md").write_text(report(out).rstrip("\n") + "\n" + "\n".join(addendum(out)) + "\n")
        return
    if OUT.exists():
        raise SystemExit(f"{OUT} exists: the replication runs once")
    frozen = json.loads(CASES.read_text(encoding="utf-8"))["cases"]
    if frozen != cases:
        raise SystemExit("v2/replication_cases.json does not match the pre-registered rule: not running")
    from shadow_cpi.budget import Budgeted, usage_check
    from shadow_cpi.recorder import Recorder
    from shadow_cpi.tavily import Tavily
    rec = Recorder()
    tav = Budgeted(Tavily(recorder=rec), [BUDGET])
    out = run(tav, rec, frozen)
    out["built_utc"] = datetime.now(timezone.utc).isoformat()
    out["metrics"] = all_metrics(out)
    out["sensitivity"] = sensitivity(out)
    after, log = wayback_retry(rec, out)
    out["retry"] = {"log": log, "metrics": all_metrics(after)}
    out["pooled"] = pooled(out["metrics"])
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    OUT.with_suffix(".md").write_text(report(out))
    print(OUT.with_suffix(".md").read_text())
    print(usage_check(tav.tav)[1])


if __name__ == "__main__":
    main()
