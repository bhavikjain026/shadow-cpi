"""Tavily Flight Recorder: every outside call from logs/flight_recorder.jsonl, one item traced, the evidence chase."""
import streamlit as st

from app_pages.common import header, read_json, read_log, read_text, tavily_credits

header("Tavily Flight Recorder", "Every outside call, in order: when, which Tavily endpoint, what was asked, "
                                 "how many results, credits and time. Repeat calls come from the cache for free.")

log = read_log()
if not log:
    st.info("No calls recorded yet (logs/flight_recorder.jsonl).")
    st.stop()


def what(e):
    p = e.get("params", {})
    if "query" in p:
        return p["query"]
    if "urls" in p:
        return ", ".join(p["urls"][:2]) + (" …" if len(p["urls"]) > 2 else "")
    return p.get("url") or p.get("model") or ""


tav = [e for e in log if e["service"] == "tavily"]
c1, c2, c3 = st.columns(3)
c1.metric("Tavily calls", len(tav))
c2.metric("Credits used", tavily_credits(log))
c3.metric("From cache", sum(bool(e.get("cached")) for e in tav))
st.caption(f"Nemotron calls: {sum(e['service'] == 'nebius' for e in log)}. Credits count only calls that were not "
           "served from the cache.")

st.subheader("Log")
st.dataframe([{"Time (UTC)": e["time"][:19].replace("T", " "), "Service": e["service"], "Endpoint": e["endpoint"],
               "What": what(e), "Results": e.get("n_results"), "Credits": e.get("credits"),
               "Seconds": round(e.get("latency_ms", 0) / 1000, 1), "Cached": "yes" if e.get("cached") else "",
               "Job": e.get("tag") or ""} for e in log], hide_index=True, width="stretch")

# ---------- tree helpers ----------
children = {}
for e in log:
    children.setdefault(e.get("parent"), []).append(e)


def subtree(e, depth=0):
    yield depth, e
    for ch in children.get(e["id"], []):
        yield from subtree(ch, depth + 1)


def tree_text(roots, mark_id=None):
    lines = []
    for r in roots:
        for d, e in subtree(r):
            mark = "└─ " if d else ""
            extra = f" · {e['n_results']} results" if e.get("n_results") is not None else ""
            here = "   ◀ read the page with this event" if e["id"] == mark_id else ""
            lines.append(f"{'   ' * d}{mark}{e['service']} {e['endpoint']}: {what(e)}{extra}  "
                         f"[{e.get('tag') or ''}]{here}")
    return "\n".join(lines)


# ---------- one item end to end ----------
st.subheader("One verified event, end to end")
by_id = {e["id"]: e for e in log}
chains = [c for c in (read_json("results/app/event_chains.json") or []) if c["root_id"] in by_id]
if chains:
    default = next((i for i, c in enumerate(chains) if c["month"] == "2026-09" and c["item"] == "electricity"),
                   len(chains) - 1)
    pick = st.selectbox("Verified event", range(len(chains)), index=default, format_func=lambda i: chains[i]["label"])
    ch = chains[pick]
    st.caption("The dated news search, the Tavily Extract call that read the event's page, and the Nemotron reads "
               "(gatekeeper, then price events) on each page.")
    st.code(tree_text([by_id[ch["root_id"]]], ch["extract_id"]), language=None)
roots = [e for e in log if e.get("parent") is None]
jobs = sorted({(e.get("tag") or "").split(" ")[0] for e in roots if e.get("tag")})
if jobs:
    with st.expander("Browse any job"):
        job = st.selectbox("Item or job", jobs)
        st.code(tree_text([r for r in roots if (r.get("tag") or "").split(" ")[0] == job]), language=None)

# ---------- evidence chase ----------
st.subheader("Evidence chase")
st.caption("When an event is verified, up to 2 follow-up searches look for the same change elsewhere and for the "
           "official circular.")
chase_roots = [e for e in roots if any((d.get("tag") or "").startswith("chase:") for _, d in subtree(e))]
if chase_roots:
    st.code(tree_text(chase_roots), language=None)
else:
    st.caption("No evidence chases recorded.")

card = read_text("results/tavily_report_card.md")
if card:
    with st.expander("Tavily report card", expanded=False):
        st.markdown(card)
