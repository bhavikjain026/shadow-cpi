#!/usr/bin/env python3
"""Build results/field_report.json for the app's Tavily field report (0 credits, no API call).

    python tools/build_field_report.py

Every figure is computed here from committed results files (results/, v2/ablation/, v2/radar/, the credit ledger),
so the page never types a number. Exploratory parts are labelled as such; nothing here changes a scored verdict.
"""
import copy
import json
import statistics
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from shadow_cpi.budget import load_budget, read_ledger, spent  # noqa: E402
from v2 import ablation as AB  # noqa: E402
from v2 import date_test as DT  # noqa: E402
from v2 import drift as DR  # noqa: E402
from v2 import finance_lookahead as F  # noqa: E402
from v2 import kinds as K  # noqa: E402
from v2 import lang_date_test as LT  # noqa: E402
from v2 import leak_types as LKT  # noqa: E402
from v2 import recall as RC  # noqa: E402
from shadow_cpi.tavily import iso_date  # noqa: E402

OUT = ROOT / "results" / "field_report.json"
EXPLORATORY = "exploratory, added after scoring; cannot change the winner (A)"


def load(p):
    return json.loads((ROOT / p).read_text(encoding="utf-8"))


def arm_runs(arm):
    return [json.loads((AB.OUT / f"arm_{arm}_{m}.json").read_text(encoding="utf-8")) for m in AB.MONTHS
            if (AB.OUT / f"arm_{arm}_{m}.json").exists()]


def per_change(credits, found):
    return credits / found if found else None


def four_arms():
    out = load("results/v2_ablation.json")
    rows = []
    for k, a in out["arms"].items():
        rows.append({"arm": k, "writer": a["writer"], "recall": a["recall"], "of": a["total"],
                     "real_new_credits": a["new_credits"], "credits_original": a["credits"],
                     "credits_per_verified_event": a["credits_per_verified_event"],
                     "credits_per_known_change": per_change(a["credits"], a["recall"]),
                     "median_latency_s": a["median_latency_s"]})
    return {"rows": rows, "verdict": out["equivalence"], "computed_utc": out["computed_utc"],
            "latency_label": "median Tavily response_time; pre-registered with no target, not used in the verdict"}


def exploratory(arm, budget, ref):
    runs = arm_runs(arm)
    full = [r["month"] for r in runs if r["complete"]]
    allr = AB.reconcile(runs, ref)
    h = AB.reconcile([r for r in runs if r["complete"]], ref)
    a = AB.reconcile([json.loads((AB.OUT / f"arm_A_{m}.json").read_text(encoding="utf-8")) for m in full], ref)
    real = spent(budget)
    out = {"arm": arm, "label": EXPLORATORY, "months_run": [r["month"] for r in runs], "complete_months": full,
           "incomplete_months": [r["month"] for r in runs if not r["complete"]], "recall_all": allr["recall"],
           "events": allr["events"], "matched_events": allr["matched_events"], "real_credits": real,
           "credits_original": allr["credits"], "credits_per_verified_event": per_change(allr["credits"], allr["events"]),
           "credits_per_known_change_real": per_change(real, allr["recall"]),
           "like_for_like": {"months": len(full), "known_changes_in_them": sum(c["month"] in full for c in ref),
                             "recall": h["recall"], "arm_a_recall": a["recall"]}}
    if arm == "H":
        plan = [s for r in runs for s in r["plan"]]
        out["fields_valid"] = {"valid": sum(sum(s["valid"].values()) for s in plan), "of": 4 * len(plan),
                               "differs_from_a": {f: sum(s["differs_from_a"][f] for s in plan) for f in AB.H_FIELDS}}
    return out


def leak_sets(out, arms):
    return {a: {row["id"] for row in out["rows"] if any(r["label"] in ("L", "confirmed")
                                                       for r in row["arms"].get(a, {}).get("results", []))}
            for a in arms}


