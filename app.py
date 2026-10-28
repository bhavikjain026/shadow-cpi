"""Shadow CPI app - an experimental nowcast of India's next CPI inflation number.

Run:  streamlit run app.py
It reads the results files in this repository (docs/app_numbers.md). The only API calls are the capped "Run live"
button on October forecast and the Leak results page's live mode (both off unless RUN_LIVE_ENABLED), and "Search the
past" (on whenever the Tavily key is set; its own credit caps, shadow_cpi/try_it.py), with keys from the environment
(SCPI_TAVILY_API_KEY, SCPI_NEBIUS_API_KEY).
"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app_pages.common import MARK_PATH, a11y_line, NOWCAST_WORDS, inject_style, more_links  # noqa: E402

st.set_page_config(page_title="Shadow CPI", page_icon=str(Path(__file__).resolve().parent / MARK_PATH), layout="wide", initial_sidebar_state="auto")
inject_style()

# (script, nav title, icon, the title the page passes to header() = its PAGE_GUIDES key), in nav order. The sidebar
# shows MAIN; everything else sits in a collapsed "More" group (no page deleted).
MAIN = [
    ("try_it", "Search the past", "travel_explore", "Search the past"),
    ("leak_demo", "Leak results", "visibility", "Leak results"),
    ("home", "October forecast", "trending_up", "Experimental nowcast"),
    ("use_it", "Use it", "code", "Use it"),
]
MORE = [
    ("field_report", "Field Report", "science", "Tavily field report"),
    ("radar", "Radar", "radar", "October radar (v2)"),
    ("evidence", "Evidence", "receipt_long", "Evidence"),
    ("replay", "Replay", "replay", "Replay"),
    ("live_build", "Live build (v2)", "construction", "Live build (v2)"),
    ("custody", "Chain of custody", "link", "Chain of custody"),
    ("as_of", "As of a date", "event", "As of a date"),
    ("research", "For research teams", "biotech", "For research teams"),
    ("tavily_trace", "Tavily trace (March)", "manage_search", "Tavily trace"),
    ("flight_recorder", "Tavily Flight Recorder", "flight", "Tavily Flight Recorder"),
    ("archive", "Archive", "lock", "Archive"),
    ("brief", "Reporter brief", "newspaper", "Reporter brief"),
]


def make(rows):
    return [st.Page(f"app_pages/{f}.py", title=t, icon=f":material/{i}:", default=f == "try_it") for f, t, i, _ in rows]


main, more = make(MAIN), make(MORE)
nav = st.navigation(main + more, position="hidden")     # the links are drawn below, so "More" can start collapsed
mark = str(Path(__file__).resolve().parent / MARK_PATH)
st.logo(mark, size="large", icon_image=mark)

with st.sidebar:
    with st.container(key="sidebar-brand"):
        st.markdown("**Shadow CPI**")
        st.caption(f"An {NOWCAST_WORDS} of India's next official CPI inflation number. Not an official statistic.")
    with st.container(key="sidebar-main"):
        for page in main:
            st.page_link(page)
    more_links([(pg, row[3]) for pg, row in zip(more, MORE)])

nav.run()
if a11y_line():
    with st.container(key="a11y-footer"):
        st.divider()
        st.caption(a11y_line())
