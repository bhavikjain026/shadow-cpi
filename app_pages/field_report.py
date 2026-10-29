"""Tavily field report: what we measured about Tavily's search parameters, for Tavily's engineers. Every number is read
from results/field_report.json (built offline by tools/build_field_report.py from the committed results files)."""
import html
from datetime import date

import altair as alt
import pandas as pd
import streamlit as st

from app_pages.common import REPO_URL, altair_chart, header, lead, lock_table, plain_box, read_json, table
from app_pages.provenance import how_we_know, provenance


def pct(x):
    return "—" if x is None else f"{x:.0%}"


def pct1(x):
    return "—" if x is None else f"{x:.1%}"


def f1(x):
    return "—" if x is None else f"{x:.1f}"


def wilson(w):
    return f"{pct(w[0])}–{pct(w[1])}" if w and w[0] is not None else "—"


def day(d):
    return f"{date.fromisoformat(d).day} {date.fromisoformat(d):%b %Y}" if d else "none"


NO_DATES, TIME_LOCK = "No dates", "Time lock (Tavily date filters)"
AFTER_RETRY = "after retrying the failed Wayback archive lookups"
RUNS = {"Pre-registered initial pass": "first pass", AFTER_RETRY[0].upper() + AFTER_RETRY[1:]: "after logged retry"}  # first = default


def day_month(d):
    return f"{date.fromisoformat(d[:10]).day} {date.fromisoformat(d[:10]):%b}"


def dark_theme():
    """True when the viewer's app theme is dark (st.context.theme; light when unknown)."""
    try:
        return st.context.theme.type == "dark"
    except AttributeError:
        return False


def leak_chart(rows):
    """Leak rate, no dates vs the time lock (Tavily date filters: dates + filter_by_published_date), the date test and the finance check
    as separate groups (never summed), Wilson 95% intervals as error bars. Every value from the leakage rows of
    results/field_report.json."""
    run = st.radio("Run", list(RUNS), horizontal=True, label_visibility="collapsed",
                   help="The initial pass is the pre-registered result and the primary count; the retry, an update, "
                        "only recovered Wayback lookups that had failed on the network (logged).")
    data = [{"Check": x["check"].split(" (")[0],
             "Setting": NO_DATES if x["setting"] == "no dates" else TIME_LOCK,
             "Leak rate": x["leak_rate"], "lo": x["wilson95"][0], "hi": x["wilson95"][1],
             "Count": f"{x['leaks']} of {x['n']}", "Interval": wilson(x["wilson95"]),
             "Label": f"{pct(x['leak_rate'])} ({x['leaks']}/{x['n']})", "zero": 0 if x["leaks"] == 0 else None,
             "Tip": f"{x['check'].split(' (')[0]} · {NO_DATES if x['setting'] == 'no dates' else TIME_LOCK} · "
                    f"{x['leaks']} of {x['n']} detected leaking · 95% CI {wilson(x['wilson95'])}"}
            for x in rows if x["run"] == RUNS[run] and x["check"].startswith(("Date test", "Replication", "Finance check"))
            and (x["setting"] == "no dates" or x["setting"].endswith("filter_by_published_date"))]
    if not data:
        return
    order = [NO_DATES, TIME_LOCK]
    base = alt.Chart(pd.DataFrame(data)).encode(
        x=alt.X("Check:N", title=None, sort=None, axis=alt.Axis(labelAngle=0, labelFontSize=13, ticks=False)),
        xOffset=alt.XOffset("Setting:N", sort=order))
    y = alt.Y("Leak rate:Q", title="Leak rate (Wilson 95%)", scale=alt.Scale(domain=[0, 1]),
              axis=alt.Axis(format="%", tickCount=5))
    tip = alt.Tooltip("Tip:N")          # one plain line per bar; every layer sets it, so no raw field ever shows
    bars = base.mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3, width={"band": 0.8}).encode(
        y=y, color=alt.Color("Setting:N", sort=order, title=None, legend=alt.Legend(orient="top"),
                             scale=alt.Scale(domain=order, range=["#dc2626", "#16a34a"])), tooltip=tip)
    # whiskers: zinc 500 is 4.8:1 on white and 4.1:1 on the dark background (>= 3:1 for graphics)
    err = base.mark_rule(strokeWidth=1.5, color="#71717a").encode(y="lo:Q", y2="hi:Q", tooltip=tip)
    caps = base.mark_tick(thickness=1.5, size=10, color="#71717a").encode(y="hi:Q", tooltip=tip)
    dark = dark_theme()
    # a zero-height bar draws nothing: a short thick tick on the baseline marks it (time-lock green, as on the Leak demo)
    zero = base.transform_filter("datum.zero === 0").mark_tick(thickness=3, size=28, color="#16a34a").encode(y="zero:Q", tooltip=tip)
    # value labels above each whisker, in the page's ink colour (>= 4.5:1 in the theme the viewer has)
    labels = base.mark_text(dy=-9, fontSize=13, fontWeight=600, color="#fafafa" if dark else "#09090b").encode(
        y="hi:Q", text="Label:N", tooltip=tip)
    altair_chart((bars + err + caps + zero + labels).properties(height=280), width="stretch")
    # counts as text too, for screen readers and copying
    groups = dict.fromkeys(x["Check"] for x in data)
    st.markdown("  \n".join(f"**{g}:** " + " · ".join(
        f"{'no dates' if x['Setting'] == NO_DATES else x['Setting']} {x['Count']} ({x['Interval']})"
        for x in data if x["Check"] == g) for g in groups))
    st.caption(f"{run}; Wilson 95% intervals in brackets. Leak = a result the Wayback Machine shows appeared after "
               "the cutoff. Time lock (Tavily date filters) = start_date + end_date + filter_by_published_date. Each test is its own "
               "group; the bars are never summed. The line below pools the pilot and the replication under the same "
               "rule, as pre-registered.")
    pooled_line()


