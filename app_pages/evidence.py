"""Evidence: every quote and event used, the government price spine, and what was dropped or failed."""
import streamlit as st

from app_pages.common import header, month_name, months_with, read_csv, read_json, tag

header("Evidence", "Every price quote and announced price change behind the experimental nowcast. "
                   "Only verified evidence is used: the exact line from the page must contain the number.")

months = months_with("manifests")
if not months:
    st.info("No evidence manifests yet (manifests/<month>.json).")
    st.stop()
month = st.selectbox("Month", months, format_func=month_name)
man = read_json(f"manifests/{month}.json")
link = {"Link": st.column_config.LinkColumn("Link"), "Exact line": st.column_config.TextColumn("Exact line", width="large")}

st.subheader(tag("Price quotes"))
src = st.radio("Source", ["All", "Government price spine", "Tavily (web)"], horizontal=True)
want = {"All": None, "Government price spine": "spine", "Tavily (web)": "tavily"}[src]
quotes = [q for q in man.get("quotes", []) if q.get("verified") and (want is None or q.get("source") == want)]
st.dataframe([{"Item": q["item"], "Price": f"{q['price']:,.2f} {q['unit']}", "Place": q["place"], "Date": q["date"],
               "Exact line": q["line"], "Source": "Spine" if q["source"] == "spine" else "Tavily",
               "Tier": q.get("tier", ""), "Link": q["url"]} for q in quotes],
             hide_index=True, width="stretch", column_config=link)

st.subheader(tag("Announced price changes (events)"))
events = [e for e in man.get("events", []) if e.get("verified")]
st.dataframe([{"Item": e["item"], "Seller": e.get("seller", ""), "Place": e["place"],
               "Change": f"{e['pct_change']:+.1f}%", "Effective": e["effective_date"],
               "Share of month": f"{e.get('days_in_month_share', 1):.0%}",
               "2 sources": "Yes" if e.get("confirmed_by_2_sources") else "No",
               "Exact line": e["line"], "Link": e["url"]} for e in events],
             hide_index=True, width="stretch", column_config=link)

spine = [r for r in read_csv("data/spine.csv") if r["month"] == month]
st.subheader(tag("Government price spine (centre monthly averages)"))
if spine:
    st.dataframe([{"Item": r["item"], "Centre": r["centre"], "Average price": f"{float(r['avg_price']):,.2f} {r['unit']}",
                   "Days": r["n_days"]} for r in spine], hide_index=True, width="stretch")
else:
    st.caption("No spine prices for this month.")

st.subheader(tag("Kept and dropped"))
c = man.get("counts", {})
st.markdown(f"Pages seen **{c.get('pages_seen', '—')}**, kept **{c.get('pages_kept', '—')}** · "
            f"quotes verified **{c.get('quotes_verified', '—')} of {c.get('quotes_extracted', '—')}** · "
            f"events verified **{c.get('events_verified', '—')} of {c.get('events_extracted', '—')}**")
st.dataframe([{"Dropped because": d["reason"], "Count": d["count"]} for d in man.get("dropped", [])],
             hide_index=True, width="stretch")

st.subheader("Sources that failed")
failed = man.get("failed_sources", [])
if failed:
    st.dataframe([{"Address": f["url"], "Tried with": f["via"], "What went wrong": f["reason"]} for f in failed],
                 hide_index=True, width="stretch")
else:
    st.caption("None this month.")

with st.expander("Searches used this month"):
    st.dataframe([{"Query": q["query"], "Language": q["language"], "Tavily endpoint": q["endpoint"],
                   "Results": q.get("n_results"), "Retrieved (UTC)": q["retrieved_at"]} for q in man.get("queries", [])],
                 hide_index=True, width="stretch")
    st.caption(f"Code commit `{man.get('code_commit', '—')}` · models: "
               + ", ".join(f"{k} = {v}" for k, v in man.get("model_ids", {}).items()))
