#!/usr/bin/env python3
"""Language date test (v2/LANG_DATE_PREREG.md): do Tavily's date fields behave the same in Hindi and regional
languages as in the English date test (v2/DATE_TEST_PREREG.md)? A pilot.

    python -m v2.lang_date_test --sample   # writes v2/lang_date_test_cases.json (seeded; 0 credits)
    python -m v2.lang_date_test            # runs once (cap 'lang-date-test', 80) -> results/lang_date_test.json + .md

Three arms per case, run close together in a seeded random order, everything else identical (language set on all):
A no date fields; C start_date/end_date (month start to cutoff) + filter_by_published_date; D C's results + our
page-date check. The page-date reader, the labels and the statistics are the English test's, unchanged
(v2.date_test). Leak labels come from Wayback captures only, never from the page date D uses.
"""
import json
import random
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from shadow_cpi.budget import BudgetExceeded  # noqa: E402
from shadow_cpi.recorder import provenance  # noqa: E402
from shadow_cpi.tavily import best_date, iso_date  # noqa: E402
from v2 import date_test as DT  # noqa: E402
from v2 import kinds as K  # noqa: E402
from v2 import rules as R  # noqa: E402

SEED = 20261027
CASES = ROOT / "v2" / "lang_date_test_cases.json"
OUT = ROOT / "results" / "lang_date_test.json"
ENGLISH = ROOT / "results" / "date_field_test.json"
BUDGET = "lang-date-test"
PER_LANG = 4
LANGS = ["hi", "mr", "ta", "kn", "bn", "te"]                 # the card's languages; used "as available"
LANG_NAMES = {"en": "English", "hi": "Hindi", "mr": "Marathi", "ta": "Tamil", "kn": "Kannada", "bn": "Bengali",
              "te": "Telugu"}
# Coverage language, decided by the change's state before any search (no credits spent to check coverage).
# National changes ([] states) -> Hindi. A state outside this map (Kerala, Odisha, Punjab, J&K) is not eligible.
STATE_LANG = {"madhya pradesh": "hi", "uttar pradesh": "hi", "bihar": "hi", "jharkhand": "hi", "chhattisgarh": "hi",
              "nct of delhi": "hi", "rajasthan": "hi", "haryana": "hi", "uttarakhand": "hi", "himachal pradesh": "hi",
              "maharashtra": "mr", "tamil nadu": "ta", "karnataka": "kn", "west bengal": "bn", "telangana": "te",
              "andhra pradesh": "te"}
# Query words: taken from v2/kinds.py QUERIES and config/items.yaml where those have them (see the pre-registration)
WORDS = {
    "hi": {"milk": "दूध के दाम बढ़े", "electricity": "बिजली की दरें बढ़ीं", "lpg": "एलपीजी सिलेंडर के दाम बढ़े",
           "fuel": "पेट्रोल डीजल के दाम बढ़े", "bus": "बस किराया बढ़ा", "rail": "रेल किराया बढ़ा"},
    "mr": {"milk": "दूध दरवाढ", "electricity": "वीज दरवाढ", "bus": "एसटी बस भाडेवाढ"},
    "ta": {"milk": "பால் விலை உயர்வு", "electricity": "மின் கட்டண உயர்வு", "bus": "பேருந்து கட்டண உயர்வு",
           "rail": "ரயில் கட்டண உயர்வு"},
}
PLACES = {
    "hi": {"": "भारत", "madhya pradesh": "मध्य प्रदेश", "bihar": "बिहार", "jharkhand": "झारखंड",
           "uttar pradesh": "उत्तर प्रदेश", "nct of delhi": "दिल्ली", "chhattisgarh": "छत्तीसगढ़"},
    "mr": {"maharashtra": "महाराष्ट्र"},
    "ta": {"tamil nadu": "தமிழ்நாடு"},
}
MONTHS = {
    "hi": ["जनवरी", "फरवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"],
    "mr": ["जानेवारी", "फेब्रुवारी", "मार्च", "एप्रिल", "मे", "जून", "जुलै", "ऑगस्ट", "सप्टेंबर", "ऑक्टोबर", "नोव्हेंबर",
           "डिसेंबर"],
    "ta": ["ஜனவரி", "பிப்ரவரி", "மார்ச்", "ஏப்ரல்", "மே", "ஜூன்", "ஜூலை", "ஆகஸ்ட்", "செப்டம்பர்", "அக்டோபர்",
           "நவம்பர்", "டிசம்பர்"],
}
# on-topic words for "valid evidence": the English test's words plus v2/kinds.py's words in every script
KIND_WORDS = {"fuel": ["petrol", "diesel"]}
TOPIC_WORDS = {k: DT.TOPIC_WORDS[k] + [w for kk in KIND_WORDS.get(k, [k]) for w in K.KINDS[kk]["words"]]
               for k in DT.TOPIC_WORDS}
