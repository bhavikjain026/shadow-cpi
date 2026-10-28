"""Leak demo (the home page): can a web search see the future? Past questions replayed as of a cutoff date, each
searched with no time lock and with Tavily's time lock. Built only from saved results (results/leak_demo.json, made
offline by tools/build_leak_demo.py from the date test and the finance check; totals from results/field_report.json
and results/leakcheck_exact_match.json; the hero's cost from results/date_field_test.json). The only API calls are the optional live mode, off unless RUN_LIVE_ENABLED."""
import re
from datetime import date, timedelta

import streamlit as st

from app_pages.common import BRAND, BRAND_LINE, GITHUB_URL, TAGLINE, VIDEO_URL, header, lock_table, read_json

AFTER_RETRY = "after retrying the failed Wayback archive lookups"
# Short tab labels "<item> · <Mon yy>", short enough for a phone (the case heading keeps the full label).
SHORT = {"fuel": "Petrol hike", "milk": "Milk hike", "electricity": "Power tariff", "lpg": "LPG hike",
         "bus": "Bus fare", "rbi": "RBI rate"}
# "Use it": the two calls exactly as in the README's extract_as_of example (tests/test_leak_demo.py checks this).
USE_IT = """from timelock import TavilyHTTP, extract_as_of, timelocked_search
client, cutoff = TavilyHTTP(), "2026-10-06"
results = timelocked_search(client, "RBI monetary policy repo rate decision October 2026", cutoff, topic="news", max_results=3, include_published_date=True)
for r in results: page = extract_as_of(client, r["url"], cutoff, published_date=r.get("published_date"))"""
COLAB = ("https://colab.research.google.com/github/bhavikjain026/shadow-cpi/blob/main/notebooks/"
         "reproduce_leak.ipynb")

OPEN, OPEN_NOTE = "No time lock", "default search, no dates"
LOCKED, LOCKED_NOTE = "Tavily time lock", "start_date/end_date + filter_by_published_date"
EXAMPLES = "examples chosen for clarity; all {n} in the picker and the totals below"
FIRST = "F3"                                  # petrol (date test) leads
EXAMPLE_RULE = ("a Wayback-confirmed leak with no time lock, and every time-locked result confirmed before the "
                "cutoff (no UNCHECKED)")
UNCHECKED_HELP = "no archive check was made for this result"
OK_LABELS = ("confirmed pre-cutoff", "valid")
# Human case labels "<item> · <month year>", built from each case's kind, query and cutoff (display only).
ITEMS = {"fuel": "Petrol price hike", "milk": "Milk price hike", "electricity": "Electricity tariff hike",
         "lpg": "LPG price hike", "bus": "Bus fare hike", "rbi": "RBI decision"}


def pct(x):
    return f"{x:.0%}"


def wilson(w):
    return f"{pct(w[0])}–{pct(w[1])}"


def human(d):
    if not d:
        return "none"
    d = date.fromisoformat(d)
    return f"{d.day} {d:%b %Y}"


def link(title, url):
    """A Markdown link from web text: brackets, image markers and parentheses escaped so nothing else renders."""
    t = "".join("\\" + ch if ch in "[]()!*_`<>#|" else ch for ch in (title or url or ""))
    return f"[{t}](<{(url or '').replace('>', '%3E').replace(' ', '%20')}>)"


def qualifies(c):
    """EXAMPLE_RULE: a confirmed leak on the left, and every result on the right confirmed pre-cutoff."""
    right = c["locked"]["results"]
    return (any(r["leak"] for r in c["open"]["results"])
            and bool(right) and all(r["label"].startswith(OK_LABELS) for r in right))


def examples(cases):
    """F3 first, then every other case meeting EXAMPLE_RULE, in file order."""
    ok = [c["id"] for c in cases if qualifies(c)]
    return sorted(ok, key=lambda x: x != FIRST)


def badge(r):
    """A text badge so colour is not the only signal: LEAK (confirmed), OK (confirmed pre-cutoff), UNCHECKED (else)."""
    if r.get("leak"):
        return ":red-badge[LEAK]"
    if r["label"].startswith(OK_LABELS):
        return ":green-badge[OK]"
    return ":gray-badge[UNCHECKED]"


def badge_help(r):
    if r.get("leak") or r["label"].startswith(OK_LABELS):
        return None
    return UNCHECKED_HELP if r["label"] == "unknown" else f"{r['label']}: not confirmed by an archive check"


