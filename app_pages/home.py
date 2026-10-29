"""Home: the October call slot, countdown and P(headline >= 6.0%); the replay scoreboard; the independent audit;
the saved run and the capped "Run live" button. Every number is read from a results file (docs/app_numbers.md)."""
from datetime import datetime, timezone

import streamlit as st

from shadow_cpi.live_range import THRESHOLD

from app_pages.common import (CODES, LABELS, LIVE_MONTH, NOWCAST_WORDS, REPO_URL, SEAL_DATE, clean_line,
                              RELEASES, countdown_text, header, headline_result, item_label, lead, month_name, next_release,
                              pass_fail, plain_box, pct, poll_direction, poll_months, read_json, seal_status, table,
                              v2_comparison)
from app_pages.v2_panels import what_tavily_adds
from app_pages.provenance import provenance
from app_pages.v3_panel import v3_beside_v1

header("Experimental nowcast", f"Shadow CPI: an {NOWCAST_WORDS} of India's next official CPI inflation number "
                               "(year-on-year, 2024-series All-India Combined).")
lock = read_json("results/score_lock.json")
sealed = read_json(f"sealed/{LIVE_MONTH}.json")
call = sealed or read_json(f"results/nowcast_{LIVE_MONTH}.json")
plain_box([f"This is our estimate of India's official inflation rate for {month_name(LIVE_MONTH)}, made before the government publishes it.",
           "It is locked with a fingerprint (a \"seal\"): if anyone changed it afterwards, the fingerprint would no longer "
           "match, and you can check it yourself.",
           "Read the sentence below for the number and its range; the replay of past months and the technical "
           "detail follow."])
release = next((sched for month, sched, _, _ in RELEASES if month == LIVE_MONTH), None)
if call:
    st.markdown(f"**Our {'sealed ' if sealed else ''}estimate for {month_name(LIVE_MONTH)} is {pct(call['headline_yoy'])} "
                f"(likely range {call['range_low']:.2f}–{call['range_high']:.2f}%)"
                + (f"; the official number comes out on {release.day} {release:%b}." if release else ".") + "**")
if sealed:
    stored, _, ok = seal_status(LIVE_MONTH)
    (st.success if ok else st.error)(f"Sealed {sealed.get('sealed_at_utc', '')[:16]} UTC · SHA-256 "
                                     f"`{stored}` · " + ("PASS" if ok else "FAIL"))
    with st.expander("How to check the seal yourself"):
        raw = f"https://raw.githubusercontent.com/bhavikjain026/shadow-cpi/seal-{LIVE_MONTH}/sealed/{LIVE_MONTH}"
        st.markdown(f"1. Save the sealed file and its fingerprint exactly as tagged: [{LIVE_MONTH}.json]({raw}.json) and "
                    f"[{LIVE_MONTH}.sha256]({raw}.sha256) (don't open and re-save the .json).\n"
                    f"2. Recompute the fingerprint: `shasum -a 256 {LIVE_MONTH}.json` (Mac), `sha256sum {LIVE_MONTH}.json` "
                    f"(Linux) or `Get-FileHash {LIVE_MONTH}.json -Algorithm SHA256` (Windows).\n"
                    f"3. Same code as in the .sha256 file → PASS; different → FAIL. The git tag `seal-{LIVE_MONTH}` and "
                    f"GitHub's push record show when it was locked.")
        st.caption("The seal proves when the forecast was committed, not what was read before it; the time lock and "
                   "extract_as_of address the evidence. Full steps: verify.md in the repository. Before the seal the links "
                   "open once the tag exists.")
elif call:
    st.warning(f"Built but not sealed yet: sealing on {SEAL_DATE:%d %b}.")
st.caption("Plain meanings: **nowcast** = an estimate of the current month made before the official figure is out; "
           "**seal** = the estimate saved with a digital fingerprint (**SHA-256**, a code worked out from the file's exact "
           "contents) and a dated git tag, so a later change would show; **likely range** = where we expect the official "
           "number to fall four times out of five; **basket coverage** = the share of the goods and services in the index "
           "that we measured directly rather than assumed to follow their recent trend.")