def pooled_line():
    """The pre-registered secondary: pilot + replication pooled under the date-test rule (initial passes), with the
    cache note from the replication's logged addendum. From results/field_report.json `replication`."""
    rp = r.get("replication")
    if not rp:
        return
    pl, ca = rp["pooled"], rp["cache"]
    a, c = pl["arms"]["A"], pl["arms"]["C"]
    st.markdown(f"**Pilot + replication, date-test rule** (pre-registered secondary, initial passes; "
                f"{pl['pilot_cases']} + {pl['replication_cases']} cases): Time lock (Tavily date filters) {c['leak_cases']} of "
                f"{c['cases']} ({wilson(c['wilson95'])}) · no dates {a['leak_cases']} of {a['cases']} "
                f"({wilson(a['wilson95'])}).")
    d = ca["without_pilot_reused"]
    st.caption(f"Cache note (descriptive, not pre-registered): {ca['served']} of the replication's no-dates answers "
               f"came from our cache, {ca['pilot_reused']} of them the pilot's own response to the same query; the "
               f"time-locked searches were all fresh. Without those {ca['pilot_reused']} cases: no dates "
               f"{d['arms']['A']['leak_cases']} of {d['cases']}, time lock {d['arms']['C']['leak_cases']} of "
               f"{d['cases']}. The pooled no-dates count includes the reused pilot response. Source: "
               "`results/replication.md`.")