def case_title(c):
    """'Milk price hike, Kerala · Jun 2026': the item, its place when the query names one (not 'India'), and the
    cutoff's month."""
    if c["kind"] in ITEMS:
        what = ITEMS[c["kind"]]
    else:                                           # company results: 'TCS Q1 results'
        q = re.search(r"\b(Q\d) FY\d+", c["query"])
        what = f"{c['name']} {q.group(1)} results" if q else f"{c['name']} results"
    m = re.search(r"\bhike (.+?) [A-Z][a-z]+ \d{4}$", c["query"])
    where = f", {m.group(1)}" if m and m.group(1) != "India" else ""
    return f"{what}{where} · {date.fromisoformat(c['cutoff']):%b %Y}"


def tab_label(c):
    """'Petrol hike · May 26 F3': a short item name, the cutoff's month, and the case ID in small grey text."""
    what = SHORT.get(c["kind"], f"{c.get('name', c['kind'])} results")
    return f"{what} · {date.fromisoformat(c['cutoff']):%b %y} {case_id(c)}"


def case_id(c):
    """The case ID as small grey text, after a human label."""
    return f":gray[:small[{c['id']}]]"


def chip(text, colour="gray"):
    return f":{colour}-badge[{text.replace('[', '(').replace(']', ')')}]"


def wayback(label):
    """The label without the '(Wayback)' it repeats after 'Wayback:'."""
    return label.replace(" (Wayback)", "").replace(", Wayback)", ")")


def chips(r, test):
    """One row of small chips: Tavily date · Page date (date test only) · Wayback verdict, then any note."""
    row = [chip(f"Tavily: {human(r['published_date'])}")]
    if test == "date":
        row.append(chip(f"Page: {human(r['page_date'])}"))
    row.append(chip(f"Wayback: {wayback(r['label'])}"))
    if r.get("leak"):
        row.append(chip(f"Published {r['days_after_cutoff']} days after the cutoff", "red"))
    if r.get("label_first_pass") and r["label_first_pass"] != r["label"]:
        row.append(chip(f"Initial pass: {wayback(r['label_first_pass'])}"))
    return " ".join(row)


def card_kind(r):
    return "leak" if r.get("leak") else "ok" if r["label"].startswith(OK_LABELS) else "unchecked"


def result_card(r, test, key):
    """A compact result card: badge + headline link, a chip row, the excerpt behind 'Show excerpt'. LEAK / OK cards get
    a subtle tint and a 3px left border (app_pages/style.css, .st-key-card-leak / -ok)."""
    with st.container(border=True, key=f"card-{card_kind(r)}-{key}"):
        st.markdown(f"{badge(r)} {link(r['title'], r['url'])}", help=badge_help(r))
        st.markdown(chips(r, test))
        if r.get("quote"):
            with st.expander("Show excerpt"):
                st.markdown(f"> {r['quote']}")


def column_head(title, note):
    st.markdown(f"**{title}**")
    st.caption(note)


def search_column(col, title, note, s, test, key):
    with col:
        column_head(title, note)
        if not s["results"]:
            st.caption("No results.")
        for i, r in enumerate(s["results"]):
            result_card(r, test, f"{key}-{i}")
        with st.expander("Request sent, credits, latency"):
            st.json(s["request"], expanded=True)
            st.caption(f"The API key travels in a request header and is never part of the body. Credits "
                       f"{s['credits']} · latency {s['latency_s']:.2f} s (Tavily's response_time) · request id "
                       f"`{s['request_id']}`")


def show_case(c):
    st.markdown(f"#### {case_title(c)} {case_id(c)}")
    st.caption(f"{c['test_name'].capitalize()} · cutoff {human(c['cutoff'])} · query “{c['query']}”"
               + (" · Page dates not read in the finance check." if c["test"] == "finance" else ""))
    left, right = st.columns(2)
    search_column(left, OPEN, OPEN_NOTE, c["open"], c["test"], f"{c['id']}-open")
    search_column(right, LOCKED, LOCKED_NOTE, c["locked"], c["test"], f"{c['id']}-locked")


