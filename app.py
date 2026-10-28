"""Shadow CPI app - an experimental nowcast of India's next CPI inflation number.

Run:  streamlit run app.py
It reads the results files in this repository (docs/app_numbers.md). The only API calls are the capped "Run live"
button on October forecast and the Leak demo's live mode (both off unless RUN_LIVE_ENABLED), with keys from the
environment (SCPI_TAVILY_API_KEY, SCPI_NEBIUS_API_KEY).
"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app_pages.common import NOWCAST_WORDS, inject_style  # noqa: E402

st.set_page_config(page_title="Shadow CPI", page_icon=":material/trending_up:", layout="wide", initial_sidebar_state="auto")
inject_style()

pages = {"": [
    st.Page("app_pages/leak_demo.py", title="Leak demo", icon=":material/visibility:", default=True),
    st.Page("app_pages/field_report.py", title="Field Report", icon=":material/science:"),
    st.Page("app_pages/home.py", title="October forecast", icon=":material/trending_up:"),
    st.Page("app_pages/radar.py", title="Radar", icon=":material/radar:"),
], "More": [
    st.Page("app_pages/evidence.py", title="Evidence", icon=":material/receipt_long:"),
    st.Page("app_pages/replay.py", title="Replay", icon=":material/replay:"),
    st.Page("app_pages/live_build.py", title="Live build (v2)", icon=":material/construction:"),
    st.Page("app_pages/custody.py", title="Chain of custody", icon=":material/link:"),
    st.Page("app_pages/as_of.py", title="As of a date", icon=":material/event:"),
    st.Page("app_pages/research.py", title="For research teams", icon=":material/biotech:"),
    st.Page("app_pages/tavily_trace.py", title="Tavily trace (March)", icon=":material/manage_search:"),
    st.Page("app_pages/flight_recorder.py", title="Tavily Flight Recorder", icon=":material/flight:"),
    st.Page("app_pages/archive.py", title="Archive", icon=":material/lock:"),
    st.Page("app_pages/brief.py", title="Reporter brief", icon=":material/newspaper:"),
]}

with st.sidebar:
    st.markdown("**Shadow CPI**")
    st.caption(f"An {NOWCAST_WORDS} of India's next official CPI inflation number. Not an official statistic.")

st.navigation(pages).run()
