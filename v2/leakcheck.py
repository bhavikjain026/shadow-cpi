#!/usr/bin/env python3
"""Leak checks P and E (v2/LEAKCHECK_PREREG.md). Exploratory and descriptive: no scored verdict changes.

    python -m v2.leakcheck --sample        # writes v2/leakcheck_cases.json (seeded; 0 credits)
    python -m v2.leakcheck P --dry         # Check P from saved text only, nothing written (0 credits)
    python -m v2.leakcheck P               # runs once (cap 'leakcheck-full-page') -> results/leakcheck_full_page.json
    python -m v2.leakcheck P --report      # after Claude Code's labels file: -> results/leakcheck_full_page.md
    python -m v2.leakcheck E               # runs once (cap 'leakcheck-exact-match') -> results/leakcheck_exact_match.*

P: every page that passed a date window in (a) date test arm C, (b) finance arm D, (c) the v2 replay's verified
evidence; find explicit dates in the full page text and flag the page if any is after its cutoff. Flagged lines are
labelled by Claude Code (later content / sidebar or related links / benign / unclear) in a separate file.
E: 40 seeded verified quotes; one verbatim span each, searched with exact_match, dated (end_date = cutoff +
filter_by_published_date) and undated.
"""
import glob
import json
import random
import re
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from shadow_cpi.budget import BudgetExceeded  # noqa: E402
from shadow_cpi.recorder import provenance, response_sha256  # noqa: E402
from v2 import rules as R  # noqa: E402
from v2.date_test import wilson  # noqa: E402

SEED = 20261026
ORDER_SEED = 20261027
N_QUOTES = 40
CASES = ROOT / "v2" / "leakcheck_cases.json"
CUSTODY = ROOT / "results" / "custody.json"
DATE_TEST = ROOT / "results" / "date_field_test.json"
FINANCE = ROOT / "results" / "finance_lookahead.json"
EVIDENCE = ROOT / "v2" / "evidence"
CACHE = ROOT / "cache" / "tavily"
OUT_P = ROOT / "results" / "leakcheck_full_page.json"
LABELS_P = ROOT / "results" / "leakcheck_full_page_labels.json"
OUT_E = ROOT / "results" / "leakcheck_exact_match.json"
BUDGET_P, BUDGET_E = "leakcheck-full-page", "leakcheck-exact-match"
SOURCES = {"a": "date test arm C", "b": "finance check arm D", "c": "v2 replay verified evidence"}
OUTCOMES_P = ["later content", "unclear", "sidebar or related links", "benign"]      # precedence, first wins
OUTCOMES_E = ["found before cutoff", "found only without dates", "not found either way"]


# ---------- Check P: population and saved text ----------
def population(date_test=None, finance=None, evidence_dir=EVIDENCE):
    """Units {source, cutoff, url, page_file?}: one per distinct URL + cutoff within a source, in file order."""
    dt = date_test or json.loads(DATE_TEST.read_text(encoding="utf-8"))
    fl = finance or json.loads(FINANCE.read_text(encoding="utf-8"))
    raw = [("a", row["cutoff"], r["url"], None) for row in dt["rows"] for r in row["arms"].get("C", {}).get("results", [])]
    raw += [("b", row["cutoff"], r["url"], None) for row in fl["rows"] for r in row["arms"].get("D", {}).get("results", [])]
    for f in sorted(glob.glob(str(Path(evidence_dir) / "events_2026-0[1-9].json"))):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        raw += [("c", d["cutoff"], c["url"], c.get("page_file")) for c in d["cards"]
                if any(cl.get("status") == "verified" for cl in c["claims"])]
    units, seen = [], set()
    for s, cut, url, pf in raw:
        if (s, cut, url) not in seen:
            seen.add((s, cut, url))
            units.append({"source": s, "cutoff": cut, "url": url, "page_file": pf})
    return units


