"""Archive: sealed predictions with their JSON, SHA-256, git tag, manifest and (after release) the miss."""
import streamlit as st

from app_pages.common import NOWCAST_WORDS, header, month_name, months_with, num, path, pct, read_csv, read_json, \
    seal_status, tag

header("Archive", f"Every sealed {NOWCAST_WORDS}, locked before MoSPI's release. Anyone can recompute the SHA-256 "
                  "of the sealed file and check the git tag date.")

months = months_with("sealed")
if not months:
    st.info("Nothing sealed yet (sealed/<month>.json).")
    st.stop()

official = {r["month"]: r for r in read_csv("data/official_releases.csv")}
for m in months:
    s = read_json(f"sealed/{m}.json")
    stored, actual, ok = seal_status(m)
    off = num(official.get(m, {}).get("official_yoy"))
    st.subheader(tag(month_name(m)))
    c1, c2 = st.columns(2)
    c1.metric(tag("Sealed nowcast"), pct(s["headline_yoy"]))
    c2.metric(tag("Official"), pct(off) if off is not None else "not released yet",
              delta=f"miss {s['headline_yoy'] - off:+.2f} pp" if off is not None else None, delta_color="off")
    st.markdown(f"Range {pct(s['range_low'])} to {pct(s['range_high'])}"
                + (f" · official inside range: **{'yes' if s['range_low'] <= off <= s['range_high'] else 'no'}**"
                   if off is not None else ""))
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
