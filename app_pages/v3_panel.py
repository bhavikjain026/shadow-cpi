"""v3 beside v1 on Home: experimental, never instead of v1 (v3/PREREG.md). Numbers come from sealed/<month>.v3.json,
else results/v3_nowcast_<month>.json; Jan-Sep from results/v3_retrospective.json, shown as retrospective only."""
import streamlit as st

from shadow_cpi.live_range import THRESHOLD

from app_pages.common import SEAL_DATE, month_name, pct, read_json

NAMES = {"v3a": "v3a (tier-weighted evidence)", "v3b": "v3b (equal-weight average of trend, spine and v1)"}


def _range(x):
    return "unbounded at 80%" if x.get("range_low") is None else f"{pct(x['range_low'])} to {pct(x['range_high'])}"


def v3_beside_v1(month):
    sealed = read_json(f"sealed/{month}.v3.json")
    call = sealed or read_json(f"results/v3_nowcast_{month}.json")
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
                    col.caption(f"P(headline ≥ {THRESHOLD:.1f}%): {x['p_headline_ge_6']:.0%}")
            st.caption(f"Ranges {call['range_label']} (split conformal). " +
                       ("Sealed with v1 in one hash bundle (`sealed/" + month + ".bundle.sha256`)." if sealed else
                        "Built, not sealed yet: sealed right after v1."))
        else:
            st.markdown(f"Built from v1's sealed inputs and sealed right after v1 on {SEAL_DATE:%d %b}.")
        if retro:
            with st.expander("Jan–Sep 2026: retrospective, not a test"):
                st.caption(f"{retro['label'].capitalize()}: v3 was designed after v1's Jan–Sep scores were public, "
                           "and its ranges are calibrated on these months.")
                st.dataframe([{"Month": month_name(mm), "Official": pct(r["official"]),
                               **{m: pct(retro["methods"][m]["months"][mm]["pred"]) for m in ("v3a", "v3b")},
                               "v1": pct(retro["v1_c"][mm])} for mm, r in retro["methods"]["v3a"]["months"].items()],
                             hide_index=True, width="stretch")
                st.caption(" · ".join(f"{m}: average miss {retro['methods'][m]['mean_abs_miss']:.3f} pp, 80% "
                                      f"half-width ±{retro['methods'][m]['half_width']:.3f} pp" for m in ("v3a", "v3b")))
