#!/usr/bin/env python3
"""Compare our timelock34 leak labels with a separate, post-hoc AI-assisted review (ChatGPT agent).

    python benchmarks/timelock34/compare_review.py            # writes results/timelock34_second_review.json
    python benchmarks/timelock34/compare_review.py --check    # exit 1 if the file would change

The review (`second_review_chatgpt.csv`) has one row per (case, URL): R001 is the first result of the first case in
cases.jsonl, in that order; the join refuses to run if a row's case or URL differs. The two reviews define a leak
differently: ours is a result dated after the cutoff (a date signal after it, `confirmed` when the Wayback Machine has
no capture by the cutoff); the reviewer's is content that reveals the outcome. UNCLEAR rows are left out of agreement.
Offline, 0 credits, standard library only.
"""
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REVIEW = HERE / "second_review_chatgpt.csv"
OUT = ROOT / "results" / "timelock34_second_review.json"
SETTINGS = ("no_dates", "dates", "dates_filter", "dates_filter_page_date")
OURS = {"confirmed": ("confirmed",), "confirmed_or_date_flag": ("confirmed", "date_flag")}
EXAMPLE = "R196"                  # TCS, finance, filtered search: dated before the cutoff, updated after it
PAGE_DATE_CHECKS = ("R010", "R020")

sys.path.insert(0, str(ROOT))
from benchmarks.timelock34.score import load_cases  # noqa: E402


def load_review(path=REVIEW):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def join(cases, review):
    """[(case, our result, review row)] in row order; raises if the review's rows are not our results in order."""
    ours = [(c, r) for c in cases for r in c["results"]]
    if len(ours) != len(review):
        raise ValueError(f"review has {len(review)} rows, cases.jsonl has {len(ours)} results")
    out = []
    for i, ((c, r), row) in enumerate(zip(ours, review), 1):
        if row["row_id"] != f"R{i:03d}" or (row["case_id"], row["cutoff"], row["url"]) != (c["id"], c["cutoff"],
                                                                                          r["url"]):
            raise ValueError(f"row {row['row_id']}: expected R{i:03d} {c['id']} {c['cutoff']} {r['url']}, got "
                             f"{row['case_id']} {row['cutoff']} {row['url']}")
        out.append((c, r, row))
    return out


def kappa(pairs):
    """Agreement and Cohen's kappa for [(ours_leak, reviewer_leak)], plus the 2x2 counts (None when undefined)."""
    n = len(pairs)
    if not n:
        return {"rows": 0, "agreement": None, "kappa": None}
    both = sum(a and b for a, b in pairs)
    ours_only = sum(a and not b for a, b in pairs)
    rev_only = sum(b and not a for a, b in pairs)
    agree = (n - ours_only - rev_only) / n
    p_ours, p_rev = (both + ours_only) / n, (both + rev_only) / n
    chance = p_ours * p_rev + (1 - p_ours) * (1 - p_rev)
    return {"rows": n, "agreement": agree, "kappa": None if chance == 1 else (agree - chance) / (1 - chance),
            "both_leak": both, "ours_only": ours_only, "reviewer_only": rev_only,
            "both_safe": n - both - ours_only - rev_only}


def dated_after(r, cutoff):
    return any(d and d > cutoff for d in (r["published_date"], r["url_date"]))


def tasks(joined):
    """Per dataset and setting: cases with at least one leak, by the reviewer and by each of our definitions."""
    review = {(c["id"], r["url"]): row["label"] for c, r, row in joined}
    out = []
    for ds in ("date_test", "finance"):
        cases = list({c["id"]: c for c, _, _ in joined if c["dataset"] == ds}.values())
        lab = {c["id"]: {r["url"]: r for r in c["results"]} for c in cases}
        for arm in SETTINGS:
            ran = [c for c in cases if arm in c["result_urls"]]
            if not ran:
                continue
            row = {"dataset": ds, "setting": arm, "cases": len(ran),
                   "results": sum(len(c["result_urls"][arm]) for c in ran),
                   "reviewer_leak": sum(any(review[(c["id"], u)] == "LEAK" for u in c["result_urls"][arm])
                                        for c in ran),
                   "reviewer_unclear_results": sum(review[(c["id"], u)] == "UNCLEAR"
                                                   for c in ran for u in c["result_urls"][arm])}
            for name, labels in OURS.items():
                row[f"ours_{name}"] = sum(any(lab[c["id"]][u]["leak"] in labels for u in c["result_urls"][arm])
                                          for c in ran)
            row["dated_after_cutoff"] = sum(any(dated_after(lab[c["id"]][u], c["cutoff"])
                                                for u in c["result_urls"][arm]) for c in ran)
            out.append(row)
    return out


