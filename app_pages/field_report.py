"""Tavily field report: what we measured about Tavily's search parameters, for Tavily's engineers. Every number is read
from results/field_report.json (built offline by tools/build_field_report.py from the committed results files)."""
import streamlit as st

from app_pages.common import header, lock_table, read_json


def pct(x):
    return "—" if x is None else f"{x:.0%}"


def pct1(x):
    return "—" if x is None else f"{x:.1%}"


def f1(x):
    return "—" if x is None else f"{x:.1f}"


def wilson(w):
    return f"{pct(w[0])}–{pct(w[1])}" if w and w[0] is not None else "—"


header("Tavily field report", "What we measured about Tavily's search parameters while building Shadow CPI, written "
                              "for Tavily's engineers. Development data (Jan–Sep 2026); exploratory parts are labelled.")
r = read_json("results/field_report.json")
if not r:
    st.info("Not built yet: run `python tools/build_field_report.py` (offline, 0 credits).")
    st.stop()

# ---------- summary (six findings, each read from its file) ----------
dt1, dt2 = r["date_test"]["first_pass"]["arms"], r["date_test"]["after_retry"]["arms"]
fn1, fn2 = r["finance"]["first_pass"]["all_14"], r["finance"]["after_retry"]["all_14"]
em = read_json("results/leakcheck_exact_match.json")
top = {x["arm"]: x for x in r["four_arms"]["rows"]}[r["four_arms"]["verdict"]["ranking"][0]]
summary = [
    ("Date test, no time lock: cases with a confirmed leak (Wayback)",
     f"{dt1['A']['leak_cases']} of {dt1['A']['cases']} ({dt2['A']['leak_cases']} after the logged retry)",
     "results/field_report.json"),
    ("Date test, Tavily time lock (dates + filter_by_published_date)",
     f"{dt1['C']['leak_cases']} of {dt1['C']['cases']} ({dt2['C']['leak_cases']} after the retry)",
     "results/field_report.json"),
    ("Finance check, no time lock: events with a confirmed leak",
     f"{fn1['arms']['N']['confirmed_events']} of {fn1['events']} ({fn2['arms']['N']['confirmed_events']} after the "
     "logged retry)", "results/field_report.json"),
    ("Finance check, Tavily time lock",
     f"{fn1['arms']['D']['confirmed_events']} of {fn1['events']} ({fn2['arms']['D']['confirmed_events']} after the retry)",
     "results/field_report.json"),
    ("Cost of strictness: known-good quotes the dated search missed (check E, exploratory)",
     f"{em['metrics']['shares']['found only without dates']['x']} of {em['metrics']['quotes']}" if em else "—",
     "results/leakcheck_exact_match.json"),
    (f"Who should write the searches: best arm ({top['writer']})", f"{top['recall']} of {top['of']} known changes",
     "results/field_report.json"),
]
lock_table([{"Finding": a, "Number": b, "File": c} for a, b, c in summary],
           lambda row, col: None if col == "File" else "open" if "no time lock" in row["Finding"]
           else "lock" if "time lock" in row["Finding"] else None)

# ---------- time-locked search leakage (first block) ----------
lk = r.get("leakage")
if lk:
    st.subheader("Time-locked search leakage")
    lock_table([{"Check": x["check"], "Run": x["run"].replace("first pass", "initial pass"), "Setting": x["setting"] or "—",
                "N": x.get("n", "—"),
                "Leak rate (Wilson 95%)": "—" if x.get("leaks") is None else
                f"{x['leaks']} of {x['n']} = {pct(x['leak_rate'])} ({wilson(x['wilson95'])})",
                "Kept (valid evidence; check E: known-good quotes)": "—" if x.get("valid_kept") is None else
                f"{x['valid_kept']} of {x['valid_total']}"
                + (" known-good quotes" if x["check"].startswith("Check E") else " valid evidence"),
                "Credits per call": "—" if x.get("credits_per_call") is None else f"{x['credits_per_call']:.2f}",
                "Median latency (s)": f1(x.get("median_latency_s")),
                "Caveats": x["caveats"]} for x in lk["rows"]],
               lambda row, col: None if col in ("Check", "Run", "Caveats") else
               "lock" if "filter_by_published_date" in row["Setting"] else "open" if row["Setting"] == "no dates"
               else None)
    with st.expander("Method, intervals and source files"):
        st.markdown(f"Built {r['built']} from the committed results files · source: `results/field_report.json`. "
                    "Can a search see the future? Each row replays searches as of a past cutoff with a different date "
                    f"setting. All figures {lk['label']}. {lk['columns']}. Bold = Tavily time lock "
                    "(filter_by_published_date); tinted = no dates.")
        st.markdown("Our own wrapper, `shadow_cpi.pit.pit_search`, always sends the date window and "
                    "`filter_by_published_date`, then re-checks every result's date in code: *a model may choose the "
                    "query, topic, domains and language; code owns the dates.* (Fixed templates won the four-arm test.)")

