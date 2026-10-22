#!/usr/bin/env python3
"""Date field test (v2/DATE_TEST_PREREG.md): do Tavily's date fields keep post-cutoff pages out? A pilot.

    python -m v2.date_test --sample   # writes v2/date_test_cases.json (seeded; 0 credits)
    python -m v2.date_test            # runs once (cap 'date-test', 150 credits) -> results/date_field_test.json + .md

Four arms per case, run close together in a seeded random order, everything else identical:
A no date fields; B start_date/end_date (month start to cutoff); C B + filter_by_published_date; D C's results +
our page-date check (Extract; only an explicit published/updated date on the page, the later if both; missing or
ambiguous = unknown, never safe, so D does not keep it). Leak labels come from independent version evidence
(Wayback CDX, a logged direct download), never from the page date D uses.
"""
import json
import math
import random
import re
import statistics
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from shadow_cpi import evidence as E  # noqa: E402
from shadow_cpi.budget import BudgetExceeded  # noqa: E402
from shadow_cpi.recorder import provenance  # noqa: E402
from shadow_cpi.tavily import best_date, iso_date  # noqa: E402
from v2 import rules as R  # noqa: E402

SEED = 20261022
CASES = ROOT / "v2" / "date_test_cases.json"
OUT = ROOT / "results" / "date_field_test.json"
BUDGET = "date-test"
REFERENCE = ROOT / "v2" / "recall_reference.json"
MONTHS_FULL = ["2026-04", "2026-05", "2026-06"]          # the only months with >= 4 reference changes
MONTHS_ALL = ["2026-07", "2026-09"]                      # 3 changes each: all taken
WORDS = {"milk": "milk price hike", "electricity": "electricity tariff hike", "lpg": "LPG cylinder price hike",
         "fuel": "petrol diesel price hike", "rail": "rail fare hike", "bus": "bus fare hike"}
TOPIC_WORDS = {"milk": ["milk"], "electricity": ["electricity", "power", "tariff"], "lpg": ["lpg", "cylinder"],
               "fuel": ["petrol", "diesel", "fuel"], "rail": ["rail", "train", "fare"], "bus": ["bus", "fare"]}
PLACE = {"nct of delhi": "Delhi", "jammu and kashmir": "Jammu and Kashmir"}
BASE = {"topic": "news", "search_depth": "basic", "max_results": 3, "include_published_date": True,
        "include_domains": E.INDIAN_NEWS, "include_domains_mode": "prefer"}


# ---------- sampling (pre-registered) ----------
def sample(reference=None, seed=SEED):
    ref = reference or json.loads(REFERENCE.read_text(encoding="utf-8"))["changes"]
    rng = random.Random(seed)
    by = {m: [r for r in ref if r["month"] == m] for m in MONTHS_FULL + MONTHS_ALL}
    picked, rest = [], []
    for m in MONTHS_FULL:
        pool = sorted(by[m], key=lambda r: r["id"])
        rng.shuffle(pool)
        picked += pool[:4]
        rest += pool[4:]
    for m in MONTHS_ALL:
        picked += sorted(by[m], key=lambda r: r["id"])
    rest.sort(key=lambda r: r["id"])
    picked += rng.sample(rest, 20 - len(picked))
    return [case(r) for r in sorted(picked, key=lambda r: (r["month"], r["id"]))]


def case(r):
    place = ", ".join(PLACE.get(s, s.title()) for s in r["states"]) or "India"
    month_words = datetime.strptime(r["month"], "%Y-%m").strftime("%B %Y")
    return {"id": r["id"], "kind": r["kind"], "month": r["month"], "states": r["states"],
            "cutoff": R.cutoff(r["month"]), "query": f"{WORDS[r['kind']]} {place} {month_words}"}


def arm_params(arm, c):
    p = dict(BASE)
    if arm == "A":
        p["filter_by_published_date"] = False
    else:
        p.update(start_date=f"{c['month']}-01", end_date=c["cutoff"], filter_by_published_date=arm == "C")
    return p