def mcnemar(sets, x, y):
    return {"only_" + x: len(sets[x] - sets[y]), "only_" + y: len(sets[y] - sets[x]),
            "p_exact": DT.mcnemar_exact(len(sets[x] - sets[y]), len(sets[y] - sets[x]))}


def with_retry(out, retry, relabel):
    o = copy.deepcopy(out)
    for row in o["rows"]:
        for a in row["arms"].values():
            for r in a.get("results", []):
                if r["url"] in retry["recovered_captures"]:
                    r["captures"] = retry["recovered_captures"][r["url"]]
                r["label"] = relabel(row, r)
    return o


def date_test():
    out, rt = load("results/date_field_test.json"), load("results/date_field_test_wayback_retry.json")
    after = with_retry(out, rt, lambda row, r: DT.label(row["cutoff"], r["captures"], r["tavily_date"],
                                                         DT.url_date(r["url"]), r["page_date"]))
    passes = {}
    for name, o in (("first_pass", out), ("after_retry", after)):
        m = DT.metrics(o)
        s = leak_sets(o, "ABCD")
        passes[name] = {"arms": {a: {"leak_cases": r["leak_cases"], "cases": r["cases"],
                                     "wilson95": r["leak_case_wilson95"], "valid_lost": r["valid_lost"],
                                     "valid_total": r["valid_total"]} for a, r in m["arms"].items()},
                        "mcnemar_A_vs_B": mcnemar(s, "A", "B"), "mcnemar_C_vs_D": mcnemar(s, "C", "D")}
    return {"label": "pilot, 20 cases; first pass is the pre-registered result, the retry only recovers failed "
                     "Wayback lookups", "retry": {k: rt[k] for k in ("failed_urls", "recovered", "still_failed")},
            **passes}


def lang_date_test():
    """The language date test (v2/LANG_DATE_PREREG.md), recomputed from its results file; None until it has run."""
    if not LT.OUT.exists():
        return None
    out = load("results/lang_date_test.json")
    m = LT.metrics(out)
    keep = ("leak_cases", "cases", "leak_case_wilson95", "results", "undated", "undated_share", "outside_window",
            "valid_lost", "valid_total", "no_page_date")
    pick = lambda arms: {a: {k: arms[a][k] for k in keep} for a in LT.ARMS}  # noqa: E731
    return {"label": f"pilot, {m['arms']['A']['cases']} cases (Hindi, Marathi, Tamil; no Kannada, Bengali or Telugu "
                     "change in the reference list); language field set; compared with the English date test's first "
                     "pass", "built_utc": out["built_utc"],
            "arms": {a: {**pick(m["arms"])[a], "credits": m["arms"][a]["credits"],
                         "median_latency_s": m["arms"][a]["median_latency_s"]} for a in LT.ARMS},
            "by_lang": {LT.LANG_NAMES[l]: pick(s) for l, s in m["by_lang"].items()},
            "english": pick(m["english"]), "paired_with_english": m["paired_with_english"],
            "differs_from_english": m["differs_from_english"], "wayback_failed": m["wayback_failed"],
            "incomplete": m["incomplete"],
            "relevance_post_hoc": {LT.LANG_NAMES[l]: v for l, v in LT.relevance(out).items()}}


def finance():
    out, rt = load("results/finance_lookahead.json"), load("results/finance_lookahead_wayback_retry.json")
    after = with_retry(out, rt, F.label)
    res = {"label": "exploratory; changes no scored verdict", "retry": {k: rt[k] for k in
                                                                       ("failed_urls", "recovered", "still_failed")}}
    for name, o in (("first_pass", out), ("after_retry", after)):
        res[name] = {}
        for key, drop in (("all_14", ()), ("without_C4", ("C4",))):
            m = F.metrics(o, drop=drop)
            res[name][key] = {"events": m["events"], "mcnemar_confirmed": m["mcnemar_confirmed"],
                              "arms": {a: {"confirmed_events": r["confirmed"]["events"],
                                           "confirmed_wilson95": r["confirmed_wilson95"],
                                           "snippet_own_month_events": r["snippet_own_month"]["events"],
                                           "snippet_loose_events": r["snippet"]["events"],
                                           "flag_events": r["flag"]["events"], "valid_lost": r["valid_lost"],
                                           "valid_total": r["valid_total"]} for a, r in m["arms"].items()}}
    return res