# ---------- four arms ----------
st.subheader("Who should write the search? Four arms, pre-registered")
fa = r["four_arms"]
st.dataframe([{"Arm": x["arm"], "Searches written by": x["writer"], "Recall (of 29)": f"{x['recall']} of {x['of']}",
               "Real new credits": x["real_new_credits"], "Credits (original cost)": x["credits_original"],
               "Credits per verified event": f1(x["credits_per_verified_event"]),
               "Credits per known change found": f1(x["credits_per_known_change"]),
               "Median latency (s)": f"{x['median_latency_s']:.2f}"} for x in fa["rows"]], hide_index=True,
             width="stretch")
st.caption(f"Verdict (pre-registered rule change F, ±1 known change): top group {', '.join(fa['verdict']['top_group'])}. Latency: "
           f"{fa['latency_label']}. Credits per known change found was added after scoring (descriptive).")

# ---------- exploratory ----------
st.subheader("Exploratory arms")
for key, title in (("H", "H: arm A's queries, Nemotron picks topic, domains, mode and language"),
                   ("Td", "T+dates: Tavily auto_parameters plus our date window")):
    x = r["exploratory"][key]
    with st.container(border=True):
        st.markdown(f"**{title}** · _{x['label']}_")
        lf = x["like_for_like"]
        c1, c2, c3 = st.columns(3)
        c1.metric(f"Recall, {lf['months']} complete months", f"{lf['recall']} vs A {lf['arm_a_recall']}",
                  help=f"{lf['known_changes_in_them']} of the 29 known changes fall in these months")
        c2.metric("Real credits", x["real_credits"])
        c3.metric("Credits per known change found", f1(x["credits_per_known_change_real"]))
        if x["incomplete_months"]:
            st.caption(f"Incomplete (the cap stopped them): {', '.join(x['incomplete_months'])}.")
        if "fields_valid" in x:
            fv = x["fields_valid"]
            st.caption(f"Fields valid {fv['valid']} of {fv['of']}; valid fields that differ from arm A: "
                       + ", ".join(f"{k} {v}" for k, v in fv["differs_from_a"].items()) + ".")

# ---------- auto_parameters ----------
st.subheader("auto_parameters and dates")
ap = r["auto_parameters"]
nd, wd = ap["no_dates"], ap["with_dates"]
st.markdown(f"- **No dates sent** ({nd['searches']} searches): time_range "
            + ", ".join(f"{k} {v}" for k, v in nd["time_range"].items())
            + f"; {nd['results_dated_oct_2026']} of {nd['results']} results dated October 2026, "
              f"{nd['results_undated']} undated. Observed in our test: a historical month needs explicit dates.")
st.markdown(f"- **Dates sent** ({wd['searches']} searches): auto_parameters still reported time_range "
            + ", ".join(f"{k} {v}" for k, v in wd["time_range"].items())
            + f", yet {wd['inside_window']} of {wd['dated_results']} dated results fell inside the window: the dates "
              "seem to win, but the logged time_range says otherwise.")

# ---------- date test ----------
st.subheader("Date fields test (pilot)")
dt = r["date_test"]
st.caption(f"{dt['label'].replace('first pass', 'initial pass')}. Retry: {dt['retry']['recovered']} of {dt['retry']['failed_urls']} failed lookups "
           "recovered.")
lock_table([{"Arm": a, "Leak cases, initial pass": f"{p['leak_cases']} of {p['cases']} ({wilson(p['wilson95'])})",
            "Leak cases, after retry": f"{q['leak_cases']} of {q['cases']} ({wilson(q['wilson95'])})",
            "Valid evidence lost (date test), initial pass": f"{p['valid_lost']} of {p['valid_total']}",
            "Valid evidence lost (date test), after retry": f"{q['valid_lost']} of {q['valid_total']}"}
            for a, p, q in ((a, dt["first_pass"]["arms"][a], dt["after_retry"]["arms"][a]) for a in "ABCD")],
           lambda row, col: "open" if row["Arm"] == "A" else "lock" if row["Arm"] in "CD" else None)
