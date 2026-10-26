#!/usr/bin/env python3
"""Score any search function on the 34 timelock cases: leak rate (Wilson 95% interval) and valid evidence kept.

    python benchmarks/timelock34/score.py          # the recorded arms, replayed offline (0 credits)

    from benchmarks.timelock34.score import score
    score(lambda question, cutoff: my_search(question, cutoff))    # -> {'all': {...}, 'date_test': ..., 'finance': ...}

A search function takes (question, cutoff) and returns its results (dicts with a 'url', or plain URLs), or None to
skip a case. Leak case: at least one returned URL is labelled `confirmed`. Only URLs in the dataset carry labels;
other URLs are counted as `unlabelled`, never as safe. Standard library only.
"""
import json
import math
import sys
from pathlib import Path

CASES = Path(__file__).resolve().parent / "cases.jsonl"


def load_cases(path=CASES):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def wilson(x, n, z=1.959964):
    if n == 0:
        return (None, None)
    p = x / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def _urls(results):
    return [r if isinstance(r, str) else r["url"] for r in results]


def _summary(rows):
    n, leaks = len(rows), sum(r["leak_case"] for r in rows)
    valid_total = sum(r["valid_total"] for r in rows)
    return {"cases": n, "leak_cases": leaks, "leak_rate": leaks / n if n else None, "wilson95": wilson(leaks, n),
            "date_flag_cases": sum(r["flag_case"] for r in rows), "results": sum(r["results"] for r in rows),
            "unlabelled": sum(r["unlabelled"] for r in rows), "valid_kept": sum(r["valid_kept"] for r in rows),
            "valid_total": valid_total}


def score(search, cases=None):
    """{'all', 'date_test', 'finance'} -> summary, plus 'per_case'. `search(question, cutoff)` -> results or None."""
    per_case = []
    for c in cases if cases is not None else load_cases():
        got = search(c["question"], c["cutoff"])
        if got is None:
            continue
        urls = set(_urls(got))
        lab = {r["url"]: r for r in c["results"]}
        valid = {u for u, r in lab.items() if r["valid_evidence"]}
        per_case.append({"id": c["id"], "dataset": c["dataset"], "results": len(urls),
                         "leak_case": any(lab[u]["leak"] == "confirmed" for u in urls if u in lab),
                         "flag_case": any(lab[u]["leak"] == "date_flag" for u in urls if u in lab),
                         "unlabelled": len(urls - lab.keys()), "valid_kept": len(urls & valid),
                         "valid_total": len(valid)})
    out = {"all": _summary(per_case)}
    for ds in ("date_test", "finance"):
        out[ds] = _summary([r for r in per_case if r["dataset"] == ds])
    out["per_case"] = per_case
    return out


def recorded(arm, cases=None):
    """A search function that replays one recorded arm ('no_dates', 'dates', 'dates_filter', ...)."""
    by = {(c["question"], c["cutoff"]): c for c in (cases if cases is not None else load_cases())}

    def search(question, cutoff):
        c = by[(question, cutoff)]
        if arm not in c["result_urls"]:
            return None
        lab = {r["url"]: r for r in c["results"]}
        return [{"url": u, "published_date": lab[u]["published_date"]} for u in c["result_urls"][arm]]
    return search


def date_checked(search):
    """Wrap a search function with timelock's own date check: keep only results labelled safe."""
    from timelock import SAFE, check_result

    def checked(question, cutoff):
        got = search(question, cutoff)
        return None if got is None else [r for r in got if check_result(r, cutoff) == SAFE]
    return checked


def _pct(x):
    return "n/a" if x is None else f"{x:.0%}"


def main():
    cases = load_cases()
    rows = [(arm, recorded(arm, cases)) for arm in ("no_dates", "dates", "dates_filter", "dates_filter_page_date")]
    rows.append(("no_dates + timelock check", date_checked(recorded("no_dates", cases))))
    print("| search | set | leak cases | leak rate (95% CI) | date-flag cases | valid evidence kept |")
    print("|---|---|---|---|---|---|")
    for name, fn in rows:
        s = score(fn, cases)
        for ds in ("date_test", "finance", "all"):
            r = s[ds]
            if not r["cases"]:
                continue
            lo, hi = r["wilson95"]
            print(f"| {name} | {ds} | {r['leak_cases']} of {r['cases']} | {_pct(r['leak_rate'])} "
                  f"({_pct(lo)}–{_pct(hi)}) | {r['date_flag_cases']} | {r['valid_kept']} of {r['valid_total']} |")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))       # for timelock when run as a script
    sys.exit(main())
