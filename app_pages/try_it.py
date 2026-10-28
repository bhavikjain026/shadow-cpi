"""Search the past (the opening screen): one question and a cutoff, searched with no time lock and with
timelocked_search, side by side. The answer sits at the top; evidence and method expand underneath; the hero numbers
follow. A saved example is preselected (results/leak_demo.json, recorded by the date test and the finance check,
judged by its Wayback labels). Live searches use our key under the caps in shadow_cpi/try_it.py (config/budget.json
plans["try-it"]), flagged from Tavily's published_date (after the cutoff yes / no / undated)."""
from datetime import date, datetime, timedelta, timezone

import streamlit as st

from app_pages.common import SUBHEAD, TITLE_CLAIM, brand_row, read_json
from app_pages.hero import stat_cards
from app_pages.provenance import provenance
from shadow_cpi import try_it as T

OPEN, OPEN_NOTE = "No time lock", "plain Tavily search, no dates"
LOCKED, LOCKED_NOTE = "Time lock", "timelocked_search: the 30 days ending on the cutoff, published-date filter on"
SAVED_LOCKED_NOTE = "start_date/end_date + filter_by_published_date"
FLAG_TEXT = {T.YES: "after cutoff: **yes**", T.NO: "after cutoff: no", T.UNDATED: "after cutoff: undated"}
HONEST = ("These are date flags from Tavily's published_date, not Wayback-confirmed leaks: a page can carry a wrong "
          "date, and an undated page could be from any time. For the measured result, with every page checked "
          "against the Wayback Machine, see the Field Report.")
SAVED_RULE = ("Saved examples are judged by the Wayback Machine: LEAK = the archive shows the page appeared after the "
              "cutoff; OK = the archive shows it existed by the cutoff; UNCHECKED = no archive record either way, so "
              "it is not counted as evidence.")
OWN = "Your own question (live)"


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


def badge(r):
    """Saved rows: a text badge from the Wayback label, so colour is never the only signal."""
    if r["leak"]:
        return ":red-badge[LEAK]"
    if (r.get("wayback") or "").startswith(T.CONFIRMED_PRE):
        return ":green-badge[OK]"
    return ":gray-badge[UNCHECKED]"


def column(title, note, side, saved):
    st.markdown(f"**{title}**")
    st.caption(note)
    if not side["results"]:
        st.caption("No results.")
    for r in side["results"]:
        if saved:
            st.markdown(f"{badge(r)} {link(r['title'], r['url'])}  \n:small[Tavily date {human(r['published_date'])} · "
                        f"Wayback: {r['wayback']}]")
        else:
            line = (f"{link(r['title'], r['url'])}  \nTavily published_date {human(r['published_date'])} · "
                    f"{FLAG_TEXT[r['after']]}")
            (st.warning if r["after"] == T.YES else st.info if r["after"] == T.UNDATED else st.success)(line)


def answer(res, note=""):
    """The verdict first, then the two columns, then evidence and method behind expanders."""
    saved = res["source"] == "saved"
    head, thin = T.verdict(res)
    with st.container(border=True, key="verdict"):
        st.markdown(f"**“{quoted(res['question'])}”**, cutoff {human(res['cutoff'])}")
        st.markdown(f"#### {head}")
        if thin:
            st.warning(thin, icon=":material/block:")
        if note:
            st.caption(note)
    left, right = st.columns(2)
    with left:
        column(OPEN, OPEN_NOTE, res["open"], saved)
    with right:
        column(LOCKED, SAVED_LOCKED_NOTE if saved else LOCKED_NOTE, res["locked"], saved)
    with st.expander("Evidence: excerpts, requests and credits"):
        for title, side in ((OPEN, res["open"]), (LOCKED, res["locked"])):
            st.markdown(f"**{title}**")
            for r in side["results"]:
                if r.get("quote"):
                    st.markdown(f"- {link(r['title'], r['url'])}: “{quoted(r['quote'])}”")
            meta = [f"credits {side['credits']}" if side.get("credits") is not None else None,
                    f"window {human(side['window'][0])} to {human(side['window'][1])}" if side.get("window") else None,
                    f"latency {side['latency_s']:.2f} s" if side.get("latency_s") is not None else None,
                    f"request id `{side['request_id']}`" if side.get("request_id") else None]
            st.caption(" · ".join(m for m in meta if m))
            if side.get("request"):
                st.json(side["request"], expanded=False)
    with st.expander("Method"):
        st.markdown(SAVED_RULE if saved else HONEST)
        st.caption("Both searches send the same question. The time lock is enforced in code (`timelock/`): it sends "
                   "start_date/end_date and filter_by_published_date, and refuses an end date after the cutoff before "
                   "any call.")
        st.page_link("app_pages/field_report.py", label="Field Report: the measured result", icon=":material/science:")


