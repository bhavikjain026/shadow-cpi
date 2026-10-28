"""Provenance footer: the results file behind a result, its SHA-256 (first 12 characters, computed when the page runs)
and its last-modified time in IST. Display only; read-only; no API call."""
import hashlib
from datetime import datetime

import streamlit as st

from app_pages.common import IST, path


@st.cache_data(show_spinner=False)
def _fingerprint(rel, mtime):
    """(first 12 hex characters of the file's SHA-256, modified time as text); keyed on mtime so an edit refreshes it."""
    p = path(rel)
    digest = hashlib.sha256(p.read_bytes()).hexdigest()[:12]
    return digest, datetime.fromtimestamp(mtime, IST).strftime("%Y-%m-%d %H:%M IST")


def provenance(rel):
    """A small muted monospace line under a result: 'results/x.json · sha256 1a2b3c4d5e6f · modified 2026-10-28 20:15 IST'."""
    p = path(rel)
    if not p.exists():
        return
    digest, modified = _fingerprint(rel, p.stat().st_mtime)
    st.html(f'<p class="provenance">source <b>{rel}</b> · sha256 <b>{digest}</b> · modified <b>{modified}</b></p>')


def how_we_know(data, analysis, limits):
    """'How we know': three short parts, Data / Analysis / Assumptions and limitations (from docs/honest_limits.md).
    Each argument is Markdown built by the page from results files, so no number is typed here."""
    with st.expander("How we know"):
        st.markdown(f"**Data.** {data}")
        st.markdown(f"**Analysis.** {analysis}")
        st.markdown(f"**Assumptions and limitations.** {limits}")