def date_test_texts(date_test=None, cache=CACHE):
    """{url: raw_content} from the date test's own Extract responses, found in the cache by response SHA-256."""
    dt = date_test or json.loads(DATE_TEST.read_text(encoding="utf-8"))
    want = {x["response_sha256"] for g in dt["extract_calls"].values() for x in g}
    texts = {}
    for f in sorted(Path(cache).glob("*.json")):
        j = json.loads(f.read_text(encoding="utf-8"))
        if j.get("endpoint") == "/extract" and response_sha256(j["response"]) in want:
            texts.update({p["url"]: p["raw_content"] for p in j["response"].get("results", []) if p.get("raw_content")})
    return texts


def saved_text(unit, dt_texts, evidence_dir=EVIDENCE):
    if unit["source"] == "a":
        return dt_texts.get(unit["url"]) or None
    if unit["source"] == "c" and unit["page_file"]:
        p = Path(evidence_dir) / unit["page_file"]
        return p.read_text(encoding="utf-8") if p.exists() else None
    return None                                           # (b): the finance check saved snippets only


# ---------- Check P: detector (fixed in the prereg) ----------
IGNORE = re.compile(r"©|copyright|all rights reserved|\(c\)\s*(19|20)\d\d|cookie|page generated|generated on|"
                    r"generated at|last generated", re.I)
EN = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7, "august": 8,
      "september": 9, "october": 10, "november": 11, "december": 12, "jan": 1, "feb": 2, "mar": 3, "apr": 4,
      "jun": 6, "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12}
HI = {"जनवरी": 1, "फरवरी": 2, "फ़रवरी": 2, "मार्च": 3, "अप्रैल": 4, "अप्रेल": 4, "मई": 5, "जून": 6, "जुलाई": 7,
      "अगस्त": 8, "सितंबर": 9, "सितम्बर": 9, "अक्टूबर": 10, "अक्तूबर": 10, "नवंबर": 11, "नवम्बर": 11, "दिसंबर": 12,
      "दिसम्बर": 12}
_alt = lambda names: "|".join(sorted(map(re.escape, names), key=len, reverse=True))  # noqa: E731
MON = rf"(?:(?<![A-Za-z])(?:{_alt(EN)})(?![A-Za-z])|{_alt(HI)})"
DAY, YEAR, ORD = r"(\d{1,2})", r"(20\d\d)(?!\d)", r"(?:st|nd|rd|th)?"
PATTERNS = [  # (name, regex, groups -> (y, m, d)); matched spans are consumed in this order
    ("YYYY-MM-DD", rf"(?<!\d)(20\d\d)-(\d{{2}})-(\d{{2}})(?!\d)", lambda g: (g[0], g[1], g[2])),
    ("DD/MM/YYYY", rf"(?<!\d){DAY}/(\d{{1,2}})/{YEAR}", lambda g: (g[2], g[1], g[0])),
    ("DD Month YYYY", rf"(?<!\d){DAY}{ORD}\s+({MON})\.?,?\s+{YEAR}", lambda g: (g[2], g[1], g[0])),
    ("Month DD, YYYY", rf"({MON})\.?\s+{DAY}{ORD},?\s+{YEAR}", lambda g: (g[2], g[0], g[1])),
    ("Month YYYY", rf"({MON})\.?,?\s+{YEAR}", lambda g: (g[1], g[0], "1")),
]
PATTERNS = [(n, re.compile(p, re.I), f) for n, p, f in PATTERNS]
DEVANAGARI = str.maketrans("०१२३४५६७८९", "0123456789")


def _month(m):
    return int(m) if m.isdigit() else EN.get(m.lower().rstrip("."), HI.get(m))


