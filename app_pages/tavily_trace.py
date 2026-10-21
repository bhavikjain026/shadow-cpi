"""Tavily trace: every Tavily call for one month (March 2026), the funnel from addresses found to numbers used, and
the failures. Reads results/app/tavily_trace_2026-03.json (tools/build_app_data.py)."""
import streamlit as st

from app_pages.common import header, month_name, read_json

MONTH = "2026-03"
header("Tavily trace", f"Every Tavily call behind {month_name(MONTH)}: the endpoint, the settings changed from "
                       "Tavily's defaults, credits, time, and what each call produced.")
t = read_json(f"results/app/tavily_trace_{MONTH}.json")
if not t:
    st.info(f"No trace yet (results/app/tavily_trace_{MONTH}.json).")
    st.stop()

c1, c2, c3 = st.columns(3)
c1.metric("Tavily calls", t["n_calls"])
c2.metric("Credits", t["credits"])
c3.metric("Failures listed", len(t["failures"]))
st.caption(t["note"])

st.subheader("Funnel: from addresses found to numbers used")
st.dataframe([{"Stage": f["stage"], "Count": str(f["n"]), "From": f["source"]} for f in t["funnel"]],
             hide_index=True, width="stretch")
used = t["funnel"][-1].get("detail", {})
if used:
    st.caption("Numbers used: " + ", ".join(f"{code} ({src})" for code, src in used.items()) + ".")

st.subheader("Calls")
endpoints = sorted({c["endpoint"] for c in t["calls"]})
pick = st.multiselect("Endpoint", endpoints, default=endpoints)
st.dataframe([{"Time (UTC)": c["time"][:19].replace("T", " "), "Endpoint": c["endpoint"], "Job": c["job"] or "",
               "Asked": c["what"], "Settings changed": ", ".join(f"{k}={v}" for k, v in c["settings"].items()),
               "Credits": c["credits"], "Seconds": round(c["latency_ms"] / 1000, 1), "Produced": c["produced"]}
              for c in t["calls"] if c["endpoint"] in pick], hide_index=True, width="stretch")

st.subheader("What failed")
st.dataframe([{"What": f["what"], "Result": f["result"], "Source": f["source"]} for f in t["failures"]],
             hide_index=True, width="stretch")
st.caption("Map returned no addresses on the government and PSU sites tried, with no error. Some rate lists are "
           "PDFs whose tables are images, so Extract returns only the letterhead.")
