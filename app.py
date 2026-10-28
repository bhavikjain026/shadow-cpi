"""Shadow CPI app - an experimental nowcast of India's next CPI inflation number.

Run:  streamlit run app.py
It reads the results files in this repository (docs/app_numbers.md). The only API calls are the capped "Run live"
button on October forecast and the Leak demo's live mode (both off unless RUN_LIVE_ENABLED), and "Try it: search the
past" (on whenever the Tavily key is set; its own credit caps, shadow_cpi/try_it.py), with keys from the environment
(SCPI_TAVILY_API_KEY, SCPI_NEBIUS_API_KEY).
"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app_pages.common import NOWCAST_WORDS, inject_style, page_guide  # noqa: E402

st.set_page_config(page_title="Shadow CPI", page_icon=":material/trending_up:", layout="wide", initial_sidebar_state="auto")
inject_style()

# (script, nav title, icon, the title the page passes to header() = its PAGE_GUIDES key), in nav order
NAV = {"": [
    ("leak_demo", "Leak demo", "visibility", "Leak demo"),
    ("field_report", "Field Report", "science", "Tavily field report"),
    ("try_it", "Try it: search the past", "travel_explore", "Try it: search the past"),
    ("home", "October forecast", "trending_up", "Experimental nowcast"),
    ("radar", "Radar", "radar", "October radar (v2)"),
], "More": [
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
]}
pages = {group: [st.Page(f"app_pages/{f}.py", title=t, icon=f":material/{i}:", default=f == "leak_demo")
                 for f, t, i, _ in rows] for group, rows in NAV.items()}
guide = [(pg, row[3]) for group, rows in NAV.items() for pg, row in zip(pages[group], rows)]

with st.sidebar:                # moved above the page links by app_pages/style.css (.st-key-sidebar-brand)
    with st.container(key="sidebar-brand"):
        st.markdown("**Shadow CPI**")
        st.caption(f"An {NOWCAST_WORDS} of India's next official CPI inflation number. Not an official statistic.")

nav = st.navigation(pages)
with st.sidebar:
    page_guide(guide)          # after st.navigation, so it sits under the page links
nav.run()