st.markdown("**How it works:** Tavily searches the web, with dates locked, for price evidence → Nemotron on Nebius "
            "Token Factory pulls out only quoted, dated prices → plain code turns them into a CPI estimate with a "
            "range, sealed before release.")
st.page_link("app_pages/field_report.py", label="Tavily field report",
             icon=":material/science:")

# ---------- the October call ----------
with st.container(border=True):
    st.subheader(f"{month_name(LIVE_MONTH)} call")
    if call:
        c1, c2 = st.columns(2)
        c1.metric("CPI inflation, year-on-year", pct(call["headline_yoy"]))
        c2.metric(f"P(headline ≥ {THRESHOLD:.1f}%)", f"{call['p_headline_ge_6']:.0%}" if "p_headline_ge_6" in call else "—",
                  help=f"Our estimated chance that the official figure comes in at {THRESHOLD:.1f}% or higher; "
                       f"{THRESHOLD:.1f}% is the RBI's projection for the quarter, used as a yardstick.")
        st.markdown(f"**80% range: {pct(call['range_low'])} to {pct(call['range_high'])}**")
        cov = call.get("coverage", {})
        if cov:
            st.progress(min(max(cov["observed"], 0.0), 1.0),
                        text=f"{cov['observed']:.0%} of the basket measured, {cov['carried']:.0%} assumed to follow its recent trend")
        if call.get("contributors"):
            lead("The three groups of goods and services that add most to the estimate, in percentage points of inflation.")
            table([{"Group": c["name"], "Contribution (percentage points)": f"{c['pp']:+.2f}"}
                          for c in call["contributors"][:3]])
        if sealed:                             # a statement, not a bare conditional: Streamlit would print its None
            provenance(f"sealed/{LIVE_MONTH}.json", "sealed_at_utc")
        else:
            provenance(f"results/nowcast_{LIVE_MONTH}.json")
    else:                                      # compact status banner until the seal
        rel = next_release()
        c1, c2, c3 = st.columns(3)
        c1.metric("CPI inflation, year-on-year", f"sealing on {SEAL_DATE:%d %b}")
        c2.metric(f"P(headline ≥ {THRESHOLD:.1f}%)", "with the seal")
        if rel:
            c3.metric(f"Official {month_name(rel['month'])} CPI in", countdown_text(rel["left"]))
        st.caption(f"The number, its 80% range and P(headline ≥ {THRESHOLD:.1f}%) appear here once sealed; "
                   f"{THRESHOLD:.1f}% is the RBI's quarterly projection for Oct–Dec 2026, not a forecast for October."
                   + (f" MoSPI release: {rel['note']}." if rel else ""))
    if sealed or call:
        rel = next_release()
        if rel:
            st.metric(f"Official {month_name(rel['month'])} CPI in", countdown_text(rel["left"]))
            st.caption(f"MoSPI release: {rel['note']}.")
v3_beside_v1(LIVE_MONTH)

# ---------- replay scoreboard ----------
st.subheader("Replay scoreboard, January–September 2026")
lead("How would the method have done on past months? Each row is a method run on January–September 2026; a smaller "
     "average miss (in percentage points of inflation) is better, and the economists' poll row is the comparison.")