def find_dates(line):
    """[(form, matched text, ISO date)] for the explicit dates in one line (Devanagari digits read as 0-9)."""
    work, out = line.translate(DEVANAGARI), []
    for name, rx, ymd in PATTERNS:
        for m in rx.finditer(work):
            y, mo, d = ymd(m.groups())
            try:
                iso = date(int(y), _month(mo), int(d)).isoformat()
            except (TypeError, ValueError):               # impossible date: skipped
                continue
            out.append((name, m.group(0), iso))
        work = rx.sub(lambda m: " " * len(m.group(0)), work)
    return out


def detect(text, cutoff, context=5):
    """Hits after the cutoff: [{line_no, line, form, matched, date, context}] (ignored lines skipped)."""
    lines, hits = (text or "").split("\n"), []
    for i, line in enumerate(lines):
        if IGNORE.search(line):
            continue
        for form, matched, iso in find_dates(line):
            if iso > cutoff:
                hits.append({"line_no": i, "line": line.strip()[:500], "form": form, "matched": matched, "date": iso,
                             "context": "\n".join(lines[max(0, i - context):i + context + 1])[:3000]})
    return hits


# ---------- Check P: the run ----------
def run_p(tav, units=None, dt_texts=None, refetch=True):
    """tav: a Budgeted Tavily client (cap 'leakcheck-full-page'), or None with refetch=False (saved text only)."""
    units = [dict(u) for u in (units if units is not None else population())]
    dt_texts = dt_texts if dt_texts is not None else date_test_texts()
    texts, calls, skipped = {}, [], []
    for u in units:
        t = saved_text(u, dt_texts)
        if t:
            texts[u["url"]], u["text_from"] = t, "saved"
    todo = list(dict.fromkeys(u["url"] for u in units if u["url"] not in texts))
    if refetch:
        for k in range(0, len(todo), 5):
            try:
                resp, cid = tav.extract(todo[k:k + 5], extract_depth="basic", tag="leakcheck P extract")
            except BudgetExceeded as e:
                skipped.append({"extract": todo[k:k + 5], "why": str(e)})
                continue
            calls.append({"call": cid, "urls": todo[k:k + 5], "credits": (resp.get("usage") or {}).get("credits", 0),
                          "failed": [f.get("url") for f in resp.get("failed_results", [])], **provenance(resp)})
            texts.update({p["url"]: p["raw_content"] for p in resp.get("results", []) if p.get("raw_content")})
    for u in units:
        u.setdefault("text_from", "extract" if u["url"] in texts else "no text")
        t = texts.get(u["url"])
        u["text_sha256"] = R.text_hash(t) if t else None
        u["hits"] = detect(t, u["cutoff"]) if t else []
        u["flagged"] = bool(u["hits"])
    return {"units": units, "extract_calls": calls, "skipped": skipped, "refetch": refetch,
            "credits": sum(c["credits"] for c in calls)}


def key(u):
    return f"{u['source']}|{u['cutoff']}|{u['url']}"


def unit_outcome(u, labels):
    """The unit's outcome from its line labels: the first of OUTCOMES_P that any flagged line has."""
    got = {labels[key(u)][str(h["line_no"])]["label"] for h in u["hits"]}
    return next(o for o in OUTCOMES_P if o in got)


def check_labels(out, labels):
    """Every flagged line of every flagged unit carries a valid label and a reason; returns the missing ones."""
    missing = []
    for u in out["units"]:
        for h in u["hits"]:
            lab = labels.get(key(u), {}).get(str(h["line_no"]))
            if not lab or lab.get("label") not in OUTCOMES_P or not lab.get("reason"):
                missing.append((key(u), h["line_no"]))
    return missing


def metrics_p(out, labels=None):
    res = {}
    for s in SOURCES:
        us = [u for u in out["units"] if u["source"] == s]
        has = [u for u in us if u["text_from"] != "no text"]
        flagged = [u for u in has if u["flagged"]]
        oc = Counter(unit_outcome(u, labels) for u in flagged) if labels is not None else Counter()
        n, later = len(has), oc["later content"]
        res[s] = {"units": len(us), "with_text": n, "no_text": len(us) - n, "flagged": len(flagged),
                  "flagged_wilson95": wilson(len(flagged), n), "outcomes": {o: oc[o] for o in OUTCOMES_P},
                  "later_content": later if labels is not None else None,
                  "later_content_wilson95": wilson(later, n) if labels is not None else None}
    return res


