#!/usr/bin/env python3
"""Build the Devpost gallery: four 1600x900 PNGs in docs/gallery/. Offline, 0 credits, 0 Nemotron calls.

    streamlit run app.py --server.port 8541           # in another terminal, for the two app shots
    python tools/build_gallery.py --app http://localhost:8541
    python tools/build_gallery.py                     # the two diagrams only

Two shots of the app (the Leak demo's first screen, the Field Report's four-arm table) and two diagrams drawn from
the results files:
the R196 timeline (results/asof_demo_r196.json) and the pipeline flow. Captions live in docs/gallery/README.md, rendered
from docs/templates/gallery.md by tools/sync_doc_numbers.py. Needs Playwright with Chromium (dev only, not in
requirements.txt: the deployed app does not use it).
"""
import html
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "gallery"
W, H = 1600, 900
# The Leak demo's first screen (the default page, at the top) -> PNG
FIRST_SCREEN = "1_leak_demo.png"
# Field Report section heading -> PNG (the heading is scrolled to the top; the sidebar and toolbar are hidden)
APP_SHOTS = {"Who should write the search? Four arms, pre-registered": "2_four_arm_table.png"}
HIDE_CHROME = ('[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"],header,'
               '[data-testid="stToolbar"],[data-testid="stDecoration"]{display:none!important}')

STYLE = """
* { box-sizing: border-box; margin: 0; }
body { width: 1600px; height: 900px; background: #ffffff; color: #1b1f24;
       font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; padding: 72px 96px; }
h1 { font-size: 44px; font-weight: 700; letter-spacing: -0.5px; }
.sub { font-size: 24px; color: #57606a; margin-top: 12px; }
.foot { position: absolute; left: 96px; bottom: 56px; font-size: 20px; color: #57606a; }
code { font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 0.92em; }
"""


def day_month(iso):
    d = date.fromisoformat(iso[:10])
    return f"{d.day} {d:%b}"


def timeline_html(demo):
    """R196: Tavily's date and the cutoff, then the page's edit after it, and extract_as_of's refusal."""
    ev = demo["evidence"]
    days = [date.fromisoformat(x) for x in (ev["tavily_date"], demo["cutoff"], ev["page_date"])]
    lo, hi = days[0].toordinal() - 1, days[-1].toordinal() + 1
    x = lambda d: 160 + (d.toordinal() - lo) / (hi - lo) * 1280             # noqa: E731
    marks = [(days[0], "Tavily date", "#1f6feb", "above"), (days[1], "Cutoff", "#1b1f24", "below"),
             (days[2], "Page edited", "#cf222e", "above")]
    svg = [f'<line x1="160" y1="330" x2="1440" y2="330" stroke="#8c959f" stroke-width="4"/>',
           f'<rect x="{x(days[1])}" y="300" width="{1440 - x(days[1])}" height="60" fill="#cf222e" opacity="0.08"/>',
           f'<text x="{x(days[1]) + 16}" y="296" font-size="20" fill="#cf222e">after the cutoff</text>']
    for d, label, colour, side in marks:
        cx, y = x(d), 250 if side == "above" else 430
        svg.append(f'<circle cx="{cx}" cy="330" r="16" fill="{colour}"/>')
        if label == "Cutoff":
            svg.append(f'<line x1="{cx}" y1="240" x2="{cx}" y2="360" stroke="{colour}" stroke-width="4" '
                       'stroke-dasharray="10 8"/>')
        svg.append(f'<text x="{cx}" y="{y - 34}" font-size="30" font-weight="700" fill="{colour}" '
                   f'text-anchor="middle">{label}</text>')
        svg.append(f'<text x="{cx}" y="{y + 6}" font-size="30" fill="#1b1f24" text-anchor="middle">'
                   f'{day_month(d.isoformat())}</text>')
    reason = demo["as_of"]["provenance"]["reason"]
    return f"""<html><head><style>{STYLE}
.box {{ position: absolute; left: 96px; right: 96px; top: 600px; border: 3px solid #cf222e; border-radius: 14px;
        padding: 26px 32px; font-size: 30px; }}
.box b {{ color: #cf222e; }}
</style></head><body>
<h1>{html.escape(demo['row_id'])}: a search date does not freeze the page</h1>
<div class="sub">A results preview Tavily dated before the cutoff, edited after it with a link to the result</div>
<svg width="1600" height="520" style="position:absolute;left:0;top:150px">{''.join(svg)}</svg>
<div class="box"><code>extract_as_of</code>: <b>{html.escape(reason)}</b> &nbsp;·&nbsp; the archive's earliest
capture is {day_month(ev['first_capture'])}, after the cutoff, so it refuses rather than return today's page</div>
<div class="foot">Source: results/asof_demo_r196.json ({html.escape(demo['label'])})</div>
</body></html>"""


# The quote-check box of the flow diagram. docs/templates/gallery.md's caption repeats these words, and
# tests/test_gallery_flow.py checks that the box names Nemotron and Nebius. No model IDs: they change on 9 Nov.
QUOTE_CHECK_TITLE = "Quote check"
QUOTE_CHECK_MODEL = "Nemotron on Nebius Token Factory: Nano screens the page, Super cites the exact line"
QUOTE_CHECK_CODE = "code checks the number on the page"
QUOTE_CHECK_LABEL = "Nebius Token Factory"


def flow_steps():
    return [("Tavily search", "dated results"), ("Time lock", "dates sent; code re-checks each date"),
            ("Extract", "the page as numbered lines"), (QUOTE_CHECK_TITLE, QUOTE_CHECK_MODEL),
            ("Seal", "SHA-256 + git tag before release")]


