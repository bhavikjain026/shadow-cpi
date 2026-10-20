"""Home: countdown, the experimental nowcast with its range, coverage, top contributors, seal, buttons."""
import streamlit as st

from app_pages.common import (NOWCAST_WORDS, countdown_text, header, month_name, next_release, pct, pp,
                              read_csv, read_json, seal_status, tag)

header("Shadow CPI", f"An {NOWCAST_WORDS} of India's next official CPI inflation number (year-on-year, "
                     "2024-series All-India Combined). Not an official statistic.")

# ---------- countdown ----------
rel = next_release()
if rel:
    st.subheader("Next MoSPI release")
    st.metric(f"{month_name(rel['month'])} CPI", countdown_text(rel["left"]))
    st.caption(f"{rel['note']}. Release time 4:00 pm IST.")

# ---------- the number ----------
nc = read_json("results/nowcast_latest.json")
if not nc:
    st.info("No nowcast has been produced yet (results/nowcast_latest.json is missing).")
    st.stop()

month = nc["target_month"]
st.subheader(tag(f"{month_name(month)}: {NOWCAST_WORDS}"))
st.metric(tag("CPI inflation, year-on-year"), pct(nc["headline_yoy"]))
level = int(round(nc.get("range_level", 0.8) * 100))
st.markdown(f"**{level}% range: {pct(nc['range_low'])} to {pct(nc['range_high'])}**")

replay = read_csv("results/replay.csv")
inside = [r for r in replay if r.get("c_inside_range") in ("True", "true", "1")]
if replay:
    n, of = len(inside), len(replay)
else:
    n, of = nc["replay_inside_range"]["n"], nc["replay_inside_range"]["of"]
st.markdown(tag(f"The actual figure was inside the range in **{n} of {of}** replay months"))

# ---------- coverage ----------
st.subheader(tag("Coverage"))
obs = nc["coverage"]["observed"]
st.progress(min(max(obs, 0.0), 1.0), text=f"{obs:.0%} of the basket measured this month, "
                                         f"{nc['coverage']['carried']:.0%} carried on trend")

# ---------- contributors ----------
st.subheader(tag("Top 3 contributors"))
st.caption("Percentage points of the year-on-year rate.")
st.dataframe([{"Group": c["name"], "Contribution": pp(c["pp"])} for c in nc["contributors"][:3]],
             hide_index=True, width="stretch")

# ---------- Tavily attribution ----------
ta = nc.get("tavily_attribution")
if ta:
    st.markdown(tag(
        f"**What Tavily added:** without Tavily evidence the nowcast would be {pct(ta['pred_without_tavily'])} "
        f"with {ta['coverage_without']:.0%} of the basket measured; with it, {pct(ta['pred_with_tavily'])} "
        f"with {ta['coverage_with']:.0%} measured."))

# ---------- seal ----------
st.subheader("Seal")
stored, actual, ok = seal_status(month)
sealed = read_json(f"sealed/{month}.json")
if sealed:
    st.markdown(f"Fingerprint (SHA-256): `{stored}`")
    st.markdown(f"Git tag: `{sealed.get('git_tag', 'seal-' + month)}` · Sealed at (UTC): "
                f"`{sealed.get('sealed_at_utc', '—')}`")
    (st.success if ok else st.error)("Fingerprint check: " + ("PASS - file unchanged since sealing" if ok
                                                              else "FAIL - file does not match its fingerprint"))
else:
    st.info(f"{month_name(month)} is not sealed yet.")


# ---------- buttons ----------
def receipt(r):
    st.caption(f"Receipt: Tavily calls {r['tavily_calls']} · credits {r['credits']} · "
               f"{r['seconds']} seconds · Nemotron calls {r['nemotron_calls']}")


st.subheader("Check it yourself")
c1, c2 = st.columns(2)
prove = c1.button("Try to prove this wrong", width="stretch")
run = c2.button("Run now", width="stretch")

if prove:
    sk = read_json(f"results/skeptic_{month}.json")
    st.info("Live skeptic runs come later. Showing the cached result.")
    if sk:
        st.markdown(tag(f"**Cached skeptic result** from {sk['ran_at_utc']} (UTC)"))
        st.dataframe([{"Contributor": c["contributor"], "Counter-search": c["counter_query"],
                       "Verified contrary quotes": c["contrary_verified_quotes"]} for c in sk["checked"]],
                     hide_index=True, width="stretch")
        st.markdown(("**Range widened by 50%.** " if sk["widened"] else "**Range unchanged.** ") + sk["reason"])
        receipt(sk["receipt"])
    else:
        st.warning("No cached skeptic result for this month yet.")

if run:
    rn = read_json("results/run_now_cached.json")
    st.info("Live runs come later. Showing the cached result.")
    if rn:
        cap = rn.get("daily_cap", 2)
        st.markdown(f"**{cap} live scans left today** (daily cap {cap}; up to ~{rn.get('credit_cap', 20)} "
                    "credits each) - live scans are not switched on yet.")
        st.markdown(tag(f"**Cached event scan** from {rn['ran_at_utc']} (UTC), "
                        f"window {rn['window_start']} to {rn['window_end']}"))
        st.dataframe([{"Item": e["item"], "Place": e["place"], "Change": f"{e['pct_change']:+.1f}%",
                       "Effective": e["effective_date"], "Exact line": e["line"], "Link": e["url"]}
                      for e in rn["events"]],
                     hide_index=True, width="stretch",
                     column_config={"Link": st.column_config.LinkColumn("Link")})
        receipt(rn["receipt"])
    else:
        st.warning("No cached scan yet.")