HERO_HEIGHT = 204          # 641-1199 px pages; style.css sets 176 px from 1200 px and 236 px on phones
HERO_FONT ="https://fonts.googleapis.com/css2?family=Inter:wght@500&family=JetBrains+Mono:wght@600&display=swap"
HERO_HTML = """<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="{font}"><style>
:root {{ --ink: #09090b; --muted: #52525b; --line: #e4e4e7; }}       /* no color-scheme: it paints an opaque canvas */
@media (prefers-color-scheme: dark) {{ :root {{ --ink: #fafafa; --muted: #a1a1aa; --line: #27272a; }} }}
html, body {{ margin: 0; background: transparent; color: var(--ink); font: 500 15px/1.4 Inter, sans-serif; }}
.title {{ font-weight: 600; font-size: 0.9375rem; margin: 0 0 8px; }}
.row {{ display: flex; align-items: stretch; gap: 8px; }}
.side {{ flex: 1 1 0; min-width: 0; border: 1px solid var(--line); border-radius: 8px; padding: 12px 16px; }}
.open {{ background: rgba(255, 75, 75, 0.12); }}                      /* LOCK/OPEN colour meaning, as common.OPEN_CSS */
.locked {{ background: rgba(33, 195, 84, 0.12); }}                     /* the same weight, green: the time lock held */
.cost {{ flex: 0.8 1 0; }}                                             /* neutral and secondary: no tint, smaller */
.cost .num {{ font-size: clamp(1.25rem, 4.5vw, 1.875rem); color: var(--muted); }}
.num {{ font: 600 clamp(1.75rem, 7vw, 2.75rem)/1.1 "JetBrains Mono", ui-monospace, monospace;
        font-variant-numeric: tabular-nums; letter-spacing: -0.03em; white-space: nowrap; }}
.label {{ color: var(--muted); font-size: 0.875rem; margin-top: 4px; }}
.arrow {{ align-self: center; color: var(--muted); font-size: 1.25rem; }}
.gap {{ width: 8px; }}
.update {{ color: var(--muted); font-size: 0.8125rem; margin: 6px 0 0; }}
/* phones (page under 641 px, class set by the script below): compact, and the cost card on its own row under
   9/20 -> 0/20 (.gap becomes a full-width, zero-height line break) */
html.narrow .row {{ flex-wrap: wrap; gap: 6px; }} html.narrow .gap {{ flex: 0 0 100%; height: 0; }}
html.narrow .cost {{ flex: 1 1 100%; }} html.narrow .side {{ padding: 8px 10px; }}
html.narrow .num {{ font-size: 1.375rem; }} html.narrow .label {{ font-size: 0.75rem; }}
html.narrow .arrow {{ font-size: 1rem; }} html.narrow .cost .num {{ font-size: 1.0625rem; }}
html.narrow .update {{ font-size: 0.75rem; }}
</style></head><body>
<p class="title">{title}</p>
<div class="row" role="img" aria-label="{aria}">
  <div class="side open"><div class="num"><span id="leaked">{open}</span>/{n}</div><div class="label">{open_label}</div></div>
  <div class="arrow" aria-hidden="true">→</div>
  <div class="side locked" id="locked"><div class="num">{locked}/{n}</div><div class="label">{locked_label}</div></div>
  <div class="gap" aria-hidden="true"></div>
  <div class="side cost" id="cost"><div class="num">{missed}/{quotes}</div><div class="label">{cost_label}</div></div>
</div>
<p class="update" id="update">{update}</p>
<script>
(function () {{
  // Phone layout follows the page's width, not this frame's (the sidebar changes the frame's width).
  try {{
    var narrow = function () {{
      document.documentElement.classList.toggle('narrow', window.parent.innerWidth < 641);
    }};
    narrow();
    window.parent.addEventListener('resize', narrow);
  }} catch (e) {{}}
  // Match the app's theme when the parent page is readable (same origin); else prefers-color-scheme above.
  try {{
    var app = window.parent.document.querySelector('[data-testid="stApp"]');
    var bg = window.parent.getComputedStyle(app).backgroundColor.match(/\\d+/g).map(Number);
    var dark = (bg[0] * 299 + bg[1] * 587 + bg[2] * 114) / 1000 < 128, r = document.documentElement.style;
    r.setProperty('--ink', dark ? '#fafafa' : '#09090b');
    r.setProperty('--muted', dark ? '#a1a1aa' : '#52525b');
    r.setProperty('--line', dark ? '#27272a' : '#e4e4e7');
  }} catch (e) {{}}
}})();
</script></body></html>"""


DATE_TEST = "results/date_field_test.json"
DATE_LOCKED_ARM = "C"                         # tools/build_leak_demo.py TESTS["date"]["locked"]
FIELD_REPORT = "results/field_report.json"


def date_test_cost():
    """The date test's own cost of the time lock, initial pass: valid evidence the locked arm dropped (not check E)."""
    arm = read_json(DATE_TEST)["metrics"]["arms"][DATE_LOCKED_ARM]
    return int(arm["valid_lost"]), int(arm["valid_total"])


