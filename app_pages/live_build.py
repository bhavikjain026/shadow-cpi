"""Live build (v2): one basket item built from evidence, card by card. Each proposed page appears grey, then turns
green (verified) or red (rejected, with the reason), and the CPI needle moves when evidence is verified.
Reads the saved tracer run (v2/evidence/run_*.json, written by `python -m v2.tracer`); makes no API call."""
import json
import os
import time

import altair as alt
import pandas as pd
import streamlit as st

from app_pages.common import ROOT, clean_line, header, month_name

header("Live build (v2)", "Shadow CPI v2 builds the number one piece of evidence at a time, under live conditions: "
                          "only pages published up to the 29th of the month count. This page replays a saved run.")
runs = sorted((ROOT / "v2" / "evidence").glob("run_*.json"))
if not runs:
    st.info("No v2 run yet (python -m v2.tracer).")
    st.stop()
run = json.loads(runs[-1].read_text(encoding="utf-8"))
nd = run.get("needle") or {}
st.caption(f"Tracer: {run['cpi_name']} in {run['state'].title()}, {month_name(run['month'])}. Search window "
           f"{run['window'][0]} to {run['window'][1]} (cutoff). One item only, so this is a demonstration of the "
           "method, not a forecast. Rules: v2/PREREGISTRATION.md.")

fast = os.environ.get("SHADOW_CPI_NO_ANIMATION") or st.checkbox("Show the result without the animation")
pause = 0 if fast else 0.35
needle_box, cards_box = st.empty(), st.container()


def draw_needle(value, label):
    lo, hi = min(run["trend_only"], nd.get("before", value)) - 0.05, max(nd.get("after", value), value) + 0.05
    with needle_box.container(border=True):
        c1, c2 = st.columns([1, 2])
        c1.metric("CPI inflation, year-on-year", f"{value:.3f}%", label)
        scale = alt.Scale(domain=[lo, hi], nice=False)
        marks = pd.DataFrame([{"x": run["trend_only"], "what": "Trend only (v1)"},
                              {"x": value, "what": "Needle"}])
        bar = alt.Chart(pd.DataFrame([{"lo": lo, "hi": hi}])).mark_rule(strokeWidth=8, opacity=0.25).encode(
            x=alt.X("lo:Q", scale=scale, title=None), x2="hi:Q")
        ticks = alt.Chart(marks).mark_tick(thickness=4, size=44).encode(
            x=alt.X("x:Q", scale=scale), color=alt.Color("what:N", legend=alt.Legend(orient="bottom", title=None),
                                                         scale=alt.Scale(range=["#F28E2B", "#9A9A9A"])))
        c2.altair_chart((bar + ticks).properties(height=90), width="stretch")


draw_needle(nd.get("before", run["trend_only"]), "before evidence (milk on its own trend)")
verified_seen = 0
for card in run["cards"]:
    with cards_box:
        box = st.status(f":gray[Checking {card['domain']} · {card['published'] or 'no date'} · "
                        f"{'Hindi' if card['lang'] == 'hi' else 'English'}]", state="running", expanded=False)
    time.sleep(pause)
    with box:
        st.markdown(f"**{card['title']}**  \n[{card['domain']}]({card['url']})")
        for cl in card["claims"]:
            mark = "✅" if cl.get("status") == "verified" else "❌"
            st.markdown(f"{mark} “{clean_line(cl['line'])}”  \n{cl.get('reason') or ''}"
                        + (f" · change {cl['change'] * 100:+.1f}%, effective {cl['effective_date']}"
                           if cl.get("status") == "verified" and cl.get("change") is not None else ""))
        if card.get("page_sha256"):
            st.caption(f"Page saved at fetch time, SHA-256 {card['page_sha256'][:16]}…")
    ok = card["status"] == "verified"
    box.update(label=(f":green[**Verified**] · {card['domain']} · {card['published']}" if ok else
                      f":red[**Rejected**] · {card['domain']} · {card['reason']}"),
               state="complete" if ok else "error")
    if ok:
        verified_seen += 1
        if nd and verified_seen == nd["n_verified"]:            # all verified evidence is in: the needle moves
            draw_needle(nd["after"], f"{nd['after'] - nd['before']:+.3f} points from {nd['n_verified']} verified pages")
if nd:
    st.markdown(f"**{nd['n_verified']} verified** of {len(run['cards'])} proposed pages. Median change "
                f"{nd['change'] * 100:+.2f}% from {nd['effective_date']}, applied to {run['state'].title()}'s share of "
                f"the all-India milk weight: the item moves {nd['applied_item_change'] * 100:+.3f}%, and CPI "
                f"inflation moves from {nd['before']:.3f}% to {nd['after']:.3f}%.")
st.caption(f"Credits for this run: {run['credits_spent']} (budget '{run['credits_budget']}'). Each claim, verified or "
           "rejected, is in v2/evidence/ledger.jsonl.")