# ---------- page date (arm D) ----------
DATE_WORDS = r"(published|updated|posted|last updated|प्रकाशित|अपडेट)"
_DATES = [(r"(\d{4})-(\d{2})-(\d{2})", lambda m: date(int(m[1]), int(m[2]), int(m[3]))),
          (r"(\d{1,2})\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})", lambda m: _dmy(m[1], m[2], m[3])),
          (r"([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})", lambda m: _dmy(m[2], m[1], m[3]))]


def _dmy(d, mon, y):
    return datetime.strptime(f"{int(d)} {mon[:3].title()} {y}", "%d %b %Y").date()


def page_date(text):
    """(ISO date or None, why). Only a date right after 'published'/'updated' (or Hindi) counts; the later if both;
    two different dates for the same word, or none, = unknown."""
    found = {}
    text = text or ""
    for m in re.finditer(DATE_WORDS + r"\s*(?:on|at)?\s*:?\s*", text, re.I):
        word = "updated" if m[1].lower() in ("updated", "last updated", "अपडेट") else "published"
        after = re.split(DATE_WORDS, text[m.end():m.end() + 40], flags=re.I)[0]   # stop at the next date word
        for pat, mk in _DATES:
            d = re.search(pat, after)
            if d:
                try:
                    found.setdefault(word, set()).add(mk(d).isoformat())
                except ValueError:
                    pass
                break
    if not found:
        return None, "no explicit published/updated date"
    if any(len(v) > 1 for v in found.values()):
        return None, "ambiguous: more than one date for the same word"
    return max(next(iter(v)) for v in found.values()), "published/updated date on the page"


# ---------- independent version evidence (Wayback CDX) ----------
def cdx_url(url):
    return ("https://web.archive.org/cdx/search/cdx?" +
            urllib.parse.urlencode({"url": url, "output": "json", "fl": "timestamp", "filter": "statuscode:200"}))


