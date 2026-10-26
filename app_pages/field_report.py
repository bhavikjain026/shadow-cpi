"""Tavily field report: what we measured about Tavily's search parameters, for Tavily's engineers. Every number is read
from results/field_report.json (built offline by tools/build_field_report.py from the committed results files)."""
import streamlit as st

from app_pages.common import header, read_json


def pct(x):
    return "—" if x is None else f"{x:.0%}"


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
st.caption(f"Built {r['built']} from the committed results files · source: `results/field_report.json`")

# ---------- time-locked search leakage (first block) ----------
lk = r.get("leakage")
if lk:
    st.subheader("Time-locked search leakage")
    st.caption("Can a search see the future? Each row replays searches as of a past cutoff with a different date "
               f"setting. All figures {lk['label']}. {lk['columns']}.")
    st.dataframe([{"Check": x["check"], "Run": x["run"], "Setting": x["setting"] or "—",
                   "N": x.get("n", "—"),
                   "Leak rate (Wilson 95%)": "—" if x.get("placeholder") else
                   f"{x['leaks']} of {x['n']} = {pct(x['leak_rate'])} ({wilson(x['wilson95'])})",
                   "Valid evidence kept": "—" if x.get("valid_kept") is None else
                   f"{x['valid_kept']} of {x['valid_total']}",
                   "Credits per call": "—" if x.get("credits_per_call") is None else f"{x['credits_per_call']:.2f}",
                   "Median latency (s)": f1(x.get("median_latency_s")),
                   "Caveats": x["caveats"]} for x in lk["rows"]], hide_index=True, width="stretch")
    st.markdown("Our own wrapper, `shadow_cpi.pit.pit_search`, always sends the date window and "
                "`filter_by_published_date`, then re-checks every result's date in code: *let the model program its "
                "filters, inside a time lock it cannot move.*")

# ---------- four arms ----------
st.subheader("Who should write the search? Four arms, pre-registered")
fa = r["four_arms"]
st.dataframe([{"Arm": x["arm"], "Searches written by": x["writer"], "Recall (of 29)": f"{x['recall']} of {x['of']}",
               "Real new credits": x["real_new_credits"], "Credits (original cost)": x["credits_original"],
               "Credits per verified event": f1(x["credits_per_verified_event"]),
               "Credits per known change found": f1(x["credits_per_known_change"]),
               "Median latency (s)": f"{x['median_latency_s']:.2f}"} for x in fa["rows"]], hide_index=True,
             width="stretch")
st.caption(f"Verdict (Amendment F, ±1 known change): top group {', '.join(fa['verdict']['top_group'])}. Latency: "
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
              f"{nd['results_undated']} undated. A historical month needs explicit dates.")
st.markdown(f"- **Dates sent** ({wd['searches']} searches): auto_parameters still reported time_range "
            + ", ".join(f"{k} {v}" for k, v in wd["time_range"].items())
            + f", yet {wd['inside_window']} of {wd['dated_results']} dated results fell inside the window: the dates "
              "seem to win, but the logged time_range says otherwise.")

# ---------- date test ----------
st.subheader("Date fields test (pilot)")
dt = r["date_test"]
st.caption(f"{dt['label']}. Retry: {dt['retry']['recovered']} of {dt['retry']['failed_urls']} failed lookups "
           "recovered.")
st.dataframe([{"Arm": a, "Leak cases, first pass": f"{p['leak_cases']} of {p['cases']} ({wilson(p['wilson95'])})",
               "Leak cases, after retry": f"{q['leak_cases']} of {q['cases']} ({wilson(q['wilson95'])})",
               "Valid lost, first pass": f"{p['valid_lost']} of {p['valid_total']}",
               "Valid lost, after retry": f"{q['valid_lost']} of {q['valid_total']}"}
              for a, p, q in ((a, dt["first_pass"]["arms"][a], dt["after_retry"]["arms"][a]) for a in "ABCD")],
             hide_index=True, width="stretch")
for k, lab in (("mcnemar_A_vs_B", "A (no dates) vs B (dates)"), ("mcnemar_C_vs_D", "C (filter) vs D (+ page date)")):
    st.caption(f"Exact McNemar, {lab}: p = {dt['first_pass'][k]['p_exact']:.4f} first pass, "
               f"{dt['after_retry'][k]['p_exact']:.4f} after retry.")
st.caption("Valid evidence lost: Wayback-confirmed pre-cutoff results found by any arm that this arm did not return; "
           "the retry adds newly confirmed pages, so its denominator is larger.")

# ---------- finance ----------
st.subheader("Second domain: finance look-ahead check")
fi = r["finance"]
st.caption(f"{fi['label']}. Replaying the day before 14 scheduled events (RBI decisions, company results): "
           "N = no dates, D = dates + filter_by_published_date.")
rows = []
for name, lab in (("first_pass", "first pass"), ("after_retry", "after Wayback retry")):
    for key in ("all_14", "without_C4"):
        m = fi[name][key]
        n, d = m["arms"]["N"], m["arms"]["D"]
        rows.append({"Run": lab, "Events": m["events"],
                     "Confirmed leaks N vs D": f"{n['confirmed_events']} vs {d['confirmed_events']}",
                     "Wilson 95% (N)": wilson(n["confirmed_wilson95"]),
                     "McNemar p": f"{m['mcnemar_confirmed']['p_exact']:.4f}",
                     "Snippet leaks N, RBI own month [loose]": f"{n['snippet_own_month_events']} "
                                                               f"[{n['snippet_loose_events']}]",
                     "Valid lost N / D": f"{n['valid_lost']} / {d['valid_lost']} of {n['valid_total']}"})
st.dataframe(rows, hide_index=True, width="stretch")

# ---------- radar and cost ----------
st.subheader("October radar: first runs")
rd = r["radar"]
st.dataframe([{"Run (UTC)": x["utc"][:16], "Real credits": x["real_credits"], "Searches": x["searches"],
               "Calls with request_id + hash": f"{x['with_provenance']} of {x['calls']}",
               "Complete": "yes" if x["complete"] else "no"} for x in rd["runs"]], hide_index=True, width="stretch")
st.caption(f"Strategy {rd['strategy']} · {rd['events']} events, {rd['corroborated']} corroborated · {rd['spent']} of "
           f"{rd['cap']} credits ({rd['cap_source']}).")
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
