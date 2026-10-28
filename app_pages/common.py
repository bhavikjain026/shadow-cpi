"""Shared helpers for the app pages: file loaders, release dates, formatting.

Every number the app shows is read from a results file in this repository (results/, manifests/, sealed/, data/,
audit/); docs/app_numbers.md lists each one and its file. The pages make no API call except the capped "Run live"
button on Home (shadow_cpi/live_run.py), the Leak demo's live mode and Try it (shadow_cpi/try_it.py).
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
GITHUB_URL = "https://github.com/bhavikjain026/shadow-cpi"
VIDEO_URL = ""             # the demo video's URL; while empty, the Leak demo hides its "Watch the video" button
BRAND = "Shadow CPI"
EYEBROW = "Nebius x NVIDIA Global AI Hackathon · Built on Tavily"
TITLE_CLAIM = BRAND_LINE = "Ask a search engine about the past, and it can answer with the future."
SUBHEAD = ("Shadow CPI replays past questions as of a cutoff date, searches each with and without Tavily's time lock, "
           "and counts the results that were published after the cutoff.")
# the README tagline, shortened to at most 20 words
TAGLINE = ("An AI agent that searches the past without cheating, checks every quote, and seals India's inflation "
           "forecast before release.")
SEAL_DATE = date(2026, 10, 29)                        # seal_checklist.md
LIVE_MONTH = "2026-10"

# MoSPI CPI releases still to come (data month, scheduled date, likely date, note). Source: audit/dates_check.md.
RELEASES = [
    ("2026-10", date(2026, 11, 12), date(2026, 11, 12), "October CPI is scheduled for Thu 12 Nov 2026, 4:00 PM IST (MoSPI's next-working-day rule applies)"),
    ("2026-11", date(2026, 12, 12), date(2026, 12, 14),
     "November data due 12 Dec, a Saturday, so likely Mon 14 Dec under MoSPI's next-working-day rule"),
]
RELEASE_HOUR_IST = 16  # MoSPI publishes CPI at 4:00 PM IST


def path(rel):
    return ROOT / rel


def wilson95(k, n, z=1.959964):
    """Wilson score interval (low, high) for k of n, as shares; the same formula and z as v2/date_test.wilson."""
    if not n:
        return None, None
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return max(0.0, centre - half), min(1.0, centre + half)


# Time-lock tables: time-locked cells bold, no-lock cells tinted (works in light and dark themes).
LOCK_CSS, OPEN_CSS = "font-weight: 700", "background-color: rgba(255, 75, 75, 0.12)"


def lock_table(rows, kind):
    """st.table (wraps text, nothing clipped) with each cell styled by kind(row, column) -> 'lock' | 'open' | None."""
    import pandas as pd
    df = pd.DataFrame(rows)
    df = df.map(lambda v: "\\" + v if isinstance(v, str) and v[:2] in ("+ ", "- ", "* ") else v)   # not a list
    css = {"lock": LOCK_CSS, "open": OPEN_CSS}
    styles = pd.DataFrame([[css.get(kind(rows[i], c), "") for c in df.columns] for i in range(len(rows))],
                          index=df.index, columns=df.columns)
    st.table(df.style.apply(lambda _: styles, axis=None).hide(axis="index"), hide_index=True)


def dark_theme():
    """True when the viewer's app theme is dark (st.context.theme; light when unknown)."""
    try:
        return st.context.theme.type == "dark"
    except AttributeError:
        return False


MAX_COLS = 5                  # columns a table shows by default, so it reads at 390 px; the rest sit under the column menu


def table(rows, show=None, config=None):
    """st.dataframe(hide_index=True) with typed columns: whole numbers and floats as NumberColumn, ISO dates as
    DateColumn, web addresses as LinkColumn (the short domain). At most MAX_COLS columns show by default (`show` names
    them; else the first MAX_COLS); the rest stay one click away in the column menu. Values are not changed."""
    import re
    import pandas as pd
    df = pd.DataFrame(rows)
    cfg = {}
    for col in df.columns:
        vals = [v for v in df[col] if v is not None and v == v and v != ""]
        if not vals:
            continue
        if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals):
            cfg[col] = st.column_config.NumberColumn(col)
        elif all(isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) for v in vals):
            df[col] = [date.fromisoformat(v) if isinstance(v, str) and v else None for v in df[col]]
            cfg[col] = st.column_config.DateColumn(col, format="D MMM YYYY")
        elif all(isinstance(v, str) and v.startswith(("http://", "https://")) for v in vals):
            cfg[col] = source_column(col)
    cfg.update(config or {})
    order = list(show) if show else list(df.columns)[:MAX_COLS]
    st.dataframe(df, hide_index=True, width="stretch", column_config=cfg, column_order=order)


