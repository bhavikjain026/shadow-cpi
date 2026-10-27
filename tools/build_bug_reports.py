#!/usr/bin/env python3
"""Feedback as bug reports: results/bug_reports.json and docs/tavily_bug_reports.md (0 credits, no API call).

    python tools/build_bug_reports.py

Each report: what we did, what happened (counts read from committed results files), what we expected, a suggested
fix, and the evidence file. Nothing is typed by hand except the wording.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "results" / "bug_reports.json"
DOC = ROOT / "docs" / "tavily_bug_reports.md"


def load(p):
    return json.loads((ROOT / p).read_text(encoding="utf-8"))


def date_lag():
    """Results whose Tavily published_date is later than the page's own published/updated date (date test)."""
    rows = load("results/date_field_test.json")["rows"]
    pages = {r["url"]: (r["tavily_date"], r["page_date"]) for row in rows for a in ("A", "B", "C")
             for r in row["arms"].get(a, {}).get("results", []) if r.get("tavily_date") and r.get("page_date")}
    pairs = list(pages.values())                                     # one per distinct page, not per arm
    later = [(t, p) for t, p in pairs if t > p]
    from datetime import date
    gap = [(date.fromisoformat(t) - date.fromisoformat(p)).days for t, p in later]
    return {"with_both_dates": len(pairs), "tavily_later": len(later), "over_7_days": sum(g > 7 for g in gap),
            "max_days": max(gap) if gap else 0}


def map_zero():
    off = load("results/prompt_t/official_crawl_2026-10.json")["sites"]
    dairy = load("results/prompt_t/dairy_map_2026-10-21.json")["sites"]
    noinstr = load("results/prompt_t/map_noinstr.json")
    silent_off = [s["site"] for s in off if not s["map_urls"] and not s.get("failed")]
    silent_dairy = [d["dairy"] for d in dairy if d.get("tried") and all(t.get("n_urls") == 0 and not t.get("error")
                                                                        for t in d["tried"])]
    errored = [d["dairy"] for d in dairy if any(t.get("error") for t in d.get("tried", []))]
    return {"official_sites": len(off), "official_silent_empty": silent_off, "dairy_sites": len(dairy),
            "dairy_silent_empty": silent_dairy, "dairy_clear_error": errored,
            "no_instructions_empty": [k for k, v in noinstr.items() if not v]}


def nano_nulls():
    """Pages where Nano gave no number but Super, re-reading the same page (Amendment B), found a verified one."""
    files = sorted((ROOT / "v2" / "ablation").glob("arm_*.json")) + sorted((ROOT / "v2" / "evidence").glob("events_*.json"))
    rereads = found = 0
    for f in files:
        for c in json.loads(f.read_text(encoding="utf-8"))["cards"]:
            if c.get("super_reread"):
                rereads += 1
                found += any(cl.get("status") == "verified" and "super" in (cl.get("read_by") or "").lower()
                             for cl in c.get("claims", []))
    return {"super_rereads": rereads, "super_found_verified": found, "files": len(files)}


def request_ids(pattern):
    """Tavily request IDs of the searches logged in v2/ablation/<pattern> that carry an auto_parameters echo
    (search_call -> results/call_receipts.json). Returns (searches, with a request ID, the IDs in file order)."""
    rid = {r["call_id"]: r.get("request_id") for r in load("results/call_receipts.json")["rows"]}
    plans = [p for f in sorted((ROOT / "v2" / "ablation").glob(pattern))
             for p in json.loads(f.read_text(encoding="utf-8"))["plan"] if p.get("auto_parameters")]
    ids = [rid[p["search_call"]] for p in plans if rid.get(p["search_call"])]
    return len(plans), len(ids), ids


def echo_dates(pattern):
    """Searches in v2/ablation/<pattern> whose auto_parameters echo (dates_kept) holds a start_date or end_date."""
    plans = [p for f in sorted((ROOT / "v2" / "ablation").glob(pattern))
             for p in json.loads(f.read_text(encoding="utf-8"))["plan"] if p.get("dates_kept")]
    return len(plans), sum(1 for p in plans if p["dates_kept"].get("auto_start_date") or p["dates_kept"].get("auto_end_date"))


def r196_receipt(ex):
    """The filtered finance search that returned the second review's example page: request_id and response hash."""
    for row in load("results/finance_lookahead.json")["rows"]:
        if row["id"] == ex["case"]:
            arm = row["arms"]["D"]
            if any(r["url"] == ex["url"] for r in arm["results"]):
                return arm["request_id"], arm["response_sha256"]
    raise SystemExit(f"{ex['row_id']}: not found in results/finance_lookahead.json")


def ids_text(n, with_id, ids, k=2):
    if not ids:
        return f"no Tavily request ID was logged for these {n} searches"
    return f"Tavily request IDs logged for {with_id} of {n} searches, e.g. " + ", ".join(f"`{i}`" for i in ids[:k])