def hero(t):
    """One titled row (date test): 'x/n → y/n' cases leaked on the pre-registered initial pass (the primary result),
    then the date test's own cost of the time lock (initial pass), then one line with the update after the logged
    archive retry, all from the results files. The markup is the final state: no count, no hidden start state."""
    import html
    d = t["date"]
    o, k, n = int(d["open"]["first"]), int(d["locked"]["first"]), int(d["cases"])
    ro, rk = int(d["open"]["retry"]), int(d["locked"]["retry"])
    failed = int(read_json(FIELD_REPORT)["date_test"]["retry"]["failed_urls"])
    missed, quotes = date_test_cost()
    leaked = "cases leaked (pre-registered)"
    update = (f"Update: {ro}/{n} with no time lock after retrying the {failed} failed Wayback archive lookups; "
              f"{rk}/{n} with the time lock.")
    st.iframe(HERO_HTML.format(
        font=HERO_FONT, open=o, locked=k, n=n, missed=missed, quotes=quotes,
        title=html.escape(f"Date test · {n} past cases · pre-registered initial pass"),
        open_label=html.escape(f"{OPEN}: {leaked}"), locked_label=html.escape(f"{LOCKED}: {leaked}"),
        cost_label="Cost: valid evidence dropped (initial pass)", update=html.escape(update),
        aria=html.escape(f"Date test, {n} past cases, pre-registered initial pass. {OPEN}: {o}/{n} {leaked}. "
                         f"{LOCKED}: {k}/{n}. Cost: {missed} of {quotes} valid evidence dropped (initial pass). "
                         f"{update}")),
        height=HERO_HEIGHT)


def totals(t, n):
    d, f, s = t["date"], t["finance"], t["strictness"]
    st.subheader(f"All {n} cases", anchor="all-cases")
    def cell(x, n, w):
        return f"{x} of {n} ({wilson(w)})"
    rows = []
    for label, x in (("Date test (cases with a confirmed leak)", d), ("Finance check (events with a confirmed leak)", f)):
        n = x["cases"]
        rows.append({"Test": label,
                     "No time lock (pre-registered)": cell(x["open"]["first"], n, x["open"]["first_wilson95"]),
                     f"No time lock, {AFTER_RETRY}": cell(x["open"]["retry"], n, x["open"]["retry_wilson95"]),
                     "Tavily time lock (pre-registered)": cell(x["locked"]["first"], n, x["locked"]["first_wilson95"]),
                     f"Time lock, {AFTER_RETRY}": cell(x["locked"]["retry"], n, x["locked"]["retry_wilson95"])})
    lock_table(rows, lambda row, col: "open" if col.startswith("No ") else "lock" if "ime lock" in col else None)
    st.markdown(f"**The cost of strictness.** The time lock also drops good evidence: the dated search missed "
                f"**{s['missed']} of {s['quotes']}** known-good quotes that the undated search found "
                f"({wilson(s['wilson95'])}, Wilson 95%).")
    st.page_link("app_pages/field_report.py", label="Field Report: every measurement, with its file",
                 icon=":material/science:")
    return d, f, s


def method(data, d, f, s):
    note = data["labels_note"]
    with st.expander("Method, intervals and source files"):
        st.markdown(f"- **Labels:** {note}. Badges: LEAK = confirmed leak (Wayback), OK = confirmed before the "
                    "cutoff (Wayback), UNCHECKED = no archive confirmation either way.\n"
                    "- **Intervals:** Wilson 95% in brackets. The initial pass is the pre-registered result; the retry "
                    "only recovered Wayback lookups that had failed on the network (logged). A confirmed leak needs "
                    "the Wayback Machine to show the page appeared after the cutoff.\n"
                    f"- **Files:** `results/leak_demo.json`; totals `{d['source']}`, `{f['source']}`; cost of "
                    f"strictness `{s['source']}`.")



