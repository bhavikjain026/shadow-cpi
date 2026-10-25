"""Shadow CPI app - an experimental nowcast of India's next CPI inflation number.

Run:  streamlit run app.py
It reads the results files in this repository (docs/app_numbers.md). The only API calls are the capped "Run live"
button on Home, with keys from the environment (SCPI_TAVILY_API_KEY, SCPI_NEBIUS_API_KEY).
"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app_pages.common import NOWCAST_WORDS  # noqa: E402

st.set_page_config(page_title="Shadow CPI", page_icon="📈", layout="centered", initial_sidebar_state="auto")

pages = [
    st.Page("app_pages/home.py", title="Home", icon="🏠", default=True),
    st.Page("app_pages/evidence.py", title="Evidence", icon="🧾"),
    st.Page("app_pages/replay.py", title="Replay", icon="🔁"),
    st.Page("app_pages/live_build.py", title="Live build (v2)", icon="🧱"),
    st.Page("app_pages/radar.py", title="October radar (v2)", icon="📡"),
    st.Page("app_pages/field_report.py", title="Tavily field report", icon="🧪"),
    st.Page("app_pages/custody.py", title="Chain of custody", icon="🔗"),
    st.Page("app_pages/as_of.py", title="As of a date", icon="🗓️"),
    st.Page("app_pages/tavily_trace.py", title="Tavily trace (March)", icon="🔎"),
    st.Page("app_pages/flight_recorder.py", title="Tavily Flight Recorder", icon="🛰️"),
    st.Page("app_pages/archive.py", title="Archive", icon="🔒"),
    st.Page("app_pages/brief.py", title="Reporter brief", icon="📰"),
]

with st.sidebar:
    st.markdown("**Shadow CPI**")
    st.caption(f"An {NOWCAST_WORDS} of India's next official CPI inflation number. Not an official statistic.")

st.navigation(pages).run()
