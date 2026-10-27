"""October radar (v2, report only): announced retail price changes taking effect in October 2026, found before MoSPI
publishes, frozen at 29 Oct 23:59 IST and scored afterwards against a list built without Tavily
(v2/RADAR_PREREG.md). Reads v2/radar/; makes no API call."""
import streamlit as st

from app_pages.common import header, pct, read_json, read_text, source_column

header("October radar (v2)", "Announced retail price changes taking effect in October 2026, found with Tavily before "
                             "MoSPI publishes October CPI. Frozen at 29 Oct, 23:59 IST, then scored against a list "
                             "built afterwards without Tavily. Report only: it never changes the sealed call.")
frozen = read_json("v2/radar/radar_2026-10.frozen.json")
radar = frozen or read_json("v2/radar/radar_2026-10.json")
if not radar:
    st.info("Not run yet. The radar starts once the search strategy is decided from the four-arm search test "
            "(v2/RADAR_PREREG.md).")
    st.stop()
sha = (read_text("v2/radar/radar_2026-10.frozen.sha256") or "").strip()
if frozen:
    st.success(f"Frozen {frozen['frozen_utc'][:16]} UTC · SHA-256 `{sha[:16]}…`")
else:
    st.warning("Running: not frozen yet (freeze at 29 Oct, 23:59 IST).")
evs = radar.get("events", [])
c1, c2, c3 = st.columns(3)
c1.metric("Events verified", len(evs))
c2.metric("Corroborated", sum(e["tier"] == "corroborated" for e in evs))
c3.metric("Tavily-only", sum(e["tavily_only"] for e in evs))
tot = sum(e["effect_pp"] or 0 for e in evs if e["tavily_only"])
st.caption(f"Search strategy {radar['strategy']} · {len(radar['runs'])} runs · Tavily-only events add "
           f"{tot:+.3f} percentage points to October inflation (each event: its change × days in force × state "
           "share, through the frozen v1 maths).")
skeptic = (read_json("v2/radar/skeptic_2026-10.json") or {}).get("events", {})


def challenged(e):
    """The skeptic's flag (v2/DRIFT_PREREG.md part B): 'challenged: URL + quote', never a tier or effect change."""
    s = skeptic.get(f"{e['kind']}|{e['effective_date']}|{','.join(sorted(e['states']))}")
    if s is None:
        return "not searched yet"
    if not s["challenged"]:
        return "no" if s.get("query") else "skeptic not run"
    c = s["challenged"][0]
    return f"challenged: {c['url']} “{c['quote']}”" + (f" (+{len(s['challenged']) - 1} more)"
                                                      if len(s["challenged"]) > 1 else "")


st.dataframe([{"Kind": e["kind"], "Where": ", ".join(e["states"]) or "India", "Effective": e["effective_date"],
               "Change": pct((e["change"] or 0) * 100) if e.get("change") is not None else "—", "Tier": e["tier"],
               "Tavily-only": "yes" if e["tavily_only"] else "no",
               "Effect (pp)": f"{e['effect_pp']:+.3f}" if e.get("effect_pp") is not None else "—",
               "Source": e["sources"][0]["url"], "Sources": len(e["sources"]), "Skeptic": challenged(e)}
              for e in evs],
             hide_index=True, width="stretch", column_config={"Source": source_column()})
st.caption("Skeptic: one model-written Tavily search per event, inside the radar's time lock, for news that the change "
           "was withdrawn, rolled back, stayed or postponed. Code picks the quote. A flag only: it never changes "
           "tiers or effects (v2/DRIFT_PREREG.md, part B).")
st.page_link("app_pages/custody.py", label="Chain of custody for each number: quote → page → request_id → hash → seal",
             icon="🔗")
sc = read_json("results/radar_2026-10_score.json")
if sc:
    st.subheader("Score")
    st.dataframe([{"Tier": t, "Precision": "—" if v["precision"] is None else f"{v['precision']:.0%}",
                   "Recall": "—" if v["recall"] is None else f"{v['recall']:.0%}",
                   "Events": v["events"], "Listed changes found": f"{v['found']} of {sc['counted']}"}
                  for t, v in sc["tiers"].items()], hide_index=True, width="stretch")
    st.caption("Changes initially reported after the freeze are not counted as misses.")

