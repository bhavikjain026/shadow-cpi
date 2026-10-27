"""Leak demo (the home page): can a web search see the future? Past questions replayed as of a cutoff date, each
searched with no time lock and with Tavily's time lock. Built only from saved results (results/leak_demo.json, made
offline by tools/build_leak_demo.py from the date test and the finance check; totals from results/field_report.json
and results/leakcheck_exact_match.json). The only API calls are the optional live mode, off unless RUN_LIVE_ENABLED."""
from datetime import date, timedelta

import streamlit as st

from app_pages.common import header, lock_table, read_json

OPEN, OPEN_NOTE = "No time lock", "default search, no dates"
LOCKED, LOCKED_NOTE = "Tavily time lock", "start_date/end_date + filter_by_published_date"
EXAMPLES = "examples chosen for clarity; all {n} in the picker and the totals below"
FIRST = "F3"                                  # petrol (date test) leads
EXAMPLE_RULE = ("a Wayback-confirmed leak with no time lock, and every time-locked result confirmed before the "
                "cutoff (no UNCHECKED)")
UNCHECKED_HELP = "no archive check was made for this result"
OK_LABELS = ("confirmed pre-cutoff", "valid")


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
    return f"{c['id']} · {c['test_name']} · {c['name']} · cutoff {human(c['cutoff'])} · “{c['query']}”"


def wayback(label):
    """The label without the '(Wayback)' it repeats after 'Wayback:'."""
    return label.replace(" (Wayback)", "").replace(", Wayback)", ")")


def result_line(r, test):
    page = f" · Page: {human(r['page_date'])}" if test == "date" else ""
    first = (f" (initial pass: {wayback(r['label_first_pass'])})"
             if r.get("label_first_pass") and r["label_first_pass"] != r["label"] else "")
    return (f"{badge(r)} {link(r['title'], r['url'])}  \nTavily: **{human(r['published_date'])}**{page} · "
            f"Wayback: **{wayback(r['label'])}**{first}")


def column_head(title, note):
    st.markdown(f"**{title}**")
    st.caption(note)


def search_column(col, title, note, s, test):
    with col:
        column_head(title, note)
        if not s["results"]:
            st.caption("No results.")
        for r in s["results"]:
            if r.get("leak"):
                st.error(result_line(r, test) + f"  \nPublished **{r['days_after_cutoff']} days after the cutoff**."
                         + (f"  \n> {r['quote']}" if r.get("quote") else ""))
            else:
                st.markdown(result_line(r, test), help=badge_help(r))
        with st.expander("Request sent, credits, latency"):
            st.json(s["request"], expanded=True)
            st.caption(f"The API key travels in a request header and is never part of the body. Credits "
                       f"{s['credits']} · latency {s['latency_s']:.2f} s (Tavily's response_time) · request id "
                       f"`{s['request_id']}`")


def show_case(c):
    st.markdown(f"#### {case_title(c)}")
    if c["test"] == "finance":
        st.caption("Page dates not read in the finance check.")
    left, right = st.columns(2)
    search_column(left, OPEN, OPEN_NOTE, c["open"], c["test"])
    search_column(right, LOCKED, LOCKED_NOTE, c["locked"], c["test"])


# The app's only JavaScript animation: anime.js (MIT), exact version from cdnjs with its SRI hash (THIRD_PARTY_NOTICES.md).
ANIME_JS = ("https://cdnjs.cloudflare.com/ajax/libs/animejs/4.5.0/anime.umd.min.js",
            "sha512-dnhflec5WaXvpVYrt0oWfe0iUyWpjNiZbxkjrhNu9WAWWHLX7VqqyxCZHL7dWCrwj6lN+XGN9FtiWIBgX2b/PA==")