def altair_chart(chart, into=st, **kwargs):
    """st.altair_chart with axis, legend and title text set explicitly for the viewer's app theme (Streamlit's default
    axis grey is 3.7:1 on white). Light: #52525b labels (7.6:1), #09090b titles; dark: #a1a1aa labels, #fafafa titles."""
    dark = dark_theme()
    label, ink = ("#a1a1aa", "#fafafa") if dark else ("#52525b", "#09090b")
    chart = (chart.configure_axis(labelColor=label, titleColor=ink, domainColor=label, tickColor=label)
             .configure_legend(labelColor=ink, titleColor=ink).configure_title(color=ink))
    return into.altair_chart(chart, **kwargs)


DARK_PRIMARY = ('[data-testid^="stBaseButton-primary"], [data-testid^="stBaseButton-primary"] * { color: #09090b; }')


def inject_style():
    """app_pages/style.css (display only), added once per run from app.py so every page gets it."""
    css = (ROOT / "app_pages" / "style.css").read_text(encoding="utf-8")
    if dark_theme():        # the dark accent #60a5fa needs dark text (white on it is 2.5:1; #09090b is 7.9:1); follows the
        css += DARK_PRIMARY  # app's theme setting, not the OS's
    st.html(f"<style>{css}</style>")


# One-line purpose of each page, keyed by the title the page passes to header() (texts from Kahan's
# origin/copilot/guide-trace-visuals-20261028, 59bd1c4).
PAGE_GUIDES = {
    "Experimental nowcast": "The latest inflation estimate, evidence behind the estimate, and comparisons with economist forecasts.",
    "Evidence": "The verified price quotes, official price series, and announced changes behind the forecast.",
    "Chain of custody": "Trace a price from its source page through search records to the forecast seal.",
    "Leak demo": "Compare searches with and without date limits to see how future information can enter a backtest.",
    "Tavily trace": "Review Tavily searches, search results, credits, response times, and failures.",
    "Tavily Flight Recorder": "Review the saved log of outside searches and requests.",
    "October radar (v2)": "Review announced retail price changes that may affect the October estimate.",
    "Replay": "Compare past forecasts with official inflation results.",
    "Live build (v2)": "See how verified price evidence updates the inflation estimate.",
    "As of a date": "See what price evidence was available on a date you choose.",
    "Tavily field report": "Read the results of tests on search dates and evidence quality.",
    "Try it: search the past": "Ask your own question and compare a search with and without a time lock.",
    "For research teams": "Learn how to use time-locked web evidence in research.",
    "Archive": "Review saved forecasts and instructions for checking each forecast's fingerprint.",
    "Reporter brief": "Read a short summary of the forecast for journalists.",
}


def page_guide(entries):
    """Sidebar expander under the navigation: each (st.Page, header title) in nav order, a link and its PAGE_GUIDES line."""
    with st.expander("Page guide", icon=":material/menu_book:", expanded=False):
        for page, key in entries:
            st.page_link(page)
            st.caption(PAGE_GUIDES[key])


def header(title, intro=None, *, eyebrow=False):
    """The page title (H1) with its PAGE_GUIDES purpose line. eyebrow=True shows the title as a small label instead,
    for a page whose H1 is elsewhere (the Leak demo's brand header)."""
    if eyebrow:
        with st.container(key="eyebrow"):
            st.markdown(title)
    else:
        st.title(title)
    if title in PAGE_GUIDES:
        st.caption(PAGE_GUIDES[title])
    if intro:
        st.caption(intro)


# ---------- loaders (each returns None / [] when the file does not exist yet) ----------
@st.cache_data(show_spinner=False)
def _load_json(rel, mtime):
    """Parsed results file, cached per file version (mtime); each caller gets its own copy."""
    return json.loads(path(rel).read_text(encoding="utf-8"))


def read_json(rel):
    p = path(rel)
    return _load_json(rel, p.stat().st_mtime) if p.exists() else None


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


# ---------- plain labels (short codes only in small text) ----------
LABELS = {"c": "Shadow CPI", "a": "Trend only", "b": "Government prices only",
          "c_strict": "Shadow CPI, official series only", "B1": "Repeat last month"}
CODES = {"c": "(c)", "a": "(a)", "b": "(b)", "c_strict": "(c-strict)", "B1": "B1"}


def pass_fail(lock):
    return ("Pass/fail rule (set before scoring): beat 'repeat last month' and 'trend only' → "
            + ("passed" if lock["go"] else "failed"))