ARMS = ["A", "C", "D"]
WAYBACK_TRIES, WAYBACK_WAIT = 3, 5                           # the tools/wayback_retry.py rule, applied in the run


def lang_of(states):
    langs = {STATE_LANG.get(s) for s in states} if states else {"hi"}
    return langs.pop() if len(langs) == 1 and None not in langs else None


# ---------- sampling (pre-registered) ----------
def frame(reference=None):
    """{language: eligible reference changes}, every language of the card listed, empty where none is available."""
    ref = reference or json.loads(DT.REFERENCE.read_text(encoding="utf-8"))["changes"]
    out = {l: [] for l in LANGS}
    for r in sorted(ref, key=lambda r: r["id"]):
        l = lang_of(r["states"])
        if l and r["kind"] in WORDS.get(l, {}):
            out[l].append(r)
    return out


def sample(reference=None, seed=SEED):
    rng = random.Random(seed)
    picked = []
    for l, pool in frame(reference).items():
        pool = list(pool)
        rng.shuffle(pool)
        picked += [case(r, l) for r in pool[:PER_LANG]]
    return sorted(picked, key=lambda c: (LANGS.index(c["lang"]), c["month"], c["id"]))


def case(r, lang):
    place = " ".join(PLACES[lang][s] for s in r["states"]) if r["states"] else PLACES[lang][""]
    y, m = r["month"].split("-")
    return {"id": r["id"], "lang": lang, "kind": r["kind"], "month": r["month"], "states": r["states"],
            "cutoff": R.cutoff(r["month"]), "query": f"{WORDS[lang][r['kind']]} {place} {MONTHS[lang][int(m) - 1]} {y}"}


def arm_params(arm, c):
    p = {**DT.BASE, "include_domains": K.DOMAINS[c["lang"]], "language": c["lang"]}
    if arm == "A":
        p["filter_by_published_date"] = False
    else:
        p.update(start_date=f"{c['month']}-01", end_date=c["cutoff"], filter_by_published_date=True)
    return p


def wayback(rec, url, tries=WAYBACK_TRIES, wait=WAYBACK_WAIT, sleep=time.sleep):
    for k in range(tries):
        caps = DT.wayback(rec, url, tag="lang-date-test wayback")
        if caps is not None or k == tries - 1:
            return caps
        sleep(wait)


