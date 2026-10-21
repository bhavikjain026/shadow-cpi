#!/usr/bin/env python3
"""Shadow CPI - Day-1 checks. Run:  python checks.py

Tests everything the plan depends on and prints a PASS / FAIL / WARN report.
Copy the whole report back to Claude. API key VALUES are never printed.
Expected Tavily cost: about 15-25 credits (results are cached; re-running is free).
"""
import json
import sys
import time

from shadow_cpi.http import ApiError, request_json
from shadow_cpi.nemotron import Nemotron
from shadow_cpi.recorder import Recorder, credits_used, read_log
from shadow_cpi.settings import MODELS_FILE, ROOT, key, load_dotenv
from shadow_cpi.tavily import Tavily, results_in_window

REPORT = []
TRANSPORT = request_json  # swapped for a fake in tests
DOCA_URL = "https://fcainfoweb.nic.in/Reports/DB/DBprices_W.aspx"
MOSPI_PDF = ("https://www.mospi.gov.in/uploads/latestreleasesfiles/1791801549227-"
             "Press%20Release%20for%20the%20month%20of%20September,%202026.pdf")
MARCH = ("2026-03-01", "2026-03-31")
HINDI_NEWS = ["aajtak.in", "navbharattimes.indiatimes.com", "bhaskar.com", "amarujala.com", "jagran.com",
              "livehindustan.com", "abplive.com", "hindi.news18.com", "zeenews.india.com", "ndtv.in", "tv9hindi.com"]
INDIAN_NEWS = ["economictimes.indiatimes.com", "m.economictimes.com", "thehindu.com", "indianexpress.com",
               "hindustantimes.com", "livemint.com", "business-standard.com", "timesofindia.indiatimes.com",
               "moneycontrol.com", "financialexpress.com", "ndtv.com", "pib.gov.in"]


def report(status, name, detail=""):
    line = f"[{status}] {name}" + (f" - {detail}" if detail else "")
    REPORT.append(line)
    print(line, flush=True)


def check_keys():
    load_dotenv()
    for label, names in [("Tavily key", ("SCPI_TAVILY_API_KEY", "TAVILY_API_KEY")),
                         ("Nebius key", ("SCPI_NEBIUS_API_KEY", "NEBIUS_API_KEY"))]:
        found = key(*names, required=False)
        report("PASS" if found else "FAIL", label, "found (value hidden)" if found else f"set {names[0]} in .env")
    try:
        gi = open(ROOT / ".gitignore", encoding="utf-8").read()
        report("PASS" if ".env" in gi else "FAIL", ".env is git-ignored")
    except FileNotFoundError:
        report("FAIL", ".env is git-ignored", ".gitignore missing")


def pick(ids, *words):
    for w in words:
        for i in ids:
            if "nemotron" in i.lower() and w in i.lower():
                return i
    return None


def check_models(nem):
    try:
        ids = nem.list_models()
    except ApiError as e:
        report("FAIL", "Nebius models list", str(e))
        return {}
    nemo = [i for i in ids if "nemotron" in i.lower()]
    report("PASS" if nemo else "FAIL", "Nemotron models on Token Factory", ", ".join(nemo) or "none found")
    chosen = {"small": pick(nemo, "nano", "lightning", "super"),
              "mid": pick(nemo, "super-120b", "super", "nano"),  # text model, not the vision (VL) one
              "large": pick(nemo, "ultra", "super")}
    MODELS_FILE.parent.mkdir(parents=True, exist_ok=True)
    MODELS_FILE.write_text(json.dumps(chosen, indent=2), encoding="utf-8")
    report("PASS" if all(chosen.values()) else "WARN", "Model roles saved to config/models.json", json.dumps(chosen))
    return chosen


def check_json_mode(nem, model):
    if not model:
        report("FAIL", "Nemotron JSON output", "no model")
        return
    try:
        out, _ = nem.chat_json(model, "Return JSON only.", 'Return {"ok": true, "n": 3}.',
                               {"type": "object", "additionalProperties": False, "required": ["ok", "n"],
                                "properties": {"ok": {"type": "boolean"}, "n": {"type": "integer"}}}, tag="check")
        report("PASS" if out.get("ok") is True else "WARN", "Nemotron JSON output", json.dumps(out))
    except Exception as e:  # noqa: BLE001
        report("FAIL", "Nemotron JSON output", str(e)[:200])


def check_doca(tav):
    text, route = tav.extract_or_download(DOCA_URL, extract_depth="advanced", tag="check-doca")
    has_onion = "onion" in text.lower()
    if route == "tavily":
        status = "PASS" if has_onion else "WARN"
    elif route == "direct":  # works, but Tavily is meant to be the main route, so flag it
        status = "WARN" if has_onion else "FAIL"
    else:
        status = "FAIL"
    report(status, "Govt daily retail prices (Tavily Extract, logged direct-download fallback)",
           f"route={route or 'both failed'}, chars={len(text)}, mentions onion={has_onion}"
           + (" (may need a form/date query)" if route == "direct" else ""))