def auto_parameters():
    t_plan = [x for r in arm_runs("T") for x in r["plan"]]
    t_cards = [c for r in arm_runs("T") for c in r["cards"]]
    td_plan = [x for r in arm_runs("Td") for x in r["plan"] if "auto_parameters" in x]
    dk = [x["dates_kept"] for x in td_plan if x.get("dates_kept")]
    return {"no_dates": {"searches": len(t_plan),
                         "time_range": dict(Counter(str((x.get("auto_parameters") or {}).get("time_range"))
                                                    for x in t_plan).most_common()),
                         "results": len(t_cards),
                         "results_dated_oct_2026": sum((c.get("published") or "").startswith("2026-10") for c in t_cards),
                         "results_undated": sum(not c.get("published") for c in t_cards)},
            "with_dates": {"searches": len(td_plan),
                           "time_range": dict(Counter(str((x["auto_parameters"] or {}).get("time_range"))
                                                      for x in td_plan).most_common()),
                           "dated_results": sum(d["dated_results"] for d in dk),
                           "inside_window": sum(d["inside_window"] for d in dk)}}


def radar():
    r = load("v2/radar/radar_2026-10.json")
    runs = [{"utc": x["utc"], "real_credits": sum(c["new_credits"] for c in x["calls"]), "calls": len(x["calls"]),
             "searches": sum(c["endpoint"] == "/search" for c in x["calls"]), "complete": x["complete"],
             "with_provenance": sum(bool(c.get("request_id")) and bool(c.get("response_sha256")) for c in x["calls"])}
            for x in r["runs"]]
    return {"strategy": r["strategy"], "runs": runs, "events": len(r["events"]),
            "corroborated": sum(e["tier"] == "corroborated" for e in r["events"]),
            "cap": load_budget()["caps"]["radar-2026-10"], "cap_source": "config/budget.json radar-2026-10",
            "spent": spent("radar-2026-10")}


def monthly_run_cost():
    a = load("results/v2_ablation.json")["arms"]["A"]
    rd = radar()["runs"]
    return {"radar_run_real_credits": [x["real_credits"] for x in rd],
            "arm_a_per_month_original": a["credits"] / len(AB.MONTHS), "arm_a_searches_per_month": a["searches"] / len(AB.MONTHS),
            "note": f"one radar run = {len(K.QUERIES)} fixed searches + page reads + corroboration; arm A per month = its credits "
                    "at original cost / 9 months"}


COMPUTED = "computed by tools/build_field_report.py from the committed results files"
SETTINGS = {"A": "no dates", "B": "start_date + end_date", "C": "+ filter_by_published_date", "D": "+ our page check"}
# checks P and E (v2/LEAKCHECK_PREREG.md): their rows appear once these results files exist
LEAKCHECKS = {"P": "results/leakcheck_full_page.json", "E": "results/leakcheck_exact_match.json"}
P_SETTINGS = {"a": "start_date + end_date + filter_by_published_date (date test, arm C)",
              "b": "start_date + end_date + filter_by_published_date (finance check, arm D)",
              "c": "start_date + end_date + our date checks (v2 verified evidence, no filter)"}


def median(xs):
    return statistics.median(xs) if xs else None


def p95(xs):
    """95th percentile (statistics.quantiles, inclusive method)."""
    return statistics.quantiles(xs, n=20, method="inclusive")[-1] if len(xs) > 1 else (xs[0] if xs else None)


