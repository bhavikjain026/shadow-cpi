"""Live build (v2): the number built from evidence, card by card, under live conditions (evidence published up to
the 29th). Each card appears grey, then turns green (verified) or red (rejected, with the reason); verified items
fill the basket treemap and move the CPI needle. Replays saved runs (v2/evidence/run_*.json); makes no API call.
Non-English lines carry an English gloss from Nemotron Nano, for display only: it is never used for a number."""
import json
import os
import time

import altair as alt
import pandas as pd
import streamlit as st

from app_pages.common import ROOT, clean_line, header, month_name

header("Live build (v2)", "Shadow CPI v2 builds the number one piece of evidence at a time, under live conditions: "
                          "only pages published up to the 29th of the month count. This page replays a saved run.")
EV = ROOT / "v2" / "evidence"
runs = {"September 2026, whole basket": EV / "run_2026-09_basket.json",
        "April 2026, milk tracer (Madhya Pradesh)": EV / "run_2026-04_milk_madhya-pradesh.json"}
runs = {k: p for k, p in runs.items() if p.exists()}
if not runs:
    st.info("No v2 run yet (python -m v2.basket).")
    st.stop()
pick = st.radio("Run", list(runs), horizontal=True)
run = json.loads(runs[pick].read_text(encoding="utf-8"))
basket = "tiles" in run
fast = os.environ.get("SHADOW_CPI_NO_ANIMATION") or st.checkbox("Show the result without the animation")
pause = 0 if fast else (0.12 if basket else 0.3)
st.caption(f"{month_name(run['month'])}: evidence published from {run['window'][0]} to the cutoff "
           f"{run['window'][1]}. Development data under v2/PREREGISTRATION.md (with Amendment A), not a forecast.")

top, tree_box, cards_box = st.empty(), st.empty(), st.container()
lo_hi = [run["needle"]["start"], run["needle"]["end"]] + ([run["v1"]["c"], run["official"]] if basket else [])


def draw_top(value, measured, label):
    lo, hi = min(lo_hi) - 0.05, max(lo_hi) + 0.05
    with top.container(border=True):
        c1, c2 = st.columns(2)
        c1.metric("CPI inflation, year-on-year", f"{value:.3f}%", label)
        if measured is not None:
            c2.metric("Measured from evidence", f"{measured:.1%} of the basket")
        scale = alt.Scale(domain=[lo, hi], nice=False)
        marks = [{"x": value, "what": "Needle"}, {"x": run["needle"]["start"], "what": "Trend only (v1)"}]
        if basket:
            marks += [{"x": run["v1"]["c"], "what": "v1 Shadow CPI"}, {"x": run["official"], "what": "Official"}]
        dom = [m["what"] for m in marks]
        rng = ["#F28E2B", "#9A9A9A", "#4C8DF6", "#2CA58D"][:len(dom)]
        base = alt.Chart(pd.DataFrame([{"lo": lo, "hi": hi}])).mark_rule(strokeWidth=8, opacity=0.25).encode(
            x=alt.X("lo:Q", scale=scale, title=None), x2="hi:Q")
        ticks = alt.Chart(pd.DataFrame(marks)).mark_tick(thickness=4, size=40).encode(
            x=alt.X("x:Q", scale=scale), tooltip=["what", alt.Tooltip("x:Q", format=".3f")],
            color=alt.Color("what:N", scale=alt.Scale(domain=dom, range=rng),
                            legend=alt.Legend(orient="bottom", title=None, columns=4)))
        st.altair_chart((base + ticks).properties(height=90), width="stretch")


def draw_tree(done):
    df = pd.DataFrame([{**t, "status": "measured" if t["code"] in done else "on trend",
                        "label": t["name"][:18] if (t["x1"] - t["x0"]) * (t["y1"] - t["y0"]) > 60 else "",
                        "cx": (t["x0"] + t["x1"]) / 2, "cy": (t["y0"] + t["y1"]) / 2} for t in run["tiles"]])
    color = alt.Color("status:N", scale=alt.Scale(domain=["measured", "on trend"], range=["#2CA58D", "#5A5A5A"]),
                      legend=alt.Legend(orient="bottom", title=None))
    x, y = alt.Scale(domain=[0, 100], nice=False), alt.Scale(domain=[60, 0], nice=False)
    rects = alt.Chart(df).mark_rect(stroke="#111111", strokeWidth=1).encode(
        x=alt.X("x0:Q", scale=x, axis=None), x2="x1:Q", y=alt.Y("y0:Q", scale=y, axis=None), y2="y1:Q",
        color=color, tooltip=["name", alt.Tooltip("weight:Q", format=".2f", title="CPI weight (%)"), "status"])
    text = alt.Chart(df).mark_text(fontSize=10, color="white").encode(x=alt.X("cx:Q", scale=x),
                                                                      y=alt.Y("cy:Q", scale=y), text="label")
    tree_box.altair_chart((rects + text).properties(height=320, title="The basket by CPI weight"), width="stretch")