def check_pdf(tav):
    try:
        resp, _ = tav.extract([MOSPI_PDF], extract_depth="advanced", tag="check-pdf")
        text = resp["results"][0].get("raw_content", "") if resp["results"] else ""
        report("PASS" if "5.54" in text else ("WARN" if text else "FAIL"),
               "Tavily Extract on a MoSPI PDF", f"chars={len(text)}, contains 5.54={'5.54' in text}, "
               f"failed={len(resp['failed_results'])}")
    except ApiError as e:
        report("FAIL", "Tavily Extract on a MoSPI PDF", str(e)[:200])


def check_search(tav, label, query, **params):
    try:
        resp, cid = tav.search(query, topic="news", start_date=MARCH[0], end_date=MARCH[1],
                               max_results=10, tag="check-search", **params)
        res = resp.get("results", [])
        inside, outside, undated = results_in_window(res, *MARCH)
        status = "PASS" if inside and not outside else ("WARN" if res else "FAIL")
        report(status, label, f"results={len(res)}, inside March={len(inside)}, outside={len(outside)}, "
               f"undated={len(undated)}, credits={resp.get('usage', {}).get('credits')}")
        return res, cid
    except ApiError as e:
        report("FAIL", label, str(e)[:200])
        return [], None


def check_extraction(tav, nem, model, urls, parent):
    if not (urls and model):
        report("FAIL", "Nemotron price extraction (cites a numbered line; code checks the number is in it)", "no pages or model")
        return
    resp, _ = tav.extract(urls[:3], query="onion price per kg", chunks_per_source=5, parent=parent,
                          tag="check-extract")
    total = passed = 0
    for page in resp["results"]:
        text = page.get("raw_content") or ""
        try:
            quotes, _ = nem.price_quotes(model, text, "onion", tag="check-extract")
        except Exception as e:  # noqa: BLE001
            report("WARN", "Nemotron extraction on one page", str(e)[:150])
            continue
        for q in quotes:
            total += 1
            passed += bool(q.get("verified"))
    share = (passed / total) if total else 0
    report("PASS" if total and share >= 0.7 else ("WARN" if total else "FAIL"),
           "Nemotron price extraction (cites a numbered line; code checks the number is in it)",
           f"pages={len(resp['results'])}, failed={len(resp['failed_results'])}, quotes={total}, verified={passed}")


def main():
    print("Shadow CPI - Day-1 checks\n")
    check_keys()
    if any(l.startswith("[FAIL] Tavily key") or l.startswith("[FAIL] Nebius key") for l in REPORT):
        print("\nAdd the missing key(s) to .env and run again.")
        sys.exit(1)
    rec = Recorder()
    log_start = len(read_log())        # only calls made by THIS run count below (cached calls are free)
    tav, nem = Tavily(recorder=rec, transport=TRANSPORT), Nemotron(recorder=rec, transport=TRANSPORT)
    chosen = check_models(nem)
    check_json_mode(nem, chosen.get("small"))
    check_doca(tav)
    check_pdf(tav)
    en, cid = check_search(tav, "Tavily news search, March 2026 window (English)",
                           "onion retail price per kg Delhi")
    check_search(tav, "Same, strict date filter (filter_by_published_date)", "onion retail price per kg Delhi",
                 filter_by_published_date=True)
    hi, _ = check_search(tav, "Tavily news search, March 2026 window (Hindi, Indian Hindi news sites)",
                         "प्याज के दाम किलो", language="hi", include_domains=HINDI_NEWS,
                         include_domains_mode="prefer")
    check_search(tav, "Event search: milk price hike in India (English)",
                 "India milk price hike per litre effective Amul Mother Dairy", include_domains=INDIAN_NEWS,
                 include_domains_mode="prefer")
    check_search(tav, "Event search: milk price hike (Hindi)", "दूध के दाम बढ़े प्रति लीटर लागू",
                 language="hi", include_domains=HINDI_NEWS, include_domains_mode="prefer")
    urls = [r["url"] for r in (hi[:1] + en[:2])]
    check_extraction(tav, nem, chosen.get("mid"), urls, cid)
    spent = credits_used(read_log()[log_start:])
    report("PASS", "Tavily credits used by this run (from include_usage)", str(spent))
    print("\n==== COPY EVERYTHING BELOW TO CLAUDE ====")
    print("\n".join(REPORT))


if __name__ == "__main__":
    t0 = time.time()
    main()
    print(f"(took {time.time() - t0:.0f}s)")
