"""v2 panels shared by the Live build page and Home. Every number comes from the saved run
(v2/evidence/run_<month>_basket.json, written by `python -m v2.basket`)."""
import altair as alt
import pandas as pd
import streamlit as st

TIME_LABEL = "retrospective replay: today's pages, filtered by their publish dates"


def what_tavily_adds(run):
    """Issue 8: the needle with the spine only, + official series (Tavily Extract), + events (Tavily Search), with the
    official figure marked."""
    adds = run.get("adds")                          # display only: each stage's jumps, then the carve-out
    if adds:
        level, stages = adds["start"], [{"label": "Trend only (everything on its trend)", "yoy": adds["start"]}]
        for b in adds["bars"]:
            level += b["pp"]
            stages.append({"label": b["label"], "yoy": level})
    else:
        stages = run["stages"]
    rows = [{"Stage": s["label"], "CPI inflation, year-on-year (%)": s["yoy"], "order": i}
            for i, s in enumerate(stages)]
    df = pd.DataFrame(rows)
    vals = list(df["CPI inflation, year-on-year (%)"]) + [run["official"], run["v1"]["c"]]
    x = alt.Scale(domain=[min(vals) - 0.15, max(vals) + 0.1], nice=False)
    xt = "CPI inflation, year-on-year (%)"
    bars = alt.Chart(df).mark_bar(color="#4C8DF6", size=24, clip=True).encode(
        y=alt.Y("Stage:N", sort=list(df["Stage"]), title=None, axis=alt.Axis(labelLimit=340, labelOverlap=False)),
        x=alt.X("CPI inflation, year-on-year (%):Q", scale=x, title=xt),
        tooltip=["Stage", alt.Tooltip("CPI inflation, year-on-year (%):Q", format=".3f")])
    labels = bars.mark_text(align="left", dx=4, color="#DDDDDD").encode(
        text=alt.Text("CPI inflation, year-on-year (%):Q", format=".2f"))
    marks = pd.DataFrame([{"x": run["official"], "what": f"Official {run['official']:.2f}%"},
                          {"x": run["v1"]["c"], "what": f"v1 Shadow CPI {run['v1']['c']:.2f}%"}])
    rules = alt.Chart(marks).mark_rule(strokeWidth=3, strokeDash=[6, 3]).encode(
        x=alt.X("x:Q", scale=x, title=xt), color=alt.Color("what:N", scale=alt.Scale(range=["#F28E2B", "#9A9A9A"]),
                                                legend=alt.Legend(orient="bottom", title=None)))
    st.altair_chart((bars + labels + rules).properties(height=210).configure_axisY(labelPadding=6),
                    width="stretch")
    if adds:
        b = adds["bars"]
        st.caption(f"Trend only {adds['start']:.3f}%; government spine {b[0]['pp']:+.3f} pp; official series via "
                   f"Tavily Extract {b[1]['pp']:+.3f} pp; announced changes via Tavily Search {b[2]['pp']:+.3f} pp; "
                   f"carving measured items out of their groups {b[3]['pp']:+.3f} pp; final {adds['end']:.3f}%. Each "
                   f"step counts against the item's own trend, so evidence equal to that trend adds 0. Official figure "
                   f"{run['official']:.2f}%. v2 on development data ({run['month']}, cutoff {run['cutoff']}).")
    else:
        s = run["stages"]
        st.caption(f"Spine only {s[0]['yoy']:.3f}% → with official series {s[1]['yoy']:.3f}% → with announced "
                   f"changes {s[2]['yoy']:.3f}%. Official figure {run['official']:.2f}%. v2 on development data "
                   f"({run['month']}, cutoff {run['cutoff']}).")


def time_machine(run, key="tm"):
    """Issue 3: a slider over the month's days; the needle uses only evidence published by that day."""
    tm = run["time_machine"]
    days = [r["date"] for r in tm]
    st.caption(f"**Time machine: {TIME_LABEL}.** Official series use their daily rows up to the chosen day, "
               "announced price changes count from the day their page was published, and the government spine "
               "(a monthly average with no daily prices) enters only on the cutoff day.")
    day = st.select_slider("Date", options=days, value=days[-1], key=key)
    row = next(r for r in tm if r["date"] == day)
    c1, c2, c3 = st.columns(3)
    c1.metric("CPI inflation, year-on-year", f"{row['yoy']:.3f}%")
    c2.metric("Basket measured from evidence", f"{row['measured']:.1%}")
    c3.metric("Ledger records published by then", row["n_ledger_records"])
    df = pd.DataFrame(tm)
    y = alt.Scale(domain=[min(list(df["yoy"]) + [run["official"]]) - 0.1,
                          max(list(df["yoy"]) + [run["official"]]) + 0.1], nice=False)
    line = alt.Chart(df).mark_line(point=True, color="#4C8DF6").encode(
        x=alt.X("date:T", title=None), y=alt.Y("yoy:Q", scale=y, title="CPI inflation, year-on-year (%)"),
        tooltip=["date", alt.Tooltip("yoy:Q", format=".3f"), alt.Tooltip("measured:Q", format=".1%")])
    official = alt.Chart(pd.DataFrame([{"y": run["official"], "what": f"Official {run['official']:.2f}%"}])).mark_rule(
        color="#F28E2B", strokeWidth=3, strokeDash=[6, 3]).encode(y="y:Q", tooltip=["what"])
    cursor = alt.Chart(pd.DataFrame([{"date": day}])).mark_rule(color="#DDDDDD").encode(x="date:T")
    st.altair_chart((line + official + cursor).properties(height=260, title="Convergence"), width="stretch")