def leak_row(check, run, setting, n, leaks, valid_kept, valid_total, credits, calls, lat, caveats):
    w = DT.wilson(leaks, n) if n else [None, None]
    return {"check": check, "run": run, "setting": setting, "n": n, "leaks": leaks, "leak_rate": leaks / n if n else None,
            "wilson95": list(w), "valid_kept": valid_kept, "valid_total": valid_total,
            "credits_per_call": credits / calls if calls else None, "median_latency_s": lat, "caveats": caveats}


def check_p_rows(res):
    """Check P, full-page date check: per source, pages whose text holds later content (Claude Code's labels)."""
    calls = res["extract_calls"]
    src_of = {}
    for u in res["units"]:                       # a page kept by two checks belongs to both sources
        src_of.setdefault(u["url"], set()).add(u["source"])
    rows = []
    for s, m in res["metrics"].items():
        mine = [c for c in calls if any(s in src_of.get(u, ()) for u in c["urls"])]
        oc = ", ".join(f"{k} {v}" for k, v in m["outcomes"].items())
        rows.append(leak_row("Check P: full-page date check", "first pass", P_SETTINGS[s], m["with_text"],
                             m["later_content"], None, None, sum(c["credits"] for c in mine), len(mine), None,
                             f"exploratory; leak = page text describes later content (labels by Claude Code); "
                             f"flagged {m['flagged']} of {m['with_text']} with a date after the cutoff anywhere in "
                             f"the text ({oc}); {m['no_text']} without text left out"))
    return rows


def check_e_dates(res):
    """For check E's 'found only without dates' quotes: does Tavily's published_date for the source page, as saved
    in the undated search's response, fall after the cutoff? (descriptive)"""
    out = []
    for c in res["cases"]:
        if c.get("outcome") != "found only without dates":
            continue
        src = [r for r in c["searches"]["undated"]["results"] if r.get("source_page")]
        dates = [x for x in (iso_date(r.get("published_date")) for r in src) if x]
        d = max(dates) if dates else ""                  # any copy of the page dated after the cutoff counts
        out.append({"id": c["id"], "cutoff": c["cutoff"], "source_page_returned": bool(src), "published": d or None,
                    "after_cutoff": bool(d) and d > c["cutoff"]})
    return {"quotes": len(out), "after_cutoff": sum(x["after_cutoff"] for x in out),
            "on_or_before_cutoff": sum(bool(x["published"]) and not x["after_cutoff"] for x in out),
            "undated_or_missing": sum(not x["published"] for x in out), "rows": out}


def check_e_rows(res):
    """Check E, exact_match back-dating: a verified quote that a dated search cannot find may have appeared later."""
    m, sh = res["metrics"], res["metrics"]["shares"]
    lat = median([s["response_time"] for c in res["cases"] for s in c["searches"].values()
                   if s.get("response_time") is not None])
    d, miss = check_e_dates(res), sh["found only without dates"]
    w = miss["wilson95"]
    row = leak_row("Check E: exact_match back-dating", "first pass",
                   "exact_match + end_date + filter_by_published_date, vs the same search undated", m["run"], 0,
                   sh["found before cutoff"]["x"], m["run"], m["credits"], 2 * m["run"], lat, "")
    row.update({"leaks": None, "leak_rate": None, "wilson95": [None, None], "caveats":
                f"exploratory; no leak measure: missed by the dated search but found undated {miss['x']} of "
                f"{m['run']} ({w[0]:.0%}\u2013{w[1]:.0%}, Wilson 95%); for those {d['quotes']}, Tavily's "
                f"published_date for the source page is after the cutoff for {d['after_cutoff']}, on or before it for "
                f"{d['on_or_before_cutoff']}, missing for {d['undated_or_missing']} (descriptive), so they read as "
                f"filter misses, not back-dating; not found either way {sh['not found either way']['x']}; valid "
                "evidence kept = found before the cutoff; credits and latency cover both searches"})
    return [row]