def pct(x):
    return "—" if x is None else f"{x:.0%}"


def ci(w):
    return "—" if not w or w[0] is None else f"{pct(w[0])}–{pct(w[1])}"


def report_p(out, labels):
    m = metrics_p(out, labels)
    L = ["# Leak check P: full-page date check (exploratory)", "",
         f"Run {out['built_utc'][:16]} UTC by `python -m v2.leakcheck P`, pre-registered in `v2/LEAKCHECK_PREREG.md`. "
         "Descriptive only: no scored verdict changes. Every page that passed a date window, its whole text searched "
         "for explicit dates after its cutoff. Outcomes of flagged pages were **judged by Claude Code** from the "
         "flagged line in context (`results/leakcheck_full_page_labels.json`).", "",
         "| Source | Pages | With text | Flagged (Wilson 95%) | Later content (Wilson 95%) | Sidebar or related | "
         "Benign | Unclear |", "|---|---|---|---|---|---|---|---|"]
    for s, r in m.items():
        o = r["outcomes"]
        L.append(f"| ({s}) {SOURCES[s]} | {r['units']} | {r['with_text']} | {r['flagged']} ({ci(r['flagged_wilson95'])}) "
                 f"| {r['later_content']} ({ci(r['later_content_wilson95'])}) | {o['sidebar or related links']} | "
                 f"{o['benign']} | {o['unclear']} |")
    L += ["", f"Credits: {out['credits']} (Extract of pages with no saved text). Pages with no text are left out of "
          "the rates and listed in the JSON.",
          "", "Source (c) note: the v2 replay sent start/end dates but not `filter_by_published_date`; its pages passed "
          "that window plus the code's own date checks.", "", "## Later-content pages", ""]
    for u in out["units"]:
        if u["flagged"] and unit_outcome(u, labels) == "later content":
            lab = next(labels[key(u)][str(h["line_no"])] for h in u["hits"]
                       if labels[key(u)][str(h["line_no"])]["label"] == "later content")
            L.append(f"- ({u['source']}) cutoff {u['cutoff']}: {u['url']} — {lab['reason']}")
    if out["skipped"]:
        L += ["", "**Incomplete:** the credit cap stopped some Extract calls (listed in the JSON)."]
    return "\n".join(L) + "\n"


# ---------- Check E: sample and span ----------
def pool(custody=None):
    rows = custody or json.loads(CUSTODY.read_text(encoding="utf-8"))["rows"]
    out, seen = [], set()
    for r in rows:
        if r["source"] == "radar":
            continue
        k = (r["quote"], R.cutoff(r["month"]))
        if k not in seen:
            seen.add(k)
            out.append(dict(r))
    out.sort(key=lambda r: (r["month"], r["source"], r["page_sha256"], r["quote"]))
    for i, r in enumerate(out, 1):
        r["id"], r["cutoff"] = f"Q{i:03d}", R.cutoff(r["month"])
    return out


def clean_words(q):
    q = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", q)
    return re.sub(r"[#*_`\"“”]", " ", q).split()


def plain(p):
    return str(int(p)) if float(p).is_integer() else repr(float(p)).rstrip("0").rstrip(".")


def span(quote, price):
    """(span text, anchor rule, words): the earliest window of up to 15 words containing the price (else a number)."""
    w = clean_words(quote)
    rx = re.compile(r"(?<![\d.])" + re.escape(plain(price)) + r"(?![\d]|\.\d)")
    i, how = next((i for i, t in enumerate(w) if rx.search(t.replace(",", ""))), None), "price"
    if i is None:
        i, how = next((i for i, t in enumerate(w) if re.search(r"\d", t)), None), "number"
    if i is None:
        i, how = 0, "no number"
    s = max(0, i - 14)
    return " ".join(w[s:s + 15]), how, len(w[s:s + 15])