# ---------- the run ----------
def run(tav, rec, cases=None, seed=SEED, sleep=time.sleep):
    """tav: a Budgeted Tavily client (cap 'lang-date-test'). Returns the result dict (also written by main)."""
    cases = cases or json.loads(CASES.read_text(encoding="utf-8"))["cases"]
    rng = random.Random(seed + 1)
    rows, skipped = [], []
    for c in cases:
        order = ["A", "C"]
        rng.shuffle(order)
        arms = {}
        for arm in order:
            try:
                resp, sid = tav.search(c["query"], **arm_params(arm, c), tag=f"lang-date-test {c['id']} {arm}")
            except BudgetExceeded as e:
                skipped.append({"case": c["id"], "arm": arm, "why": str(e)})
                continue
            arms[arm] = {"order": order.index(arm), "call": sid, "credits": (resp.get("usage") or {}).get("credits", 0),
                         "response_time": resp.get("response_time"), **provenance(resp),
                         "results": [{"url": r["url"], "title": r.get("title") or "", "content": r.get("content") or "",
                                      "tavily_date": iso_date(r.get("published_date")) or None,
                                      "best_date": best_date(r)[0]} for r in resp.get("results", [])]}
        rows.append({**c, "arms": arms})
    c_urls = list(dict.fromkeys(r["url"] for row in rows for r in row["arms"].get("C", {}).get("results", [])))
    other = [u for u in dict.fromkeys(r["url"] for row in rows for a in row["arms"].values() for r in a["results"])
             if u not in c_urls]
    pages, extract_calls = {}, {"D": [], "evaluation": []}
    for group, urls in (("D", c_urls), ("evaluation", other)):
        for k in range(0, len(urls), 5):
            try:
                resp, eid = tav.extract(urls[k:k + 5], extract_depth="basic", tag=f"lang-date-test extract {group}")
            except BudgetExceeded as e:
                skipped.append({"extract": urls[k:k + 5], "why": str(e)})
                continue
            extract_calls[group].append({"call": eid, "credits": (resp.get("usage") or {}).get("credits", 0),
                                         "response_time": resp.get("response_time"), **provenance(resp)})
            pages.update({p["url"]: p.get("raw_content") or "" for p in resp.get("results", [])})
    captures = {u: wayback(rec, u, sleep=sleep) for u in c_urls + other}
    for row in rows:
        for a in row["arms"].values():
            for r in a["results"]:
                r["page_date"], r["page_date_why"] = DT.page_date(pages.get(r["url"], ""))
                r["captures"] = captures.get(r["url"])
                r["label"] = DT.label(row["cutoff"], r["captures"], r["tavily_date"], DT.url_date(r["url"]),
                                      r["page_date"])
                text = f"{r['title']} {r['content']}".lower()
                r["on_topic"] = any(w.lower() in text for w in TOPIC_WORDS[row["kind"]])
                r["outside_window"] = bool(r["tavily_date"]) and not (f"{row['month']}-01" <= r["tavily_date"]
                                                                     <= row["cutoff"])
        if "C" in row["arms"]:
            row["arms"]["D"] = {"from": "C", "results": [r for r in row["arms"]["C"]["results"]
                                                         if r["page_date"] and r["page_date"] <= row["cutoff"]]}
    return {"rows": rows, "skipped": skipped, "extract_calls": extract_calls, "seed": seed,
            "wayback_failed": sorted(u for u, v in captures.items() if v is None)}


def arm_stats(rows, a, extract_calls=None):
    """Pre-registered metrics for one arm over the given rows (one language, or all)."""
    n = len(rows)
    kept = {row["id"]: row["arms"].get(a, {}).get("results", []) for row in rows}
    valid = {row["id"]: {r["url"] for x in ARMS for r in row["arms"].get(x, {}).get("results", [])
                         if r["label"] == "P" and r["on_topic"]} for row in rows}
    labels = [r["label"] for i in kept for r in kept[i]]
    res = [r for i in kept for r in kept[i]]
    leak_cases = sum(any(r["label"] == "L" for r in kept[i]) for i in kept)
    out = {"cases": n, "leak_cases": leak_cases, "leak_case_wilson95": DT.wilson(leak_cases, n),
           "leak_fraction": DT.leak_fraction(labels), "results": len(res),
           "undated": sum(r["tavily_date"] is None for r in res),
           "undated_share": sum(r["tavily_date"] is None for r in res) / len(res) if res else None,
           "outside_window": sum(r["outside_window"] for r in res),
           "valid_lost": sum(len(valid[i] - {r["url"] for r in kept[i]}) for i in valid),
           "valid_total": sum(len(v) for v in valid.values()),
           "no_page_date": sum(r["page_date"] is None for r in res)}
    if extract_calls is not None:
        src = [row["arms"]["C" if a == "D" else a] for row in rows if ("C" if a == "D" else a) in row["arms"]]
        times = [x["response_time"] for x in src if x.get("response_time") is not None]
        credits = sum(x["credits"] for x in src)
        if a == "D":
            credits += sum(x["credits"] for x in extract_calls["D"])
            times += [x["response_time"] for x in extract_calls["D"] if x.get("response_time") is not None]
        out.update(credits=credits, median_latency_s=statistics.median(times) if times else None)
    return out


def english_stats(eng=None):
    """The English date test's first pass (its primary numbers), same metrics, arms A, C, D."""
    eng = eng or json.loads(ENGLISH.read_text(encoding="utf-8"))
    for row in eng["rows"]:
        for a in row["arms"].values():
            for r in a["results"]:
                r["outside_window"] = bool(r["tavily_date"]) and not (f"{row['month']}-01" <= r["tavily_date"]
                                                                     <= row["cutoff"])
    return {a: arm_stats(eng["rows"], a) for a in ARMS}, eng


