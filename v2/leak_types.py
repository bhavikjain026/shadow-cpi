#!/usr/bin/env python3
"""Leaks by source type (v2/DRIFT_PREREG.md, part C). 0 credits: saved date-test and finance results only.
Exploratory: written after both tests were scored; it changes no verdict.

    python -m v2.leak_types      # prints the table (the Field Report builder reads table() directly)

Each result's URL is classified (live blog / hub or tag page / article / other) by the rule fixed in the
pre-registration; leaks and totals per type, with Wilson 95% intervals.
"""
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from v2.date_test import wilson

ROOT = Path(__file__).resolve().parent.parent
DATE_TEST = ROOT / "results" / "date_field_test.json"
FINANCE = ROOT / "results" / "finance_lookahead.json"
TYPES = ["article", "live blog", "hub or tag page", "other"]
HUB_SEGMENTS = {"tag", "tags", "topic", "topics", "category", "categories", "section", "sections", "hub", "archive",
                "archives", "search", "author", "authors", "latest", "latest-news", "keyword", "keywords", "page"}
ARTICLE_SEGMENTS = {"article", "articles", "articleshow", "story", "news"}
LEAK = {"date test": "L", "finance": "confirmed"}          # rule C.2


def source_type(url):
    """Rule C.3, first match wins."""
    path = urlparse(url or "").path.lower()
    segs = [s for s in path.split("/") if s]
    if re.search(r"(^|[/\-_.])live([/\-_.]|$)", path) or any(w in path for w in
                                                              ("liveblog", "live-blog", "live-updates", "liveupdates")):
        return "live blog"
    if not segs or HUB_SEGMENTS & set(segs) or (path.endswith("/") and not re.search(r"\d", segs[-1])
                                                and segs[-1].count("-") <= 1):
        return "hub or tag page"
    if segs[-1].count("-") >= 3 or re.search(r"\d{6,}", path) or any(s in ARTICLE_SEGMENTS for s in segs[:-1]):
        return "article"
    return "other"


def units(date_test=None, finance=None):
    """(source, url, leak, arm) for every result row of every arm of every case (rule C.1)."""
    out = []
    for name, data in (("date test", date_test), ("finance", finance)):
        for row in data["rows"]:
            for a, arm in row["arms"].items():
                out += [(name, r["url"], r.get("label") == LEAK[name], a) for r in arm.get("results", [])]
    return out


def table(date_test=None, finance=None):
    date_test = date_test or json.loads(DATE_TEST.read_text(encoding="utf-8"))
    finance = finance or json.loads(FINANCE.read_text(encoding="utf-8"))
    us = units(date_test, finance)
    rows = []
    for t in TYPES:
        mine = [u for u in us if source_type(u[1]) == t]
        row = {"type": t}
        for src in ("date test", "finance", "pooled"):
            sel = [u for u in mine if src == "pooled" or u[0] == src]
            leaks = sum(u[2] for u in sel)
            row[src] = {"leaks": leaks, "results": len(sel), "rate": leaks / len(sel) if sel else None,
                        "wilson95": list(wilson(leaks, len(sel))) if sel else None}
        rows.append(row)
    by_arm = {}
    for u in us:
        if u[2]:
            by_arm[f"{u[0]} {u[3]}"] = by_arm.get(f"{u[0]} {u[3]}", 0) + 1
    return {"rows": rows, "results": len(us), "leaks": sum(u[2] for u in us), "leaks_by_arm": by_arm,
            "rule": "v2/DRIFT_PREREG.md part C (URL only; first match wins: live blog, hub or tag page, article, "
                    "other)",
            "leak_definition": "date test: Wayback-confirmed leak (label L); finance: confirmed leak; unconfirmed "
                               "results count in the totals only",
            "label": "exploratory, 0 credits, after both tests were scored; changes no verdict",
            "sources": ["results/date_field_test.json", "results/finance_lookahead.json"]}


if __name__ == "__main__":
    t = table()
    for r in t["rows"]:
        p = r["pooled"]
        print(f"{r['type']:16} {p['leaks']:3} of {p['results']:3}  date test {r['date test']['leaks']} of "
              f"{r['date test']['results']}, finance {r['finance']['leaks']} of {r['finance']['results']}")
