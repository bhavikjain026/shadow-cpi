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


def build():
    fr = load("results/field_report.json")["auto_parameters"]
    usage = load("results/feedback_evidence/tavily_usage_2026-10-20.json")
    lag, mz, nn = date_lag(), map_zero(), nano_nulls()
    gokul = load("results/prompt_t/dairy_followup_2026-10-21.json")["gokul_adv_chars"]
    nd, wd = fr["no_dates"], fr["with_dates"]
    reports = [
        {"title": "auto_parameters picks a recent time_range when no dates are sent", "to": "Tavily",
         "did": f"{nd['searches']} searches with auto_parameters: true, a query and max_results only, for months Jan–Sep 2026",
         "happened": "time_range " + ", ".join(f"{k} {v}" for k, v in nd["time_range"].items())
                     + f"; {nd['results_dated_oct_2026']} of {nd['results']} results dated October 2026, "
                       f"{nd['results_undated']} undated",
         "expected": "a documented default, or a warning that a historical query needs start_date/end_date",
         "fix": "document the behaviour; let auto_parameters return no time_range for queries naming a past month",
         "evidence": "v2/ablation/arm_T_*.json (plan[].auto_parameters, cards[].published)"},
        {"title": "auto_parameters reports a time_range that explicit dates override", "to": "Tavily",
         "did": f"{wd['searches']} searches with auto_parameters plus start_date/end_date",
         "happened": "auto_parameters echoed time_range " + ", ".join(f"{k} {v}" for k, v in wd["time_range"].items())
                     + f", yet {wd['inside_window']} of {wd['dated_results']} dated results fell inside the window",
         "expected": "the echo shows the window actually applied",
         "fix": "echo start_date/end_date (or drop time_range) when the caller sends dates",
         "evidence": "v2/ablation/arm_Td_*.json (plan[].auto_parameters, plan[].dates_kept)"},
        {"title": "published_date later than the page's own date", "to": "Tavily",
         "did": f"compared, by code (not a hand check), Tavily's published_date with the page's own published/updated date "
                f"on the {lag['with_both_dates']} distinct date-test pages that had both (sample: results/date_field_test.json)",
         "happened": f"{lag['tavily_later']} had a later published_date ({lag['over_7_days']} by more than 7 days; "
                     f"largest gap {lag['max_days']} days)",
         "expected": "published_date equal to the page's first-publication date",
         "fix": "return first-published and last-updated separately",
         "evidence": "results/date_field_test.json (rows[].arms[].results[].tavily_date, page_date)"},
        {"title": "Map returns 0 results silently", "to": "Tavily",
         "did": f"Map on the {mz['official_sites']} sites of our official crawl list and {mz['dairy_sites']} dairy sites, with and "
                "without instructions",
         "happened": f"empty results with no failed_results and no error on {len(mz['official_silent_empty'])} sites of the official "
                     "crawl list "
                     f"({', '.join(mz['official_silent_empty'])}) and {len(mz['dairy_silent_empty'])} dairy sites "
                     f"({', '.join(mz['dairy_silent_empty'])}); without instructions also empty on "
                     f"{', '.join(mz['no_instructions_empty'])}; a bad start URL did get a clear error "
                     f"({', '.join(mz['dairy_clear_error']) or 'none'})",
         "expected": "an empty answer that says why (blocked, robots, nothing matched)",
         "fix": "a reason field on empty Map/Crawl responses",
         "evidence": "results/prompt_t/official_crawl_2026-10.json, dairy_map_2026-10-21.json, map_noinstr.json"},
        {"title": "Scanned PDFs return only the letterhead", "to": "Tavily",
         "did": "Extract (basic and advanced) on Gokul's dairy rate-list PDF",
         "happened": f"{gokul} characters of letterhead; the rates are an image",
         "expected": "OCR of image-only PDF pages, or a flag that the text layer is empty",
         "fix": "an ocr option, or an 'image_only' flag on the result",
         "evidence": "results/prompt_t/dairy_followup_2026-10-21.json (gokul_adv_chars)"},
        {"title": "/usage lags per-call usage", "to": "Tavily",
         "did": "compared GET /usage with the per-call include_usage credits the same day",
         "happened": f"/usage reported plan_usage {usage['tavily_usage_endpoint_response']['account']['plan_usage']} while "
                     f"per-call include_usage credits added up to {usage['flight_recorder_credits_include_usage']}",
         "expected": "/usage close to the sum of per-call usage", "fix": "update /usage within minutes, or document the lag",
         "evidence": "results/feedback_evidence/tavily_usage_2026-10-20.json"},
        {"title": "Nano gives no number where Super finds one on the same page", "to": "Nebius / NVIDIA (Nemotron Nano)",
         "did": f"Nano read each fetched page; where it gave no number, Super re-read the page ({nn['files']} saved arm "
                "and evidence files)",
         "happened": f"Super re-read {nn['super_rereads']} pages and found a verified number (the number is in the cited "
                     f"line) on {nn['super_found_verified']} of them",
         "expected": "a number whenever the cited line states one",
         "fix": "a schema-level 'required number when a currency or % is present' hint, or a confidence field",
         "evidence": "v2/ablation/arm_*.json, v2/evidence/events_*.json (cards[].super_reread, claims[].read_by)"},
    ]
    OUT.write_text(json.dumps({"reports": reports}, ensure_ascii=False, indent=1))
    L = ["# Feedback as bug reports", "",
         "Generated by `python tools/build_bug_reports.py` from committed results files (counts are read, not typed).", ""]
    for i, r in enumerate(reports, 1):
        L += [f"## {i}. {r['title']} ({r['to']})", "", f"- **What we did:** {r['did']}.",
              f"- **What happened:** {r['happened']}.", f"- **What we expected:** {r['expected']}.",
              f"- **Suggested fix:** {r['fix']}.", f"- **Evidence:** `{r['evidence']}`.", ""]
    DOC.write_text("\n".join(L))
    return reports


if __name__ == "__main__":
    print(f"{len(build())} reports -> {OUT.relative_to(ROOT)}, {DOC.relative_to(ROOT)}")