if lock:
    m1, m2, m3 = st.columns(3)
    m1.metric(f"{LABELS['c']}: average miss", f"{lock['mae']['c']:.3f} pp", help="Replay, Jan–Sep 2026")
    m2.metric(f"{LABELS['a']}: average miss", f"{lock['mae']['a']:.3f} pp", help="Replay, Jan–Sep 2026")
    m3.metric(f"Poll months: {LABELS['c']} vs poll",
              f"{lock['mae_poll_months']['c']:.3f} vs {lock['mae_poll_months']['poll']:.3f}",
              help=f"The {poll_months()} months with a published economists' poll")
    st.caption(f"{headline_result(lock)} Source: `results/score_lock.json`.")
    provenance("results/score_lock.json", "scored_at_utc")
    before = (lock.get("history") or [None])[-1]
    rows = [{"Method": LABELS[k], "Average miss (percentage points)": f"{lock['mae'][k]:.3f}",
             "Before fixes": f"{before['mae'][k]:.3f}" if before else "—",
             "Direction right": f"{lock['direction_hits'][k]} of 9 months"} for k in ("c", "a", "b", "c_strict", "B1")]
    rows.append({"Method": f"Economists' poll (its {poll_months()} dated months)", "Average miss (percentage points)":
                 f"{lock['mae_poll_months']['poll']:.3f}",
                 "Before fixes": f"{before['mae_poll_months']['poll']:.3f}" if before else "—",
                 "Direction right": poll_direction()})
    table(rows)
    st.markdown(f"**{pass_fail(lock)}.** Actual inside the 80% range in {lock['inside_range']} of 9 months.")
    st.caption("Codes: " + ", ".join(f"{LABELS[k]} = {CODES[k]}" for k in ("c", "a", "b", "c_strict", "B1"))
               + f". On the poll's months, Shadow CPI missed by {lock['mae_poll_months']['c']:.3f} pp. Scored once, "
               "then re-scored once after logged bug fixes.")
    st.markdown(f"[Before/after table and every fix]({REPO_URL}/docs/after_scoring_changes.md"
                "#4-amendment-3-bug-fixes-found-by-the-independent-audit-re-scored-once)")
    v2_comparison()
else:
    st.info("No scored replay yet (results/score_lock.json).")

with st.expander("Details for experts: the independent audit and the v2 experiment"):
    # ---------- independent audit ----------
    au = read_json("results/app/audit_summary.json")
    if au:
        with st.container(border=True):
            st.subheader("Independent audit")
            v = au["verdicts"]
            st.markdown(f"**{au['events_checked']} events checked** (AI-assisted audit; pages then opened in a browser): "
                        f"{v['correct']} correct, {v['partly']} partly, {v['wrong']} wrong, {v['unclear']} unclear; "
                        f"{au['second_source']} of {au['events_checked']} confirmed by another outlet (the audit's web search).")
            st.markdown(f"**Fixes made:** {len(au['fixes'])} general rules (retail only, the CPI fuel grade, national "
                        f"vs regional scope, no double counting). Events {au['events_before_fixes']} → "
                        f"{au['events_after_fixes']} (events dropped or merged by the fixes).")
            st.markdown(f"**Recall:** {au['found_directly']} of {au['reference_changes']} known retail price changes "
                        f"found directly; {au['found_incl_official_series']} of {au['reference_changes']} including the "
                        "official series (IOCL LPG, PPAC petrol).")
            st.caption(f"[Audit]({REPO_URL}/audit/event_audit.md) · [Recall check]({REPO_URL}/audit/missed_events.md)")

    # ---------- v2 (in development): what Tavily adds ----------
    v2run = read_json("v2/evidence/run_2026-09_basket.json")
    if v2run and v2run.get("stages"):
        with st.container(border=True):
            st.subheader("What Tavily adds (v2, September 2026)")
            what_tavily_adds(v2run)
            st.caption("v2 is in development (v2/PREREGISTRATION.md): September is development data, not a scored result. "
                       "See the Live build page.")

with st.expander("Details for experts: the latest event scan and the capped live run"):
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
                       f"{r['n_searches']} searches · {r['credits']} credits when originally run (0 now).")
        if r.get("events"):
            table([{"Item": item_label(e["item"]), "Source": e["url"], "Place": e.get("place", ""),
                           "Change": f"{e['pct_change']:+.2f}%", "Effective": e["effective_date"],
                           "Exact line": clean_line(e["line"])} for e in r["events"]], show=["Item", "Source", "Change", "Effective", "Exact line"])
        else:
            st.caption("No verified price events in this scan.")
        if r.get("receipt"):
            rc = r["receipt"]
            st.caption(f"Receipt: Tavily calls {rc['tavily_calls']} · credits {rc['credits']} · {rc['seconds']} s · "
                       f"Nemotron calls {rc['nemotron_calls']}" + (f" · {r['stopped']}" if r.get("stopped") else "")
                       + (f" · models {', '.join(r['models'])}{r.get('models_note', '')}" if r.get("models") else ""))


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
