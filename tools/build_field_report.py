#!/usr/bin/env python3
"""Build results/field_report.json for the app's Tavily field report (0 credits, no API call).

    python tools/build_field_report.py

Every figure is computed here from committed results files (results/, v2/ablation/, v2/radar/, the credit ledger),
so the page never types a number. Exploratory parts are labelled as such; nothing here changes a scored verdict.
"""
import copy
import json
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
from v2 import finance_lookahead as F  # noqa: E402
from v2 import kinds as K  # noqa: E402
from v2 import recall as RC  # noqa: E402

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


def build():
    ref = json.loads(RC.REFERENCE.read_text(encoding="utf-8"))["changes"]
    ledger = read_ledger()
    rep = {"built": date.today().isoformat(), "four_arms": four_arms(),
           "exploratory": {"H": exploratory("H", "v2-ablation-H", ref), "Td": exploratory("Td", "v2-ablation-Td", ref)},
           "date_test": date_test(), "finance": finance(), "auto_parameters": auto_parameters(), "radar": radar(),
           "monthly_run_cost": monthly_run_cost(), "ledger_rows": len(ledger)}
    OUT.write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=float))
    return rep


if __name__ == "__main__":
    r = build()
    print(f"{OUT.relative_to(ROOT)}: four arms {len(r['four_arms']['rows'])}, radar runs {len(r['radar']['runs'])}")
