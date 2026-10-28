"""Try it: search the past. A visitor's question and cutoff, searched with no time lock and with timelocked_search,
each result flagged from Tavily's published_date (after the cutoff yes / no / undated). Live searches use our key
under the caps in shadow_cpi/try_it.py (config/budget.json plans["try-it"]); with no key the page shows a saved
example (one Leak demo case, results/leak_demo.json, recorded by the date test)."""
from datetime import date, datetime, timedelta, timezone

import streamlit as st

from app_pages.common import header, read_json
from app_pages.provenance import provenance
from shadow_cpi import try_it as T

OPEN, OPEN_NOTE = "No time lock", "plain Tavily search, no dates"
LOCKED, LOCKED_NOTE = "Time lock (Tavily date filters)", "timelocked_search: the 30 days ending on the cutoff, published-date filter on"
SAVED_LOCKED_NOTE = "the date test's window and Tavily's published-date filter"
FLAG_TEXT = {T.YES: "after cutoff: **yes**", T.NO: "after cutoff: no", T.UNDATED: "after cutoff: undated"}
HONEST = ("These are date flags from Tavily's published_date, not Wayback-confirmed leaks: a page can carry a wrong "
          "date, and an undated page could be from any time. For the measured result, with every page checked "
          "against the Wayback Machine, see the Field Report.")


def human(d):
    if not d:
        return "none"
    d = date.fromisoformat(d[:10])
    return f"{d.day} {d:%b %Y}"


def link(title, url):
    """A Markdown link from web text: brackets, image markers and parentheses escaped so nothing else renders."""
    t = "".join("\\" + ch if ch in "[]()!*_`<>#|$~" else ch for ch in (title or url or ""))
    return f"[{t}](<{(url or '').replace('>', '%3E').replace(' ', '%20')}>)"


def quoted(text):
    """The visitor's question as plain text inside bold quotes (Markdown characters escaped)."""
    return "".join("\\" + ch if ch in "[]()!*_`<>#|$~\\" else ch for ch in text)


def column(title, note, side):
    st.markdown(f"**{title}**")
    st.caption(note)
    if not side["results"]:
        st.caption("No results.")
    for r in side["results"]:
        line = (f"{link(r['title'], r['url'])}  \nTavily published_date {human(r['published_date'])} · "
                f"{FLAG_TEXT[r['after']]}")
        (st.warning if r["after"] == T.YES else st.info if r["after"] == T.UNDATED else st.success)(line)
    meta = [f"credits {side['credits']}" if side.get("credits") is not None else None,
            f"window {human(side['window'][0])} to {human(side['window'][1])}" if side.get("window") else None,
            f"request id `{side['request_id']}`" if side.get("request_id") else None]
    st.caption(" · ".join(m for m in meta if m))


def show(res, note=""):
    st.markdown(f"**“{quoted(res['question'])}”**, cutoff {human(res['cutoff'])}")
    if note:
        st.caption(note)
    st.markdown(f"**{T.summary(res)}**")
    left, right = st.columns(2)
    with left:
        column(OPEN, OPEN_NOTE, res["open"])
    with right:
        column(LOCKED, SAVED_LOCKED_NOTE if res["source"] == "saved" else LOCKED_NOTE, res["locked"])
    st.caption(HONEST)
    st.page_link("app_pages/field_report.py", label="Field Report: the measured result", icon=":material/science:")


def saved_example():
    built = (read_json("results/date_field_test.json") or {}).get("built_utc")
    res = T.example(read_json("results/leak_demo.json"), built)
    if not res:
        st.caption("No saved example in this copy of the app.")
        return
    n = res["open"]["max_results"]
    show(res, f"Saved example, not a live run: Leak demo case {res['case']}, recorded by the date test "
              f"(results/date_field_test.json, built {human(built)}) with {n} results per search and its own "
              f"window ({human(res['locked']['window'][0])} to {human(res['locked']['window'][1])}); "
              "flagged here by the same rule as a live run.")
    provenance("results/date_field_test.json", "built_utc")


def colab(msg):
    st.info(f"{msg} You can run the same comparison with your own Tavily key in Colab.")
    st.link_button("Open the Colab notebook", T.COLAB_URL, icon=":material/open_in_new:")


header("Try it: search the past")
st.markdown("Ask a question about the past and pick a cutoff date. We run the same question twice: once as a plain "
            "search, once through the time lock. Each result shows the date Tavily gives it and whether that date "
            "is after your cutoff.")
lim = T.limits()
if not T.tavily_key():
    st.info("Live search is switched off on this copy of the app: there is no Tavily key. Below is a saved example "
            "of what a run looks like.")
    saved_example()
    st.stop()

today = datetime.now(timezone.utc).date()
with st.form("try_it"):
    q = st.text_input("Question", max_chars=T.MAX_QUESTION, placeholder="e.g. petrol diesel price hike India May 2026")
    cut = st.date_input("Cutoff date", value=today - timedelta(days=60), min_value=T.MIN_CUTOFF,
                        max_value=today - timedelta(days=1), format="YYYY-MM-DD")
    go = st.form_submit_button("Run both searches", type="primary")
st.caption(f"Each run is two basic Tavily searches ({lim['per_run']} credits) on our key. Limits: {lim['per_session']} "
           f"runs per visit, {lim['per_day']} credits a day for this page; the same question and cutoff within "
           f"{lim['cache_hours']} hours is answered from the last run for free.")
st.session_state.setdefault("try_it_runs", 0)
if go:
    try:
        res, hit = T.run(q, cut, st.session_state["try_it_runs"])
        st.session_state["try_it_result"] = (res, hit)
        if not hit:
            st.session_state["try_it_runs"] += 1
    except T.Refused as e:
        st.session_state["try_it_result"] = None
        if str(e).startswith(("Type a question", "Pick a cutoff", "The cutoff")):
            st.warning(str(e))
        else:
            colab(str(e))
    except Exception as e:                       # never raise to the page; the key is never part of the message
        st.session_state["try_it_result"] = None
        st.info(f"The search could not finish ({type(e).__name__}). Please try again later.")
out = st.session_state.get("try_it_result")
if out:
    res, hit = out
    show(res, f"Answered from the run of {human(res['utc'])}, {res['utc'][11:16]} UTC (same question and cutoff); "
              "no credits used." if hit else "")
