"""Replay: Jan-Sep 2026 scoreboard against 'repeat last month', 'trend only' and the economists' poll; chart; one miss
explained. Plain labels on screen; the short codes (a)/(b)/(c)/B1 only in small text."""
import math

import altair as alt
import pandas as pd
import streamlit as st

from app_pages.common import (CODES, LABELS, NOWCAST_WORDS, header, month_name, num, pass_fail, pct, poll_direction,
                              read_csv, read_json)

header("Replay", f"How the {NOWCAST_WORDS} would have done in January-September 2026, using only evidence "
                 "available before each month's cutoff. Rules were frozen before scoring. After scoring we made only "
                 "logged bug fixes, found by an independent audit, and we show the scores before and after.")

replay = read_csv("results/replay.csv")
base = {r["month"]: r for r in read_csv("results/baselines.csv")}
if not replay:
    st.info("No replay results yet (results/replay.csv).")
    st.stop()

MODELS = [(LABELS["c"], "c_tavily_pred"), (LABELS["a"], "a_trend_pred"), (LABELS["b"], "b_spine_pred")]


def row_preds(r):
    b = base.get(r["month"], {})
    out = {name: num(r[col]) for name, col in MODELS}
    out[LABELS["B1"]] = num(b.get("b1_pred"))
    out["Economists' poll"] = num(b.get("poll_pred"))
    return out


lock = read_json("results/score_lock.json")
st.subheader("Scoreboard")
if lock:
    before = (lock.get("history") or [None])[-1]
    st.dataframe([{"Method": LABELS[k], "Average miss (percentage points)": f"{lock['mae'][k]:.3f}",
                   "Before fixes": f"{before['mae'][k]:.3f}" if before else "—",
                   "Direction right": f"{lock['direction_hits'][k]} of 9 months"}
                  for k in ("c", "a", "b", "c_strict", "B1")]
                 + [{"Method": "Economists' poll (its dated months only)",
                     "Average miss (percentage points)": f"{lock['mae_poll_months']['poll']:.3f}",
                     "Before fixes": f"{before['mae_poll_months']['poll']:.3f}" if before else "—",
                     "Direction right": poll_direction()}],
                 hide_index=True, width="stretch")
    st.markdown(f"**{pass_fail(lock)}.**")
    st.caption("From results/score_lock.json (the scoring run). Direction = up or down versus the previous month's "
               f"official rate, as pre-registered. On the poll's months Shadow CPI missed by "
               f"{lock['mae_poll_months']['c']:.3f} pp. Codes: "
               + ", ".join(f"{LABELS[k]} = {CODES[k]}" for k in ("c", "a", "b", "c_strict", "B1")) + ".")
inside = sum(r.get("c_inside_range") in ("True", "true", "1") for r in replay)
st.markdown(f"80% range for Shadow CPI: actual inside in **{inside} of {len(replay)}** months")

# ---------- chart ----------
st.subheader("Predicted vs actual")
others = st.checkbox("Show other methods", value=False)
MON = [month_name(r["month"])[:3] for r in replay]
long = []
for r in replay:
    for name, val in [("Actual (official)", num(r["actual_yoy"]))] + list(row_preds(r).items()):
        if val is None or name == "Economists' poll":
            continue
        if others or name in ("Actual (official)", LABELS["c"]):
            long.append({"Month": month_name(r["month"])[:3], "Series": name, "YoY": val})
df = pd.DataFrame(long)
band = pd.DataFrame([{"Month": month_name(r["month"])[:3], "low": num(r["c_range_low"]),
                      "high": num(r["c_range_high"])} for r in replay])
x = alt.X("Month:O", sort=MON, title=None, axis=alt.Axis(labelAngle=0))
y_title = "CPI inflation, year-on-year (%)"
# y-axis padded so the top of the band is not clipped: data and band ± 0.25, rounded out to half points
vals = list(df["YoY"]) + list(band["low"]) + list(band["high"])
y_scale = alt.Scale(domain=[math.floor((min(vals) - 0.25) * 2) / 2, math.ceil((max(vals) + 0.25) * 2) / 2], nice=False)
ACTUAL = "Actual (official)"
# colours that read on light and dark backgrounds: Actual orange and thick, Shadow CPI blue with its band
palette = {ACTUAL: "#F28E2B", LABELS["c"]: "#4C8DF6", LABELS["a"]: "#9A9A9A", LABELS["b"]: "#2CA58D",
           LABELS["B1"]: "#C774B0"}
series = list(dict.fromkeys(df["Series"]))
color = alt.Color("Series:N", scale=alt.Scale(domain=series, range=[palette.get(n, "#9A9A9A") for n in series]),
                  legend=alt.Legend(orient="bottom", columns=2, title=None, symbolStrokeWidth=4, symbolSize=120))
y = alt.Y("YoY:Q", title=y_title, scale=y_scale)
tip = ["Month", "Series", alt.Tooltip("YoY:Q", format=".2f")]
band_layer = alt.Chart(band).mark_area(opacity=0.22, color=palette[LABELS["c"]]).encode(
    x=x, y=alt.Y("low:Q", title=y_title, scale=y_scale), y2="high:Q")
methods = alt.Chart(df[df["Series"] != ACTUAL]).mark_line(
    strokeWidth=2.5, point=alt.OverlayMarkDef(filled=True, size=45)).encode(x=x, y=y, color=color, tooltip=tip)
actual = alt.Chart(df[df["Series"] == ACTUAL]).mark_line(
    strokeWidth=4.5, point=alt.OverlayMarkDef(filled=True, size=110)).encode(x=x, y=y, color=color, tooltip=tip)
chart = (band_layer + methods + actual).properties(height=340)
st.altair_chart(chart, width="stretch")
st.caption("Shaded band = 80% range for Shadow CPI.")

# ---------- per-month ----------
with st.expander("Per-month table"):
    st.dataframe([{"Month": r["month"], "Actual": pct(num(r["actual_yoy"])),
                   **{k: pct(v) for k, v in row_preds(r).items()},
                   "Range (Shadow CPI)": f"{pct(num(r['c_range_low']))} to {pct(num(r['c_range_high']))}",
                   "Measured share (Shadow CPI)": f"{num(r['c_coverage_observed']):.0%}"} for r in replay],
                 hide_index=True, width="stretch")

# ---------- one miss explained ----------
noted = [r for r in replay if r.get("note")]
worst = max(noted or replay, key=lambda r: abs(num(r["c_tavily_pred"]) - num(r["actual_yoy"])))
st.subheader(f"One miss explained: {month_name(worst['month'])}")
miss = num(worst["c_tavily_pred"]) - num(worst["actual_yoy"])
st.markdown(f"Shadow CPI said {pct(num(worst['c_tavily_pred']))}; the official figure was "
            f"{pct(num(worst['actual_yoy']))}. Shadow CPI came in {abs(miss):.2f} percentage points too "
            f"{'low' if miss < 0 else 'high'}.")
st.markdown(worst.get("note") or "No explanation written yet.")

# ---------- (c) vs (b) honestly ----------
attr = read_csv("results/tavily_attribution.csv")
if attr:
    st.subheader("What Tavily evidence changed, month by month")
    st.dataframe([{"Month": a["month"], "Without Tavily": pct(num(a["pred_without_tavily"])),
                   "With Tavily": pct(num(a["pred_with_tavily"])), "Actual": pct(num(a["actual_yoy"])),
                   "Coverage without": f"{num(a['coverage_without']):.0%}",
                   "Coverage with": f"{num(a['coverage_with']):.0%}"} for a in attr],
                 hide_index=True, width="stretch")