HERO_HEIGHT = 128          # content is 104 px at 390 px wide and 120 px at 1440 px ("content" sizing left 150 px)
HERO_FONT ="https://fonts.googleapis.com/css2?family=Inter:wght@500&family=JetBrains+Mono:wght@600&display=swap"
HERO_HTML = """<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="{font}"><style>
:root {{ --ink: #09090b; --muted: #52525b; --line: #e4e4e7; }}       /* no color-scheme: it paints an opaque canvas */
@media (prefers-color-scheme: dark) {{ :root {{ --ink: #fafafa; --muted: #a1a1aa; --line: #27272a; }} }}
html, body {{ margin: 0; background: transparent; color: var(--ink); font: 500 15px/1.4 Inter, sans-serif; }}
.row {{ display: flex; align-items: stretch; gap: 8px; }}
.side {{ flex: 1 1 0; min-width: 0; border: 1px solid var(--line); border-radius: 8px; padding: 12px 16px; }}
.open {{ background: rgba(255, 75, 75, 0.12); }}                      /* LOCK/OPEN colour meaning, as common.OPEN_CSS */
.num {{ font: 600 clamp(1.75rem, 7vw, 2.75rem)/1.1 "JetBrains Mono", ui-monospace, monospace;
        font-variant-numeric: tabular-nums; letter-spacing: -0.03em; white-space: nowrap; }}
.label {{ color: var(--muted); font-size: 0.875rem; margin-top: 4px; }}
.arrow {{ align-self: center; color: var(--muted); font-size: 1.25rem; }}
.sub {{ color: var(--muted); font-size: 0.875rem; margin: 8px 0 0; }}
</style></head><body>
<div class="row" role="img" aria-label="{aria}">
  <div class="side open"><div class="num"><span id="leaked">{open}</span>/{n}</div><div class="label">{open_label}</div></div>
  <div class="arrow" aria-hidden="true">→</div>
  <div class="side locked" id="locked"><div class="num">{locked}/{n}</div><div class="label">{locked_label}</div></div>
</div>
<p class="sub" id="sub">{sub}</p>
<script src="{js}" integrity="{sri}" crossorigin="anonymous"></script>
<script>
(function () {{
  // Match the app's theme when the parent page is readable (same origin); else prefers-color-scheme above.
  try {{
    var app = window.parent.document.querySelector('[data-testid="stApp"]');
    var bg = window.parent.getComputedStyle(app).backgroundColor.match(/\\d+/g).map(Number);
    var dark = (bg[0] * 299 + bg[1] * 587 + bg[2] * 114) / 1000 < 128, r = document.documentElement.style;
    r.setProperty('--ink', dark ? '#fafafa' : '#09090b');
    r.setProperty('--muted', dark ? '#a1a1aa' : '#52525b');
    r.setProperty('--line', dark ? '#27272a' : '#e4e4e7');
  }} catch (e) {{}}
  // One count, once. Final values are already in the markup: no script, reduced motion or a blocked CDN shows them.
  if (!window.anime || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  var el = document.getElementById('leaked'), to = Number(el.textContent), o = {{ v: 0 }};
  var later = [document.getElementById('locked'), document.getElementById('sub')];
  // Start only on a real frame (a background tab never zeroes the number), and end on the file's values by 2.5 s
  // whatever the frame rate, so the hero never rests on anything but the results file.
  requestAnimationFrame(function () {{
    el.textContent = '0';
    later.forEach(function (x) {{ x.style.opacity = 0; }});
    var tl = anime.createTimeline({{ defaults: {{ ease: 'outExpo' }} }})
      .add(o, {{ v: to, duration: 900, onUpdate: function () {{ el.textContent = Math.round(o.v); }} }})
      .add(later[0], {{ opacity: [0, 1], translateY: [6, 0], duration: 450 }}, '-=250')
      .add(later[1], {{ opacity: [0, 1], duration: 450 }}, '-=200');
    setTimeout(function () {{
      try {{ tl.pause(); }} catch (e) {{}}
      el.textContent = to;
      later.forEach(function (x) {{ x.style.opacity = 1; x.style.transform = 'none'; }});
    }}, 2500);
  }});
}})();
</script></body></html>"""


def hero(t):
    """The headline 'x/n → y/n' (date test, after retry) from the same totals as summary_line, counted up once."""
    import html
    d = t["date"]
    o, k, n = int(d["open"]["retry"]), int(d["locked"]["retry"]), int(d["cases"])
    st.iframe(HERO_HTML.format(
        font=HERO_FONT, js=ANIME_JS[0], sri=ANIME_JS[1], open=o, locked=k, n=n,
        open_label=html.escape(OPEN), locked_label=html.escape(LOCKED), sub="cases leaked (after retry)",
        aria=html.escape(f"{OPEN}: {o}/{n} cases leaked (after retry). {LOCKED}: {k}/{n}.")),
        height=HERO_HEIGHT)


def summary_line(t):
    d, s = t["date"], t["strictness"]
    st.markdown(f"**No time lock: {d['open']['retry']}/{d['cases']} cases leaked (after retry). Tavily time lock: "
                f"{d['locked']['retry']}/{d['cases']}. Cost: {s['missed']} of {s['quotes']} known-good quotes "
                f"missed.** [Totals below](#all-cases)")


def totals(t, n):
    d, f, s = t["date"], t["finance"], t["strictness"]
    st.subheader(f"All {n} cases", anchor="all-cases")
    def cell(x, n, w):
        return f"{x} of {n} ({wilson(w)})"
    rows = []
    for label, x in (("Date test (cases with a confirmed leak)", d), ("Finance check (events with a confirmed leak)", f)):
        n = x["cases"]
        rows.append({"Test": label, "No time lock": cell(x["open"]["first"], n, x["open"]["first_wilson95"]),
                     "No lock, after retry": cell(x["open"]["retry"], n, x["open"]["retry_wilson95"]),
                     "Tavily time lock": cell(x["locked"]["first"], n, x["locked"]["first_wilson95"]),
                     "Time lock, after retry": cell(x["locked"]["retry"], n, x["locked"]["retry_wilson95"])})
    lock_table(rows, lambda row, col: "open" if col.startswith("No ") else "lock" if "ime lock" in col else None)
    st.markdown(f"**The cost of strictness.** The time lock also drops good evidence: the dated search missed "
                f"**{s['missed']} of {s['quotes']}** known-good quotes that the undated search found "
                f"({wilson(s['wilson95'])}, Wilson 95%).")
    st.page_link("app_pages/field_report.py", label="Field Report: every measurement, with its file", icon="🧪")
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




header("Leak demo", "The same past question, searched twice as of its cutoff: no time lock vs Tavily's time lock.")
data = read_json("results/leak_demo.json")
if not data:
    st.info("Not built yet: run `python tools/build_leak_demo.py` (offline, 0 credits).")
    st.stop()
hero(data["totals"])
summary_line(data["totals"])
by_id = {c["id"]: c for c in data["cases"]}
shown = examples(data["cases"])
choice = st.selectbox("Case", ["Examples: " + ", ".join(shown)] + list(by_id),
                      format_func=lambda k: k if k.startswith("Examples") else case_title(by_id[k]))
st.caption(f"Default: {EXAMPLES.format(n=len(data['cases']))}. Rule: {EXAMPLE_RULE}. Cases that qualify: "
           f"{', '.join(shown)}" + (" (only one qualifies, so one is shown)." if len(shown) == 1 else "."))
cases = shown if choice.startswith("Examples") else [choice]
for tab, cid in zip(st.tabs([case_title(by_id[x]).split(" · “")[0] for x in cases]) if len(cases) > 1
                    else [st.container()], cases):
    with tab:
        show_case(by_id[cid])
st.divider()
method(data, *totals(data["totals"], len(data["cases"])))
live()