def live():
    from shadow_cpi import leak_live as LL
    from shadow_cpi import live_run as L
    st.subheader("Try it live")
    if not L.enabled():
        st.caption("Live mode is off on this copy of the app (it opens only when RUN_LIVE_ENABLED is set). "
                   "Everything above is saved results.")
        return
    st.caption(f"Type a question and pick a cutoff: we run both searches ({LL.BASE['search_depth']}, "
               f"{LL.BASE['max_results']} results) and label each result "
               "only “date flag” (Tavily's published date is after the cutoff, or missing) or “safe”. A date flag is "
               "not a confirmed leak: live mode does no Wayback check and calls no model.")
    with st.form("leak_live"):
        q = st.text_input("Question", max_chars=LL.MAX_QUESTION,
                          placeholder="e.g. RBI repo rate decision October 2026")
        cut = st.date_input("Cutoff date", value=date.today() - timedelta(days=60),
                            max_value=date.today() - timedelta(days=1), min_value=date(2024, 1, 1))
        go = st.form_submit_button("Run both searches")
    st.session_state.setdefault("live_runs", 0)
    if go:
        if not q.strip():
            st.warning("Type a question to start.")
            return
        ok, msg = L.gate(st.session_state["live_runs"], tavily_only=True)
        if not ok:
            st.info(msg.replace(" Showing the saved run.", ""))
            return
        st.session_state["live_runs"] += 1
        try:
            st.session_state["leak_live_result"] = LL.run_pair(L.setting(L.KEY_VARS[0]), q, cut.isoformat())
        except Exception as e:                       # never raise to the page
            st.session_state["leak_live_result"] = None
            st.info(f"The live search could not finish ({type(e).__name__}).")
    res = st.session_state.get("leak_live_result")
    if res:
        st.markdown(f"**“{res['question']}”**, cutoff {human(res['cutoff'])}")
        left, right = st.columns(2)
        for col, title, note, side in ((left, OPEN, OPEN_NOTE, "open"), (right, LOCKED, LOCKED_NOTE, "locked")):
            with col:
                column_head(title, note)
                for r in res[side]["results"]:
                    line = f"{link(r['title'], r['url'])}  \nTavily published_date {human(r['published_date'])}"
                    (st.warning if r["label"] == "date flag" else st.success)(f"{line} · **{r['label']}**")
                with st.expander("Request sent, credits, latency"):
                    st.json(res[side]["request"], expanded=True)
                    st.caption(f"Credits {res[side]['credits']} · latency {res[side]['latency_s']} s · request id "
                               f"`{res[side]['request_id']}`")




def brand():
    """The first screen's identity: a small wordmark, the headline as the page's H1, the shortened tagline, and link
    buttons (Field Report, GitHub, and the video only when common.VIDEO_URL is set)."""
    with st.container(key="brand"):
        with st.container(key="wordmark"):
            st.markdown(BRAND)
        st.title(BRAND_LINE)
        st.markdown(TAGLINE)
        with st.container(key="brand-links", horizontal=True, gap="small", vertical_alignment="center"):
            st.page_link("app_pages/field_report.py", label="Field Report", icon=":material/science:")
            st.link_button("GitHub", GITHUB_URL, icon=":material/code:")
            if VIDEO_URL:
                st.link_button("Watch the video", VIDEO_URL, icon=":material/play_circle:")


def pick_cases(cases, shown):
    """'Recommended examples (n)' or 'All N cases'; the second opens a picker of every case (its ID in small grey
    text on the case heading, as before)."""
    by_id = {c["id"]: c for c in cases}
    rec, every = f"Recommended examples ({len(shown)})", f"All {len(cases)} cases"
    mode = st.selectbox("Cases", [rec, every], label_visibility="collapsed")
    with st.expander("How these examples were picked"):
        st.caption(f"Default: {EXAMPLES.format(n=len(cases))}. Rule: {EXAMPLE_RULE}. Cases that qualify: "
                   f"{', '.join(shown)}" + (" (only one qualifies, so one is shown)." if len(shown) == 1 else "."))
    if mode == rec:
        return shown
    return [st.selectbox("Case", list(by_id), format_func=lambda k: f"{case_title(by_id[k])} · {k}")]


brand()
header("Leak demo", eyebrow=True)
data = read_json("results/leak_demo.json")
if not data:
    st.info("Not built yet: run `python tools/build_leak_demo.py` (offline, 0 credits).")
    st.stop()
with st.container(key="hero"):          # style.css sets its height on wide screens and phones
    hero(data["totals"])
with st.container(key="use-it"):
    st.markdown("**Use it**")
    st.code(USE_IT, language="python", wrap_lines=True)
    st.markdown(f"[`timelock/`]({GITHUB_URL}/tree/main/timelock) (standard library only) · "
                f"[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)]({COLAB}) "
                "reproduce the leak with your own Tavily key")
by_id = {c["id"]: c for c in data["cases"]}
shown = examples(data["cases"])
cases = pick_cases(data["cases"], shown)
for tab, cid in zip(st.tabs([tab_label(by_id[x]) for x in cases]) if len(cases) > 1
                    else [st.container()], cases):
    with tab:
        show_case(by_id[cid])
st.divider()
method(data, *totals(data["totals"], len(data["cases"])))
live()