def row_view(c, r, row):
    return {"row_id": row["row_id"], "case": c["id"], "dataset": c["dataset"], "cutoff": c["cutoff"],
            "url": r["url"], "reviewer_label": row["label"], "reviewer_date": row["date_relied_on"] or None,
            "reviewer_date_source": row["date_source"], "reviewer_quote": row["evidence_quote"] or None,
            "reviewer_reason": row["reason"],
            "our_leak": r["leak"], "our_published_date": r["published_date"], "our_page_date": r["page_date"],
            "wayback_captures": r["wayback_captures"]}


def build(cases=None, review=None):
    joined = join(cases if cases is not None else load_cases(), review if review is not None else load_review())
    decided = [(r, row) for _, r, row in joined if row["label"] != "UNCLEAR"]
    by_id = {row["row_id"]: (c, r, row) for c, r, row in joined}
    task_rows = tasks(joined)
    fin = next(t for t in task_rows if (t["dataset"], t["setting"]) == ("finance", "dates_filter"))
    return {
        "source": f"benchmarks/timelock34/{REVIEW.name}",
        "reviewer": "separate, post-hoc AI-assisted review (ChatGPT agent)",
        "leak_definitions": {"ours": "a result dated after the cutoff (confirmed: no Wayback capture by the cutoff)",
                             "reviewer": "content that reveals the outcome"},
        "rows": len(joined), "decided": len(decided), "unclear": len(joined) - len(decided),
        "reviewer_labels": {k: sum(row["label"] == k for _, _, row in joined) for k in ("LEAK", "SAFE", "UNCLEAR")},
        "unclear_reasons": sorted({row["reason"] for _, _, row in joined if row["label"] == "UNCLEAR"}),
        "agreement": {name: kappa([(r["leak"] in labels, row["label"] == "LEAK") for r, row in decided])
                      for name, labels in OURS.items()},
        "crosstab": {ds: {f"{ours}/{rev}": sum(c["dataset"] == ds and r["leak"] == ours and row["label"] == rev
                                               for c, r, row in joined)
                          for ours in ("confirmed", "date_flag", "unknown") for rev in ("LEAK", "SAFE", "UNCLEAR")}
                     for ds in ("date_test", "finance")},
        "tasks": task_rows,
        "finance_filtered": {"searches": fin["cases"], "results": fin["results"],
                             "searches_with_result_dated_after_cutoff": fin["dated_after_cutoff"],
                             "reviewer_leak_pages": sum(row["label"] == "LEAK" for c, _, row in joined
                                                        if c["dataset"] == "finance"
                                                        and row["url"] in c["result_urls"].get("dates_filter", ())),
                             "example": row_view(*by_id[EXAMPLE])},
        "page_date_checks": [row_view(*by_id[i]) for i in PAGE_DATE_CHECKS],
    }


def dumps(rep):
    return json.dumps(rep, ensure_ascii=False, indent=1) + "\n"


def main(argv):
    text = dumps(build())
    if "--check" in argv:
        same = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        print(f"{OUT.relative_to(ROOT)}: {'up to date' if same else 'would change'}")
        return 0 if same else 1
    OUT.write_text(text, encoding="utf-8")
    rep = json.loads(text)
    a = rep["agreement"]
    print(f"{OUT.relative_to(ROOT)}: {rep['decided']} decided of {rep['rows']}; agreement "
          + "; ".join(f"{k} {v['agreement']:.1%} (kappa {v['kappa']:.2f})" for k, v in a.items() if v["kappa"] is not None))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
