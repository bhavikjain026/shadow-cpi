#!/usr/bin/env python3
"""results/repro_check_<date>.json: did each Tavily item reproduce in the repro/ run? (0 credits, no API call)

    python tools/build_repro_check.py

Reads the saved output of tools/run_repro.py (results/repro_run.json) and applies one rule per script, written below
next to the item it checks. Verdict: yes (the original behaviour showed), no (it did not), unclear (the output cannot
decide it). A script whose output was not saved is "unclear (output not saved)"; nothing is reconstructed from the
ledger. "showed" holds the output lines the rule read, copied as printed.
"""
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUN = ROOT / "results" / "repro_run.json"


def lines(out, *starts):
    return [l for l in out.splitlines() if l.startswith(starts)]


def time_range(out):
    """Original: auto_parameters picked a recent window, so most results were dated after the month the query names."""
    shown = lines(out, "auto_parameters echo", "10 results", "results dated")
    months = re.search(r"by month \(None = undated\): (\{.*\})", out)
    m = ast.literal_eval(months.group(1)) if months else {}                   # the dict the script printed
    dated = sum(v for k, v in m.items() if k is not None)
    asked = int(re.search(r"results dated \S+: (\d+) of", out).group(1))
    if dated == 0:
        return "no", shown, "every result came back undated, so the window's effect on result dates could not show"
    return ("yes" if dated - asked > dated / 2 else "no"), shown, "most dated results outside the asked month" \
        if dated - asked > dated / 2 else "most dated results inside the asked month"


def echo_dates(out):
    """Original: with our start_date/end_date sent, the echo showed a time_range and no dates."""
    shown = lines(out, "sent window", "auto_parameters echo", "echo shows")
    ok = "echo shows start_date or end_date: False; echo shows time_range: True" in out
    return ("yes" if ok else "no"), shown, "echo reports time_range and not the dates we sent" if ok else \
        "echo shows our dates or no time_range"


def no_asof(out):
    """Original: Extract returns the page as it is now, with no as-of or crawl-date field."""
    shown = lines(out, "date-like keys", "result keys")
    keys = re.search(r"date-like keys[^:]*: (\[.*\])", out).group(1)
    ok = not re.search(r"as_of|crawl|fetched", keys)
    return ("yes" if ok else "no"), shown, "no as-of or crawl-date field returned" if ok else "an as-of field is present"


def published_vs_modified(out):
    """Original: compared by code on 42 pages, Tavily's date was later than the page's own date on some. A text match on
    a handful of results cannot repeat that comparison, so this run is not used to decide it."""
    rows = [l for l in out.splitlines() if "page says:" in l]
    return "unclear", rows, "the script prints dates side by side; it does not repeat the 42-page comparison"


def map_empty(out):
    """Original: Map returned no URLs and no reason."""
    shown = lines(out, "0 urls", "empty answer", "response keys")
    ok = bool(re.search(r"^0 urls", out, re.M)) and "reason-like keys present: []" in out
    return ("yes" if ok else "no"), shown, "empty result with no reason field" if ok else "URLs or a reason came back"


def scanned_pdf(out):
    """Original: Extract returned the letterhead (a few hundred characters) and no image-only flag."""
    shown = [l for l in out.splitlines() if l.startswith(("result keys", "a flag for image-only")) or " characters of text" in l]
    chars = int(re.search(r"(\d+) characters of text", out).group(1))
    ok = "a flag for image-only pages is present: False" in out and chars < 1000
    return ("yes" if ok else "no"), shown, f"{chars} characters and no image-only flag" if ok else "text or a flag came back"


def usage_lag(out):
    """Original: /usage did not reflect calls that per-call usage had already counted."""
    shown = lines(out, "/usage (account", "the search reported")
    m = re.search(r"reported (\d+) credit\(s\); /usage moved by (-?\d+) \(account\)", out)
    ok = m and int(m.group(1)) > 0 and int(m.group(2)) < int(m.group(1))
    return ("yes" if ok else "no"), shown, "/usage did not move straight after a billed search" if ok else \
        "/usage moved by the search's credits"


RULES = {"auto_parameters_time_range": time_range, "auto_parameters_echo_dates": echo_dates,
         "extract_no_asof": no_asof, "published_vs_modified": published_vs_modified, "map_empty": map_empty,
         "scanned_pdf_extract": scanned_pdf, "usage_lag": usage_lag}


def build(run=RUN):
    r = json.loads(Path(run).read_text(encoding="utf-8"))
    rows = []
    for x in r["runs"]:
        s, out = x["script"], x.get("output")
        if not out:
            verdict, shown, why = "unclear (output not saved)", [], "only the ledger row exists"
        else:
            verdict, shown, why = RULES[s](out)
        rows.append({"script": f"repro/{s}.py", "request_ids": [i for i in x.get("request_ids", []) if i],
                     "credits": x.get("credits"), "showed": shown, "reproduced": verdict, "why": why,
                     "rule": " ".join(RULES[s].__doc__.split())})
    res = {"date": r["date"], "source": str(Path(run).relative_to(ROOT)), "tavily_calls_made_for_this_file": 0,
           "note": "Verdicts are read from the saved output of one run each; Tavily's index changes, so a verdict says "
                   "what showed on this date only. The original measurements stand as measured on their dates.",
           "rows": rows}
    out = ROOT / "results" / f"repro_check_{r['date']}.json"
    out.write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return out, res


if __name__ == "__main__":
    p, res = build()
    print(f"{p.relative_to(ROOT)}: " + ", ".join(f"{Path(x['script']).stem} {x['reproduced']}" for x in res["rows"]))
