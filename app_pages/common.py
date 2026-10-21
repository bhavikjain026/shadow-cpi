"""Shared helpers for the app pages: file loaders, release dates, formatting.

Every number the app shows is read from a results file in this repository (results/, manifests/, sealed/, data/,
audit/); docs/app_numbers.md lists each one and its file. The pages make no API call except the capped "Run live"
button on Home (shadow_cpi/live_run.py).
"""
import csv
import hashlib
import json
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
NOWCAST_WORDS = "experimental nowcast"
IST = timezone(timedelta(hours=5, minutes=30))
REPO_URL = "https://github.com/bhavikjain026/shadow-cpi/blob/main"
SEAL_DATE = date(2026, 10, 29)                        # seal_checklist.md
LIVE_MONTH = "2026-10"

# MoSPI CPI releases still to come (data month, scheduled date, likely date, note). Source: audit/dates_check.md.
RELEASES = [
    ("2026-10", date(2026, 11, 12), date(2026, 11, 12), "Thu 12 Nov 2026, 4:00 PM IST"),
    ("2026-11", date(2026, 12, 12), date(2026, 12, 14),
     "November data due 12 Dec, a Saturday, so likely Mon 14 Dec under MoSPI's next-working-day rule"),
]
RELEASE_HOUR_IST = 16  # MoSPI publishes CPI at 4:00 PM IST


def path(rel):
    return ROOT / rel


def header(title, intro=None):
    st.title(title)
    if intro:
        st.caption(intro)


# ---------- loaders (each returns None / [] when the file does not exist yet) ----------
def read_json(rel):
    p = path(rel)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def read_csv(rel):
    p = path(rel)
    if not p.exists():
        return []
    with p.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def read_text(rel):
    p = path(rel)
    return p.read_text(encoding="utf-8") if p.exists() else None


def read_log(rel="results/app/flight_recorder.jsonl"):
    """The committed snapshot of the flight recorder (tools/build_app_data.py). Same reading rule as
    shadow_cpi.recorder.read_log."""
    text = read_text(rel)
    return [json.loads(l) for l in text.splitlines() if l.strip()] if text else []


def tavily_credits(entries, include_cached=False):
    """Same counting rule as shadow_cpi.recorder.credits_used."""
    return sum((e.get("credits") or 0) for e in entries
               if e.get("service") == "tavily" and (include_cached or not e.get("cached")))


def months_with(folder, suffix=".json"):
    d = path(folder)
    return sorted((p.name[: -len(suffix)] for p in d.glob(f"*{suffix}")), reverse=True) if d.exists() else []


def num(x):
    """CSV cell -> float, or None for blank / 'none'."""
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    x = str(x).strip()
    if not x or x.lower() in ("none", "nan", "na"):
        return None
    try:
        return float(x)
    except ValueError:
        return None


def pct(x, digits=2):
    return "—" if x is None else f"{x:.{digits}f}%"


def pp(x, digits=2):
    return "—" if x is None else f"{x:+.{digits}f} pp"


def month_name(m):
    return datetime.strptime(m, "%Y-%m").strftime("%B %Y")


# ---------- seals ----------
def seal_status(month):
    """(stored sha256, recomputed sha256 of the sealed JSON text, match?) like shadow_cpi.seal.verify."""
    jp, hp = path(f"sealed/{month}.json"), path(f"sealed/{month}.sha256")
    if not jp.exists():
        return None, None, False
    actual = hashlib.sha256(jp.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
    stored = hp.read_text(encoding="utf-8").strip() if hp.exists() else None
    return stored, actual, stored == actual


# ---------- release countdown ----------
def next_release(now=None):
    now = now or datetime.now(timezone.utc)
    for month, sched, likely, note in RELEASES:
        at = datetime(likely.year, likely.month, likely.day, RELEASE_HOUR_IST, tzinfo=IST)
        if at > now:
            return {"month": month, "scheduled": sched, "likely": likely, "note": note, "at": at, "left": at - now}
    return None


def countdown_text(left):
    days, rest = divmod(int(left.total_seconds()), 86400)
    return f"{days} days {rest // 3600} hours"


def poll_direction(rel="results/scoreboard.md"):
    """'6 of 6' from the scoreboard line 'poll 0.148 pp (direction 6 of 6)' (the lock file does not store it)."""
    import re
    m = re.search(r"poll [\d.]+ pp \(direction (\d+) of (\d+)\)", read_text(rel) or "")
    return f"{m.group(1)} of {m.group(2)}" if m else "—"
