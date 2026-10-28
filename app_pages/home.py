"""Home: the October call slot, countdown and P(headline >= 6.0%); the replay scoreboard; the independent audit;
the saved run and the capped "Run live" button. Every number is read from a results file (docs/app_numbers.md)."""
from datetime import datetime, timezone

import streamlit as st

from shadow_cpi.live_range import THRESHOLD

from app_pages.common import (CODES, LABELS, LIVE_MONTH, NOWCAST_WORDS, REPO_URL, SEAL_DATE, clean_line,
                              countdown_text, header, headline_result, item_label, month_name, next_release,
                              pass_fail, pct, poll_direction, poll_months, read_json, seal_status, table,
                              v2_comparison)
from app_pages.v2_panels import what_tavily_adds
from app_pages.provenance import provenance
from app_pages.v3_panel import v3_beside_v1

header("Experimental nowcast", f"Shadow CPI: an {NOWCAST_WORDS} of India's next official CPI inflation number "
                               "(year-on-year, 2024-series All-India Combined).")
lock = read_json("results/score_lock.json")
if lock:
    m1, m2, m3 = st.columns(3)
    m1.metric(f"{LABELS['c']}: average miss", f"{lock['mae']['c']:.3f} pp", help="Replay, Jan–Sep 2026")
    m2.metric(f"{LABELS['a']}: average miss", f"{lock['mae']['a']:.3f} pp", help="Replay, Jan–Sep 2026")
    m3.metric(f"Poll months: {LABELS['c']} vs poll",
              f"{lock['mae_poll_months']['c']:.3f} vs {lock['mae_poll_months']['poll']:.3f}",
              help=f"The {poll_months()} months with a published economists' poll")
    st.caption(f"{headline_result(lock)} Source: `results/score_lock.json`.")
    provenance("results/score_lock.json")
st.markdown("**How it works:** Tavily searches the web, with dates locked, for price evidence → Nemotron on Nebius "
            "Token Factory pulls out only quoted, dated prices → plain code turns them into a CPI estimate with a "
            "range, sealed before release.")
st.page_link("app_pages/field_report.py", label="Tavily field report",
             icon=":material/science:")

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
                        text=f"{cov['observed']:.0%} of the basket measured, {cov['carried']:.0%} assumed to follow its recent trend")
        if call.get("contributors"):
            table([{"Group": c["name"], "Contribution (percentage points)": f"{c['pp']:+.2f}"}
                          for c in call["contributors"][:3]])
        if sealed:
            stored, _, ok = seal_status(LIVE_MONTH)
            (st.success if ok else st.error)(f"Sealed {sealed.get('sealed_at_utc', '')[:16]} UTC · SHA-256 "
                                             f"`{stored}` · " + ("PASS" if ok else "FAIL"))
        else:
            st.warning(f"Built but not sealed yet: sealing on {SEAL_DATE:%d %b}.")
        provenance(f"sealed/{LIVE_MONTH}.json" if sealed else f"results/nowcast_{LIVE_MONTH}.json")
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
with st.expander("How to check the seal yourself"):
    raw = f"https://raw.githubusercontent.com/bhavikjain026/shadow-cpi/seal-{LIVE_MONTH}/sealed/{LIVE_MONTH}"
    st.markdown(f"1. Save the sealed file and its fingerprint exactly as tagged: [{LIVE_MONTH}.json]({raw}.json) and "
                f"[{LIVE_MONTH}.sha256]({raw}.sha256) (don't open and re-save the .json).\n"
                f"2. Recompute the fingerprint: `shasum -a 256 {LIVE_MONTH}.json` (Mac), `sha256sum {LIVE_MONTH}.json` "
                f"(Linux) or `Get-FileHash {LIVE_MONTH}.json -Algorithm SHA256` (Windows).\n"
                f"3. Same code as in the .sha256 file → PASS; different → FAIL. The git tag `seal-{LIVE_MONTH}` and "
                f"GitHub's push record show when it was locked.")
    st.caption("Full steps: verify.md in the repository. Before the seal the links open once the tag exists.")
v3_beside_v1(LIVE_MONTH)

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
