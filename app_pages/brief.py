"""Reporter brief: What moved / What we observed / What's uncertain - as a download."""
import streamlit as st

from app_pages.common import NOWCAST_WORDS, header, month_name, months_with, read_text

header("Reporter brief", f"A one-page summary of the {NOWCAST_WORDS} for journalists. Written only from computed "
                         "numbers and verified quotes; it always states coverage and the range.")

months = months_with("results", suffix=".md")
months = [m.removeprefix("reporter_brief_") for m in months if m.startswith("reporter_brief_")]
if not months:
    st.info("No reporter brief yet (results/reporter_brief_<month>.md).")
    st.stop()

month = st.selectbox("Month", months, format_func=month_name)
text = read_text(f"results/reporter_brief_{month}.md")
missing = [w for w in ("coverage", "range") if w not in text.lower()]
if missing:
    st.error("This brief does not state: " + ", ".join(missing) + ". Do not publish it.")

st.download_button("Download reporter brief", text.encode("utf-8"),
                   file_name=f"shadow-cpi-brief-{month}.md",
                   mime="text/markdown", width="stretch")
with st.container(border=True):
    st.markdown(text)
