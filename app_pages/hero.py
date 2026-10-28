"""The three hero cards (no dates / dates + time lock / cost of correctness), shared by Search the past (the landing
page, below the action) and Leak results. Every value is read from a results file."""
import streamlit as st

from app_pages.common import read_json, wilson95


def pct(x):
    return f"{x:.0%}"


DATE_TEST = "results/date_field_test.json"
DATE_LOCKED_ARM = "C"                         # tools/build_leak_demo.py TESTS["date"]["locked"]
FIELD_REPORT = "results/field_report.json"
REPLICATION = "results/replication.json"


def date_test_cost():
    """The date test's own cost of the time lock, initial pass: valid evidence the locked arm dropped (not check E)."""
    arm = read_json(DATE_TEST)["metrics"]["arms"][DATE_LOCKED_ARM]
    return int(arm["valid_lost"]), int(arm["valid_total"])


def stat_cards(t):
    """The opening screen's three bordered cards, every value read from a results file: (a) no dates, pilot and
    replication shown separately, the pooled count in the caption as the pre-registered secondary; (b) dates + time
    lock, pilot and replication pooled, with its Wilson 95% interval computed here; (c) the cost of correctness, the
    date test's own valid evidence dropped (initial pass; never check E). The pre-registered initial pass leads."""
    d = t["date"]
    o, n = int(d["open"]["first"]), int(d["cases"])
    rep = read_json(REPLICATION)
    rc = rep["metrics"]["price"]["arms"]["A"]
    pool = rep["pooled"]["price"]["arms"]
    lost, valid = date_test_cost()
    pk, pn = int(pool["C"]["leak_cases"]), int(pool["C"]["cases"])
    lo, hi = wilson95(pk, pn)
    a, b, c = st.columns(3)
    with a:
        st.metric(":red[No dates]: cases that leaked", f"{o}/{n} · {rc['leak_cases']}/{rc['cases']}",
                  delta=f"Pilot · replication. Pooled {pool['A']['leak_cases']} of {pool['A']['cases']} "
                        "(pre-registered secondary).",
                  delta_color="off", delta_arrow="off", border=True,
                  help="Cases where the plain search, with no date limits, returned a page the Wayback Machine shows "
                       "appeared after the cutoff. Pre-registered initial pass: the pilot, then the replication of new "
                       "cases. The pooled count adds them under the same rule; it counts one cached pilot answer "
                       "twice (see How we know).")
    with b:
        st.metric(":green[Dates + time lock]: cases that leaked", f"{pk} of {pn}",
                  delta=f"Wilson 95% interval {pct(lo)}–{pct(hi)}. Pilot and replication pooled.",
                  delta_color="off", delta_arrow="off", border=True,
                  help="Cases where the search with start_date, end_date and filter_by_published_date still returned a "
                       "confirmed leak. Date test only; the finance check is never added to it. A zero count means "
                       "the true rate is plausibly below the upper bound, not that leaks are impossible.")
    with c:
        st.metric("Cost of correctness", f"{lost} of {valid}",
                  delta="Valid evidence the date filter dropped (initial pass).",
                  delta_color="off", delta_arrow="off", border=True,
                  help="Of the valid results the plain search found in the date test, how many the dated search did "
                       "not return. This is the date test's own pre-registered initial pass, separate from the "
                       "exploratory exact-match check.")