def wayback(rec, url):
    """Capture dates (ISO) of the URL in the Wayback Machine, via a logged direct download of the CDX API (service
    'direct', as the MoSPI exception). None if the lookup failed."""
    def get():
        req = urllib.request.Request(cdx_url(url), headers={"User-Agent": "Mozilla/5.0 (ShadowCPI research)"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return {"rows": json.loads(r.read().decode("utf-8") or "[]")}
    try:
        resp, _ = rec.call("direct", "GET", {"url": cdx_url(url)}, get, tag="date-test wayback")
    except (OSError, ValueError):
        return None
    rows = resp.get("rows") or []
    return sorted(f"{t[0][:4]}-{t[0][4:6]}-{t[0][6:8]}" for t in rows[1:] if t and len(t[0]) >= 8)


def url_date(url):
    m = re.search(r"/(20\d{2})[/-](\d{1,2})[/-](\d{1,2})/", url)
    try:
        return date(int(m[1]), int(m[2]), int(m[3])).isoformat() if m else None
    except ValueError:
        return None


def label(cutoff, captures, tavily_date, u_date, p_date):
    """L confirmed leak | P confirmed pre-cutoff | F post-cutoff date flag | U unknown. L and P use only the Wayback
    captures (plus, for L, an independent date signal: Tavily's or the URL's date), never the page date."""
    if captures:
        if captures[0] <= cutoff:
            return "P"
        if any(d and d > cutoff for d in (tavily_date, u_date)):
            return "L"
    if any(d and d > cutoff for d in (tavily_date, u_date, p_date)):
        return "F"
    return "U"


# ---------- statistics ----------
def wilson(x, n, z=1.959964):
    if n == 0:
        return (None, None)
    p = x / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def mcnemar_exact(b, c):
    """Two-sided exact McNemar p-value on the discordant pairs b (C yes, D no) and c (C no, D yes)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def leak_fraction(labels):
    L, P = labels.count("L"), labels.count("P")
    U = len(labels) - L - P                                   # F and U are both unconfirmed
    tot = L + P + U
    return {"L": L, "P": P, "unconfirmed": U, "point": L / (L + P) if L + P else None,
            "lower": L / tot if tot else None, "upper": (L + U) / tot if tot else None}


# ---------- the run ----------
def run(tav, rec, cases=None, seed=SEED):
    """tav: a Budgeted Tavily client (cap 'date-test'). Returns the result dict (also written by main)."""
    cases = cases or json.loads(CASES.read_text(encoding="utf-8"))["cases"]
    rng = random.Random(seed + 1)
    rows, skipped = [], []
    for c in cases:
        order = ["A", "B", "C"]
        rng.shuffle(order)
        arms = {}
        for arm in order:
            try:
                resp, sid = tav.search(c["query"], **arm_params(arm, c), tag=f"date-test {c['id']} {arm}")
            except BudgetExceeded as e:
                skipped.append({"case": c["id"], "arm": arm, "why": str(e)})
                continue
            arms[arm] = {"order": order.index(arm), "call": sid, "credits": (resp.get("usage") or {}).get("credits", 0),
                         "response_time": resp.get("response_time"), **provenance(resp),
                         "results": [{"url": r["url"], "title": r.get("title") or "", "content": r.get("content") or "",
                                      "tavily_date": iso_date(r.get("published_date")) or None,
                                      "best_date": best_date(r)[0]} for r in resp.get("results", [])]}
        rows.append({**c, "arms": arms})
    # Extract each unique URL once: arm C's first (they are D's page-date check), then the rest for evaluation
    c_urls = list(dict.fromkeys(r["url"] for row in rows for r in row["arms"].get("C", {}).get("results", [])))
    other = [u for u in dict.fromkeys(r["url"] for row in rows for a in row["arms"].values() for r in a["results"])
             if u not in c_urls]
    pages, extract_calls = {}, {"D": [], "evaluation": []}
    for group, urls in (("D", c_urls), ("evaluation", other)):
        for k in range(0, len(urls), 5):
            try:
                resp, eid = tav.extract(urls[k:k + 5], extract_depth="basic", tag=f"date-test extract {group}")
            except BudgetExceeded as e:
                skipped.append({"extract": urls[k:k + 5], "why": str(e)})
                continue
            extract_calls[group].append({"call": eid, "credits": (resp.get("usage") or {}).get("credits", 0),
                                         "response_time": resp.get("response_time"), **provenance(resp)})
            pages.update({p["url"]: p.get("raw_content") or "" for p in resp.get("results", [])})
    captures = {u: wayback(rec, u) for u in c_urls + other}
    for row in rows:
        for a in row["arms"].values():
            for r in a["results"]:
                r["page_date"], r["page_date_why"] = page_date(pages.get(r["url"], ""))
                r["captures"] = captures.get(r["url"])
                r["label"] = label(row["cutoff"], r["captures"], r["tavily_date"], url_date(r["url"]), r["page_date"])
                text = f"{r['title']} {r['content']}".lower()
                r["on_topic"] = any(w in text for w in TOPIC_WORDS[row["kind"]])
        if "C" in row["arms"]:
            row["arms"]["D"] = {"from": "C", "results": [r for r in row["arms"]["C"]["results"]
                                                         if r["page_date"] and r["page_date"] <= row["cutoff"]]}
    return {"rows": rows, "skipped": skipped, "extract_calls": extract_calls, "seed": seed}


def metrics(out):
    rows, arms = out["rows"], ["A", "B", "C", "D"]
    n = len(rows)
    kept = {a: {row["id"]: row["arms"].get(a, {}).get("results", []) for row in rows} for a in arms}
    valid = {row["id"]: {r["url"] for a in arms for r in kept[a][row["id"]] if r["label"] == "P" and r["on_topic"]}
             for row in rows}
    res = {}
    for a in arms:
        leak_cases = sum(any(r["label"] == "L" for r in kept[a][i]) for i in kept[a])
        labels = [r["label"] for i in kept[a] for r in kept[a][i]]
        calls = [row["arms"][a] for row in rows if a in row["arms"] and "call" in row["arms"][a]]
        src = [row["arms"]["C"] for row in rows if "C" in row["arms"]] if a == "D" else calls
        times = [x["response_time"] for x in src if x.get("response_time") is not None]
        credits = sum(x["credits"] for x in src)
        if a == "D":
            credits += sum(x["credits"] for x in out["extract_calls"]["D"])
            times += [x["response_time"] for x in out["extract_calls"]["D"] if x.get("response_time") is not None]
        res[a] = {"leak_cases": leak_cases, "cases": n, "leak_case_wilson95": wilson(leak_cases, n),
                  "leak_fraction": leak_fraction(labels), "results": len(labels),
                  "valid_lost": sum(len(valid[i] - {r["url"] for r in kept[a][i]}) for i in valid),
                  "valid_total": sum(len(v) for v in valid.values()),
                  "undated": sum(r["tavily_date"] is None for i in kept[a] for r in kept[a][i]),
                  "credits": credits, "median_latency_s": statistics.median(times) if times else None}
    yes = {a: {i for i in kept[a] if any(r["label"] == "L" for r in kept[a][i])} for a in ("C", "D")}
    b, c = len(yes["C"] - yes["D"]), len(yes["D"] - yes["C"])
    return {"arms": res, "c_vs_d_mcnemar": {"b_C_only": b, "c_D_only": c, "p_exact": mcnemar_exact(b, c)},
            "undated_b_vs_c": {"B": res["B"]["undated"], "C": res["C"]["undated"]},
            "evaluation_extract_credits": sum(x["credits"] for x in out["extract_calls"]["evaluation"]),
            "incomplete": bool(out["skipped"])}


def secs(x):
    return "—" if x is None else f"{x:.2f} s"


def report(m, built):
    lines = ["# Date field test (pilot)", "",
             f"Run {built[:16]} UTC by `python -m v2.date_test`, pre-registered in `v2/DATE_TEST_PREREG.md`. 20 cases "
             "from the hand-built audit list (`audit/missed_events.md`), one frozen query each. A **pilot**: 20 cases "
             "cannot show small differences.", "",
             "| Arm | What it does | Cases with a confirmed leak (Wilson 95%) | Leak fraction (bounds) | Valid evidence "
             "lost | Undated results | Credits | Median latency |", "|---|---|---|---|---|---|---|---|"]
    what = {"A": "no date fields", "B": "start/end dates", "C": "dates + filter_by_published_date",
            "D": "C + our page-date check"}
    for a, r in m["arms"].items():
        lo, hi = r["leak_case_wilson95"]
        lf = r["leak_fraction"]
        f = lambda x: "—" if x is None else f"{x:.0%}"  # noqa: E731
        lines.append(f"| {a} | {what[a]} | {r['leak_cases']} of {r['cases']} ({f(lo)}–{f(hi)}) | {f(lf['point'])} "
                     f"({f(lf['lower'])}–{f(lf['upper'])}) | {r['valid_lost']} of {r['valid_total']} | {r['undated']} |"
                     f" {r['credits']} | {secs(r['median_latency_s'])} |")
    mc = m["c_vs_d_mcnemar"]
    lines += ["", f"C vs D (paired, exact McNemar): leaks only in C {mc['b_C_only']}, only in D {mc['c_D_only']}, "
              f"p = {mc['p_exact']:.3f}. Undated results: B {m['undated_b_vs_c']['B']}, C {m['undated_b_vs_c']['C']}.",
              "", "A **confirmed leak** needs independent version evidence: the Wayback Machine has no copy of the page "
              "on or before the cutoff, its first copy is after it, and Tavily's or the address's date is after the "
              "cutoff. The page date that arm D uses is never used to label a leak. Unconfirmed results set the "
              "bounds of the leak fraction."]
    if m["incomplete"]:
        lines += ["", "**Incomplete:** the credit cap stopped some calls (listed in results/date_field_test.json)."]
    return "\n".join(lines) + "\n"


def main():
    if "--sample" in sys.argv:
        cases = sample()
        CASES.write_text(json.dumps({"seed": SEED, "made_utc": datetime.now(timezone.utc).isoformat(),
                                     "cases": cases}, ensure_ascii=False, indent=1))
        print("\n".join(f"{c['id']} {c['month']} {c['query']}" for c in cases))
        return
    if OUT.exists():
        raise SystemExit(f"{OUT} exists: the date field test runs once")
    from shadow_cpi.budget import Budgeted
    from shadow_cpi.recorder import Recorder
    from shadow_cpi.tavily import Tavily
    rec = Recorder()
    out = run(Budgeted(Tavily(recorder=rec), [BUDGET]), rec)
    out["built_utc"] = datetime.now(timezone.utc).isoformat()
    out["metrics"] = metrics(out)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    OUT.with_suffix(".md").write_text(report(out["metrics"], out["built_utc"]))
    print(OUT.with_suffix(".md").read_text())


if __name__ == "__main__":
    main()
