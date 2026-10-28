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

from app_pages.common import ROOT, altair_chart, chart_table, clean_line, header, month_name
from app_pages.v2_panels import time_machine, what_tavily_adds

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
           f"{run['window'][1]}. Development data under v2/PREREGISTRATION.md (with its logged rule change A), not a forecast.")
REC = ROOT / "results" / f"replay_{month_name(run['month'])[:3].lower()}.jsonl"
rec_events = ([json.loads(line) for line in REC.read_text(encoding="utf-8").splitlines() if line.strip()]
              if basket and REC.exists() else [])
if rec_events and rec_events[0].get("month") == run["month"]:
    with st.expander("Replay a saved run: 0 calls, 0 credits"):
        built = pd.Timestamp(rec_events[0]["built_utc"])
        st.caption(f"Replay of a recorded run ({built.day} {built:%b}). Recomputing it needs the page cache, which "
                   "holds copyrighted article text and isn't published; run `python -m v2.replay` locally to "
                   f"recompute. Source: `{REC.relative_to(ROOT)}`.")
        if st.button("Replay a saved run"):
            needle_box, log_box = st.empty(), st.container(height=320)
            for e in rec_events:
                needle_box.metric("Needle (CPI inflation, year-on-year)", f"{e['needle_after']:.3f}%",
                                  f"after event {e['seq']} of {len(rec_events) - 1}", delta_color="off")
                if e["type"] != "start":
                    mark = {"verified": "✅", "applied": "➡️"}.get(e["verdict"], "❌")
                    where = f" · {e['place']}" if e.get("place") else ""
                    quote = f" “{e['quote_short']}”" if e.get("quote_short") else ""
                    link = f" · [{e['url'][:60]}]({e['url']})" if e.get("url") else ""
                    date = f" · page date {e['page_date']}" if e.get("page_date") else ""
                    log_box.markdown(f"{mark} **{e['item']}**{where} · {e['verdict']}: {e['reason']}{quote}{link}"
                                     f"{date}")
                time.sleep(pause / 2)
            st.caption(f"Played {len(rec_events) - 1} recorded events; final needle {rec_events[-1]['needle_after']:.3f}%"
                       f" (committed run {run['needle']['end']:.3f}%). No call was made.")

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
        altair_chart((base + ticks).properties(height=90), width="stretch")
        st.caption(" · ".join(f"{m['what']} {m['x']:.3f}%" for m in marks))


def pct(x):
    return "0%" if x == 0 else f"{x * 100:+.1f}%"


def jump(step):
    """Display only: the step against the item's own trend, e.g. 'Petrol: 0% change, trend expected a rise of 1.4%
    → −0.067 pp vs. trend' (0 pp when the evidence equals that trend)."""
    if "jump_pp" not in step:
        return ""
    t = step.get("trend_change")
    if t is None:
        return f" · {step['jump_pp']:+.3f} pp vs. trend"
    expected = "no change" if t == 0 else f"a {'rise' if t > 0 else 'fall'} of {abs(t) * 100:.1f}%"
    change = (f"{pct(step['value'])} announced on top of its trend" if step.get("mode") == "add"
              else f"{pct(step.get('value', step.get('change')))} change")
    pp = "0.000" if abs(step["jump_pp"]) < 0.0005 else f"{step['jump_pp']:+.3f}"
    return f" · {step['name']}: {change}, trend expected {expected} → {pp} pp vs. trend"


def draw_tree(done):
    df = pd.DataFrame([{**t, "status": "measured" if t["code"] in done else "on trend",
                        "label": t["name"][:18] if (t["x1"] - t["x0"]) * (t["y1"] - t["y0"]) > 60 else "",
                        "cx": (t["x0"] + t["x1"]) / 2, "cy": (t["y0"] + t["y1"]) / 2} for t in run["tiles"]])
    color = alt.Color("status:N", scale=alt.Scale(domain=["measured", "on trend"], range=["#0f766e", "#5A5A5A"]),
                      legend=alt.Legend(orient="bottom", title=None))
    x, y = alt.Scale(domain=[0, 100], nice=False), alt.Scale(domain=[60, 0], nice=False)
    rects = alt.Chart(df).mark_rect(stroke="#111111", strokeWidth=1).encode(
        x=alt.X("x0:Q", scale=x, axis=None), x2="x1:Q", y=alt.Y("y0:Q", scale=y, axis=None), y2="y1:Q",
        color=color, tooltip=["name", alt.Tooltip("weight:Q", format=".2f", title="CPI weight (%)"), "status"])
    text = alt.Chart(df).mark_text(fontSize=10, color="white").encode(x=alt.X("cx:Q", scale=x),
                                                                      y=alt.Y("cy:Q", scale=y), text="label")
    with tree_box.container():                    # st.empty holds one element: the chart and its table go in one container
        altair_chart((rects + text).properties(height=320, title="The basket by CPI weight"), width="stretch")
        chart_table([{"Group": t["name"], "CPI weight (%)": f"{t['weight']:.2f}", "Status": t["status"]}
                     for t in df.sort_values("weight", ascending=False).to_dict("records")])


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


if any("jump_pp" in s for s in run.get("timeline", run.get("items", []))):
    st.caption("Each step is the item's measured change minus what its own trend expected.")
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
            draw_top(step["yoy_after"], step["measured_after"], f"after {step['name']}" + jump(step))
            draw_tree(done)
    for card in run["cards"]:
        stream(card, f"{card['domain']} · {card['published']}", lambda c=card: card_body(c))
    for step, m in zip(run["timeline"][len(done):], run["moving_events"]):
        done.add(step["cpi_code"])
        draw_top(step["yoy_after"], step["measured_after"], f"after {m['event_kind']} in {m['where']}" + jump(step))
        draw_tree(done)
    ev = [cl for c in run["cards"] for cl in c["claims"] if "status" in cl]
    st.markdown(f"**{sum(c['status'] == 'verified' for c in run['item_cards'])} of {len(run['item_cards'])}** "
                f"government-price and official-series items measured · announced price changes: **{len(run['cards'])}** pages "
                f"proposed, **{len(ev)}** claims checked, **{sum(cl['status'] == 'verified' for cl in ev)}** verified, "
                f"**{len(run['moving_events'])}** moving the number.")
    st.markdown(f"Final: **{run['needle']['end']:.3f}%** (v2, development data) · v1 Shadow CPI "
                f"{run['v1']['c']:.3f}% · official {run['official']:.2f}%.")
    for n in run.get("notes", []):
        st.caption(n)
    if run.get("stages"):
        st.subheader("What Tavily adds")
        what_tavily_adds(run)
    if run.get("time_machine"):
        st.subheader("Time machine")
        time_machine(run)
else:
    draw_top(run["needle"]["start"], None, "trend only")
    for card in run["cards"]:
        stream(card, f"{card['domain']} · {card['published']}", lambda c=card: card_body(c))
    for it in run.get("items", []):
        draw_top(it["yoy_after"], None, f"{it['name']} from the {it['source']}" + jump(it))
        st.markdown(f"Milk moves by the **{it['source']}** ({it['detail']}): {it['change'] * 100:+.3f}%. Verified "
                    "milk events are context only under logged rule change A (government food prices are milk's source; a city event "
                    "with no statewide confirmation moves nothing).")
st.caption(f"Credits for this run: {run['credits_spent']} (budget '{run['credits_budget']}'). Each checked claim, "
           "verified or rejected, is in v2/evidence/ledger.jsonl.")
