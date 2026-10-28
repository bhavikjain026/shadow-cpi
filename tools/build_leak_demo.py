#!/usr/bin/env python3
"""Leak demo data (app page "Leak demo"), built offline with 0 calls from the saved date test and finance check.

    python tools/build_leak_demo.py

For each of the 34 cases (20 date test, 14 finance), two searches: no time lock (date test arm A, finance arm N) and
the time lock, Tavily date filters (start_date/end_date + filter_by_published_date: date test arm C, finance arm D). Per search:
the exact request body, read from the local response cache through the flight recorder's call id and checked against
the response SHA-256 saved in the results file (the API key travels in a header and is never in the body); credits,
latency and Tavily's request id; per result Tavily's published_date, the page date and the existing label after the
logged Wayback retry (the retry files' recovered captures, relabelled with the same code as tools/wayback_retry.py).
Totals are read from results/field_report.json and results/leakcheck_exact_match.json.

Writes results/leak_demo.json. Needs logs/ and cache/ (kept locally); the app reads only the written file.
"""
import copy
import hashlib
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from shadow_cpi.recorder import response_sha256  # noqa: E402
from v2 import date_test as DT  # noqa: E402
from v2 import finance_lookahead as F  # noqa: E402

OUT = ROOT / "results" / "leak_demo.json"
LOG = ROOT / "logs" / "flight_recorder.jsonl"
CACHE = ROOT / "cache" / "tavily"
TESTS = {"date": {"file": "results/date_field_test.json", "retry": "results/date_field_test_wayback_retry.json",
                  "open": "A", "locked": "C", "name": "date test"},
         "finance": {"file": "results/finance_lookahead.json", "retry": "results/finance_lookahead_wayback_retry.json",
                     "open": "N", "locked": "D", "name": "finance check"}}
# the existing labels (v2/date_test.py label, v2/finance_lookahead.py label), worded for the page
LABELS = {"date": {"L": "confirmed leak (Wayback)", "P": "confirmed pre-cutoff (Wayback)", "F": "date flag",
                   "U": "unknown"},
          "finance": {"confirmed": "confirmed leak (Wayback)", "snippet": "snippet leak (not Wayback-confirmed)",
                      "flag": "date flag", "valid": "valid (pre-cutoff, Wayback)", "none": "unknown"}}
LEAK = {"date": "L", "finance": "confirmed"}
QUOTE_WORDS = 25


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def cache_keys(ids):
    """{flight-recorder call id: cache_key} for the given ids (one pass over the local log)."""
    out = {}
    with LOG.open(encoding="utf-8") as f:
        for line in f:
            if any(i in line for i in ids):
                e = json.loads(line)
                if e["id"] in ids:
                    out[e["id"]] = e["cache_key"]
    return out


def request_body(call, keys):
    """The body sent for one call, from the cache, after checking the cached response is the one the results saved."""
    if call["call"] not in keys:
        raise SystemExit(f"call {call['call']} is not in {LOG.relative_to(ROOT)}: the local flight recorder is "
                         "incomplete on this machine")
    entry = json.loads((CACHE / f"{keys[call['call']]}.json").read_text(encoding="utf-8"))
    if response_sha256(entry["response"]) != call["response_sha256"]:
        raise SystemExit(f"call {call['call']}: cached response does not match the saved SHA-256")
    body = {k: v for k, v in entry["request"].items() if k.lower() not in ("api_key", "authorization")}
    return body


def short(text, n=QUOTE_WORDS):
    words = (text or "").replace("\n", " ").split()
    return " ".join(words[:n]) + (" …" if len(words) > n else "")


def item_words(test, row):
    """Words that name the case's item (date test: v2.kinds words; finance: the company or RBI names)."""
    from v2 import kinds as K
    if test == "finance":
        return F.NAMES[row["name"]]
    return [w for k in ({"fuel": ["petrol", "diesel"]}.get(row["kind"]) or [row["kind"]]) for w in K.KINDS[k]["words"]]


def quote(test, row, r):
    """A short quote from the result's snippet: the first sentence that names the case's item, else the title."""
    import re
    from v2 import kinds as K
    words = item_words(test, row)
    for sent in re.split(r"(?<=[.!?])\s+|\n+|#+", r.get("content") or ""):
        if any(K.has_word(sent, w) for w in words):
            return short(sent.strip(" *-|"))
    return short(r["title"])


def relabelled(test, out, retry):
    """The results after the logged Wayback retry: recovered captures put back, labels recomputed (wayback_retry)."""
    after = copy.deepcopy(out)
    got = retry["recovered_captures"]
    for row in after["rows"]:
        for a in row["arms"].values():
            for r in a.get("results", []):
                if r["captures"] is None and r["url"] in got:
                    r["captures"] = got[r["url"]]
                r["label"] = (F.label(row, r) if test == "finance" else
                              DT.label(row["cutoff"], r["captures"], r["tavily_date"], DT.url_date(r["url"]),
                                       r["page_date"]))
    return after


def days_after(d, cutoff):
    return (date.fromisoformat(d) - date.fromisoformat(cutoff)).days if d else None


