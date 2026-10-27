"""Evidence: every quote and event used, the government price spine, and what was dropped or failed."""
import streamlit as st

from app_pages.common import (clean_line, header, item_label, month_name, months_with, read_csv, read_json,
                              readable_quote, source_column)

header("Evidence", "Every price quote and announced price change behind the experimental nowcast. "
                   "Only verified evidence is used: the exact line from the page must contain the number.")

months = months_with("manifests")
if not months:
    st.info("No evidence manifests yet (manifests/<month>.json).")
    st.stop()
month = st.selectbox("Month", months, format_func=month_name,
                     index=months.index("2026-03") if "2026-03" in months else 0)
if "2026-01" <= month <= "2026-09" and month != "2026-03":
    st.caption("To save credits (cut 2), replay months other than March skipped web price quotes, so they show only the "
               "government food prices, the official observed series (IBJA, IOCL, PPAC) and announced price "
               "changes. March has the full set of web price quotes.")
man = read_json(f"manifests/{month}.json")
cols = {"Source": source_column(), "Line": st.column_config.TextColumn("Line", width="large")}

# ---------- price quotes ----------
st.subheader("Price quotes")
src = st.radio("Show", ["All", "Official series (IBJA, IOCL, PPAC)", "News pages"], horizontal=True)
want = {"All": None, "Official series (IBJA, IOCL, PPAC)": "observed", "News pages": "exploratory"}[src]
quotes = [q for q in man.get("quotes", []) if q.get("verified") and (want is None or q.get("tier") == want)]
st.dataframe([{"Item": item_label(q["item"]), "Source": q["url"], "Price": f"{q['price']:,.2f} {q['unit']}",
               "Place": q["place"], "Date": q["date"], "Line": readable_quote(q),
               "Kind": "Official series" if q.get("tier") == "observed" else "News page"} for q in quotes],
             hide_index=True, width="stretch", column_config=cols)
with st.expander("Exact lines as they appear on the page"):
    st.dataframe([{"Item": item_label(q["item"]), "Date": q["date"], "Exact line": clean_line(q["line"]),
                   "Source": q["url"]} for q in quotes],
                 hide_index=True, width="stretch", column_config=cols)

# ---------- events ----------
st.subheader("Announced price changes (events)")
events = [e for e in man.get("events", []) if e.get("verified")]
if events:
    st.dataframe([{"Item": item_label(e["item"]), "Source": e["url"], "Place": e["place"],
                   "Seller": e.get("seller", ""), "Change": f"{e['pct_change']:+.1f}%", "Effective": e["effective_date"],
                   "Share of month": f"{e.get('days_in_month_share', 1):.0%}",
                   "2 sources": "Yes" if e.get("confirmed_by_2_sources") else "No"} for e in events],
                 hide_index=True, width="stretch", column_config=cols)
    with st.expander("Exact lines behind these changes"):
        for e in events:
            st.markdown(f"**{item_label(e['item'])}, {e['place']}:** “{clean_line(e['line'])}”")
else:
    st.caption("No verified price events this month.")

# ---------- spine ----------
spine = [r for r in read_csv("data/spine.csv") if r["month"] == month]
st.subheader("Government food prices (centre monthly averages)")
if spine:
    rows = [{"Item": item_label(r["item"]), "Centre": r["centre"].title(),
             "Average price": f"{float(r['avg_price']):,.2f} {r['unit']}", "Days": r["n_days"]} for r in spine]
    if not any(r["Days"] for r in rows):
        for r in rows:
            del r["Days"]
    st.dataframe(rows, hide_index=True, width="stretch",
                 column_config={"Centre": st.column_config.TextColumn("Centre", width="medium")})
    st.caption("Units as printed by DoCA; eggs and milk are labelled Rs./Kg. by the source. The model uses "
               "month-on-month % changes only.")
else:
    st.caption("No government food prices for this month.")

# ---------- kept and dropped ----------
st.subheader("Kept and dropped")
c = man.get("counts", {})
n_off = sum(q.get("tier") == "observed" for q in man.get("quotes", []) if q.get("verified"))
n_news = sum(q.get("tier") == "exploratory" for q in man.get("quotes", []) if q.get("verified"))
st.markdown(f"Price quotes listed above: **{n_off + n_news}**, all verified word for word ({n_off} official-series "
            f"rows, {n_news} news quotes).")
st.markdown(f"This month's latest event search: pages seen **{c.get('pages_seen', '—')}**, kept "
            f"**{c.get('pages_kept', '—')}** · events verified **{c.get('events_verified', '—')} of "
            f"{c.get('events_extracted', '—')}** extracted.")
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
