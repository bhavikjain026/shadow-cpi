"""For research teams / Beyond CPI: how to use the exports, as_of() and seal checks without look-ahead bias, and the
finance check as a second domain. Numbers are read from results/field_report.json; no API call."""
import streamlit as st

from app_pages.common import header, read_json

header("For research teams", "Designed for research teams that need web evidence without look-ahead bias. "
                             "Research tool, not investment advice.")
st.markdown("""
**Look-ahead bias.** A replay that uses a page published after its cutoff looks better than it could ever be live.
Shadow CPI locks every search to a date window, re-checks each page's date, and logs every call.

**How to use it**
- **Exports:** `python tools/export.py` writes `exports/nowcast.csv`, `exports/evidence.csv` (short cited lines only,
  never page text) and `exports/radar.jsonl`; columns and limits in `docs/exports_schema.md`.
- **As of a date:** `v2.asof.as_of(day)`, or the "As of a date" page: only items found on or before the day.
- **Seal checks:** `verify.md`, and the "Chain of custody" page from any number to its quote, page, request ID, response
  hash and seal.
- **Leak checker:** `shadow_cpi.leakcheck.check_result(result, cutoff)` → safe / date_flag / leak (undated pages are
  flagged, not dropped).
""")
st.page_link("app_pages/as_of.py", label="As of a date", icon="🗓️")
st.page_link("app_pages/custody.py", label="Chain of custody", icon="🔗")

st.subheader("Beyond CPI: a second domain")
r = read_json("results/field_report.json")
if r:
    m = r["finance"]["first_pass"]["all_14"]
    a = r["finance"]["after_retry"]["all_14"]
    st.markdown(f"Replaying the day before {m['events']} scheduled financial events (RBI policy decisions, large-company "
                f"results): with **no dates**, pages stating the outcome were returned for "
                f"{m['arms']['N']['snippet_own_month_events']} of {m['events']} events (snippet leaks; Wayback-confirmed "
                f"for {a['arms']['N']['confirmed_events']} after a network retry); with **dates + "
                f"filter_by_published_date**, for {a['arms']['D']['confirmed_events']}. Designed for event studies and "
                "backtests that must not see the outcome early.")
    st.page_link("app_pages/field_report.py", label="Full numbers: Tavily field report", icon="🧪")
st.caption("Research tool, not investment advice.")
