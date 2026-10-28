"""Accessibility audit of a running copy of the app (display only, 0 credits, no API call):

    python tools/a11y_audit.py http://localhost:8501 [screenshots_dir]

- Contrast: on every page, with every expander opened, at 1440 and 390 px wide, in the light and dark themes, each
  visible text element's colour (opacity included) against the backgrounds behind it (tools/a11y_contrast.js);
  target 4.5:1. Two kinds are checked by hand instead and counted as `manual`: a slider's value label (it sits above
  the slider thumb, whose fill the script would mistake for its background) and white labels drawn on chart tiles.
- Keyboard: on every page at 1440 px (light), Tab from the top until focus comes round again; every stop must show a
  visible focus ring.
Writes results/accessibility_check.json (read by the app footer and the README). Needs Playwright with Chromium
(`pip install playwright && playwright install chromium`), which the app itself does not use.
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
BASE, OUT = sys.argv[1].rstrip("/"), ROOT / "results" / "accessibility_check.json"
SHOTS = Path(sys.argv[2]) if len(sys.argv) > 2 else None
PAGES = ["", "leak_demo", "home", "use_it", "field_report", "radar", "evidence", "replay", "live_build", "custody",
         "as_of", "research", "tavily_trace", "flight_recorder", "archive", "brief"]
JS = (Path(__file__).parent / "a11y_contrast.js").read_text().strip()
JS = JS[JS.index("{") + 1: JS.rindex("}")]           # body of the async arrow -> page.evaluate function
JS = "async()=>{" + JS + "}"

KEY = """async (n)=>{
 const vis=e=>{const r=e.getBoundingClientRect();const s=getComputedStyle(e);return r.width>0&&r.height>0&&s.visibility!=='hidden'};
 const main=document.querySelector('[data-testid="stMain"]');
 const want=[...main.querySelectorAll('a[href],button:not([disabled]),input:not([disabled]),textarea,select,summary,[role="tab"],[role="radio"],[tabindex="0"]')].filter(vis);
 return want.length}"""


def idle(page):
    page.wait_for_selector('[data-testid="stMain"]', timeout=60000)
    for _ in range(80):
        if page.evaluate("!document.querySelector('[data-testid=\"stStatusWidget\"]')"):
            break
        page.wait_for_timeout(250)
    page.wait_for_timeout(1500)


def focus_ok(page):
    return page.evaluate("""()=>{const e=document.activeElement;if(!e||e===document.body)return null;
      const s=getComputedStyle(e);const ring=(s.outlineStyle!=='none'&&parseFloat(s.outlineWidth)>0)||s.boxShadow!=='none';
      let inner=false;for(const k of e.querySelectorAll('*')){const t=getComputedStyle(k);if(t.boxShadow!=='none'||t.outlineStyle!=='none'){inner=true;break}}
      const p=e.parentElement?getComputedStyle(e.parentElement):null;
      const pr=p&&(p.boxShadow!=='none'||(p.outlineStyle!=='none'&&parseFloat(p.outlineWidth)>0)||p.borderColor);
      return {tag:e.tagName,role:e.getAttribute('role'),txt:(e.innerText||e.value||e.getAttribute('aria-label')||'').trim().slice(0,30),
        ring:ring||inner,main:!!e.closest('[data-testid="stMain"]')}}""")


res = {"contrast": [], "keyboard": []}
with sync_playwright() as p:
    b = p.chromium.launch()
    for scheme in ("light", "dark"):
        for w, h in ((1440, 900), (390, 844)):
            ctx = b.new_context(viewport={"width": w, "height": h}, color_scheme=scheme, device_scale_factor=1)
            pg = ctx.new_page()
            for path in PAGES:
                pg.goto(f"{BASE}/{path}")
                idle(pg)
                r = json.loads(pg.evaluate(JS))
                r.update(scheme=scheme, bg=pg.evaluate("getComputedStyle(document.querySelector('.stApp')).backgroundColor"))
                res["contrast"].append(r)
                print(scheme, w, path or "/", r["n"], r["nf"], r["fails"][:3], flush=True)
            ctx.close()
    # keyboard: 1440 light, Tab through each page
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light")
    pg = ctx.new_page()
    for path in PAGES:
        pg.goto(f"{BASE}/{path}")
        idle(pg)
        want = pg.evaluate(KEY, 0)
        seen, noring, inmain = [], [], 0
        for i in range(400):
            pg.keyboard.press("Tab")
            f = focus_ok(pg)
            if not f:
                continue
            key = (f["tag"], f["role"], f["txt"])
            if seen and key == seen[0] and i > 5:
                break
            seen.append(key)
            inmain += f["main"]
            if not f["ring"]:
                noring.append(key)
        r = {"p": path or "/", "interactive_in_main": want, "tab_stops": len(seen), "tab_stops_in_main": inmain,
             "no_visible_ring": noring[:8], "n_no_ring": len(noring)}
        res["keyboard"].append(r)
        print("kbd", r, flush=True)
    ctx.close()
    # screenshots of the landing page (light) at both widths
    for w, h in ((1440, 900), (390, 844)) if SHOTS else ():
        SHOTS.mkdir(parents=True, exist_ok=True)
        ctx = b.new_context(viewport={"width": w, "height": h}, color_scheme="light", device_scale_factor=1)
        pg = ctx.new_page()
        pg.goto(BASE + "/")
        idle(pg)
        pg.screenshot(path=str(SHOTS / f"search_the_past_{w}.png"))
        ctx.close()
    b.close()
c, k = res["contrast"], res["keyboard"]
summary = {"checked_ist": datetime.now(timezone(timedelta(hours=5, minutes=30))).date().isoformat(),
           "pages": len(PAGES), "widths_px": [1440, 390], "themes": ["light", "dark"], "min_contrast": 4.5,
           "text_elements": sum(x["n"] for x in c), "below_min": sum(x["nf"] for x in c),
           "checked_by_hand": sum(x["manual"] for x in c),
           "keyboard_pages": len(k), "keyboard_stops": sum(x["tab_stops"] for x in k),
           "keyboard_stops_without_ring": sum(x["n_no_ring"] for x in k)}
OUT.write_text(json.dumps({"summary": summary, **res}, indent=1) + "\n", encoding="utf-8")
print(json.dumps(summary))