def flow_html():
    steps = flow_steps()

    def box(t, d):
        if t == QUOTE_CHECK_TITLE:
            return (f'<div class="step wide"><div class="tag">{html.escape(QUOTE_CHECK_LABEL)}</div>'
                    f'<div class="t">{html.escape(t)}</div><div class="d">{html.escape(d)}</div>'
                    f'<div class="d code">{html.escape(QUOTE_CHECK_CODE)}</div></div>')
        return (f'<div class="step{" lock" if t == "Time lock" else ""}"><div class="t">{html.escape(t)}</div>'
                f'<div class="d">{html.escape(d)}</div></div>')

    boxes = "".join(box(t, d) + ('<div class="arrow">→</div>' if i < len(steps) - 1 else "")
                    for i, (t, d) in enumerate(steps))
    return f"""<html><head><style>{STYLE}
.row {{ position: absolute; left: 96px; right: 96px; top: 305px; display: flex; align-items: center; }}
.step {{ flex: 1; height: 280px; border: 3px solid #1f6feb; border-radius: 16px; padding: 28px 16px;
         display: flex; flex-direction: column; justify-content: center; text-align: center; background: #f6f8fa; }}
.wide {{ flex: 1.9; border-color: #76b900; }}
.tag {{ align-self: center; font-size: 16px; font-weight: 700; color: #3f6212; background: #ecfccb;
        border-radius: 8px; padding: 3px 10px; margin-bottom: 10px; }}
.code {{ font-weight: 700; color: #1b1f24; margin-top: 10px; }}
.lock {{ border-color: #1b1f24; background: #1b1f24; color: #fff; }}
.lock .d {{ color: #d0d7de; }}
.t {{ font-size: 32px; font-weight: 700; }}
.d {{ font-size: 21px; color: #57606a; margin-top: 14px; line-height: 1.3; }}
.arrow {{ font-size: 48px; color: #8c959f; padding: 0 14px; }}
</style></head><body>
<h1>From search to seal</h1>
<div class="sub">The model reads and cites; code owns the dates and checks each cited number</div>
<div class="row">{boxes}</div>
<div class="foot">Shadow CPI pipeline (docs/pipeline.md)</div>
</body></html>"""


def render(page, markup, path):
    page.set_content(markup)
    page.screenshot(path=str(path), clip={"x": 0, "y": 0, "width": W, "height": H})


def first_screen(page, url, path):
    """The default page as a visitor first sees it: eyebrow, claim, subhead, the plain-words box, one real case and the
    three result cards with their captions. Sidebar and toolbar hidden, as in the other app shot."""
    sys.path.insert(0, str(ROOT))
    from app_pages.common import BRAND_LINE
    page.goto(url.rstrip("/") + "/", wait_until="networkidle")
    page.add_style_tag(content=HIDE_CHROME)
    page.get_by_role("heading", name=BRAND_LINE, exact=True).wait_for(timeout=60_000)
    page.locator('.st-key-hero [data-testid="stMetric"]').nth(2).wait_for(timeout=60_000)   # the third card has drawn
    page.wait_for_timeout(1500)                                    # web fonts and the theme sync settle
    page.evaluate("window.scrollTo(0, 0)")
    # the crop ends just below the three cards and their captions (the chart and the rest follow below). Streamlit
    # scrolls inside its own container, so the viewport is made tall enough to hold the whole crop.
    bottom = page.locator(".st-key-hero").bounding_box()
    height = int(bottom["y"] + bottom["height"] + 12)
    page.set_viewport_size({"width": W, "height": height})
    page.wait_for_timeout(1500)
    bottom = page.locator(".st-key-hero").bounding_box()
    page.screenshot(path=str(path), clip={"x": 0, "y": 0, "width": W, "height": int(bottom["y"] + bottom["height"] + 12)})


def app_shot(page, url, heading, path):
    page.goto(f"{url.rstrip('/')}/field_report", wait_until="networkidle")
    page.add_style_tag(content=HIDE_CHROME)
    h = page.get_by_role("heading", name=heading, exact=True)
    h.wait_for(timeout=60_000)
    page.wait_for_timeout(1500)                                    # let the dataframe canvas paint
    # Streamlit headings keep room for its (hidden) toolbar above them; shrink it so the previous section is off-frame
    h.evaluate("el => { el.style.scrollMarginTop = '28px'; el.scrollIntoView({block: 'start'}); }")
    page.wait_for_timeout(800)
    # crop from just above the heading to just below the verdict line under the table (no earlier section above it,
    # no Exploratory arms or auto_parameters below it)
    top = h.bounding_box()
    verdict = page.get_by_text("Verdict (pre-registered", exact=False).first.bounding_box()
    y0 = max(0, int(top["y"] - 12))
    y1 = int(verdict["y"] + verdict["height"] + 12)
    page.screenshot(path=str(path), clip={"x": 0, "y": y0, "width": W, "height": y1 - y0})


def main(argv):
    from playwright.sync_api import sync_playwright
    OUT.mkdir(parents=True, exist_ok=True)
    demo = json.loads((ROOT / "results" / "asof_demo_r196.json").read_text(encoding="utf-8"))
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": W, "height": H}, color_scheme="light")
        render(page, timeline_html(demo), OUT / "3_r196_timeline.png")
        render(page, flow_html(), OUT / "4_flow.png")
        if "--app" in argv:
            url = argv[argv.index("--app") + 1]
            first_screen(page, url, OUT / FIRST_SCREEN)
            for heading, name in APP_SHOTS.items():
                app_shot(page, url, heading, OUT / name)
        browser.close()
    print("wrote", ", ".join(sorted(p.name for p in OUT.glob("*.png"))))


if __name__ == "__main__":
    main(sys.argv[1:])