def r196_timeline(a):
    """R196 (demo, n=1) as a numbered chain: Tavily's date, the cutoff, the page's edit, what extract_as_of returned.
    Dates and outcomes from results/asof_demo_r196.json; the company from the review example it comes from
    (results/timelock34_second_review.json, results/finance_lookahead.json); the served-copy demo for contrast."""
    from urllib.parse import urlparse
    ev, reason, cut = a["evidence"], a["as_of"]["provenance"]["reason"], day_month(a["cutoff"])
    steps = [("Tavily date", day_month(ev["tavily_date"]),
              "passes the search filter" if ev["tavily_date"] <= a["cutoff"] else "fails the search filter"),
             ("Cutoff", cut, "the question is asked as of this day"),
             ("Page edited", day_month(ev["page_date"]),
              "now links the actual result, and live Extract returns it" if a["live"].get("result_link_hits")
              else "after the cutoff"),
             ("extract_as_of", "refuses the page" if reason == "no as-of copy" else "serves an archive copy",
              f"no archive copy on/before {cut}" if ev["last_capture_on_or_before_cutoff"] is None
              else f"archive copy of {day_month(ev['last_capture_on_or_before_cutoff'])}")]
    st.subheader("Why date filters aren't enough: a page edited after the cutoff")
    st.html('<ol class="r196">' + "".join(
        f'<li class="{"cut" if k == "Cutoff" else ""}"><span class="k">{i} · {html.escape(k)}</span>'
        f'<span class="v">{html.escape(v)}</span><span class="c">{html.escape(c)}</span></li>'
        for i, (k, v, c) in enumerate(steps, 1)) + "</ol>")
    ex = (read_json("results/timelock34_second_review.json") or {}).get("finance_filtered", {}).get("example", {})
    names = {x["id"]: x["name"] for x in (read_json("results/finance_lookahead.json") or {}).get("rows", [])}
    what = f"a {names[ex['case']]} results preview" if ex.get("row_id") == a["row_id"] and ex["case"] in names else "the page"
    line = f"The page: {what} on {urlparse(a['url']).netloc.removeprefix('www.')}, row {a['row_id']} ({a['label']})."
    served = read_json("results/asof_demo_served.json")
    if served:
        line += (f" The other outcome, case {served['case']}: `extract_as_of` served the "
                 f"{day(served['as_of']['provenance']['capture_time'][:10])} archive copy instead of the live page "
                 f"([served-copy demo, `results/asof_demo_served.json`]({REPO_URL}/results/asof_demo_served.json)).")
    st.caption(line)


header("Tavily field report", "What we measured about Tavily's search parameters while building Shadow CPI, written "
                              "for Tavily's engineers. Development data (Jan–Sep 2026); exploratory parts are labelled.")
r = read_json("results/field_report.json")
if not r:
    st.info("Not built yet: run `python tools/build_field_report.py` (offline, 0 credits).")
    st.stop()

plain_box(["We tested whether a search engine can see the future when asked about a past date, and whether date limits fix it.",
           "Without date limits, some searches returned pages published after the date; with dates and a filter we detected none, but some good pages were dropped.",
           "Start with the chart, then the six findings under it; the rest is evidence for experts."])

# ---------- lead: one chart, then one case up close ----------
r196 = read_json("results/asof_demo_r196.json")
lead("**The main result.** Each bar is the share of past questions where a search returned a page from after the date asked about. Red is a normal search, green is the time lock; the thin line is the likely range, because the samples are small.")
if r.get("leakage"):
    leak_chart(r["leakage"]["rows"])
st.caption("Plain meanings: **leak** = a search result for a past date that was actually published after it; **Wayback** = the Internet Archive's Wayback Machine, which keeps dated copies of web pages and is our proof of when a page appeared; **pre-registered** = the rule was written down before we ran the test; **initial pass** = the original count under that rule; **update** = the same count after we retried archive lookups that had failed on the network; **arm** = one way of writing the searches; **Wilson interval** = the likely range for a rate measured on a small sample; **time lock** = date filters plus a check in code.")

