#!/usr/bin/env python3
"""Build benchmarks/timelock34/cases.jsonl from the committed results of the date test and the finance check
(0 credits, no network). Run from the repository root:

    python benchmarks/timelock34/build.py            # writes cases.jsonl
    python benchmarks/timelock34/build.py --check    # exit 1 if cases.jsonl would change

Labels are the experiments' own, after the logged Wayback retry (tools/build_field_report.py does the same), mapped
to one scale: confirmed (Wayback confirms the page is from after the cutoff) / date_flag (a date after the cutoff,
not confirmed) / unknown. No page text is written: only a short quote (at most 25 words) per result.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from build_field_report import with_retry  # noqa: E402
from v2 import date_test as DT  # noqa: E402
from v2 import finance_lookahead as F  # noqa: E402

OUT = Path(__file__).resolve().parent / "cases.jsonl"
QUOTE_WORDS = 25
# each experiment's arm -> one name for the same search setting
ARMS = {"date_test": {"A": "no_dates", "B": "dates", "C": "dates_filter", "D": "dates_filter_page_date"},
        "finance": {"N": "no_dates", "D": "dates_filter"}}
LEAK = {"L": "confirmed", "F": "date_flag", "P": "unknown", "U": "unknown",                 # date test
        "confirmed": "confirmed", "snippet": "date_flag", "flag": "date_flag", "valid": "unknown", "none": "unknown"}


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def clip(text, n=QUOTE_WORDS):
    words = (text or "").split()
    return " ".join(words[:n]) + ("…" if len(words) > n else "")


def quote(r, ev=None):
    """A sentence of the snippet that states the outcome (finance check), else the title; at most 25 words."""
    if ev is not None:
        for s in re.split(r"(?<=[.!?])\s+|\n+", r.get("content") or ""):
            if F.states_outcome(ev, s):
                return clip(s), "snippet"
    return clip(r.get("title")), "title"


def request(params, query):
    return {"query": query, **params, "include_usage": True}      # shadow_cpi.tavily adds include_usage to every call


def case(dataset, row, ev=None):
    names, urls, by_url = ARMS[dataset], {}, {}
    requests, receipts = {}, {}
    for a, arm in row["arms"].items():
        name = names[a]
        if "request_id" in arm:
            params = DT.arm_params(a, row) if dataset == "date_test" else F.arm_params(a, ev)
            requests[name] = request(params, row["query"])
            receipts[name] = {"request_id": arm["request_id"], "response_sha256": arm["response_sha256"]}
        else:
            requests[name] = {"derived_from": names[arm["from"]],
                              "rule": "kept only results whose page date (Tavily Extract) is on or before the cutoff"}
        urls[name] = [r["url"] for r in arm["results"]]
        for r in arm["results"]:
            src = r["label"]
            valid = (src == "P" and r.get("on_topic")) if dataset == "date_test" else src == "valid"
            q, qfrom = quote(r, ev)
            rec = by_url.setdefault(r["url"], {
                "url": r["url"], "published_date": r.get("tavily_date"), "url_date": DT.url_date(r["url"]),
                "page_date": None, "wayback_captures": r.get("captures"), "leak": LEAK[src], "source_label": src,
                "valid_evidence": bool(valid), "quote": q, "quote_from": qfrom})
            if dataset == "finance":
                rec["states_outcome"] = r.get("states_outcome")
            if r.get("page_date"):
                rec["page_date"] = r["page_date"]
    out = {"id": row["id"], "dataset": dataset, "question": row["query"], "cutoff": row["cutoff"]}
    if dataset == "finance":
        out.update(event=row["name"], event_date=row["event_date"], flag=row["flag"] or None)
    else:
        out.update(kind=row["kind"], month=row["month"], states=row["states"])
    return {**out, "requests": requests, "receipts": receipts, "result_urls": urls, "results": list(by_url.values())}


def build():
    dt = with_retry(load("results/date_field_test.json"), load("results/date_field_test_wayback_retry.json"),
                    lambda row, r: DT.label(row["cutoff"], r["captures"], r["tavily_date"], DT.url_date(r["url"]),
                                            r["page_date"]))
    fin = with_retry(load("results/finance_lookahead.json"), load("results/finance_lookahead_wayback_retry.json"),
                     F.label)
    events = {e[0]: F.event(e) for e in F.EVENTS}
    return ([case("date_test", row) for row in dt["rows"]] +
            [case("finance", row, events[row["id"]]) for row in fin["rows"]])


def dumps(cases):
    return "".join(json.dumps(c, ensure_ascii=False, sort_keys=True) + "\n" for c in cases)


def main():
    text = dumps(build())
    if "--check" in sys.argv:
        same = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        print("cases.jsonl up to date" if same else "cases.jsonl would change")
        return 0 if same else 1
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {text.count(chr(10))} cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