def saved_example(case_id):
    built = (read_json("results/date_field_test.json") or {}).get("built_utc")
    res = T.example(read_json("results/leak_demo.json"), built, case_id)
    if not res:
        st.caption("No saved example in this copy of the app.")
        return
    answer(res, f"Saved example, not a live run: Leak results case {res['case']} ({res['test_name']}), "
                f"{res['open']['max_results']} results per search, time-lock window "
                f"{human(res['locked']['window'][0])} to {human(res['locked']['window'][1])}.")
    provenance("results/leak_demo.json", "built_utc")


def example_label(case_id, data):
    res = T.example(data, None, case_id)
    if not res:
        return case_id
    thin = T.verdict(res)[1]
    return f"{res['question']} · cutoff {human(res['cutoff'])}" + (" (thin evidence)" if thin else " (leak caught)")


def colab(msg):
    st.info(f"{msg} You can run the same comparison with your own Tavily key in Colab.")
    st.link_button("Open the Colab notebook", T.COLAB_URL, icon=":material/open_in_new:")


def live_form():
    lim = T.limits()
    today = datetime.now(timezone.utc).date()
    with st.form("try_it"):
        q = st.text_input("Question", max_chars=T.MAX_QUESTION, placeholder="e.g. petrol diesel price hike India May 2026")
        cut = st.date_input("Cutoff date", value=today - timedelta(days=60), min_value=T.MIN_CUTOFF,
                            max_value=today - timedelta(days=1), format="YYYY-MM-DD")
        go = st.form_submit_button("Run both searches", type="primary")
    st.caption(f"Each run is two basic Tavily searches ({lim['per_run']} credits) on our key. Limits: "
               f"{lim['per_session']} runs per visit, {lim['per_day']} credits a day for this page; the same question "
               f"and cutoff within {lim['cache_hours']} hours is answered from the last run for free.")
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
        answer(res, f"Answered from the run of {human(res['utc'])}, {res['utc'][11:16]} UTC (same question and cutoff); "
                    "no credits used." if hit else "")


brand_row()
with st.container(key="eyebrow"):
    st.markdown("Search the past")
st.title(TITLE_CLAIM)
st.markdown(SUBHEAD)
data = read_json("results/leak_demo.json")
live = bool(T.tavily_key())
options = [c for c in T.SAVED_CASES if T.example(data, None, c)] + ([OWN] if live else [])
choice = st.radio("Question and cutoff", options, horizontal=False, key="search-past-choice",
                  format_func=lambda k: k if k == OWN else example_label(k, data))
if not live:
    st.caption("Live search is switched off on this copy of the app: there is no Tavily key. The examples are saved "
               "runs.")
if choice == OWN:
    live_form()
elif choice:
    saved_example(choice)

# ---------- the measured result: the hero numbers, below the action ----------
if data:
    st.subheader("The measured result")
    with st.container(key="hero"):
        stat_cards(data["totals"])
    st.page_link("app_pages/leak_demo.py", label="Leak results: every case, the intervals and what we learned",
                 icon=":material/visibility:")