def sample(custody=None, seed=SEED):
    picked = sorted(random.Random(seed).sample(pool(custody), N_QUOTES), key=lambda r: r["id"])
    out = []
    for r in picked:
        sp, how, n = span(r["quote"], r["price"])
        out.append({"id": r["id"], "source": r["source"], "month": r["month"], "cutoff": r["cutoff"], "url": r["url"],
                    "page_sha256": r["page_sha256"], "price": r["price"], "span": sp, "anchor": how, "words": n})
    return out


def params(arm, q):
    p = {"exact_match": True, "search_depth": "basic", "max_results": 5, "include_published_date": True}
    if arm == "dated":
        p.update(end_date=q["cutoff"], filter_by_published_date=True)
    else:
        p["filter_by_published_date"] = False
    return p


def same_page(a, b):
    n = lambda u: (urlparse(u).netloc.lower().removeprefix("www."), urlparse(u).path.rstrip("/"))  # noqa: E731
    return n(a) == n(b)


def outcome_e(q):
    s = q["searches"]
    if set(s) != {"dated", "undated"}:
        return "not run"
    if s["dated"]["results"]:
        return "found before cutoff"
    return "found only without dates" if s["undated"]["results"] else "not found either way"


# ---------- Check E: the run ----------
def run_e(tav, cases=None):
    cases = [dict(c) for c in (cases or json.loads(CASES.read_text(encoding="utf-8"))["cases"])]
    rng, skipped = random.Random(ORDER_SEED), []
    for q in cases:
        order = ["dated", "undated"]
        rng.shuffle(order)
        q["order"], q["searches"] = order, {}
        for arm in order:
            try:
                resp, sid = tav.search(f'"{q["span"]}"', **params(arm, q), tag=f"leakcheck E {q['id']} {arm}")
            except BudgetExceeded as e:
                skipped.append({"quote": q["id"], "arm": arm, "why": str(e)})
                continue
            except Exception as e:                       # an API error: the quote is "not run", never guessed
                skipped.append({"quote": q["id"], "arm": arm, "why": f"error: {e}"})
                continue
            q["searches"][arm] = {"call": sid, "credits": (resp.get("usage") or {}).get("credits", 0),
                                  "response_time": resp.get("response_time"), **provenance(resp),
                                  "results": [{"url": r["url"], "published_date": r.get("published_date"),
                                               "source_page": same_page(r["url"], q["url"])}
                                              for r in resp.get("results", [])]}
        q["outcome"] = outcome_e(q)
        if q["outcome"] == "found before cutoff":
            q["found_by"] = ("the source page" if any(r["source_page"] for r in q["searches"]["dated"]["results"])
                             else "another page only")
    return {"cases": cases, "skipped": skipped}


def metrics_e(out):
    run = [q for q in out["cases"] if q["outcome"] != "not run"]
    n, c = len(run), Counter(q["outcome"] for q in run)
    credits = sum(s["credits"] for q in out["cases"] for s in q["searches"].values())
    return {"quotes": len(out["cases"]), "run": n, "not_run": len(out["cases"]) - n,
            "shares": {o: {"x": c[o], "wilson95": wilson(c[o], n)} for o in OUTCOMES_E},
            "found_by": dict(Counter(q.get("found_by") for q in run if q.get("found_by"))),
            "undated_finds_source": sum(any(r["source_page"] for r in q["searches"]["undated"]["results"]) for q in run),
            "credits": credits, "credits_per_quote": credits / n if n else None, "incomplete": bool(out["skipped"])}