for k, lab in (("mcnemar_A_vs_B", "A (no dates) vs B (dates)"), ("mcnemar_C_vs_D", "C (filter) vs D (+ page date)")):
    st.caption(f"Exact McNemar, {lab}: p = {dt['first_pass'][k]['p_exact']:.4f} initial pass, "
               f"{dt['after_retry'][k]['p_exact']:.4f} after retry.")
st.caption("Valid evidence lost: Wayback-confirmed pre-cutoff results found by any arm that this arm did not return; "
           "the retry adds newly confirmed pages, so its denominator is larger.")

# ---------- language date test ----------
ld = r.get("lang_date_test")
if ld:
    st.subheader("Date fields by language (pilot)")
    st.caption(f"{ld['label']}. A = no dates, C = dates + filter_by_published_date, D = C + our page-date check "
               "(it reads English and Hindi date words only).")
    by = {**ld["by_lang"], "English (date test)": ld["english"]}
    st.dataframe([{"Language": name, "Cases": s["A"]["cases"],
                   "Leak cases A / C / D": " / ".join(str(s[a]["leak_cases"]) for a in "ACD"),
                   "Undated A": f"{s['A']['undated']} of {s['A']['results']}",
                   "Undated C": f"{s['C']['undated']} of {s['C']['results']} ({pct(s['C']['undated_share'])})",
                   "C dated outside window": s["C"]["outside_window"],
                   "Valid evidence lost C / D (language test)": f"{s['C']['valid_lost']} / {s['D']['valid_lost']} of {s['C']['valid_total']}",
                   "C with no readable page date": f"{s['C']['no_page_date']} of {s['C']['results']}"}
                  for name, s in by.items()], hide_index=True, width="stretch")
    pw = ld["paired_with_english"]
    st.caption(f"Paired with English on {len(pw['ids'])} shared cases, exact McNemar: "
               + "; ".join(f"{a} p = {pw[a]['p_exact']:.3f}" for a in "ACD") + ". "
               + ("Differs from English: " + "; ".join(ld["differs_from_english"]) + "."
                  if ld["differs_from_english"] else "No pre-registered difference from English."))
    rel = ld["relevance_post_hoc"]
    st.markdown("**Post-hoc, not pre-registered:** with the date filter on, how many results still named the item "
                "(arm A → arm C): " + "; ".join(f"{name} {v['A']['on_topic']} of {v['A']['results']} → "
                                                f"{v['C']['on_topic']} of {v['C']['results']}" for name, v in rel.items())
                + ". The dates held in every language; relevance fell further in Marathi and Tamil. A lead, 12 cases.")

# ---------- finance ----------
st.subheader("Second domain: finance look-ahead check")
fi = r["finance"]
st.caption(f"{fi['label']}. Replaying the day before 14 scheduled events (RBI decisions, company results): "
           "N = no dates, D = dates + filter_by_published_date.")
rows = []
for name, lab in (("first_pass", "initial pass"), ("after_retry", "after Wayback retry")):
    for key in ("all_14", "without_C4"):
        m = fi[name][key]
        n, d = m["arms"]["N"], m["arms"]["D"]
        rows.append({"Run": lab, "Events": m["events"],
                     "Confirmed leaks N vs D": f"{n['confirmed_events']} vs {d['confirmed_events']}",
                     "Wilson 95% (N)": wilson(n["confirmed_wilson95"]),
                     "McNemar p": f"{m['mcnemar_confirmed']['p_exact']:.4f}",
                     "Snippet leaks N, RBI own month [loose]": f"{n['snippet_own_month_events']} "
                                                               f"[{n['snippet_loose_events']}]",
                     "Valid evidence lost N / D (finance check)": f"{n['valid_lost']} / {d['valid_lost']} of {n['valid_total']}"})
st.dataframe(rows, hide_index=True, width="stretch")

