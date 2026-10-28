"""Tavily trace: every Tavily call for one month (March 2026), the funnel from addresses found to numbers used, and
the failures. Reads results/app/tavily_trace_2026-03.json (tools/build_app_data.py)."""
import streamlit as st

from app_pages.common import ROOT, header, month_name, read_json

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
funnel = t.get("funnel", [])
if funnel:
    cols = st.columns(len(funnel))
    for idx, f in enumerate(funnel):
        with cols[idx]:
            with st.container(key=f"trace_funnel_step_{idx}", border=True):
                st.markdown(f"**Step {idx + 1}**")
                count = f["n"]
                display_count = f"{count:,}" if isinstance(count, int) else count
                st.markdown(f"### {display_count}")
                st.markdown(f"**{f['stage']}**")
                st.caption(f"Source: {f['source']}")

used = funnel[-1].get("detail", {}) if funnel else {}
if used:
    kinds = {"spine": "government food prices", "observed": "official observed series (IBJA, IOCL, PPAC)",
             "event+trend": "announced price changes"}
    groups = {}
    for code, d in used.items():
        groups.setdefault(kinds.get(d["source"], d["source"]), []).append(f"{d['name']} ({code})")
    st.markdown("**Numbers used:** " + "; ".join(f"from the {k}: " + ", ".join(v) for k, v in groups.items()) + ".")

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

# ---------- Amendment E: searches written by Nemotron ----------
st.subheader("Searches written by Nemotron (v2, logged rule change E)")
st.caption("DEVELOPMENT data. In arms B and C, Nemotron Nano (Super if Nano fails) writes each search as JSON: query, "
           "language, topic, dates, domains and how to use them, number of results. Code checks every parameter "
           "before the call (dates inside the window, allowed values only, at most 20 domains) and logs each "
           "correction. Arm A is our fixed query templates.")
ab = read_json("results/v2_ablation.json")
if ab:
    st.dataframe([{"Arm": k, "Searches written by": a["writer"], "Languages": ", ".join(a["languages"]),
                   "Known changes found": f"{a['recall']} of {a['total']}",
                   "False events (upper bound)": f"{a['false_events_upper_bound']} of {a['moving_events']}",
                   "Credits per verified event": (f"{a['credits_per_verified_event']:.1f}"
                                                  if a["credits_per_verified_event"] is not None else "—"),
                   "Median Tavily latency": (f"{a['median_latency_s']:.2f} s"
                                             if a["median_latency_s"] is not None else "—"),
                   "Incomplete months": ", ".join(a["incomplete_months"]) or "none"} for k, a in ab["arms"].items()],
                 hide_index=True, width="stretch")
    st.caption("From results/v2_ablation.json. False events = CPI-moving verified events that match none of the 29 "
               "known changes (the list is the audit's, so an upper bound).")
plans = sorted(ROOT.joinpath("v2", "ablation").glob("arm_[BC]_*.json"))
if plans:
    c1, c2 = st.columns(2)
    arm = c1.selectbox("Arm", sorted({p.name[4] for p in plans}),
                       format_func=lambda a: {"B": "B: English + Hindi", "C": "C: + regional languages"}[a])
    months = sorted(p.name[6:13] for p in plans if p.name[4] == arm)
    m = c2.selectbox("Month", months, index=len(months) - 1, format_func=month_name)
    run = read_json(f"v2/ablation/arm_{arm}_{m}.json")
    by_call = {c["call_id"]: c for c in run["calls"]}
    st.dataframe([{"Language": s["language"], "Query": s["query"], "Topic": s["topic"],
                   "Dates": f"{s['start_date']} to {s['end_date']}",
                   "Domains": (f"{s['include_domains_mode']}: " + ", ".join(s["include_domains"])
                               if s["include_domains"] else "none"),
                   "Max results": s["max_results"], "Written by": s["written_by"].split("/")[-1],
                   "Code corrections": "; ".join(s["corrections"]) or "none",
                   "Results": s.get("n_results", "not sent"),
                   "Credits": by_call.get(s.get("search_call"), {}).get("credits", "—")} for s in run["plan"] or []],
                 hide_index=True, width="stretch")
    dropped = [d for t in run["plan_tries"] for d in t["dropped"]]
    st.caption(f"Plan {'complete' if run['plan_complete'] else 'incomplete'} · written by "
               + " then ".join(t["model"].split("/")[-1] for t in run["plan_tries"])
               + f" · {len(dropped)} searches dropped by code" + (" · " + "; ".join(d["why"][0] for d in dropped)
                                                                 if dropped else ""))
    with st.expander("Exactly what was sent to Tavily"):
        st.json([c["sent"] for c in run["calls"] if c["endpoint"] == "/search"], expanded=False)
