"""Chain of custody: pick any verified number and see quote -> URL -> page date -> request_id -> response hash -> seal.
Reads results/custody.json (built offline by tools/build_custody.py); makes no API call."""
import streamlit as st

from app_pages.common import header, read_json

header("Chain of custody", "Pick any verified number to see where it came from: the exact quote, the page, its date, "
                           "Tavily's request IDs and response hashes, and the seal.")
d = read_json("results/custody.json")
if not d:
    st.info("Not built yet: run `python tools/build_custody.py` (offline, 0 credits).")
    st.stop()
rows = d["rows"]
sources = sorted({r["source"] for r in rows})
src = st.selectbox("Source", sources, index=sources.index("radar") if "radar" in sources else 0)
pick = [r for r in rows if r["source"] == src]


def label(r):
    num = f"{r['change'] * 100:+.2f}%" if r.get("change") is not None else (f"₹{r['price']}" if r.get("price") else "—")
    return f"{r['month']} · {r['kind'] or 'item?'} · {num} · {r['url'].split('/')[2]}"


i = st.selectbox("Number", range(len(pick)), format_func=lambda k: label(pick[k]))
r = pick[i]
steps = [("Quote (exact cited line)", r["quote"]), ("URL", r["url"]),
         ("Page date", f"{r['page_date'] or '—'}" + (f" (printed on the page: {r['printed_date']})"
                                                     if r.get("printed_date") else "")),
         ("Search request_id", r["search_request_id"]), ("Search response SHA-256", r["search_response_sha256"]),
         ("Extract request_id", r["extract_request_id"]), ("Extract response SHA-256", r["extract_response_sha256"]),
         ("Saved page SHA-256", r["page_sha256"]), ("Seal", r["seal"])]
for name, val in steps:
    with st.container(border=True):
        st.caption(name)
        if val == d["not_logged"]:
            st.markdown("_not logged_")
        elif name == "URL":
            st.markdown(f"[{val}]({val})")
        else:
            st.code(val, language=None, wrap_lines=True)
st.caption(d["note"] + ".")