# ---------- retry reconciliation ----------
rr = read_json("results/retry_reconciliation.json")
if rr:
    st.subheader("Retry reconciliation: every case whose label changed")
    st.caption(f"{rr['changed']} of {rr['cases']} cases changed label after the logged Wayback retry, which only "
               "repeated archive lookups that had failed on the network. The initial pass stays the pre-registered "
               "result. File: `results/retry_reconciliation.json` (also `docs/retry_reconciliation.md`).")
    st.dataframe([{"Case": x["case"], "Test": x["test"], "Item": x["item"], "Search": x["search"],
                   "Before": x["before"], "After": x["after"], "Reason": " · ".join(x["reasons"])}
                  for x in rr["rows"]], hide_index=True, width="stretch")

# ---------- post-hoc second review (AI-assisted) ----------
sr = read_json("results/timelock34_second_review.json")
if sr:
    st.subheader("Second review (separate, post-hoc, AI-assisted: ChatGPT agent)")
    st.caption(f"Every result URL in the timelock34 benchmark labelled again in a separate, post-hoc AI-assisted "
               f"review (ChatGPT agent); {sr['unclear']} of {sr['rows']} rows stayed unclear. Our leak: {sr['leak_definitions']['ours']}. The reviewer's leak: "
               f"{sr['leak_definitions']['reviewer']}. Source: `results/timelock34_second_review.json`.")
    st.markdown(f"The reviewer decided **{sr['decided']} of {sr['rows']}** rows (LEAK or SAFE); {sr['unclear']} are "
                "UNCLEAR, because the live page would not open and archive lookups were rate-limited.")
    ag = sr["agreement"]
    st.dataframe([{"Our leak =": lab, "Rows": ag[k]["rows"], "Agreement": pct1(ag[k]["agreement"]),
                   "Cohen's kappa": "—" if ag[k]["kappa"] is None else f"{ag[k]['kappa']:.2f}"}
                  for k, lab in (("confirmed_or_date_flag", "confirmed or date_flag"), ("confirmed", "confirmed only"))],
                 hide_index=True, width="stretch")
    st.dataframe([{"Set": t["dataset"].replace("_", " "), "Setting": t["setting"], "Cases": t["cases"],
                   "Cases with a leak: reviewer": t["reviewer_leak"], "Ours (confirmed)": t["ours_confirmed"],
                   "Ours (confirmed or date_flag)": t["ours_confirmed_or_date_flag"]} for t in sr["tasks"]],
                 hide_index=True, width="stretch")
    ff, ex = sr["finance_filtered"], sr["finance_filtered"]["example"]
    st.markdown(f"**Search filters by date; Extract reads the page as it is today.** "
                f"{ff['searches_with_result_dated_after_cutoff']} of {ff['searches']} filtered searches returned a "
                f"result dated after the cutoff; the post-hoc review found {ff['reviewer_leak_pages']} page whose "
                f"current version leaks the outcome. Example `{ex['row_id']}` ({ex['case']}, cutoff {ex['cutoff']}): "
                f"Tavily's published date {ex['our_published_date']} "
                f"({'before' if ex['our_published_date'] < ex['cutoff'] else 'not before'} the cutoff); the reviewer "
                f"relied on the {ex['reviewer_date_source']} {ex['reviewer_date']}. Reviewer: _{ex['reviewer_reason']}_ "
                f"Quote: _{ex['reviewer_quote']}_.")
    dta = read_json("results/date_field_test.json")
    pc = r.get("pages_changed")
    if dta:
        m = dta["metrics"]["arms"]
        st.markdown("**What covers the gap, partly.** "
                    f"Our page-date check reads the date printed on the extracted page: in the date test it kept "
                    f"{m['D']['results']} of the {m['C']['results']} results the filter let through (date-test valid evidence lost: "
                    f"{m['D']['valid_lost']} of {m['D']['valid_total']} with it, {m['C']['valid_lost']} with the filter "
                    "alone). It reads a page's date, not its edit history. The drift monitor re-reads October radar "
                    "pages daily: " + ("no drift run committed yet" if not pc else
                                      f"{pc['changed']} of {pc['checked']} changed") + ". Wayback Machine checks "
                    f"confirm whether a page existed by the cutoff; failed lookups were retried and logged "
                    f"({r['date_test']['retry']['recovered']} in the date test, {r['finance']['retry']['recovered']} "
                    f"in the finance check), and {sr['unclear']} of {sr['rows']} second-review rows stayed unclear, "
                    "partly from archive rate limits.")

