"""As of a date: the nowcast, evidence and coverage from items found on or before that date (v2.asof). Reads the saved
September basket run and the October radar; makes no API call."""
from datetime import date

import streamlit as st

from app_pages.common import header, pct
from v2.asof import as_of

header("As of a date", "What Shadow CPI knew on a given day: only evidence found on or before it. Nothing found later "
                       "can appear (tested in tests/test_v2_asof.py).")
month = st.radio("Month", ["2026-09", "2026-10"], horizontal=True,
                 format_func=lambda m: {"2026-09": "September 2026 (replay)", "2026-10": "October 2026 (radar)"}[m])
lo, hi = (date(2026, 8, 22), date(2026, 9, 29)) if month == "2026-09" else (date(2026, 9, 21), date(2026, 10, 29))
day = st.slider("Day", min_value=lo, max_value=hi, value=hi, format="D MMM YYYY")
v = as_of(day.isoformat(), month)
c1, c2, c3 = st.columns(3)
c1.metric("Nowcast (YoY)", "—" if v["nowcast"] is None else pct(v["nowcast"], 2))
c2.metric("Basket measured", "—" if v["coverage"] is None else f"{v['coverage']:.0%}")
c3.metric("Verified quotes found", len(v["evidence"]))
st.caption(v["note"] + ".")
if v["evidence"]:
    st.dataframe([{"Published": e["published"], "Kind": e["kind"] or "—",
                   "Change": "—" if e["change"] is None else f"{e['change'] * 100:+.2f}%", "Quote": e["quote"],
                   "URL": e["url"]} for e in v["evidence"]], hide_index=True, width="stretch")
else:
    st.info("No verified evidence had been found by this day.")