def leakage_table():
    """'Time-locked search leakage': one row per setting, for the date test and the finance check (first pass and
    after the Wayback retry), and checks P and E (placeholder rows until their results files exist)."""
    rows = []
    out, rt = load("results/date_field_test.json"), load("results/date_field_test_wayback_retry.json")
    after = with_retry(out, rt, lambda row, r: DT.label(row["cutoff"], r["captures"], r["tavily_date"],
                                                         DT.url_date(r["url"]), r["page_date"]))
    n_extract = len(out["extract_calls"].get("D", []))
    for run, o in (("first pass", out), ("after logged retry", after)):
        m = DT.metrics(o)["arms"]
        for a in "ABCD":
            x = m[a]
            calls = x["cases"] + (n_extract if a == "D" else 0)
            cav = [f"pilot, {len(o['rows'])} cases; leak = Wayback-confirmed (no capture by the cutoff)"]
            if a == "D":
                cav.append(f"page check adds {n_extract} Extract calls; keeps only pages with an explicit date")
            if run == "after logged retry":
                cav.append("retry only recovers failed Wayback lookups; valid total grows")
            rows.append(leak_row(f"Date test ({len(o['rows'])} replay cases)", run, SETTINGS[a], x["cases"], x["leak_cases"],
                                 x["valid_total"] - x["valid_lost"], x["valid_total"], x["credits"], calls,
                                 x["median_latency_s"], "; ".join(cav)))
    fo, frt = load("results/finance_lookahead.json"), load("results/finance_lookahead_wayback_retry.json")
    for run, o in (("first pass", fo), ("after logged retry", with_retry(fo, frt, F.label))):
        m = F.metrics(o)
        for a, setting in (("N", SETTINGS["A"]), ("D", "start_date + end_date + filter_by_published_date")):
            x = m["arms"][a]
            rows.append(leak_row(f"Finance check ({m['events']} scheduled events)", run, setting, m["events"],
                                 x["confirmed"]["events"], x["valid_total"] - x["valid_lost"], x["valid_total"],
                                 x["credits"], m["events"], x["median_latency_s"],
                                 f"exploratory; {x['wayback_failed']} Wayback lookups failed; C4 date from a "
                                 "board-meeting notice (see the finance table)"))
    for chk, path in LEAKCHECKS.items():
        if not (ROOT / path).exists():
            rows.append({"check": f"Check {chk}", "run": "pending", "setting": None, "placeholder": True,
                         "caveats": f"placeholder: fills in from {path} when it exists"})
        else:
            rows += (check_p_rows if chk == "P" else check_e_rows)(load(path))
    return {"label": COMPUTED, "rows": rows,
            "columns": "leak rate = cases (events) with at least one confirmed post-cutoff result among the kept "
                       "results, Wilson 95%; valid evidence kept = Wayback-confirmed pre-cutoff, on-topic results "
                       "this setting kept, of those any setting found; median latency = Tavily response_time"}


# experiments whose evidence was quote-checked (code takes the cited line and finds the number in it): the files
# holding their claims. Others (date test, finance, recall audit, ...) have no quote step, so no ratio.
QUOTE_SOURCES = {"scored v2 pipeline (arm A)": (("v2-issue4", "v2-issue14"), "v2/ablation/arm_A_*.json"),
                 "arm B (Nemotron writes)": (("v2-ablation-B",), "v2/ablation/arm_B_*.json"),
                 "arm C (Nemotron, regional)": (("v2-ablation-C",), "v2/ablation/arm_C_*.json"),
                 "arm T (Tavily auto_parameters)": (("v2-ablation-T",), "v2/ablation/arm_T_*.json"),
                 "T+dates (exploratory)": (("v2-ablation-Td",), "v2/ablation/arm_Td_*.json"),
                 "H (exploratory)": (("v2-ablation-H",), "v2/ablation/arm_H_*.json"),
                 "September Live build": (("v2-issue2",), "v2/evidence/run_2026-09_basket.json"),
                 "October radar": (("radar-2026-10",), "v2/radar/radar_2026-10.json")}