def search(test, row, arm, first, keys):
    a = row["arms"][arm]
    results = []
    for r, r0 in zip(a["results"], first["arms"][arm]["results"]):
        signals = (r.get("tavily_date"), DT.url_date(r["url"]) if test == "date" else r.get("url_date"))
        dated = next((d for d in signals if d and d > row["cutoff"]), None)      # the signal that made it a leak
        results.append({"url": r["url"], "title": r["title"], "published_date": r.get("tavily_date"),
                        "page_date": r.get("page_date") if test == "date" else None,
                        "url_date": DT.url_date(r["url"]) if test == "date" else r.get("url_date"),
                        "label": LABELS[test][r["label"]], "leak": r["label"] == LEAK[test],
                        "label_first_pass": LABELS[test][r0["label"]],
                        "days_after_cutoff": days_after(dated, row["cutoff"]) if r["label"] == LEAK[test] else None,
                        "quote": quote(test, row, r) if r["label"] == LEAK[test] else ""})
    return {"arm": arm, "request": request_body(a, keys), "credits": a["credits"],
            "latency_s": a["response_time"], "request_id": a["request_id"], "call": a["call"],
            "response_sha256": a["response_sha256"], "results": results}


def cases():
    out = []
    for test, t in TESTS.items():
        first, retry = load(t["file"]), load(t["retry"])
        after = relabelled(test, first, retry)
        keys = cache_keys({row["arms"][a]["call"] for row in first["rows"] for a in (t["open"], t["locked"])})
        for row, row0 in zip(after["rows"], first["rows"]):
            out.append({"id": row["id"], "test": test, "test_name": t["name"], "kind": row["kind"],
                        "name": row.get("name") or row["kind"], "cutoff": row["cutoff"], "query": row["query"],
                        "open": search(test, row, t["open"], row0, keys),
                        "locked": search(test, row, t["locked"], row0, keys)})
    return out


def names_item(c, title):
    """The title names the case's item (v2.kinds words, whole words; 'fuel' = petrol or diesel)."""
    from v2 import kinds as K
    words = [w for k in ({"fuel": ["petrol", "diesel"]}.get(c["kind"]) or [c["kind"]]) for w in K.KINDS[k]["words"]]
    return any(K.has_word(title, w) for w in words)


def examples(cs):
    """Rule (the page says 'examples chosen for clarity'): the first two date-test cases and the first finance case,
    in file order, whose no-lock search has a confirmed leak that is on topic (date test: the leaking result's title
    names the case's item; finance: the pre-registered outcome rule) and whose time-locked search has none."""
    picked = {"date": [], "finance": []}
    for c in cs:
        leaks = [r for r in c["open"]["results"] if r["leak"]]
        clear = c["test"] == "finance" or any(names_item(c, r["title"]) for r in leaks)
        if leaks and clear and not any(r["leak"] for r in c["locked"]["results"]):
            picked[c["test"]].append(c["id"])
    return picked["date"][:2] + picked["finance"][:1]


def totals():
    fr, em = load("results/field_report.json"), load("results/leakcheck_exact_match.json")
    d1, d2 = fr["date_test"]["first_pass"]["arms"], fr["date_test"]["after_retry"]["arms"]
    f1, f2 = fr["finance"]["first_pass"]["all_14"], fr["finance"]["after_retry"]["all_14"]
    miss = em["metrics"]["shares"]["found only without dates"]
    return {
        "date": {"cases": d1["A"]["cases"],
                 "open": {"first": d1["A"]["leak_cases"], "first_wilson95": d1["A"]["wilson95"],
                          "retry": d2["A"]["leak_cases"], "retry_wilson95": d2["A"]["wilson95"]},
                 "locked": {"first": d1["C"]["leak_cases"], "first_wilson95": d1["C"]["wilson95"],
                            "retry": d2["C"]["leak_cases"], "retry_wilson95": d2["C"]["wilson95"]},
                 "source": "results/field_report.json (date_test)"},
        "finance": {"cases": f1["events"],
                    "open": {"first": f1["arms"]["N"]["confirmed_events"],
                             "first_wilson95": f1["arms"]["N"]["confirmed_wilson95"],
                             "retry": f2["arms"]["N"]["confirmed_events"],
                             "retry_wilson95": f2["arms"]["N"]["confirmed_wilson95"]},
                    "locked": {"first": f1["arms"]["D"]["confirmed_events"],
                               "first_wilson95": f1["arms"]["D"]["confirmed_wilson95"],
                               "retry": f2["arms"]["D"]["confirmed_events"],
                               "retry_wilson95": f2["arms"]["D"]["confirmed_wilson95"]},
                    "source": "results/field_report.json (finance)"},
        "strictness": {"missed": miss["x"], "quotes": em["metrics"]["quotes"], "wilson95": miss["wilson95"],
                       "source": "results/leakcheck_exact_match.json (check E)"}}


def build():
    cs, tot = cases(), totals()
    for t in ("date", "finance"):                                     # the per-case labels must give the totals
        n = sum(any(r["leak"] for r in c["open"]["results"]) for c in cs if c["test"] == t)
        if n != tot[t]["open"]["retry"]:
            raise SystemExit(f"{t}: {n} cases with a confirmed leak after the retry, field report says otherwise")
    return {"built_utc": datetime.now(timezone.utc).isoformat(), "examples": examples(cs), "totals": tot,
            "cases": cs, "labels_note": "labels after the logged Wayback retry (each result also carries its "
                                        "first-pass label); the totals show both",
            "sources": [t["file"] for t in TESTS.values()] + [t["retry"] for t in TESTS.values()]}


if __name__ == "__main__":
    out = build()
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"{len(out['cases'])} cases; examples {out['examples']}; sha256 "
          f"{hashlib.sha256(OUT.read_bytes()).hexdigest()[:12]}")
