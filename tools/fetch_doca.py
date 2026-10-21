#!/usr/bin/env python3
"""Human-in-the-loop fetcher for the Dept of Consumer Affairs retail price report (the spine).

    .venv/bin/python tools/fetch_doca.py            # all 6 chunks (skips chunks already saved)
    .venv/bin/python tools/fetch_doca.py 2026A      # one chunk

The report menu (fcainfoweb.nic.in/reports/report_menu_web.aspx) is behind a CAPTCHA. This script opens a VISIBLE
browser, fills in the form, then PAUSES: a person types the CAPTCHA in the browser and presses Enter in the terminal.
The script never reads, solves or guesses the CAPTCHA (it does not look at the image or the box).

Per chunk: Retail -> "Average/Month End Report" (reload) -> "Average for selected Zone" (reload) -> all 5 zones,
Monthly, From/To and the commodities set directly in the page, with NO further reload (each reload replaces the
CAPTCHA) -> pause for the person -> Get Data -> wait up to 3 minutes -> save the raw response HTML (and the Excel
export if the page offers one) to data/official/doca/raw/<chunk>.html, without rendering it.
Each fetch is logged through Recorder as a "manual-captcha direct download". Up to 2 tries per chunk; if a request
freezes (no response within 3 minutes), the commodity list is split in half and each half is tried once.
"""
import json
import select
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from shadow_cpi.recorder import Recorder  # noqa: E402

MENU = "https://fcainfoweb.nic.in/reports/report_menu_web.aspx"
RAW = ROOT / "data" / "official" / "doca" / "raw"
P = "ctl00_MainContent_"
WAIT_RESPONSE_S = 180

GROUP_A = ["Rice", "Atta (Wheat)", "Tur/Arhar Dal", "Gram Dal", "Moong Dal", "Urad Dal", "Masoor Dal", "Sugar",
           "Milk @", "Eggs"]
GROUP_B = ["Groundnut Oil (Packed)", "Mustard Oil (Packed)", "Soya Oil (Packed)", "Sunflower Oil (Packed)",
           "Palm Oil (Packed)", "Vanaspati (Packed)", "Potato", "Onion", "Tomato"]
RANGES = {"2025H1": (("December", "2024"), ("June", "2025")),
          "2025H2": (("July", "2025"), ("December", "2025")),
          "2026": (("January", "2026"), ("October", "2026"))}
CHUNKS = {f"{r}{g}": (RANGES[r], items) for r in RANGES for g, items in (("A", GROUP_A), ("B", GROUP_B))}
# Both groups in one request (fewer CAPTCHAs); used after 2025H1A/B came back quickly. Freeze -> split in half.
CHUNKS.update({f"{r}AB": (RANGES[r], GROUP_A + GROUP_B) for r in RANGES})
# Re-fetch after 2025H2AB / 2026AB were saved before they finished loading: the 12 commodities missing from 2026
# (milk and eggs were also missing for Jul-Dec 2025), Jul 2025 - Oct 2026 in one request.
CHUNKS["2025H2-2026fill"] = ((("July", "2025"), ("October", "2026")),
                             ["Sugar", "Milk @", "Eggs", "Groundnut Oil (Packed)", "Mustard Oil (Packed)",
                              "Soya Oil (Packed)", "Sunflower Oil (Packed)", "Palm Oil (Packed)", "Vanaspati (Packed)",
                              "Potato", "Onion", "Tomato"])
TRY_EXCEL = False      # the export button was not clickable on the response page (30 s wasted per chunk)

SET_FORM_JS = """([zones, monthly, fm, fy, tm, ty, items]) => {
  const byId = id => document.getElementById(id);
  const pick = (sel, texts) => { let n = 0;
    for (const o of sel.options) { const hit = texts.includes(o.text.trim()); o.selected = hit; if (hit) n++; }
    return n; };
  const one = (id, text) => { const s = byId(id); let ok = false;
    for (const o of s.options) { if (o.text.trim() === text || o.value === text) { s.value = o.value; ok = true; } }
    return ok; };
  const z = byId('P_Lst_Zone'); for (const o of z.options) o.selected = true;
  byId('P_rbl_mthly_yrly_0').checked = true;          // Monthly (no postback when set directly)
  return { zones: z.selectedOptions.length,
           from: one('P_Ddl_from_month', fm) && one('P_Ddl_from_Year', fy),
           to: one('P_Ddl_to_month', tm) && one('P_Ddl_to_Year', ty),
           commodities: pick(byId('P_Lst_Commodity'), items) };
}""".replace("P_", P)


