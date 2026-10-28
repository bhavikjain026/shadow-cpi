"""Provenance footer: the results file behind a result, its SHA-256 (first 12 characters, computed when the page runs)
and, when the file stores one, the timestamp it was generated at. Never a file-system time (a checkout resets it).
Display only; read-only; no API call."""
import hashlib
from datetime import datetime, timezone

import streamlit as st

from app_pages.common import IST, path, read_json


@st.cache_data(show_spinner=False)
def _sha(rel, mtime):
    """First 12 hex characters of the file's SHA-256; mtime is only the cache key, never shown."""
    return hashlib.sha256(path(rel).read_bytes()).hexdigest()[:12]


def generated(rel, field):
    """The generation timestamp stored in the file under `field`, as text; None when the field is absent. A UTC ISO
    timestamp is shown in IST; a bare date (e.g. field_report.json `built`) is shown as written."""
    value = (read_json(rel) or {}).get(field) if field else None
    if not value:
        return None
    try:
        when = datetime.fromisoformat(value)
    except ValueError:
        return None
    if "T" not in value:
        return value
    return when.astimezone(IST).strftime("%Y-%m-%d %H:%M IST") if when.tzinfo else when.strftime("%Y-%m-%d %H:%M")


def provenance(rel, field=None):
    """A small muted monospace line under a result: 'source results/x.json · sha256 1a2b3c4d5e6f · generated <field>
    2026-10-26 …'. `field` names the key inside the file that holds its generation time; leave it out (or when the file
    has none) and only the path and the SHA-256 show."""
    p = path(rel)
    if not p.exists():
        return
    line = f'source <b>{rel}</b> · sha256 <b>{_sha(rel, p.stat().st_mtime)}</b>'
    when = generated(rel, field)
    if when:
        line += f' · {field} <b>{when}</b>'
    st.html(f'<p class="provenance">{line}</p>')


def how_we_know(data, analysis, limits):
    """'How we know': three short parts, Data / Analysis / Assumptions and limitations (from docs/honest_limits.md).
    Each argument is Markdown built by the page from results files, so no number is typed here."""
    with st.expander("How we know"):
        st.markdown(f"**Data.** {data}")
        st.markdown(f"**Analysis.** {analysis}")
        st.markdown(f"**Assumptions and limitations.** {limits}")
