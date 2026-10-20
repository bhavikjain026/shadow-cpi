"""Shadow CPI app - an experimental nowcast of India's next CPI inflation number.

Run:  streamlit run app.py
It only reads files (data/sample/ by default; see app_pages/README.md). No API calls, no keys.
"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app_pages.common import NOWCAST_WORDS, is_sample  # noqa: E402

st.set_page_config(page_title="Shadow CPI", page_icon="📈", layout="centered")

pages = [
    st.Page("app_pages/home.py", title="Home", icon="🏠", default=True),
    st.Page("app_pages/evidence.py", title="Evidence", icon="🧾"),
    st.Page("app_pages/replay.py", title="Replay", icon="🔁"),
    st.Page("app_pages/flight_recorder.py", title="Tavily Flight Recorder", icon="🛰️"),
    st.Page("app_pages/archive.py", title="Archive", icon="🔒"),
    st.Page("app_pages/brief.py", title="Reporter brief", icon="📰"),
]

with st.sidebar:
    st.markdown("**Shadow CPI**")
    st.caption(f"An {NOWCAST_WORDS} of India's next official CPI inflation number. Not an official statistic.")
    if is_sample():
        st.error("Showing SAMPLE data only.")

st.navigation(pages).run()
