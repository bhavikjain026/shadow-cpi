"""Use it: the time lock in your own code. The two calls exactly as in the README's extract_as_of example
(tests/test_leak_demo.py checks this), the Colab notebook, the MCP tool, and the research-team guide. No API call."""
import streamlit as st

from app_pages.common import GITHUB_URL, header

# The two calls exactly as in the README's extract_as_of example.
USE_IT = """from timelock import TavilyHTTP, extract_as_of, timelocked_search
client, cutoff = TavilyHTTP(), "2026-10-06"
results = timelocked_search(client, "RBI monetary policy repo rate decision October 2026", cutoff, topic="news", max_results=3, include_published_date=True)
for r in results: page = extract_as_of(client, r["url"], cutoff, published_date=r.get("published_date"))"""
COLAB = ("https://colab.research.google.com/github/bhavikjain026/shadow-cpi/blob/main/notebooks/"
         "reproduce_leak.ipynb")

header("Use it")
with st.container(key="use-it"):
    st.markdown("**Search as of a cutoff, then read each page as it was on that day**")
    st.code(USE_IT, language="python", wrap_lines=True)
    st.markdown(f"[`timelock/`]({GITHUB_URL}/tree/main/timelock) (standard library only) · "
                f"[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)]({COLAB}) "
                "reproduce the leak with your own Tavily key")
st.markdown("- **`timelocked_search`** sends `start_date`/`end_date` and `filter_by_published_date`, refuses an end "
            "date after the cutoff before any call, and labels each result `safe`, `date_flag` or `leak`.\n"
            "- **`extract_as_of`** returns an archive copy from on or before the cutoff, or refuses the page.\n"
            f"- **Any agent:** the same time lock as an MCP tool ([`mcp/`]({GITHUB_URL}/tree/main/mcp)).")
st.page_link("app_pages/research.py", label="For research teams: exports, as-of reads and seal checks",
             icon=":material/biotech:")