GO_DIR = RAW / ".go"


def wait_for_person(chunk):
    """Wait until the person says the CAPTCHA is typed: Enter in this terminal, or a go-signal file
    data/official/doca/raw/.go/<chunk> (created on the person's say-so, e.g. when they reply 'enter' in the chat).
    Nothing here looks at the CAPTCHA."""
    GO_DIR.mkdir(parents=True, exist_ok=True)
    flag = GO_DIR / chunk
    flag.unlink(missing_ok=True)
    print(f"[{chunk}] Type the CAPTCHA in the browser and press Enter here (or say 'enter' in the chat)", flush=True)
    use_stdin = sys.stdin is not None and sys.stdin.isatty()     # in the background only the chat signal works
    while True:
        if flag.exists():
            flag.unlink()
            return
        if not use_stdin:
            time.sleep(1.0)
            continue
        ready, _, _ = select.select([sys.stdin], [], [], 1.0)
        if ready:
            if sys.stdin.readline() == "":                        # end of input: fall back to the chat signal
                use_stdin = False
                continue
            return


def log(rec, chunk, body, result):
    rec.call("direct", "manual-captcha", {**body, "chunk": chunk, "at": datetime.now(timezone.utc).isoformat()},
             lambda: result, tag="spine:doca manual-captcha direct download")


def prepare(page, rng, items):
    page.goto(MENU, wait_until="domcontentloaded", timeout=90_000)
    page.select_option(f"#{P}Ddl_Rpt_type", "Retail")
    with page.expect_navigation(timeout=90_000):
        page.check(f"#{P}Rbl_Rpt_type_1")                     # Average/Month End Report -> reload
    with page.expect_navigation(timeout=90_000):
        page.select_option(f"#{P}Ddl_Rpt_Option2", "Average for selected Zone")   # -> reload
    page.wait_for_selector(f"#{P}Lst_Zone", timeout=60_000)
    (fm, fy), (tm, ty) = rng
    got = page.evaluate(SET_FORM_JS, [True, True, fm, fy, tm, ty, items])
    if got["zones"] != 5 or not got["from"] or not got["to"] or got["commodities"] != len(items):
        raise RuntimeError(f"form not set as expected: {got} (wanted 5 zones, {len(items)} commodities)")
    return got


_SEEN = {}


def find_report(cands, menu_page, items):
    """The page holding the COMPLETE report: fully loaded and one table per requested commodity, or (if DoCA leaves
    some out) unchanged for 15 seconds after loading. Saving earlier cut large reports short (2025H2AB, 2026AB)."""
    for p in cands:
        try:
            if p is not menu_page:
                p.wait_for_load_state("load", timeout=5_000)
            if p.evaluate("document.readyState") != "complete":
                continue
            content = p.content()
        except Exception:  # noqa: BLE001 - page still loading
            continue
        if "<table" not in content.lower() or f"{P}Captcha" in content or \
                not any(i.split(" (")[0] in content for i in items):
            continue
        n_tables = content.count("Prices of")
        if n_tables >= len(items):
            return p, content
        key, now = id(p), time.time()
        size, since = _SEEN.get(key, (None, now))
        if size != len(content):
            _SEEN[key] = (len(content), now)
        elif now - since >= 15:
            print(f"  report stable with {n_tables} of {len(items)} commodity tables; saving what DoCA returned")
            return p, content
    return None, ""