def verified_quotes(pattern):
    seen = set()
    for p in sorted(ROOT.glob(pattern)):
        for c in json.loads(p.read_text(encoding="utf-8")).get("cards", []):
            seen |= {(c["url"], cl["line"]) for cl in c.get("claims", []) if cl.get("status") == "verified"}
    return len(seen)


def receipt():
    """Credit and speed receipt: per endpoint and per experiment, from results/call_receipts.json (the ledger joined
    to Tavily's response_time by tools/build_call_receipts.py)."""
    cr = load("results/call_receipts.json")
    calls = cr["rows"]

    def agg(rows):
        rts = [r["response_time"] for r in rows if r["response_time"] is not None]
        cr_ = sum(r["credits"] for r in rows)
        return {"calls": len(rows), "credits": cr_, "credits_per_call": cr_ / len(rows) if rows else None,
                "median_latency_s": median(rts), "p95_latency_s": p95(rts), "with_latency": len(rts)}

    by_ep = [{"endpoint": ep, **agg([r for r in calls if r["endpoint"] == ep])}
             for ep in sorted({r["endpoint"] for r in calls})]
    pairs = sorted({(ex, r["endpoint"]) for r in calls for ex in r["experiments"]})
    by_exp = [{"experiment": ex, "endpoint": ep,
               **agg([r for r in calls if ex in r["experiments"] and r["endpoint"] == ep])} for ex, ep in pairs]
    per_quote = []
    for label, (exps, pattern) in QUOTE_SOURCES.items():
        cr_ = sum(r["credits"] for r in calls if set(r["experiments"]) & set(exps))
        q = verified_quotes(pattern)
        per_quote.append({"what": label, "budgets": list(exps), "credits": cr_, "verified_quotes": q,
                          "credits_per_verified_quote": cr_ / q if q else None, "source": pattern})
    return {"label": COMPUTED, "built_from": f"results/call_receipts.json (built {cr['built']})",
            "by_endpoint": by_ep, "by_experiment": by_exp, "per_verified_quote": per_quote,
            "total": agg(calls), "reconcile_credits": sum(r["credits"] for r in cr["reconcile"]),
            "notes": ["include_usage can read 0 credits for calls below Tavily's reporting threshold, so a call "
                      "showing 0 is not proof it was free; account totals are reconciled to the billing page "
                      "(the reconcile rows, not in the per-endpoint figures)",
                      "a call charged to two budgets counts under both experiments (as the caps count it), so the "
                      "experiment rows add up to more than the endpoint totals; arm A re-used the "
                      "scored pipeline's searches from the cache, so its credits are v2-issue4 + v2-issue14",
                      "latency = Tavily's response_time (server time), not our wall-clock time",
                      "cache hits and phantom rows (cache hits charged by an old budget bug) are left out"]}


def build():
    ref = json.loads(RC.REFERENCE.read_text(encoding="utf-8"))["changes"]
    ledger = read_ledger()
    rep = {"built": date.today().isoformat(), "leakage": leakage_table(), "receipt": receipt(),
           "four_arms": four_arms(),
           "exploratory": {"H": exploratory("H", "v2-ablation-H", ref), "Td": exploratory("Td", "v2-ablation-Td", ref)},
           "date_test": date_test(), "lang_date_test": lang_date_test(), "finance": finance(),
           "auto_parameters": auto_parameters(), "radar": radar(),
           "monthly_run_cost": monthly_run_cost(), "ledger_rows": len(ledger),
           "pages_changed": DR.latest(DR.load_state()), "leak_by_source_type": LKT.table()}
    OUT.write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=float))
    return rep


if __name__ == "__main__":
    r = build()
    print(f"{OUT.relative_to(ROOT)}: four arms {len(r['four_arms']['rows'])}, radar runs {len(r['radar']['runs'])}")