def paired_with_english(out, eng):
    """Cases in both tests (same reference id): confirmed-leak case per arm in English vs this test, exact McNemar."""
    e_rows = {row["id"]: row for row in eng["rows"]}
    both = [row for row in out["rows"] if row["id"] in e_rows]
    leak = lambda row, a: any(r["label"] == "L" for r in row["arms"].get(a, {}).get("results", []))  # noqa: E731
    res = {"ids": [row["id"] for row in both]}
    for a in ARMS:
        b = sum(leak(e_rows[row["id"]], a) and not leak(row, a) for row in both)
        c = sum(leak(row, a) and not leak(e_rows[row["id"]], a) for row in both)
        res[a] = {"english_only": b, "language_only": c, "p_exact": DT.mcnemar_exact(b, c)}
    return res


def differs(by_lang, english):
    """Pre-registered trigger for a FEEDBACK note: in any language, arm C (a) keeps a Tavily-dated result outside the
    supplied window, or (b) has an undated share at least 20 points above English C's, or (c) has a confirmed-leak
    case. Returns the reasons (empty = the date fields behaved as in English)."""
    why = []
    e_und = english["C"]["undated_share"] or 0
    for l, s in by_lang.items():
        c = s["C"]
        if c["outside_window"]:
            why.append(f"{LANG_NAMES[l]}: C kept {c['outside_window']} Tavily-dated results outside the window")
        if c["undated_share"] is not None and c["undated_share"] - e_und >= 0.20:
            why.append(f"{LANG_NAMES[l]}: C undated share {c['undated_share']:.0%} vs English {e_und:.0%}")
        if c["leak_cases"]:
            why.append(f"{LANG_NAMES[l]}: C has {c['leak_cases']} confirmed-leak cases (English C: "
                       f"{english['C']['leak_cases']})")
    return why


def metrics(out, eng=None):
    english, eng = english_stats(eng)
    langs = list(dict.fromkeys(row["lang"] for row in out["rows"]))
    by_lang = {l: {a: arm_stats([r for r in out["rows"] if r["lang"] == l], a) for a in ARMS} for l in langs}
    yes = {a: {row["id"] for row in out["rows"] if any(r["label"] == "L" for r in row["arms"].get(a, {})
                                                         .get("results", []))} for a in ("C", "D")}
    b, c = len(yes["C"] - yes["D"]), len(yes["D"] - yes["C"])
    return {"arms": {a: arm_stats(out["rows"], a, out["extract_calls"]) for a in ARMS}, "by_lang": by_lang,
            "english": english, "paired_with_english": paired_with_english(out, eng),
            "c_vs_d_mcnemar": {"b_C_only": b, "c_D_only": c, "p_exact": DT.mcnemar_exact(b, c)},
            "evaluation_extract_credits": sum(x["credits"] for x in out["extract_calls"]["evaluation"]),
            "differs_from_english": differs(by_lang, english), "wayback_failed": len(out["wayback_failed"]),
            "incomplete": bool(out["skipped"])}


def pct(x):
    return "—" if x is None else f"{x:.0%}"


