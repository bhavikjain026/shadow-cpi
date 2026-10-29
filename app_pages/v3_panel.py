"""v3 beside v1 on Home: experimental, never instead of v1 (v3/PREREG.md). v3 numbers are shown only when v3 really was
sealed (sealed/<month>.v3.json, sealed/<month>.bundle.sha256 and the git tag seal-<month>-bundle all exist); otherwise
the panel says it was not sealed. Jan-Sep comes from results/v3_retrospective.json, shown as retrospective only."""
import subprocess

import streamlit as st

from shadow_cpi.live_range import THRESHOLD

from app_pages.common import month_name, path, pct, read_json

NAMES = {"v3a": "v3a (tier-weighted evidence)", "v3b": "v3b (equal-weight average of trend, government prices and v1)"}


def _range(x):
    return "unbounded at 80%" if x.get("range_low") is None else f"{pct(x['range_low'])} to {pct(x['range_high'])}"


NOT_SEALED = ("v3 (experimental) was not sealed for October: its build check counted the radar's data files as code "
              "changes; per the pre-registration, v1 stands alone.")


def _tag_exists(tag):
    try:
        return subprocess.run(["git", "rev-parse", "-q", "--verify", f"refs/tags/{tag}"], cwd=path("."),
                              capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False                                   # no git here: v3 cannot be shown as sealed


def v3_sealed(month):
    """True only when the v3 file, the bundle hash and the bundle's git tag all exist."""
    return (path(f"sealed/{month}.v3.json").exists() and path(f"sealed/{month}.bundle.sha256").exists()
            and _tag_exists(f"seal-{month}-bundle"))


def v3_beside_v1(month):
    sealed = read_json(f"sealed/{month}.v3.json") if v3_sealed(month) else None
    call = sealed
    retro = read_json("results/v3_retrospective.json")
    with st.container(border=True):
        st.subheader(f"Experimental v3, beside v1 ({month_name(month)})")
        st.caption("Experimental: shown next to v1's call above, never instead of it. v3a is v3's main number. "
                   "Rules fixed before any v3 number existed: `v3/PREREG.md`.")
        if call:
            c1, c2 = st.columns(2)
            for col, m in ((c1, "v3a"), (c2, "v3b")):
                x = call[m]
                col.metric(NAMES[m], pct(x["yoy"]))
                col.markdown(f"80% range: {_range(x)}")
                if x.get("p_headline_ge_6") is not None:
                    col.caption(f"P(headline ≥ {THRESHOLD:.1f}%): {x['p_headline_ge_6']:.0%} (from a normal-error model)")
            st.caption(f"Ranges {call['range_label']} (split conformal). Sealed with v1 in one hash bundle "
                       f"(`sealed/{month}.bundle.sha256`).")
        else:
            st.markdown(NOT_SEALED)
            st.caption("Logged in `docs/after_scoring_changes.md`, section 11; the retrospective below is not a forecast.")
        if retro:
            with st.expander("Jan–Sep 2026: retrospective, not a test"):
                st.caption(f"{retro['label'].capitalize()}: v3 was designed after v1's Jan–Sep scores were public, "
                           "and its ranges are calibrated on these same months, so the Jan–Sep hit rate is not a test.")
                st.dataframe([{"Month": month_name(mm), "Official": pct(r["official"]),
                               **{m: pct(retro["methods"][m]["months"][mm]["pred"]) for m in ("v3a", "v3b")},
                               "v1": pct(retro["v1_c"][mm])} for mm, r in retro["methods"]["v3a"]["months"].items()],
                             hide_index=True, width="stretch")
                st.caption(" · ".join(f"{m}: average miss {retro['methods'][m]['mean_abs_miss']:.3f} pp, 80% "
                                      f"half-width ±{retro['methods'][m]['half_width']:.3f} pp" for m in ("v3a", "v3b")))