# ---------- leaks by source type ----------
lt = r.get("leak_by_source_type")
if lt:
    st.subheader("Which pages leak? Leaks by source type")
    st.caption(f"{lt['label']}. {lt['leaks']} leaks among {lt['results']} returned result rows, pooled across settings, "
               f"exploratory (date test and finance check each by its own rule). Leak = {lt['leak_definition']}. Type from the URL only, by a rule written before counting "
               f"({lt['rule'].replace('first match wins', 'earliest match wins')}).")

    def cell(x):
        return "—" if not x["results"] else f"{x['leaks']} of {x['results']} = {pct(x['rate'])} ({wilson(x['wilson95'])})"

    st.dataframe([{"Source type": x["type"], "Leaks / results, pooled (Wilson 95%)": cell(x["pooled"]),
                   "Date test": cell(x["date test"]), "Finance check": cell(x["finance"])} for x in lt["rows"]],
                 hide_index=True, width="stretch")
    st.caption("Where the leaks came from: " + ", ".join(f"{k} {v}" for k, v in lt["leaks_by_arm"].items())
               + ". Sources: " + ", ".join(f"`{s}`" for s in lt["sources"]) + ".")

# ---------- leaks at three levels ----------
dta, fna = read_json("results/date_field_test.json"), read_json("results/finance_lookahead.json")
if dta and fna and lt:
    def calls(rows, arm, label):
        sent = [x["arms"][arm] for x in rows if arm in x["arms"]]
        return sum(any(y["label"] == label for y in c["results"]) for c in sent), len(sent)
    dt_l, dt_n = calls(dta["rows"], "A", "L")
    fn_l, fn_n = calls(fna["rows"], "N", "confirmed")
    st.subheader("Leaks at three levels")
    st.caption("Initial pass → after the logged archive retry. One search call per task and setting, so call counts "
               "equal task counts.")
    st.dataframe([{"Level": "Task (case or event), no dates",
                   "Date test": f"{dt1['A']['leak_cases']} → {dt2['A']['leak_cases']} of {dt1['A']['cases']}",
                   "Finance check": f"{fn1['arms']['N']['confirmed_events']} → {fn2['arms']['N']['confirmed_events']} "
                                    f"of {fn1['events']}",
                   "Source": "results/field_report.json"},
                  {"Level": "Task, dates + filter",
                   "Date test": f"{dt1['C']['leak_cases']} → {dt2['C']['leak_cases']} of {dt1['C']['cases']}",
                   "Finance check": f"{fn1['arms']['D']['confirmed_events']} → {fn2['arms']['D']['confirmed_events']} "
                                    f"of {fn1['events']}",
                   "Source": "results/field_report.json"},
                  {"Level": "Search call, no dates (initial pass)", "Date test": f"{dt_l} of {dt_n}",
                   "Finance check": f"{fn_l} of {fn_n}",
                   "Source": "results/date_field_test.json, results/finance_lookahead.json"},
                  {"Level": "Result (exploratory, counted after scoring, initial pass)",
                   "Date test": str(lt["leaks_by_arm"]["date test A"]), "Finance check": str(lt["leaks_by_arm"]["finance N"]),
                   "Source": f"leak_by_source_type: {lt['leaks']} of {lt['results']} returned result rows, pooled "
                             "across settings, exploratory"}],
                 hide_index=True, width="stretch")

# ---------- radar and cost ----------
st.subheader("October radar: runs so far")
rd = r["radar"]
st.dataframe([{"Run (UTC)": x["utc"][:16], "Real credits": x["real_credits"], "Searches": x["searches"],
               "Calls with request_id + hash": f"{x['with_provenance']} of {x['calls']}",
               "Complete": "yes" if x["complete"] else "no"} for x in rd["runs"]], hide_index=True, width="stretch")
st.caption(f"Strategy {rd['strategy']} · {rd['events']} events, {rd['corroborated']} corroborated · {rd['spent']} of "
           f"{rd['cap']} credits ({rd['cap_source']}).")
st.markdown("**Pages that changed**")
pc = r.get("pages_changed")
if not pc:
    st.caption("No drift run yet. Once a day until the 29 Oct freeze, every radar page with a cited line is read "
               "again with Tavily Extract and compared with the saved copy (v2/DRIFT_PREREG.md, part A).")
