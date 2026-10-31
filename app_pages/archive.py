"""Archive: sealed predictions with their JSON, SHA-256, git tag, manifest and (after release) the miss."""
import streamlit as st

from app_pages.common import (NOWCAST_WORDS, header, month_name, months_with, num, path, pct, read_csv, read_json,
                              seal_status)

header("Archive", f"Every sealed {NOWCAST_WORDS}, locked before MoSPI's release. Anyone can recompute the SHA-256 "
                  "of the sealed file and check the git tag date.")

months = months_with("sealed")
if not months:
    st.info("Nothing sealed yet (sealed/<month>.json).")
    st.stop()

official = {r["month"]: r for r in read_csv("data/official_releases.csv")}
scored = {r["month"]: r for r in read_csv("results/archive.csv")}       # written by score.py / tools/score_october.py
for m in months:
    s = read_json(f"sealed/{m}.json")
    stored, actual, ok = seal_status(m)
    off = num(official.get(m, {}).get("official_yoy"))
    st.subheader(month_name(m))
    c1, c2 = st.columns(2)
    c1.metric("Sealed nowcast", pct(s["headline_yoy"]))
    c2.metric("Official", pct(off) if off is not None else "not released yet",
              delta=f"miss {s['headline_yoy'] - off:+.2f} pp" if off is not None else None, delta_color="off")
    st.markdown(f"Range {pct(s['range_low'])} to {pct(s['range_high'])}"
                + (f" · official inside range: **{'yes' if s['range_low'] <= off <= s['range_high'] else 'no'}**"
                   if off is not None else ""))
    row = scored.get(m, {})
    if off is not None and row.get("brier_ge_6", "") != "":
        p_seal, bs = float(row["p_headline_ge_6"]), float(row["brier_ge_6"])
        st.markdown(f"Sealed P(headline ≥ 6.0%): **{p_seal:.2f}**; the official figure is "
                    f"{'at or above' if off >= 6.0 else 'below'} 6.0%, so the Brier score is **{bs:.3f}** "
                    "(0 is perfect; always saying 50% scores 0.250).")
    if off is not None and row.get("main_surprise") and not row["main_surprise"].startswith("waiting"):
        st.caption(f"Main surprise: {row['main_surprise']}")
    st.markdown(f"SHA-256 `{stored}` · check: **{'PASS' if ok else 'FAIL'}**")
    st.markdown(f"Git tag `{s.get('git_tag', 'seal-' + m)}` · sealed `{s.get('sealed_at_utc', '—')}` UTC · "
                f"evidence cutoff `{s.get('evidence_cutoff_utc', '—')}`")
    man = s.get("manifest")
    if man:
        st.markdown(f"Manifest: `{man}`" + ("" if path(man).exists() else " (file not found)"))
    with st.expander("Sealed JSON"):
        st.json(s)
    st.download_button("Download sealed JSON", path(f"sealed/{m}.json").read_bytes(), file_name=f"{m}.json",
                       mime="application/json", key=f"dl-{m}")
    st.divider()

st.caption("Verify yourself: `sha256sum sealed/2026-10.json` must equal the text in `sealed/2026-10.sha256`.")
