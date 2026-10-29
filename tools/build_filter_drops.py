#!/usr/bin/env python3
"""Why the time-locked search (arm C) did not return some of the valid evidence items in the date test pilot
(initial pass): results/filter_drops.json. Exploratory, added after scoring; changes no headline. 0 credits, offline.

    python tools/build_filter_drops.py

A valid item is a result some arm returned that the archive shows existed on or before the cutoff and that is on
topic (v2.date_test.metrics). A missed item is a valid item arm C did not return for its case. Each is sorted into one
class from the date fields saved with it; the class rules are in RULES below and read only the saved fields.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from v2 import date_test as DT  # noqa: E402

OUT = ROOT / "results" / "filter_drops.json"
LABEL = "exploratory, added after scoring; changes no headline"
SOURCE = "results/date_field_test.json"
RULES = {
    "a": "no detectable date: Tavily, the address and the page all give none",
    "b": "Tavily's date is after the cutoff although the archive holds a copy from on or before it, and the saved page "
         "shows no later edit",
    "c": "Tavily's date is after the cutoff and the page itself shows a later edit date",
    "d": "other: the saved dates do not put the item outside what the filter keeps (reason given per item)",
}


def classify(row, r):
    """(class, reason) for one valid item the dated filter did not return."""
    cut = row["cutoff"]
    start = DT.arm_params("C", row)["start_date"]
    tav, page, earliest = r["tavily_date"], r["page_date"], (r["captures"] or [None])[0]
    seen = [d for d in (tav, r["best_date"], DT.url_date(r["url"]), page) if d]
    if not seen:
        return "a", "no date from Tavily, the address or the page"
    if tav and tav > cut:
        if page and page > cut:
            return "c", f"Tavily dates it {tav}, after {cut}; the page shows {page}; earliest archive copy {earliest}"
        return "b", (f"Tavily dates it {tav}, after {cut}; earliest archive copy {earliest} is on or before it; "
                     "the page shows no later edit date")
    if tav and tav < start:
        return "d", f"Tavily dates it {tav}, before the window start {start}: outside the filter's lower bound"
    return "d", (f"Tavily dates it {tav}, inside {start} to {cut}: the date fields would keep it; the dated search "
                 "returned a different set, and the saved fields do not say why")


def build(path=ROOT / SOURCE):
    out = json.loads(Path(path).read_text(encoding="utf-8"))
    items = []
    for row in out["rows"]:
        arms = row["arms"]
        kept = {r["url"] for r in arms.get("C", {}).get("results", [])}
        seen = {}
        for a in "ABCD":
            for r in arms.get(a, {}).get("results", []):
                if r["label"] == "P" and r["on_topic"] and r["url"] not in kept:
                    seen.setdefault(r["url"], (a, r))
        for url, (a, r) in seen.items():
            cls, why = classify(row, r)
            items.append({"case": row["id"], "url": url, "returned_by_arm": a, "cutoff": row["cutoff"],
                          "window_start": DT.arm_params("C", row)["start_date"], "tavily_date": r["tavily_date"],
                          "best_date": r["best_date"], "address_date": DT.url_date(url), "page_date": r["page_date"],
                          "earliest_archive_copy": (r["captures"] or [None])[0], "class": cls, "reason": why})
    m = out["metrics"]["arms"]["C"]
    if (len(items), m["valid_total"]) != (m["valid_lost"], sum(1 for _ in _valid(out))):
        raise SystemExit("items not returned differ from the committed valid_lost / valid_total for arm C")
    counts = {k: sum(x["class"] == k for x in items) for k in RULES}
    split = {"excluded_for_their_dates": counts["a"] + counts["b"] + counts["c"],
             "before_window_start": sum(x["class"] == "d" and x["tavily_date"] < x["window_start"] for x in items),
             "inside_window": sum(x["class"] == "d" and x["tavily_date"] >= x["window_start"] for x in items)}
    sentence = (f"Only {split['excluded_for_their_dates']} of the {len(items)} were excluded for their dates; "
                f"{split['before_window_start']} fell just before our window start; the other {split['inside_window']} were "
                "dated inside the window, so the difference is mostly which results the dated search returned, not the filter.")
    return {"label": LABEL, "source": SOURCE, "pass": "initial pass (pre-registered run, before the Wayback retry)",
            "arm": "C", "not_returned": len(items), "valid_total": m["valid_total"], "rules": RULES, "counts": counts, "split": split, "plain_sentence": sentence,
            "items": items}


def _valid(out):
    return {(row["id"], r["url"]) for row in out["rows"] for a in "ABCD"
            for r in row["arms"].get(a, {}).get("results", []) if r["label"] == "P" and r["on_topic"]}


if __name__ == "__main__":
    res = build()
    OUT.write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{LABEL}: {res['not_returned']} of {res['valid_total']} not returned; classes {res['counts']} -> {OUT.relative_to(ROOT)}")
