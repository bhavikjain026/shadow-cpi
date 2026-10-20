"""Replay: Jan-Sep 2026 three-way scoreboard vs B1 and the economists' poll; chart; one miss explained."""
import altair as alt
import pandas as pd
import streamlit as st

from app_pages.common import NOWCAST_WORDS, header, month_name, num, pct, read_csv, tag

header("Replay", f"How the {NOWCAST_WORDS} would have done in January-September 2026, using only evidence "
                 "available before each month's cutoff. These test months were never used to tune anything.")

replay = read_csv("results/replay.csv")
base = {r["month"]: r for r in read_csv("results/baselines.csv")}
if not replay:
    st.info("No replay results yet (results/replay.csv).")
    st.stop()

MODELS = [("(a) Trend only", "a_trend_pred"), ("(b) Government price spine only", "b_spine_pred"),
          ("(c) Spine + Tavily evidence", "c_tavily_pred")]


def row_preds(r):
    b = base.get(r["month"], {})
    out = {name: num(r[col]) for name, col in MODELS}
    out["B1 (last month's rate)"] = num(b.get("b1_pred"))
    out["Economists' poll"] = num(b.get("poll_pred"))
    return out


def score(name):
    misses, hits, n_dir = [], 0, 0
    for r in replay:
        actual, pred = num(r["actual_yoy"]), row_preds(r)[name]
        prev = num(base.get(r["month"], {}).get("b1_pred"))  # B1 = last published rate, so it is the previous actual
        if actual is None or pred is None:
            continue
        misses.append(abs(pred - actual))
        if prev is not None and name != "B1 (last month's rate)" and actual != prev:
            n_dir += 1
            hits += (pred - prev > 0) == (actual - prev > 0)
    return {"Method": name, "Months": len(misses),
            "Mean absolute miss": f"{sum(misses) / len(misses):.2f} pp" if misses else "—",
            "Direction right": f"{hits} of {n_dir}" if n_dir else "n/a"}


names = [m[0] for m in MODELS] + ["B1 (last month's rate)", "Economists' poll"]
st.subheader(tag("Scoreboard"))
st.dataframe([score(n) for n in names], hide_index=True, width="stretch")
st.caption("Poll is scored only on months with a dated source article. Direction = up or down versus the previous "
           "month's official rate (B1 always predicts no change, so it has no direction score).")

inside = sum(r.get("c_inside_range") in ("True", "true", "1") for r in replay)
st.markdown(tag(f"80% range for (c): actual inside in **{inside} of {len(replay)}** months"))

# ---------- chart ----------
st.subheader(tag("Predicted vs actual"))
long = []
for r in replay:
    for name, val in [("Actual (official)", num(r["actual_yoy"]))] + list(row_preds(r).items()):
        if val is not None and name != "Economists' poll":
            long.append({"Month": r["month"] + "-01", "Series": name, "YoY %": val})
df = pd.DataFrame(long)
band = pd.DataFrame([{"Month": r["month"] + "-01", "low": num(r["c_range_low"]), "high": num(r["c_range_high"])}
                     for r in replay])
chart = (alt.Chart(band).mark_area(opacity=0.2).encode(x=alt.X("Month:T", title=None), y="low:Q", y2="high:Q")
         + alt.Chart(df).mark_line(point=True).encode(
             x="Month:T", y=alt.Y("YoY %:Q", scale=alt.Scale(zero=False)),
             color=alt.Color("Series:N", legend=alt.Legend(orient="bottom", columns=2)))).properties(height=340)
st.altair_chart(chart, width="stretch")
st.caption("Shaded band = 80% range for (c).")

# ---------- per-month ----------
with st.expander(tag("Per-month table")):
    st.dataframe([{"Month": r["month"], "Actual": pct(num(r["actual_yoy"])),
                   **{k: pct(v) for k, v in row_preds(r).items()},
                   "Range (c)": f"{pct(num(r['c_range_low']))} to {pct(num(r['c_range_high']))}",
                   "Coverage (c)": f"{num(r['c_coverage_observed']):.0%}"} for r in replay],
                 hide_index=True, width="stretch")

# ---------- one miss explained ----------
noted = [r for r in replay if r.get("note")]
worst = max(noted or replay, key=lambda r: abs(num(r["c_tavily_pred"]) - num(r["actual_yoy"])))
st.subheader(tag(f"One miss explained: {month_name(worst['month'])}"))
miss = num(worst["c_tavily_pred"]) - num(worst["actual_yoy"])
st.markdown(f"Nowcast (c) {pct(num(worst['c_tavily_pred']))} vs official {pct(num(worst['actual_yoy']))} "
            f"- missed by {miss:+.2f} pp.")
st.markdown(worst.get("note") or "No explanation written yet.")

# ---------- (c) vs (b) honestly ----------
attr = read_csv("results/tavily_attribution.csv")
if attr:
    st.subheader(tag("What Tavily evidence changed, month by month"))
    st.dataframe([{"Month": a["month"], "Without Tavily": pct(num(a["pred_without_tavily"])),
                   "With Tavily": pct(num(a["pred_with_tavily"])), "Actual": pct(num(a["actual_yoy"])),
                   "Coverage without": f"{num(a['coverage_without']):.0%}",
                   "Coverage with": f"{num(a['coverage_with']):.0%}"} for a in attr],
                 hide_index=True, width="stretch")