def fetch_once(ctx, rec, chunk, rng, items):
    """One try. Returns 'ok', 'freeze' or 'error'."""
    page = ctx.new_page()
    dialogs = []
    def on_dialog(d):
        dialogs.append(d.message)
        d.dismiss()
    page.on("dialog", on_dialog)
    got = prepare(page, rng, items)
    print(f"\n[{chunk}] form set: {got}")
    page.bring_to_front()
    page.evaluate("() => { const c = document.getElementById('ctl00_MainContent_Captcha'); if (c) c.focus(); }")
    wait_for_person(chunk)
    new_pages = []

    def on_page(p):
        new_pages.append(p)
    ctx.on("page", on_page)
    target, html, rejected = None, "", False
    for wrong in range(3):                      # the site says "Captcha not correct" inside the page, not as a pop-up
        t0 = time.time()
        page.click(f"#{P}btn_getdata1", no_wait_after=True)
        rejected = False
        while time.time() - t0 < WAIT_RESPONSE_S:
            time.sleep(2)
            if dialogs:
                break
            try:
                if "captcha not correct" in page.content().lower():
                    rejected = True
                    break
            except Exception:  # noqa: BLE001 - page navigating
                pass
            target, html = find_report(new_pages + [page], page, items)
            if target:
                break
        if not rejected:
            break
        print(f"[{chunk}] the site said the CAPTCHA was not correct; re-filling the form (no reload)", flush=True)
        page.evaluate(SET_FORM_JS, [True, True, *rng[0], *rng[1], items])
        page.bring_to_front()
        wait_for_person(chunk)
    if rejected:
        dialogs.append("Captcha not correct (3 times)")
    body = {"url": MENU, "from": " ".join(rng[0]), "to": " ".join(rng[1]), "zones": "all 5", "commodities": items}
    if dialogs:
        print(f"[{chunk}] the site said: {dialogs[0]}")
        log(rec, chunk, body, {"status": "error", "site_message": dialogs[0]})
        ctx.remove_listener("page", on_page)
        page.close()
        return "error"
    if not target:
        print(f"[{chunk}] no report within {WAIT_RESPONSE_S}s")
        log(rec, chunk, body, {"status": "freeze", "seconds": round(time.time() - t0)})
        ctx.remove_listener("page", on_page)
        page.close()
        return "freeze"
    RAW.mkdir(parents=True, exist_ok=True)
    out = RAW / f"{chunk}.html"
    out.write_text(html, encoding="utf-8")                    # raw response, not rendered
    excel = None
    for sel in (("#btnsave", "input[name=btnsave]", "#ctl00_MainContent_btnsave") if TRY_EXCEL else ()):
        try:
            if target.query_selector(sel):
                with target.expect_download(timeout=60_000) as dl:
                    target.click(sel)
                excel = RAW / f"{chunk}{Path(dl.value.suggested_filename).suffix or '.xls'}"
                dl.value.save_as(excel)
                break
        except Exception as e:  # noqa: BLE001 - the export is optional
            print(f"[{chunk}] Excel export not saved ({str(e)[:80]})")
            break
    log(rec, chunk, body, {"status": "ok", "saved": str(out.relative_to(ROOT)), "bytes": len(html.encode()),
                           "excel": str(excel.relative_to(ROOT)) if excel else None,
                           "seconds": round(time.time() - t0)})
    print(f"[{chunk}] saved {out.relative_to(ROOT)} ({len(html):,} chars)" + (f" + {excel.name}" if excel else ""))
    ctx.remove_listener("page", on_page)
    for p in new_pages:
        p.close()
    page.close()
    return "ok"


def run_chunk(ctx, rec, chunk, rng, items, tries=2):
    if (RAW / f"{chunk}.html").exists():
        print(f"[{chunk}] already saved, skipping")
        return "ok"
    for attempt in range(1, tries + 1):
        try:
            status = fetch_once(ctx, rec, chunk, rng, items)
        except Exception as e:  # noqa: BLE001 - site hang while preparing the form
            print(f"[{chunk}] try {attempt} failed: {str(e)[:200]}")
            status = "error"
        if status == "ok":
            return "ok"
        if status == "freeze" and len(items) > 1 and not chunk.endswith(("-1", "-2")):
            half = len(items) // 2
            print(f"[{chunk}] froze: splitting into two halves and trying each once")
            a = run_chunk(ctx, rec, f"{chunk}-1", rng, items[:half], tries=1)
            b = run_chunk(ctx, rec, f"{chunk}-2", rng, items[half:], tries=1)
            return "ok" if a == b == "ok" else "partial"
    return "failed"


def main():
    from playwright.sync_api import sync_playwright
    want = [a for a in sys.argv[1:] if a in CHUNKS] or list(CHUNKS)
    rec = Recorder(use_cache=False)
    results = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        ctx = browser.new_context(accept_downloads=True)
        for chunk in want:
            rng, items = CHUNKS[chunk]
            results[chunk] = run_chunk(ctx, rec, chunk, rng, items)
            print(f"[{chunk}] -> {results[chunk]}")
        browser.close()
    print("\nSUMMARY " + json.dumps(results))
    (RAW / "fetch_summary.json").write_text(json.dumps({"at": datetime.now(timezone.utc).isoformat(),
                                                        "results": results}, indent=1))


if __name__ == "__main__":
    main()
