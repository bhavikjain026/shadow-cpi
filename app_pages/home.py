"""Home: the October call slot, countdown and P(headline >= 6.0%); the replay scoreboard; the independent audit;
the saved run and the capped "Run live" button. Every number is read from a results file (docs/app_numbers.md)."""
from datetime import datetime, timezone

import streamlit as st

from shadow_cpi.live_range import THRESHOLD

from app_pages.common import (CODES, LABELS, LIVE_MONTH, NOWCAST_WORDS, REPO_URL, SEAL_DATE, countdown_text, header,
                              headline_result, month_name, next_release, pass_fail, pct, poll_direction, poll_months, read_json,
                              seal_status)

header("Experimental nowcast", f"Shadow CPI: an {NOWCAST_WORDS} of India's next official CPI inflation number "
                               "(year-on-year, 2024-series All-India Combined). Not an official statistic.")
st.markdown("**How it works:** Tavily searches the web, with dates locked, for price evidence → Nemotron on Nebius "
            "Token Factory pulls out only quoted, dated prices → plain code turns them into a CPI estimate with a "
            "range, sealed before release.")
lock = read_json("results/score_lock.json")
if lock:
    st.markdown(f"**{headline_result(lock)}**")

# ---------- the October call ----------
sealed = read_json(f"sealed/{LIVE_MONTH}.json")
call = sealed or read_json(f"results/nowcast_{LIVE_MONTH}.json")
with st.container(border=True):
    st.subheader(f"{month_name(LIVE_MONTH)} call")
    if call:
        c1, c2 = st.columns(2)
        c1.metric("CPI inflation, year-on-year", pct(call["headline_yoy"]))
        c2.metric(f"P(headline ≥ {THRESHOLD:.1f}%)", f"{call['p_headline_ge_6']:.0%}" if "p_headline_ge_6" in call else "—")
        st.markdown(f"**80% range: {pct(call['range_low'])} to {pct(call['range_high'])}**")
        cov = call.get("coverage", {})
        if cov:
            st.progress(min(max(cov["observed"], 0.0), 1.0),
                        text=f"{cov['observed']:.0%} of the basket measured, {cov['carried']:.0%} carried on trend")
        if call.get("contributors"):
            st.dataframe([{"Group": c["name"], "Contribution (percentage points)": f"{c['pp']:+.2f}"}
                          for c in call["contributors"][:3]],
                         hide_index=True, width="stretch")
        if sealed:
            stored, _, ok = seal_status(LIVE_MONTH)
            (st.success if ok else st.error)(f"Sealed {sealed.get('sealed_at_utc', '')[:16]} UTC · SHA-256 "
                                             f"`{stored}` · " + ("PASS" if ok else "FAIL"))
        else:
            st.warning(f"Built but not sealed yet: sealing on {SEAL_DATE:%d %b}.")
    else:
        st.markdown(f"**Sealing on {SEAL_DATE:%d %b}.** The number, its 80% range and P(headline ≥ "
                    f"{THRESHOLD:.1f}%) appear here once the call is sealed. {THRESHOLD:.1f}% is the RBI's projection "
                    "for Oct–Dec 2026.")
        c1, c2 = st.columns(2)
        c1.metric("CPI inflation, year-on-year", f"sealing on {SEAL_DATE:%d %b}")
        c2.metric(f"P(headline ≥ {THRESHOLD:.1f}%)", "with the seal")
    rel = next_release()
    if rel:
        st.metric(f"Official {month_name(rel['month'])} CPI in", countdown_text(rel["left"]))
        st.caption(f"MoSPI release: {rel['note']}.")