lead("**The six findings.** One line per test: read the number at the end of each row; rows for a normal search are tinted, rows for the time lock are bold.")
# ---------- summary (six findings, each read from its file) ----------
dt1, dt2 = r["date_test"]["first_pass"]["arms"], r["date_test"]["after_retry"]["arms"]
fn1, fn2 = r["finance"]["first_pass"]["all_14"], r["finance"]["after_retry"]["all_14"]
em = read_json("results/leakcheck_exact_match.json")
top = {x["arm"]: x for x in r["four_arms"]["rows"]}[r["four_arms"]["verdict"]["ranking"][0]]
summary = [
    ("Date test, no time lock: cases with a confirmed leak (Wayback)",
     f"{dt1['A']['leak_cases']} of {dt1['A']['cases']} ({dt2['A']['leak_cases']} {AFTER_RETRY})",
     "results/field_report.json"),
    ("Date test, Time lock (Tavily date filters): dates + filter_by_published_date",
     f"{dt1['C']['leak_cases']} of {dt1['C']['cases']} ({dt2['C']['leak_cases']} {AFTER_RETRY})",
     "results/field_report.json"),
    ("Finance check, no time lock: events with a confirmed leak",
     f"{fn1['arms']['N']['confirmed_events']} of {fn1['events']} ({fn2['arms']['N']['confirmed_events']} {AFTER_RETRY})",
     "results/field_report.json"),
    ("Finance check, Time lock (Tavily date filters)",
     f"{fn1['arms']['D']['confirmed_events']} of {fn1['events']} ({fn2['arms']['D']['confirmed_events']} {AFTER_RETRY})",
     "results/field_report.json"),
    ("Cost of strictness: known-good quotes the dated search missed (check E, exploratory)",
     f"{em['metrics']['shares']['found only without dates']['x']} of {em['metrics']['quotes']}" if em else "—",
     "results/leakcheck_exact_match.json"),
    (f"Who should write the searches: best arm ({top['writer']})", f"{top['recall']} of {top['of']} known changes",
     "results/field_report.json"),
]
lock_table([{"Finding": a, "Number": b} for a, b, _ in summary],
           lambda row, col: "open" if "no time lock" in row["Finding"]
           else "lock" if "time lock" in row["Finding"] else None)
with st.expander("Sources"):
    files = [("Chart above", "results/field_report.json")] + ([("R196 timeline", "results/asof_demo_r196.json")]
                                                               if r196 else [])
    st.markdown("\n".join(f"- {a}: `{c}`" for a, _, c in summary) + "\n"
                + "\n".join(f"- {a}: `{c}`" for a, c in files))

provenance("results/field_report.json", "built")
rp, dtc = r.get("replication") or {}, r["date_test"]["first_pass"]["arms"]["A"]["cases"]
how_we_know(
    f"The date test: {dtc} pilot cases and {rp.get('cases', 0)} new cases in the pre-registered replication, a "
    f"finance look-ahead check of {r['finance']['first_pass']['all_14']['events']} events, and the four-arm search "
    "comparison. Every count on this page is read from `results/field_report.json`, built offline from the "
    "committed results files.",
    "A result is a leak only when the Wayback Machine shows the page appeared after the cutoff. The pre-registered "
    "initial pass is the primary figure; the retry, shown as an update, only recovered archive lookups that had "
    "failed on the network. Intervals are Wilson 95%. The date test and the finance check are separate groups and "
    "are never summed.",
    "The samples are small, and a zero count means the true rate is plausibly below the upper bound, not that leaks "
    "cannot happen. The Wayback Machine is the ground truth, and a page it never archived can only be flagged. "
    "Tavily's published dates are estimates. The time lock is enforced in code (`timelock/`). The R196 and E2 "
    "examples are single demonstrations, not measurements.")
if r196:
    r196_timeline(r196)