else:
    st.caption(f"{pc['changed']} of {pc['checked']} pages changed since the radar saved them (run of "
               f"{pc['ist_date']} IST; {pc['failed']} could not be fetched"
               + ("" if pc["complete"] else f", {pc['not_checked']} not checked: the credit cap stopped the run")
               + f"). {pc['runs']} run(s), {pc['credits_total']} credits. Page furniture (copyright, cookie lines) "
                 "and whitespace are ignored. Descriptive only: nothing in the radar changes.")
    if pc["pages"]:
        st.dataframe([{"Page": x["url"], "Quote still present": "yes" if x["quote_present"] else "no",
                       "Number changed": x["number_changed"], "What changed (≤300 characters)": x["diff"]}
                      for x in pc["pages"]], hide_index=True, width="stretch")
mc = r["monthly_run_cost"]
st.markdown(f"**Credits for one full monthly run:** radar run(s) {', '.join(str(x) for x in mc['radar_run_real_credits'])}"
            f" real credits; arm A {mc['arm_a_per_month_original']:.1f} per month at original cost "
            f"({mc['arm_a_searches_per_month']:.0f} searches). _{mc['note']}._")

# ---------- credit and speed receipt ----------
rc = r.get("receipt")
if rc:
    st.subheader("Credit and speed receipt")
    t = rc["total"]
    st.caption(f"All figures {rc['label']} · {rc['built_from']} · {t['calls']} real calls, {t['credits']} credits "
               f"(account reconcile rows {rc['reconcile_credits']:+d}, not in these rows).")

    def receipt_rows(rows, first):
        return [{**({first: x[first.lower()]} if first != "Experiment" else
                    {"Experiment": x["experiment"], "Endpoint": x["endpoint"]}),
                 "Calls": x["calls"], "Credits": x["credits"], "Credits per call": f"{x['credits_per_call']:.2f}",
                 "Median latency (s)": f"{x['median_latency_s']:.2f}" if x["median_latency_s"] is not None else "—",
                 "p95 latency (s)": f"{x['p95_latency_s']:.2f}" if x["p95_latency_s"] is not None else "—"}
                for x in rows]

    st.markdown("**By endpoint**")
    st.dataframe(receipt_rows(rc["by_endpoint"], "Endpoint"), hide_index=True, width="stretch")
    st.markdown("**Credits per verified quote** (a quote counts once code has found the number in the exact line "
                "on the page)")
    st.dataframe([{"Run": x["what"], "Budgets": ", ".join(x["budgets"]), "Credits": x["credits"],
                   "Verified quotes": x["verified_quotes"], "Credits per verified quote":
                   f1(x["credits_per_verified_quote"]), "Source": x["source"]} for x in rc["per_verified_quote"]],
                 hide_index=True, width="stretch")
    with st.expander("By experiment and endpoint"):
        st.dataframe(receipt_rows(rc["by_experiment"], "Experiment"), hide_index=True, width="stretch")
    for n in rc["notes"]:
        st.caption(n)

# ---------- cost vs results by search setting ----------
cv = read_json("results/cost_vs_results.json")
if cv:
    st.subheader("Cost vs results: search depth and max_results")
    st.caption(f"Built {cv['built']} from saved runs, {cv['credits_spent_building']} credits · {cv['note']} "
               "Source: `results/cost_vs_results.json`.")
    st.dataframe([{"search_depth": x["search_depth"], "max_results": x["max_results"], "Real calls": x["calls"],
                   "Credits": x["credits"], "Credits per call": f"{x['credits_per_call']:.2f}",
                   "Results per call": f1(x["results_per_call"]), "Filled (of max_results)": pct(x["fill_rate"]),
                   "Credits per 100 results": f1(x["credits_per_100_results"]),
                   "Results with a published_date": pct(x["dated_share"]),
                   "Median response_time (s)": "—" if x["median_seconds"] is None else f"{x['median_seconds']:.2f}",
                   "Tasks": ", ".join(x["tasks"])} for x in cv["rows"]], hide_index=True, width="stretch")

# ---------- bug reports ----------
br = read_json("results/bug_reports.json")
if br:
    st.subheader("Feedback as bug reports")
    st.caption("Counts read from the committed results files (`results/bug_reports.json`, also `docs/tavily_bug_reports.md`).")
    for b in br["reports"]:
        with st.expander(f"{b['title']} · to {b['to']}"):
            st.markdown(f"- **What we did:** {b['did']}.\n- **What happened:** {b['happened']}.\n"
                        f"- **What we expected:** {b['expected']}.\n- **Suggested fix:** {b['fix']}.\n"
                        f"- **Evidence:** `{b['evidence']}`.")