REPRO = {  # Tavily report index -> script in repro/ (each: one request, your own key, at most 2 credits)
    0: "auto_parameters_time_range",
    1: "auto_parameters_echo_dates",
    2: "extract_no_asof",
    3: "published_vs_modified",
    4: "map_empty",
    5: "scanned_pdf_extract",
    6: "usage_lag",
}

SECTIONS = (("top", "Top 3"), ("feature", "Feature requests"), ("smaller", "Smaller observations"))


def build():
    fr = load("results/field_report.json")["auto_parameters"]
    usage = load("results/feedback_evidence/tavily_usage_2026-10-20.json")
    lag, mz, nn = date_lag(), map_zero(), nano_nulls()
    gokul = load("results/prompt_t/dairy_followup_2026-10-21.json")["gokul_adv_chars"]
    nd, wd = fr["no_dates"], fr["with_dates"]
    ff = load("results/timelock34_second_review.json")["finance_filtered"]
    sr = load("results/timelock34_second_review.json")
    ex = ff["example"]
    t_ids, td_ids = request_ids("arm_T_*.json"), request_ids("arm_Td_*.json")
    td_n, td_echo_dates = echo_dates("arm_Td_*.json")
    ex_rid, ex_sha = r196_receipt(ex)
    tr = lambda d: ", ".join(f"{k} {v}" for k, v in d.items())          # noqa: E731
    reports = [
        {"section": "top", "title": "auto_parameters picks a recent time_range for queries about a past month", "to": "Tavily",
         "did": f"{nd['searches']} searches with auto_parameters: true, a query naming a month in Jan–Sep 2026, and "
                "max_results only (no dates)",
         "happened": f"auto_parameters chose time_range {tr(nd['time_range'])}; {nd['results_dated_oct_2026']} of "
                     f"{nd['results']} results were dated October 2026 and {nd['results_undated']} were undated",
         "expected": "a time_range that covers the month the query names, or none, with a note that a historical query "
                     "needs start_date/end_date",
         "fix": "when the query names a past month, return no time_range (or that month's window); document the "
                "default",
         "evidence": f"{nd['results_dated_oct_2026']} of {nd['results']} results from October 2026, "
                     f"{nd['searches']} searches; {ids_text(*t_ids)}; files `v2/ablation/arm_T_*.json` "
                     "(plan[].auto_parameters, cards[].published)"},
        {"section": "top", "title": "With explicit dates, auto_parameters still reports a time_range", "to": "Tavily",
         "did": f"{wd['searches']} searches with auto_parameters: true plus our start_date/end_date (arm T+dates, "
                "exploratory)",
         "happened": f"the auto_parameters echo in the response reported time_range {tr(wd['time_range'])}, and a start_date or "
                     f"end_date in {td_echo_dates} of {td_n} echoes; yet {wd['inside_window']} of "
                     f"{wd['dated_results']} dated results fell inside our window, so the dates were applied",
         "expected": "the echo shows the window actually applied (our start_date/end_date)",
         "fix": "echo start_date/end_date, or drop time_range from the echo, when the caller sends dates",
         "evidence": f"{wd['inside_window']} of {wd['dated_results']} dated results inside the window, "
                     f"{wd['searches']} searches; {ids_text(*td_ids)}; files `v2/ablation/arm_Td_*.json` "
                     "(plan[].auto_parameters, plan[].dates_kept)"},
        {"section": "top", "title": "Extract has no as-of view, so Search dates do not freeze page content", "to": "Tavily",
         "did": f"{ff['searches']} finance-check searches with start_date/end_date and filter_by_published_date, then a "
                "separate, post-hoc AI-assisted review (ChatGPT agent) of every result page "
                f"({sr['unclear']} of {sr['rows']} rows stayed unclear)",
         "happened": f"{ff['searches_with_result_dated_after_cutoff']} of {ff['searches']} searches returned a result "
                     f"dated after the cutoff, yet {ff['reviewer_leak_pages']} page's current version leaks the "
                     f"outcome: {ex['row_id']} was dated {ex['our_published_date']} by Tavily (cutoff {ex['cutoff']}) "
                     f"and updated on {ex['reviewer_date']} with a link to the actual result",
         "expected": "a way for a time-locked user to read, or at least detect, the page as it was on the cutoff",
         "fix": "an as-of / crawl-date field on Extract (the date of the copy returned), or an as_of parameter",
         "evidence": f"{ff['reviewer_leak_pages']} of {ff['results']} filtered result pages; {ex['row_id']} from the "
                     f"search with request ID `{ex_rid}` (response SHA-256 `{ex_sha[:16]}…`); file "
                     "`results/timelock34_second_review.json` (finance_filtered.example)"},
        {"section": "feature", "title": "Separate original-publication and last-modified dates", "to": "Tavily",
         "did": f"compared, by code, Tavily's published_date with the page's own published/updated date on the "
                f"{lag['with_both_dates']} distinct date-test pages that had both",
         "happened": f"{lag['tavily_later']} had a later published_date ({lag['over_7_days']} by more than 7 days; "
                     f"largest gap {lag['max_days']} days)",
         "expected": "nothing different: this is consistent with Tavily's documented definition of published_date "
                     "(published or last updated, beta)",
         "fix": "return original-publication and last-modified dates as two fields, and let the date filter choose",
         "evidence": f"{lag['tavily_later']} of {lag['with_both_dates']} pages; file `results/date_field_test.json` "
                     "(rows[].arms[].results[].tavily_date, page_date)"},
        {"section": "smaller", "title": "Map returns empty results silently", "to": "Tavily",
         "did": f"Map on the {mz['official_sites']} sites of our official crawl list and {mz['dairy_sites']} dairy sites, "
                "with and without instructions",
         "happened": f"empty results with no failed_results and no error on {len(mz['official_silent_empty'])} sites of "
                     f"the official crawl list ({', '.join(mz['official_silent_empty'])}) and "
                     f"{len(mz['dairy_silent_empty'])} dairy sites ({', '.join(mz['dairy_silent_empty'])}); without "
                     f"instructions also empty on {', '.join(mz['no_instructions_empty'])}; a bad start URL did get a "
                     f"clear error ({', '.join(mz['dairy_clear_error']) or 'none'})",
         "expected": "an empty answer that says why (blocked, robots, nothing matched)",
         "fix": "a reason field on empty Map/Crawl responses",
         "evidence": "files `results/prompt_t/official_crawl_2026-10.json`, `dairy_map_2026-10-21.json`, "
                     "`map_noinstr.json`"},
        {"section": "smaller", "title": "One scanned PDF: Extract returned the letterhead but not the image-only rates",
         "to": "Tavily",
         "did": "Extract (basic and advanced) on one scanned dairy rate-list PDF (Gokul)",
         "happened": f"{gokul} characters of letterhead; the rates are an image and did not come back",
         "expected": "OCR of image-only PDF pages, or a flag that the text layer is empty",
         "fix": "an ocr option, or an 'image_only' flag on the result",
         "evidence": "file `results/prompt_t/dairy_followup_2026-10-21.json` (gokul_adv_chars)"},
        {"section": "smaller", "title": "/usage lags per-call usage", "to": "Tavily",
         "did": "compared GET /usage with the per-call include_usage credits the same day",
         "happened": f"/usage reported plan_usage {usage['tavily_usage_endpoint_response']['account']['plan_usage']} "
                     f"while per-call include_usage credits added up to {usage['flight_recorder_credits_include_usage']}",
         "expected": "/usage close to the sum of per-call usage", "fix": "update /usage within minutes, or document the lag",
         "evidence": "file `results/feedback_evidence/tavily_usage_2026-10-20.json`"},
    ]
    nebius = [
        {"key": "nano_nulls", "title": "Nano gives no number where Super finds one on the same page",
         "to": "Nebius / NVIDIA (Nemotron Nano)", "counts": nn,
         "did": f"Nano read each fetched page; where it gave no number, Super re-read the page ({nn['files']} saved arm "
                "and evidence files)",
         "happened": f"Super re-read {nn['super_rereads']} pages and found a verified number (the number is in the cited "
                     f"line) on {nn['super_found_verified']} of them",
         "expected": "a number whenever the cited line states one",
         "fix": "a schema-level 'required number when a currency or % is present' hint, or a confidence field",
         "evidence": "files `v2/ablation/arm_*.json`, `v2/evidence/events_*.json` (cards[].super_reread, claims[].read_by)"},
    ]
    for i, r in enumerate(reports):
        r["repro"] = f"repro/{REPRO[i]}.py"
    OUT.write_text(json.dumps({"reports": reports, "nebius": nebius}, ensure_ascii=False, indent=1))
    L = ["# Tavily feedback", "",
         "Generated by `python tools/build_bug_reports.py` from committed results files (counts are read, not typed). "
         "The top 3 lead; each has what we observed, what we expected, a suggested fix, and evidence (counts and Tavily "
         "request IDs, so the calls can be looked up).", ""]
    n = 0
    for key, head in SECTIONS:
        L += [f"## {head}", ""]
        for r in (r for r in reports if r["section"] == key):
            n += 1
            L += [f"### {n}. {r['title']}", "", f"- **What we did:** {r['did']}.",
                  f"- **Observed:** {r['happened']}.", f"- **Expected:** {r['expected']}.",
                  f"- **Suggested fix:** {r['fix']}.", f"- **Evidence:** {r['evidence']}.",
                  f"- **Reproduce it:** [`{r['repro']}`](../{r['repro']}) (your own key, at most 2 credits; see "
                  "[`repro/README.md`](../repro/README.md)).", ""]
    L += ["Nebius / NVIDIA feedback is in the Devpost write-up (`docs/devpost_draft.md`), separate from Tavily.", ""]
    DOC.write_text("\n".join(L))
    return reports


if __name__ == "__main__":
    print(f"{len(build())} reports -> {OUT.relative_to(ROOT)}, {DOC.relative_to(ROOT)}")