def report_e(out):
    m = metrics_e(out)
    L = ["# Leak check E: exact_match back-dating (exploratory)", "",
         f"Run {out['built_utc'][:16]} UTC by `python -m v2.leakcheck E`, pre-registered in `v2/LEAKCHECK_PREREG.md`. "
         f"Descriptive only. {m['quotes']} seeded verified quotes from the chain-of-custody list; one verbatim span "
         "each, searched with `exact_match` twice: dated (end_date = cutoff + filter_by_published_date) and undated.",
         "", "| Outcome | Quotes | Share (Wilson 95%) |", "|---|---|---|"]
    for o, s in m["shares"].items():
        L.append(f"| {o} | {s['x']} of {m['run']} | {pct(s['x'] / m['run']) if m['run'] else '—'} ({ci(s['wilson95'])}) |")
    fb, cpq = m["found_by"], m["credits_per_quote"]
    L += ["", f"Found before the cutoff by the source page {fb.get('the source page', 0)}, by another page only "
          f"{fb.get('another page only', 0)}. The undated search returned the source page for "
          f"{m['undated_finds_source']} quotes. `exact_match` can return nothing for text that is online; that is "
          "reported as is.", "",
          f"Credits: {m['credits']} ({'—' if cpq is None else f'{cpq:.1f}'} per quote). Every call's request_id and response SHA-256 are in `results/leakcheck_exact_match.json`."]
    if m["not_run"]:
        L += ["", f"**Not run:** {m['not_run']} quotes (cap or error; listed in the JSON)."]
    return "\n".join(L) + "\n"


# ---------- entry point ----------
def _client(budget):
    from shadow_cpi.budget import Budgeted
    from shadow_cpi.recorder import Recorder
    from shadow_cpi.tavily import Tavily
    return Budgeted(Tavily(recorder=Recorder()), [budget])


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    now = lambda: datetime.now(timezone.utc).isoformat()  # noqa: E731
    if "--sample" in argv:
        cases = sample()
        CASES.write_text(json.dumps({"seed": SEED, "made_utc": now(), "cases": cases}, ensure_ascii=False, indent=1))
        print("\n".join(f"{c['id']} {c['cutoff']} {c['span']}" for c in cases))
    elif "P" in argv and "--dry" in argv:
        out = run_p(None, refetch=False)
        m = metrics_p(out)
        for s, r in m.items():
            print(f"({s}) {SOURCES[s]}: {r['units']} pages, {r['with_text']} with saved text, {r['flagged']} flagged")
    elif "P" in argv and "--report" in argv:
        out, labels = (json.loads(p.read_text(encoding="utf-8")) for p in (OUT_P, LABELS_P))
        missing = check_labels(out, labels["labels"])
        if missing:
            raise SystemExit(f"{len(missing)} flagged lines have no label, e.g. {missing[:3]}")
        out["metrics"] = metrics_p(out, labels["labels"])
        OUT_P.write_text(json.dumps(out, ensure_ascii=False, indent=1))
        OUT_P.with_suffix(".md").write_text(report_p(out, labels["labels"]))
        print(OUT_P.with_suffix(".md").read_text())
    elif "P" in argv:
        if OUT_P.exists():
            raise SystemExit(f"{OUT_P} exists: check P runs once")
        out = run_p(_client(BUDGET_P))
        out["built_utc"] = now()
        OUT_P.write_text(json.dumps(out, ensure_ascii=False, indent=1))
        print(f"{sum(u['flagged'] for u in out['units'])} flagged pages; credits {out['credits']}; label them in "
              f"{LABELS_P.name}, then run with --report")
    elif "E" in argv:
        if OUT_E.exists():
            raise SystemExit(f"{OUT_E} exists: check E runs once")
        out = run_e(_client(BUDGET_E))
        out["built_utc"] = now()
        out["metrics"] = metrics_e(out)
        OUT_E.write_text(json.dumps(out, ensure_ascii=False, indent=1))
        OUT_E.with_suffix(".md").write_text(report_e(out))
        print(OUT_E.with_suffix(".md").read_text())
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