def report(m, built):
    what = {"A": "no date fields", "C": "dates + filter_by_published_date", "D": "C + our page-date check"}
    n = m["arms"]["A"]["cases"]
    langs = ", ".join(f"{LANG_NAMES[l]} {m['by_lang'][l]['A']['cases']}" for l in m["by_lang"])
    L = ["# Language date test (pilot)", "",
         f"Run {built[:16]} UTC by `python -m v2.lang_date_test`, pre-registered in `v2/LANG_DATE_PREREG.md`. {n} cases "
         f"from the hand-built audit list ({langs}), one frozen query each in its language, with Tavily's `language` "
         f"field set. A **pilot**: {n} cases cannot show small differences. Compared with the English date test "
         "(`results/date_field_test.md`, first pass).", "",
         "| Arm | What it does | Cases with a confirmed leak (Wilson 95%) | Leak fraction (bounds) | Valid evidence lost "
         "| Undated share | Dated outside the window | Credits | Median latency |", "|---|---|---|---|---|---|---|---|---|"]
    for a, r in m["arms"].items():
        lo, hi = r["leak_case_wilson95"]
        lf = r["leak_fraction"]
        L.append(f"| {a} | {what[a]} | {r['leak_cases']} of {r['cases']} ({pct(lo)}–{pct(hi)}) | {pct(lf['point'])} "
                 f"({pct(lf['lower'])}–{pct(lf['upper'])}) | {r['valid_lost']} of {r['valid_total']} | "
                 f"{r['undated']} of {r['results']} ({pct(r['undated_share'])}) | {r['outside_window']} | {r['credits']} "
                 f"| {DT.secs(r['median_latency_s'])} |")
    L += ["", "## By language, next to English", "",
          "| Language | Cases | A: leak cases | C: leak cases | D: leak cases | A undated | C undated | C dated outside "
          "window | C valid lost | D results with no readable page date |", "|---|---|---|---|---|---|---|---|---|---|"]
    rows = [(LANG_NAMES[l], s) for l, s in m["by_lang"].items()] + [("English (date test)", m["english"])]
    for name, s in rows:
        L.append(f"| {name} | {s['A']['cases']} | {s['A']['leak_cases']} | {s['C']['leak_cases']} | "
                 f"{s['D']['leak_cases']} | {s['A']['undated']} of {s['A']['results']} | {s['C']['undated']} of "
                 f"{s['C']['results']} ({pct(s['C']['undated_share'])}) | {s['C']['outside_window']} | "
                 f"{s['C']['valid_lost']} of {s['C']['valid_total']} | {s['C']['no_page_date']} of {s['C']['results']} |")
    pw = m["paired_with_english"]
    mc = m["c_vs_d_mcnemar"]
    L += ["", f"Paired with English on the {len(pw['ids'])} cases in both tests ({', '.join(pw['ids']) or 'none'}), "
          "exact McNemar on confirmed-leak cases: " + "; ".join(
              f"{a} English only {pw[a]['english_only']}, language only {pw[a]['language_only']}, p = {pw[a]['p_exact']:.3f}"
              for a in ARMS) + ".",
          f"C vs D (paired, exact McNemar): leaks only in C {mc['b_C_only']}, only in D {mc['c_D_only']}, "
          f"p = {mc['p_exact']:.3f}.", "",
          "**Date fields by language:** " + ("; ".join(m["differs_from_english"]) + "." if m["differs_from_english"]
                                             else "no pre-registered difference from English (arm C kept nothing dated "
                                                  "outside the window, its undated share was within 20 points of "
                                                  "English, and it had no confirmed leak)."), "",
          "A **confirmed leak** needs the Wayback Machine: no copy of the page on or before the cutoff, its first copy "
          "after it, and Tavily's or the address's date after the cutoff. D's page date never labels a leak. D's "
          "page-date reader is the English test's, unchanged: it reads English and Hindi date words only, so "
          "\"no readable page date\" in Marathi and Tamil measures our reader as much as the page."]
    if m["wayback_failed"]:
        L += ["", f"{m['wayback_failed']} Wayback lookups still failed after {WAYBACK_TRIES} tries: those results are "
                  "unconfirmed (they widen the bounds)."]
    if m["incomplete"]:
        L += ["", "**Incomplete:** the credit cap stopped some calls (listed in results/lang_date_test.json)."]
    return "\n".join(L) + "\n"


def main():
    if "--report" in sys.argv:                     # offline: rewrite the .md from the saved results (0 credits)
        out = json.loads(OUT.read_text(encoding="utf-8"))
        OUT.with_suffix(".md").write_text(report(out["metrics"], out["built_utc"]))
        return
    if "--sample" in sys.argv:
        cases = sample()
        CASES.write_text(json.dumps({"seed": SEED, "made_utc": datetime.now(timezone.utc).isoformat(),
                                     "frame": {l: [r["id"] for r in v] for l, v in frame().items()},
                                     "cases": cases}, ensure_ascii=False, indent=1) + "\n")
        print("\n".join(f"{c['id']} {c['lang']} {c['month']} {c['query']}" for c in cases))
        return
    if OUT.exists():
        raise SystemExit(f"{OUT} exists: the language date test runs once")
    from shadow_cpi.budget import Budgeted, usage_check
    from shadow_cpi.recorder import Recorder
    from shadow_cpi.tavily import Tavily
    rec = Recorder()
    tav = Budgeted(Tavily(recorder=rec), [BUDGET])
    out = run(tav, rec)
    out["built_utc"] = datetime.now(timezone.utc).isoformat()
    out["metrics"] = metrics(out)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    OUT.with_suffix(".md").write_text(report(out["metrics"], out["built_utc"]))
    print(OUT.with_suffix(".md").read_text())
    print(usage_check(tav.tav)[1])


if __name__ == "__main__":
    main()