# ---------- replay scoreboard ----------
st.subheader("Replay scoreboard, January–September 2026")
if lock:
    before = (lock.get("history") or [None])[-1]
    rows = [{"Method": LABELS[k], "Average miss (percentage points)": f"{lock['mae'][k]:.3f}",
             "Before fixes": f"{before['mae'][k]:.3f}" if before else "—",
             "Direction right": f"{lock['direction_hits'][k]} of 9 months"} for k in ("c", "a", "b", "c_strict", "B1")]
    rows.append({"Method": f"Economists' poll (its {poll_months()} dated months)", "Average miss (percentage points)":
                 f"{lock['mae_poll_months']['poll']:.3f}",
                 "Before fixes": f"{before['mae_poll_months']['poll']:.3f}" if before else "—",
                 "Direction right": poll_direction()})
    st.dataframe(rows, hide_index=True, width="stretch")
    st.markdown(f"**{pass_fail(lock)}.** Actual inside the 80% range in {lock['inside_range']} of 9 months.")
    st.caption("Codes: " + ", ".join(f"{LABELS[k]} = {CODES[k]}" for k in ("c", "a", "b", "c_strict", "B1"))
               + f". On the poll's months, Shadow CPI missed by {lock['mae_poll_months']['c']:.3f} pp. Scored once, "
               "then re-scored once after logged bug fixes.")
    st.markdown(f"[Before/after table and every fix]({REPO_URL}/docs/after_scoring_changes.md"
                "#4-amendment-3-bug-fixes-found-by-the-independent-audit-re-scored-once)")
else:
    st.info("No scored replay yet (results/score_lock.json).")

# ---------- independent audit ----------
au = read_json("results/app/audit_summary.json")
if au:
    with st.container(border=True):
        st.subheader("Independent audit")
        v = au["verdicts"]
        st.markdown(f"**{au['events_checked']} events checked** by hand: {v['correct']} correct, {v['partly']} "
                    f"partly, {v['wrong']} wrong, {v['unclear']} unclear; {au['second_source']} confirmed by a "
                    "second source.")
        st.markdown(f"**Fixes made:** {len(au['fixes'])} general rules (retail only, the CPI fuel grade, national "
                    f"vs regional scope, no double counting). Events {au['events_before_fixes']} → "
                    f"{au['events_after_fixes']}.")
        st.markdown(f"**Recall:** {au['found_directly']} of {au['reference_changes']} known retail price changes "
                    f"found directly; {au['found_incl_official_series']} of {au['reference_changes']} including the "
                    "official series (IOCL LPG, PPAC petrol).")
        st.caption(f"[Audit]({REPO_URL}/audit/event_audit.md) · [Recall check]({REPO_URL}/audit/missed_events.md)")

# ---------- saved run and Run live ----------
st.subheader("Latest event scan")
saved = read_json("results/app/saved_run.json")


def show_run(r, note=""):
    if note:
        st.info(note)
    st.markdown(f"**{r['label']}**")
    if r.get("evidence_window"):
        w0, w1 = r["evidence_window"]
        st.caption(f"Evidence window {w0} to {w1} ({month_name(r['month'])}, plus the last {r['pre_days']} days "
                   f"before it for announcements) · replayed from saved results on {r['replayed_on']} · "
                   f"{r['n_searches']} searches · {r['credits']} credits when first run (0 now).")
    if r.get("events"):
        st.dataframe([{"Item": e["item"], "Place": e.get("place", ""), "Change": f"{e['pct_change']:+.2f}%",
                       "Effective": e["effective_date"], "Exact line": e["line"], "Link": e["url"]}
                      for e in r["events"]], hide_index=True, width="stretch",
                     column_config={"Link": st.column_config.LinkColumn("Link")})
    else:
        st.caption("No verified price events in this scan.")
    if r.get("receipt"):
        rc = r["receipt"]
        st.caption(f"Receipt: Tavily calls {rc['tavily_calls']} · credits {rc['credits']} · {rc['seconds']} s · "
                   f"Nemotron calls {rc['nemotron_calls']}" + (f" · {r['stopped']}" if r.get("stopped") else ""))


st.session_state.setdefault("live_runs", 0)
if st.button("Run live (last 7 days)", width="stretch"):
    from shadow_cpi import live_run as L
    ok, msg = L.gate(st.session_state["live_runs"])
    if not ok:
        st.session_state["last_run"] = None
        st.session_state["note"] = msg
    else:
        st.session_state["live_runs"] += 1
        try:
            st.session_state["last_run"] = L.run_live(*L.keys(), now=datetime.now(timezone.utc))
            st.session_state["note"] = ""
        except Exception as e:                         # never an error box: fall back to the saved run
            st.session_state["last_run"] = None
            st.session_state["note"] = f"The live run could not finish ({type(e).__name__}). Showing the saved run."
run = st.session_state.get("last_run")
if run:
    show_run(run)
elif saved:
    show_run(saved, st.session_state.get("note", ""))
else:
    st.info("No saved run yet (results/app/saved_run.json).")