def card_body(card):
    st.markdown(f"**{card['title']}**  \n[{card['domain']}]({card['url']})")
    for cl in card["claims"]:
        mark = "✅" if cl.get("status") == "verified" else "❌"
        extra = (f" · change {cl['change'] * 100:+.2f}%, effective {cl['effective_date']}"
                 if cl.get("status") == "verified" and cl.get("change") is not None else "")
        st.markdown(f"{mark} “{clean_line(cl['line'])}”  \n{cl.get('reason') or 'not checked'}{extra}"
                    + (f"  \n**{cl['use']}**" if cl.get("use") else ""))
        if cl.get("gloss"):
            st.caption(f"English gloss (Nemotron Nano, display only): {cl['gloss']}")
    if card.get("page_sha256"):
        st.caption(f"Page saved at fetch time, SHA-256 {card['page_sha256'][:16]}…")


def stream(card, label_ok, body):
    with cards_box:
        box = st.status(f":gray[Checking {card.get('domain') or card.get('name')}]", state="running", expanded=False)
    time.sleep(pause)
    with box:
        body()
    ok = card["status"] == "verified"
    box.update(label=(f":green[**Verified**] · {label_ok}" if ok else
                      f":red[**Rejected**] · {card.get('domain') or card.get('name')} · {card['reason']}"),
               state="complete" if ok else "error")
    return ok


if basket:
    draw_top(run["needle"]["start"], 0.0, "everything on trend")
    draw_tree(set())
    done, steps = set(), iter(run["timeline"])
    for card in run["item_cards"]:
        def body(c=card):
            st.markdown(f"**{c['source']}**: {c['detail']}.  \nChange used: "
                        + (f"{c['change'] * 100:+.2f}%" if c["change"] is not None else "none"))
        if stream(card, f"{card['name']} · {card['source']}", body):
            step = next(steps)
            done.add(step["cpi_code"])
            draw_top(step["yoy_after"], step["measured_after"], f"after {step['name']}")
            draw_tree(done)
    for card in run["cards"]:
        stream(card, f"{card['domain']} · {card['published']}", lambda c=card: card_body(c))
    for step, m in zip(run["timeline"][len(done):], run["moving_events"]):
        done.add(step["cpi_code"])
        draw_top(step["yoy_after"], step["measured_after"], f"after {m['event_kind']} in {m['where']}")
        draw_tree(done)
    ev = [cl for c in run["cards"] for cl in c["claims"] if "status" in cl]
    st.markdown(f"**{sum(c['status'] == 'verified' for c in run['item_cards'])} of {len(run['item_cards'])}** "
                f"spine and official-series items measured · announced price changes: **{len(run['cards'])}** pages "
                f"proposed, **{len(ev)}** claims checked, **{sum(cl['status'] == 'verified' for cl in ev)}** verified, "
                f"**{len(run['moving_events'])}** moving the number.")
    st.markdown(f"Final: **{run['needle']['end']:.3f}%** (v2, development data) · v1 Shadow CPI "
                f"{run['v1']['c']:.3f}% · official {run['official']:.2f}%.")
    for n in run.get("notes", []):
        st.caption(n)
else:
    draw_top(run["needle"]["start"], None, "trend only")
    for card in run["cards"]:
        stream(card, f"{card['domain']} · {card['published']}", lambda c=card: card_body(c))
    for it in run.get("items", []):
        draw_top(it["yoy_after"], None, f"{it['name']} from the {it['source']}")
        st.markdown(f"Milk moves by the **{it['source']}** ({it['detail']}): {it['change'] * 100:+.3f}%. Verified "
                    "milk events are context only under Amendment A (the spine is milk's source; a city event "
                    "with no statewide confirmation moves nothing).")
st.caption(f"Credits for this run: {run['credits_spent']} (budget '{run['credits_budget']}'). Each checked claim, "
           "verified or rejected, is in v2/evidence/ledger.jsonl.")