def poll_months():
    """Number of months with a dated economists' poll (results/baselines.csv)."""
    return sum(bool((r.get("poll_pred") or "").strip()) for r in read_csv("results/baselines.csv"))


def headline_result(lock):
    """The one-line result, worded from results/score_lock.json."""
    c, pc, poll = lock["mae"]["c"], lock["mae_poll_months"]["c"], lock["mae_poll_months"]["poll"]
    verdict = ("about a tie" if abs(pc - poll) < 0.005 else
               "Shadow CPI closer" if pc < poll else "poll closer")
    return (f"Over Jan–Sep 2026: Shadow CPI missed by {c:.3f} percentage points on average. On the {poll_months()} "
            f"months with a published economists' poll: Shadow CPI {pc:.3f} vs poll {poll:.3f} ({verdict}).")


# ---------- display helpers (text only; numbers are not changed) ----------
def clean_line(line):
    """An exact line without markdown heading marks ('#', '##') at the start."""
    import re
    return re.sub(r"^\s*#+\s*", "", line or "").strip()


def item_label(item):
    return (item or "").replace("_", " ").capitalize()


def source_column(label="Source"):
    """A link column that shows the short domain (e.g. 'bhaskar.com') and opens the page."""
    return st.column_config.LinkColumn(label, display_text=r"https?://(?:www\.|m\.|amp\.)?([^/]+)")


def indian_number(x):
    """153183 -> '1,53,183' (Indian digit grouping)."""
    s = f"{int(round(x))}"
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    return ",".join(([head] if head else []) + groups) + "," + tail


def readable_quote(q):
    """A readable line for official table rows (IBJA, IOCL); other quotes keep their exact line."""
    url, unit = q.get("url") or "", q.get("unit") or ""
    if "ibja" in url and q["item"] in ("gold", "silver"):
        per = "per 10 g" if "10 g" in unit else "per kg"
        return f"{q['item'].capitalize()} 999, ₹{indian_number(q['price'])} {per} (IBJA daily rate)"
    if "iocl.com" in url and q["item"] == "lpg":
        return (f"Domestic LPG 14.2 kg, ₹{indian_number(q['price'])} per cylinder in {q.get('place', '')} "
                f"(IOCL price list, from {q['date']})")
    return clean_line(q.get("line"))


def v2_comparison():
    """The v1-vs-v2 table (v2 = experimental, stricter rules), every number from results/v2_score_lock.json and
    results/v2_recall_lock.json. Shown under v1, which stays the headline."""
    sc, rc = read_json("results/v2_score_lock.json"), read_json("results/v2_recall_lock.json")
    if not (sc and rc):
        return
    v1, v2, n = sc["v1"], sc["v2"], len(sc["months"])
    pm = sum(r["poll"] is not None for r in sc["months"])
    nano, sup = (v2["verified_by_model"][k] for k in sorted(v2["verified_by_model"], key=lambda k: "super" in k))
    dr = v2["date_rejections"]
    st.markdown("**v2 (experimental, stricter rules)**")
    st.dataframe([
        {"Measure": "Average miss (percentage points)", "v1 Shadow CPI": f"{v1['mae']:.3f}", "v2": f"{v2['mae']:.3f}"},
        {"Measure": f"Average miss on the {pm} poll months", "v1 Shadow CPI": f"{v1['mae_poll_months']:.3f}",
         "v2": f"{v2['mae_poll_months']:.3f}"},
        {"Measure": f"Known price changes found directly (of {rc['total']})", "v1 Shadow CPI": str(rc["v1_found"]),
         "v2": str(rc["v2_found"])},
        {"Measure": "Actual inside the range*", "v1 Shadow CPI": f"{v1['inside_range']} of {n}",
         "v2": f"{v2['inside_range']} of {n}"},
        {"Measure": "Pages rejected by the page-date check", "v1 Shadow CPI": "no such check",
         "v2": f"{dr['after cutoff'] + dr['edited after its date']} ({dr['edited after its date']} edited after their "
               "date)"},
        {"Measure": "Verified claims, by model", "v1 Shadow CPI": "—", "v2": f"Nano {nano} / Super {sup}"},
    ], hide_index=True, width="stretch")
    st.caption("*Not like-for-like: v2's range is a fixed ± 0.284 pp; v1's 80% range was set by its own "
               "pre-registered rule. Rule set before scoring: v2 counts as better only with a lower average miss AND "
               f"more than {rc['v1_found']} changes found → "
               + ("met" if rc["v2_better_than_v1"] else "not met: v1 stays the headline") + ". Scored once "
               "(v2/PREREGISTRATION.md, logged rule changes A–D).")
