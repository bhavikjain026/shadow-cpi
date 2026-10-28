#!/usr/bin/env python3
"""Post-hoc statistics on the committed leak counts: results/posthoc_stats.json and results/posthoc_stats.md
(0 credits, no API call, offline). Labelled "post-hoc, not pre-registered": nothing here changes a verdict.

    python tools/build_posthoc_stats.py

- exact McNemar, no dates vs dates + filter, per study (date test pilot, replication, finance check, pooled), on the
  pre-registered initial pass; recomputed from the per-case labels and checked against any value already in results;
- the rule-of-three upper bound for the pooled zero (and the exact one-sided 95% bound it approximates);
- the cache-excluded replication counts, reused from the logged addendum (results/field_report.json replication.cache).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from v2 import date_test as DT  # noqa: E402

OUT = ROOT / "results" / "posthoc_stats.json"
MD = ROOT / "results" / "posthoc_stats.md"
LABEL = "post-hoc, not pre-registered"


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def leak_ids(rows, arm, labels):
    return {row["id"] for row in rows
            if any(r["label"] in labels for r in row["arms"].get(arm, {}).get("results", []))}


def paired(rows, x, y, labels):
    """Exact McNemar on the cases both arms ran: leaks only with x, only with y, two-sided exact p."""
    ids = {row["id"] for row in rows if x in row["arms"] and y in row["arms"]}
    a, b = leak_ids(rows, x, labels) & ids, leak_ids(rows, y, labels) & ids
    return {"cases": len(ids), "leaks_" + x: len(a), "leaks_" + y: len(b), "only_" + x: len(a - b),
            "only_" + y: len(b - a), "p_exact": DT.mcnemar_exact(len(a - b), len(b - a))}


def build():
    dt, rep, fin = load("results/date_field_test.json"), load("results/replication.json"), load(
        "results/finance_lookahead.json")
    fr = load("results/field_report.json")
    studies = {
        "date_test": dict(rule="date-test rule (v2/DATE_TEST_PREREG.md)", no_dates="A", dated="C",
                          **paired(dt["rows"], "A", "C", ("L",))),
        "replication": dict(rule="date-test rule (v2/DATE_TEST_PREREG.md)", no_dates="A", dated="C",
                            **paired(rep["rows"], "A", "C", ("L",))),
        "finance": dict(rule="finance rule (v2/FINANCE_PREREG.md, as amended)", no_dates="N", dated="D",
                        **paired(fin["rows"], "N", "D", ("confirmed",))),
    }
    pool_rows = dt["rows"] + rep["rows"]
    studies["pooled"] = dict(rule="date-test rule; pilot + replication", no_dates="A", dated="C",
                             **paired(pool_rows, "A", "C", ("L",)))
    # cross-checks against values already committed (same counts, same p)
    known = {"replication": rep["metrics"]["price"]["a_vs_c_mcnemar"],
             "pooled": fr["replication"]["pooled"]["a_vs_c_mcnemar"]}
    for k, m in known.items():
        s = studies[k]
        if (s["only_A"], s["only_C"]) != (m["A_only"], m["C_only"]) or abs(s["p_exact"] - m["p_exact"]) > 1e-12:
            raise SystemExit(f"{k}: recomputed McNemar differs from the committed value {m}")
    pl = fr["replication"]["pooled"]["arms"]["C"]
    if (studies["pooled"]["leaks_C"], studies["pooled"]["cases"]) != (pl["leak_cases"], pl["cases"]):
        raise SystemExit("pooled dates + filter count differs from results/field_report.json")
    n, x = pl["cases"], pl["leak_cases"]
    zero = {"leaks": x, "cases": n, "rule_of_three_upper": 3 / n if x == 0 else None,
            "exact_one_sided_95_upper": 1 - 0.05 ** (1 / n) if x == 0 else None, "wilson95": pl["wilson95"]}
    ca = fr["replication"]["cache"]
    out = {"label": LABEL, "mcnemar": studies, "pooled_zero": zero,
           "cache_excluded_replication": {"source": "results/replication.md addendum (logged 2026-10-28), reused",
                                          "label": ca["label"], "served": ca["served"],
                                          "pilot_reused": ca["pilot_reused"], **ca["without_pilot_reused"]}}
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    L = ["# Post-hoc statistics (" + LABEL + ")", "",
         "Built by `python tools/build_posthoc_stats.py` from committed per-case labels; 0 credits. Nothing here was "
         "pre-registered and nothing here changes a verdict.", "",
         "## Exact McNemar, no dates vs dates + filter (pre-registered initial pass, paired by case)", "",
         "| Study | Rule | Cases | Leaks, no dates | Leaks, dates + filter | Only no dates | Only dates + filter "
         "| Exact p (two-sided) |", "|---|---|---|---|---|---|---|---|"]
    for k, s in studies.items():
        a, c = s["no_dates"], s["dated"]
        L.append(f"| {k.replace('_', ' ')} | {s['rule']} | {s['cases']} | {s['leaks_' + a]} | {s['leaks_' + c]} "
                 f"| {s['only_' + a]} | {s['only_' + c]} | {s['p_exact']:.2g} |")
    L += ["", "## The pooled zero", "",
          f"{x} detected of {n} with dates + filter (Wilson 95% {zero['wilson95'][0]:.0%}–{zero['wilson95'][1]:.0%}). "
          + (f"Rule of three: the true leak rate is below {zero['rule_of_three_upper']:.1%} with about 95% "
             f"confidence (exact one-sided bound {zero['exact_one_sided_95_upper']:.1%})." if x == 0 else ""),
          "", "## Replication without the cache-served responses (reused from the logged addendum)", "",
          f"{ca['served']} no-dates answers were served from our cache, {ca['pilot_reused']} of them the pilot's own "
          f"response. Without those {ca['pilot_reused']} cases: no dates "
          f"{ca['without_pilot_reused']['arms']['A']['leak_cases']} of {ca['without_pilot_reused']['cases']}, "
          f"dates + filter {ca['without_pilot_reused']['arms']['C']['leak_cases']} detected of "
          f"{ca['without_pilot_reused']['cases']} ({ca['label']}).", ""]
    MD.write_text("\n".join(L), encoding="utf-8")
    return out


if __name__ == "__main__":
    o = build()
    print(f"{LABEL}: " + "; ".join(f"{k} p={s['p_exact']:.2g}" for k, s in o["mcnemar"].items())
          + f" -> {OUT.relative_to(ROOT)}, {MD.relative_to(ROOT)}")