# ---------- time-locked search leakage (first block) ----------
lk = r.get("leakage")
if lk:
    st.subheader("Time-locked search leakage")
    lead("Each row replays searches as of a past date. Read across: how many returned a page from after that date, and how many good pages were kept.")
    lock_table([{"Check": x["check"], "Run": x["run"].replace("first pass", "initial pass").replace(
                    "after logged retry", AFTER_RETRY), "Setting": x["setting"] or "—",
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
                    f"setting. All figures {lk['label']}. {lk['columns']}. Bold = Time lock (Tavily date filters) "
                    "(filter_by_published_date); tinted = no dates.")
        st.markdown("Our own wrapper, `shadow_cpi.pit.pit_search`, always sends the date window and "
                    "`filter_by_published_date`, then re-checks every result's date in code: *a model may choose the "
                    "query, topic, domains and language; code owns the dates.* (Fixed templates won the four-arm test.)")


def cost_of_correctness(rows):
    """Three cards, date test only: credits per search and median latency, no dates vs the time lock (Tavily date filters: dates +
    filter_by_published_date), and the valid evidence the time lock lost on each pass. From the leakage rows of
    results/field_report.json."""
    dt = {(x["run"], x["setting"]): x for x in rows if x["check"].startswith("Date test")}
    lock = "+ filter_by_published_date"
    o1, l1, l2 = dt[("first pass", "no dates")], dt[("first pass", lock)], dt[("after logged retry", lock)]
    st.subheader("Cost of correctness")
    lead("The three cards show what the time lock costs: credits, speed, and good pages it dropped.")
    c1, c2, c3 = st.columns(3)
    c1.metric("Credits per search: no dates → time lock", f"{o1['credits_per_call']:.2f} → {l1['credits_per_call']:.2f}",
              help="Date test, initial pass. The retry re-ran archive lookups only, not searches.")
    c2.metric("Median latency: no dates → time lock", f"{o1['median_latency_s']:.1f} s → {l1['median_latency_s']:.1f} s",
              help="Date test, initial pass: Tavily's response_time. The retry sent no new searches.")
    c3.metric("Valid evidence the time lock lost", f"{l1['valid_total'] - l1['valid_kept']}/{l1['valid_total']}",
              f"{l2['valid_total'] - l2['valid_kept']}/{l2['valid_total']} {AFTER_RETRY}", delta_color="off",
              delta_arrow="off", help="Date test: pages the Wayback Machine shows existed by the cutoff that name "
                                      "the item, and that the time-locked search did not return.")
    st.caption(f"Date test, pre-registered initial pass; the evidence card also gives the count {AFTER_RETRY}, "
               "which adds newly confirmed pages, so its denominator is larger. "
               "Source: `results/field_report.json` (leakage rows).")


if lk:
    cost_of_correctness(lk["rows"])

# ---------- four arms ----------
st.subheader("Who should write the search? Four arms, pre-registered")
lead("Four ways of writing the searches (arms) compared on how many of 29 known price changes each found. More found is better; credits and speed show the price.")
fa = r["four_arms"]
arm_rows = [{"Arm": x["arm"], "Searches written by": x["writer"], "Recall (of 29)": f"{x['recall']} of {x['of']}",
             "Real new credits": x["real_new_credits"], "Credits (original cost)": x["credits_original"],
             "Credits per verified event": f1(x["credits_per_verified_event"]),
             "Credits per known change found": f1(x["credits_per_known_change"]),
             "Median latency (s)": f"{x['median_latency_s']:.2f}"} for x in fa["rows"]]
table(arm_rows, show=list(arm_rows[0]))      # every column (the one table exempt from the 5-column default); scrolls on phones
st.caption(f"Verdict (pre-registered rule change F, ±1 known change): top group {', '.join(fa['verdict']['top_group'])}. Latency: "
           f"{fa['latency_label']}. Credits per known change found was added after scoring (descriptive).")
st.caption("This compares who writes the search (query planning), on the same Tavily endpoint; it is not a result "
           "about Tavily.")

with st.expander("Details for experts: extra arms, auto_parameters, date fields and languages"):
    # ---------- exploratory ----------
    st.subheader("Exploratory arms")
    lead("Two extra ways of writing searches, tried after the main comparison. Treat them as extras, not results.")
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
    from tools.build_bug_reports import auto_note  # noqa: E402  (the qualifier the README and Devpost use)
    st.subheader("auto_parameters and dates")
    lead("Tavily can choose its own date range (auto_parameters). This checks what it did when we sent no dates and when we did.")
    ap = r["auto_parameters"]
    nd, wd = ap["no_dates"], ap["with_dates"]
    st.markdown(f"- **No dates sent** ({nd['searches']} searches): time_range "
                + ", ".join(f"{k} {v}" for k, v in nd["time_range"].items())
                + f"; {nd['results_dated_oct_2026']} of {nd['results']} results dated October 2026 ({auto_note()}), "
                  f"{nd['results_undated']} undated. Observed in our test: a historical month needs explicit dates.")
    st.markdown(f"- **Dates sent** ({wd['searches']} searches): auto_parameters still reported time_range "
                + ", ".join(f"{k} {v}" for k, v in wd["time_range"].items())
                + f", yet {wd['inside_window']} of {wd['dated_results']} dated results fell inside the window: the dates "
                  "seem to win, but the logged time_range says otherwise.")

    # ---------- date test ----------
    st.subheader("Date fields test (pilot)")
    lead("The main test: one row per way of searching, with how many past questions returned a confirmed leak.")
    dt = r["date_test"]
    st.caption(f"{dt['label'].replace('first pass', 'initial pass')}. Retry: {dt['retry']['recovered']} of {dt['retry']['failed_urls']} failed lookups "
               "recovered.")
    lock_table([{"Arm": a, "Leak cases, initial pass": f"{p['leak_cases']} of {p['cases']} ({wilson(p['wilson95'])})",
                f"Leak cases, {AFTER_RETRY}": f"{q['leak_cases']} of {q['cases']} ({wilson(q['wilson95'])})",
                "Valid evidence lost (date test), initial pass": f"{p['valid_lost']} of {p['valid_total']}",
                f"Valid evidence lost (date test), {AFTER_RETRY}": f"{q['valid_lost']} of {q['valid_total']}"}
                for a, p, q in ((a, dt["first_pass"]["arms"][a], dt["after_retry"]["arms"][a]) for a in "ABCD")],
               lambda row, col: "open" if row["Arm"] == "A" else "lock" if row["Arm"] in "CD" else None)
    for k, lab in (("mcnemar_A_vs_B", "A (no dates) vs B (dates)"), ("mcnemar_C_vs_D", "C (filter) vs D (+ page date)")):
        st.caption(f"Exact McNemar, {lab}: p = {dt['first_pass'][k]['p_exact']:.4f} initial pass, "
                   f"{dt['after_retry'][k]['p_exact']:.4f} {AFTER_RETRY}.")
    st.caption("Valid evidence lost: Wayback-confirmed pre-cutoff results found by any arm that this arm did not return; "
               "the retry adds newly confirmed pages, so its denominator is larger.")

    # ---------- language date test ----------
    ld = r.get("lang_date_test")
    if ld:
        st.subheader("Date fields by language (pilot)")
        lead("The same test in other languages, one row per language.")
        st.caption(f"{ld['label']}. A = no dates, C = dates + filter_by_published_date, D = C + our page-date check "
                   "(it reads English and Hindi date words only).")
        by = {**ld["by_lang"], "English (date test)": ld["english"]}
        table([{"Language": name, "Cases": s["A"]["cases"],
                       "Leak cases A / C / D": " / ".join(str(s[a]["leak_cases"]) for a in "ACD"),
                       "Undated A": f"{s['A']['undated']} of {s['A']['results']}",
                       "Undated C": f"{s['C']['undated']} of {s['C']['results']} ({pct(s['C']['undated_share'])})",
                       "C dated outside window": s["C"]["outside_window"],
                       "Valid evidence lost C / D (language test)": f"{s['C']['valid_lost']} / {s['D']['valid_lost']} of {s['C']['valid_total']}",
                       "C with no readable page date": f"{s['C']['no_page_date']} of {s['C']['results']}"}
                      for name, s in by.items()])
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

with st.expander("Details for experts: finance check, retries, second review and leak breakdowns"):
    # ---------- finance ----------
    st.subheader("Second domain: finance look-ahead check")
    lead("A second kind of question: the day before 14 scheduled events, did a search already show the result?")
    fi = r["finance"]
    st.caption(f"{fi['label']}. Replaying the day before 14 scheduled events (RBI decisions, company results): "
               "N = no dates, D = dates + filter_by_published_date.")
    rows = []
    for name, lab in (("first_pass", "initial pass"), ("after_retry", AFTER_RETRY)):
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
    table(rows)

    # ---------- retry reconciliation ----------
    rr = read_json("results/retry_reconciliation.json")
    if rr:
        st.subheader("Retry reconciliation: every case whose label changed")
        lead("Every case whose label changed after we retried failed archive lookups, before and after.")
        st.caption(f"{rr['changed']} of {rr['cases']} cases changed label {AFTER_RETRY} (logged), which only "
                   "repeated archive lookups that had failed on the network. The initial pass stays the pre-registered "
                   "result. File: `results/retry_reconciliation.json` (also `docs/retry_reconciliation.md`).")
        table([{"Case": x["case"], "Test": x["test"], "Item": x["item"], "Search": x["search"],
                       "Before": x["before"], "After": x["after"], "Reason": " · ".join(x["reasons"])}
                      for x in rr["rows"]], show=["Case", "Item", "Before", "After", "Reason"])

    # ---------- post-hoc second review (AI-assisted) ----------
    sr = read_json("results/timelock34_second_review.json")
    if sr:
        st.subheader("Second review (separate, post-hoc, AI-assisted: ChatGPT agent)")
        lead("A second, separate AI labelling of the same results, to see whether our leak labels hold up.")
        st.caption(f"Every result URL in the timelock34 benchmark labelled again in a separate, post-hoc AI-assisted "
                   f"review (ChatGPT agent); {sr['unclear']} of {sr['rows']} rows stayed unclear. Our leak: {sr['leak_definitions']['ours']}. The reviewer's leak: "
                   f"{sr['leak_definitions']['reviewer']}. Source: `results/timelock34_second_review.json`.")
        st.markdown(f"The reviewer decided **{sr['decided']} of {sr['rows']}** rows (LEAK or SAFE); {sr['unclear']} are "
                    "UNCLEAR, because the live page would not open and archive lookups were rate-limited.")
        ag = sr["agreement"]
        table([{"Our leak =": lab, "Rows": ag[k]["rows"], "Agreement": pct1(ag[k]["agreement"]),
                       "Cohen's kappa": "—" if ag[k]["kappa"] is None else f"{ag[k]['kappa']:.2f}"}
                      for k, lab in (("confirmed_or_date_flag", "confirmed or date_flag"), ("confirmed", "confirmed only"))])
        table([{"Set": t["dataset"].replace("_", " "), "Setting": t["setting"], "Cases": t["cases"],
                       "Cases with a leak: reviewer": t["reviewer_leak"], "Ours (confirmed)": t["ours_confirmed"],
                       "Ours (confirmed or date_flag)": t["ours_confirmed_or_date_flag"]} for t in sr["tasks"]])
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
        lead("Which kinds of websites the leaking pages came from.")
        st.caption(f"{lt['label']}. {lt['leaks']} leaks among {lt['results']} returned result rows, pooled across settings, "
                   f"exploratory (date test and finance check each by its own rule). Leak = {lt['leak_definition']}. Type from the URL only, by a rule written before counting "
                   f"({lt['rule'].replace('first match wins', 'earliest match wins')}).")

        def cell(x):
            return "—" if not x["results"] else f"{x['leaks']} of {x['results']} = {pct(x['rate'])} ({wilson(x['wilson95'])})"

        table([{"Source type": x["type"], "Leaks / results, pooled (Wilson 95%)": cell(x["pooled"]),
                       "Date test": cell(x["date test"]), "Finance check": cell(x["finance"])} for x in lt["rows"]])
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
        lead("The same leak counts taken three ways: per question, per search and per result.")
        st.caption(f"Initial pass → {AFTER_RETRY}. One search call per task and setting, so call counts "
                   "equal task counts.")
        table([{"Level": "Task (case or event), no dates",
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
                                 "across settings, exploratory"}])

with st.expander("Details for experts: radar runs, credit receipt and cost by search setting"):
    # ---------- radar and cost ----------
    st.subheader("October radar: runs so far")
    lead("Daily runs of the October price-change radar, and what each cost.")
    rd = r["radar"]
    table([{"Run (UTC)": x["utc"][:16], "Real credits": x["real_credits"], "Searches": x["searches"],
                   "Calls with request_id + hash": f"{x['with_provenance']} of {x['calls']}",
                   "Complete": "yes" if x["complete"] else "no"} for x in rd["runs"]])
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
            table([{"Page": x["url"], "Quote still present": "yes" if x["quote_present"] else "no",
                           "Number changed": x["number_changed"], "What changed (≤300 characters)": x["diff"]}
                          for x in pc["pages"]])
    mc = r["monthly_run_cost"]
    st.markdown(f"**Credits for one full monthly run:** radar run(s) {', '.join(str(x) for x in mc['radar_run_real_credits'])}"
                f" real credits; arm A {mc['arm_a_per_month_original']:.1f} per month at original cost "
                f"({mc['arm_a_searches_per_month']:.0f} searches). _{mc['note']}._")

    # ---------- credit and speed receipt ----------
    rc = r.get("receipt")
    if rc:
        st.subheader("Credit and speed receipt")
        lead("What the work cost in Tavily credits and how fast it ran.")
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
        table(receipt_rows(rc["by_endpoint"], "Endpoint"))
        st.markdown("**Credits per verified quote** (a quote counts once code has found the number in the exact line "
                    "on the page)")
        table([{"Run": x["what"], "Budgets": ", ".join(x["budgets"]), "Credits": x["credits"],
                       "Verified quotes": x["verified_quotes"], "Credits per verified quote":
                       f1(x["credits_per_verified_quote"]), "Source": x["source"]} for x in rc["per_verified_quote"]])
        with st.container():
            st.markdown("**By experiment and endpoint**")
            table(receipt_rows(rc["by_experiment"], "Experiment"))
        for n in rc["notes"]:
            st.caption(n)

    # ---------- cost vs results by search setting ----------
    cv = read_json("results/cost_vs_results.json")
    if cv:
        st.subheader("Cost vs results: search depth and max_results")
        lead("Whether deeper searches or more results found more.")
        st.caption(f"Built {cv['built']} from saved runs, {cv['credits_spent_building']} credits · {cv['note']} "
                   "Source: `results/cost_vs_results.json`.")
        table([{"search_depth": x["search_depth"], "max_results": x["max_results"], "Real calls": x["calls"],
                       "Credits": x["credits"], "Credits per call": f"{x['credits_per_call']:.2f}",
                       "Results per call": f1(x["results_per_call"]), "Filled (of max_results)": pct(x["fill_rate"]),
                       "Credits per 100 results": f1(x["credits_per_100_results"]),
                       "Results with a published_date": pct(x["dated_share"]),
                       "Median response_time (s)": "—" if x["median_seconds"] is None else f"{x['median_seconds']:.2f}",
                       "Tasks": ", ".join(x["tasks"])} for x in cv["rows"]])

# ---------- field notes ----------
br = read_json("results/bug_reports.json")
if br:
    st.subheader("Tavily field notes / repro kit")
    st.caption("Counts read from the committed results files (`results/bug_reports.json`, also `docs/tavily_bug_reports.md`). "
               "Each note is tagged against Tavily's docs: documented behaviour, doc gap or unexplained.")
    for b in br["reports"]:
        with st.expander(f"{b['title']} · {b.get('tag', 'untagged')} · to {b['to']}"):
            st.markdown(f"- **What we did:** {b['did']}.\n- **What happened:** {b['happened']}.\n"
                        f"- **What we expected:** {b['expected']}.\n- **Suggested change:** {b['fix']}.\n"
                        f"- **Evidence:** `{b['evidence']}`.")
