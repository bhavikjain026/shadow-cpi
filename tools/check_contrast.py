#!/usr/bin/env python3
"""Real-browser contrast check of every app page. Dev only (Playwright with Chromium, not in requirements.txt); 0 credits.

    streamlit run app.py --server.port 8541           # in another terminal
    python tools/check_contrast.py --base http://localhost:8541 --write docs/contrast_check.json

Loads each page in Chromium at each width and in each theme (the browser's prefers-color-scheme), walks every visible
text element of the main area and compares its colour with the background it sits on (the nearest opaque ancestor
colour that is drawn under the text, alpha-blended): at least RATIO for normal text, LARGE_RATIO for large text (24 px, or 18.66 px bold). Also
reports horizontal overflow. Not covered: text drawn inside chart canvases and the contents of closed expanders.
Exits 1 if any element is below its threshold or any page overflows. tests/test_aesthetic.py checks the theme's own
colour pairs the same way without a browser.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIDTHS = (1440, 390)
SCHEMES = ("light", "dark")
RATIO, LARGE_RATIO = 4.5, 3.0
PAGES = ("", "field_report", "try_it", "home", "radar", "evidence", "replay", "live_build", "custody", "as_of",
         "research", "tavily_trace", "flight_recorder", "archive", "brief")     # "" is the Leak demo, the default page

JS = """([ratio, largeRatio]) => {
const parse = c => { const m = c.match(/rgba?\\(([^)]+)\\)/); if (!m) return null;
  const p = m[1].split(/[ ,\\/]+/).filter(Boolean).map(Number); return {r:p[0], g:p[1], b:p[2], a:p.length>3?p[3]:1}; };
const lin = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
const lum = c => 0.2126 * lin(c.r) + 0.7152 * lin(c.g) + 0.0722 * lin(c.b);
const over = (t, b) => ({r: t.r*t.a + b.r*(1-t.a), g: t.g*t.a + b.g*(1-t.a), b: t.b*t.a + b.b*(1-t.a), a: 1});
const bgOf = el => { const chain = [], r0 = el.getBoundingClientRect(), cx = r0.x + r0.width / 2, cy = r0.y + r0.height / 2;
  for (let e = el; e; e = e.parentElement) { const c = parse(getComputedStyle(e).backgroundColor);
    const r = e.getBoundingClientRect(), cs = getComputedStyle(e);
    // a background counts only where it is drawn under the text's centre; the page roots and scroll containers
    // paint behind everything they hold, including content below the fold
    const root = e === document.documentElement || e === document.body || /auto|scroll/.test(cs.overflowY);
    if (c && c.a > 0 && (root || (cx >= r.left && cx <= r.right && cy >= r.top && cy <= r.bottom))) {
      chain.push(c); if (c.a >= 1) break; } }
  let base = {r:255, g:255, b:255, a:1}; for (const c of chain.reverse()) base = over(c, base); return base; };
const fails = []; const seen = new Set();
const w = document.createTreeWalker(document.querySelector('[data-testid="stMain"]') || document.body, NodeFilter.SHOW_TEXT);
while (w.nextNode()) { const n = w.currentNode; if (!n.textContent.trim()) continue;
  const el = n.parentElement; if (!el || seen.has(el)) continue; seen.add(el);
  const cs = getComputedStyle(el), r = el.getBoundingClientRect();
  if (r.width === 0 || r.height === 0 || cs.visibility === 'hidden' || cs.display === 'none') continue;
  const fg0 = parse(cs.color); if (!fg0) continue; const bg = bgOf(el);
  const fg = over({...fg0, a: fg0.a * (parseFloat(cs.opacity) || 1)}, bg);
  const a = lum(fg), b = lum(bg), got = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
  const px = parseFloat(cs.fontSize), large = px >= 24 || (px >= 18.66 && parseInt(cs.fontWeight) >= 700);
  if (got < (large ? largeRatio : ratio)) fails.push({text: n.textContent.trim().slice(0, 60), ratio: +got.toFixed(2)}); }
return {checked: seen.size, fails, overflow: document.documentElement.scrollWidth > window.innerWidth};
}"""


def main(argv):
    from playwright.sync_api import sync_playwright
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default="http://localhost:8541")
    ap.add_argument("--write", help="write the result as JSON (e.g. docs/contrast_check.json)")
    a = ap.parse_args(argv)
    rows, bad = [], 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for path in PAGES:
            row = {"path": path or "(leak demo)", "checked": 0, "below_threshold": 0, "overflow": False}
            for width in WIDTHS:
                for scheme in SCHEMES:
                    ctx = browser.new_context(viewport={"width": width, "height": 900}, color_scheme=scheme)
                    pg = ctx.new_page()
                    pg.goto(f"{a.base.rstrip('/')}/{path}", wait_until="networkidle")
                    pg.locator("h1").first.wait_for(timeout=60_000)
                    pg.wait_for_timeout(3000)
                    res = pg.evaluate(JS, [RATIO, LARGE_RATIO])
                    row["checked"] += res["checked"]
                    row["below_threshold"] += len(res["fails"])
                    row["overflow"] = row["overflow"] or res["overflow"]
                    for f in res["fails"][:5]:
                        print(f"  FAIL {row['path']} {width} {scheme}: {f['ratio']}:1 {f['text']!r}")
                    ctx.close()
            bad += row["below_threshold"] + row["overflow"]
            print(f"{row['path']:<16} {row['checked']:>6} text elements, {row['below_threshold']} below threshold, "
                  f"overflow={row['overflow']}")
            rows.append(row)
        browser.close()
    out = {"tool": "tools/check_contrast.py", "checked_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "widths": list(WIDTHS), "schemes": list(SCHEMES), "ratio": RATIO, "large_ratio": LARGE_RATIO,
           "pages": rows, "below_threshold": sum(r["below_threshold"] for r in rows),
           "overflow_pages": sum(r["overflow"] for r in rows)}
    print(f"TOTAL: {out['below_threshold']} below threshold, {out['overflow_pages']} pages with horizontal overflow")
    if a.write:
        (ROOT / a.write).write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
