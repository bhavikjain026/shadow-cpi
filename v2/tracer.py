#!/usr/bin/env python3
"""v2 issue 1, the tracer bullet: one basket item end to end (milk, Madhya Pradesh, April 2026).

    python -m v2.tracer                 # may spend credits (hard cap 'v2-issue1' in config/budget.json)
    python -m v2.tracer --cache-only    # re-run from the cache, 0 credits

1. Tavily Search proposes pages (English + Hindi, dates locked to the window that ends at the cutoff).
2. Nemotron Nano reads the price from the search snippet and cites a line.
3. Tavily Extract fetches the page; the text is saved and hashed (SHA-256) at fetch time.
4. Code verifies the cited line is on the page, the price is in it, and the page date is inside the window
   (v2.rules.verify); every claim goes to the v2 evidence ledger, verified or rejected, with the reason.
5. The verified change moves the CPI needle (v2.needle). The run is saved for the Live build page.
"""
import calendar
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from shadow_cpi import evidence as E  # noqa: E402
from shadow_cpi.budget import Budgeted, spent  # noqa: E402
from shadow_cpi.event_rules import absolute_change, base_price, normalise_date  # noqa: E402
from shadow_cpi.nemotron import Nemotron  # noqa: E402
from shadow_cpi.recorder import Recorder  # noqa: E402
from shadow_cpi.settings import models  # noqa: E402
from shadow_cpi.tavily import Tavily, best_date  # noqa: E402
from shadow_cpi.verify import norm, split_lines  # noqa: E402
from v2 import ledger as LG  # noqa: E402
from v2 import rules as R  # noqa: E402
from v2.needle import needle, trend_only  # noqa: E402

BUDGET = "v2-issue1"
QUERIES = {"milk": [("en", "milk price hike per litre Madhya Pradesh"),
                    ("hi", "मध्य प्रदेश दूध के दाम बढ़े प्रति लीटर")]}
OUT = LG.ROOT


def claim_of(ev):
    """A Nano price event -> the claim the verifier checks (the price number must be in the cited line)."""
    price = next((ev[k] for k in ("new_price", "pct_change", "old_price") if ev.get(k) is not None), None)
    return {"line": ev.get("quote") or "", "price": price, "unit": ev.get("unit"), "region": ev.get("region"),
            "old_price": ev.get("old_price"), "new_price": ev.get("new_price"), "pct_change": ev.get("pct_change"),
            "effective_date": ev.get("effective_date")}


def context_for(page_text, line):
    """Title + the sentences around the cited line on the fetched page (for the retail/wholesale check)."""
    lines = split_lines(page_text)
    n = next((i + 1 for i, l in enumerate(lines) if norm(line) and norm(line) in norm(l)), None)
    return E.line_context(page_text, n) if n else (lines[0] if lines else "")


def run(month="2026-04", item="milk", state="madhya pradesh", cache_only=False):
    cfg = R.ITEMS[item]
    start, end = R.window(month)
    rec = Recorder()
    tav = Budgeted(Tavily(recorder=rec), [BUDGET], cache_only=cache_only)
    nem, nano = Nemotron(recorder=rec), models()["small"]
    found = datetime.now(timezone.utc).date().isoformat()
    cards, by_url = [], {}
    for lang, q in QUERIES[item]:
        resp, sid = tav.search(q, topic="news", search_depth="basic", max_results=8, start_date=start, end_date=end,
                               include_domains=E.INDIAN_NEWS if lang == "en" else E.HINDI_NEWS,
                               include_domains_mode="prefer", **({"language": "hi"} if lang == "hi" else {}),
                               tag=f"v2:{item} search")
        for r in resp.get("results", []):
            if r["url"] in by_url:
                continue
            d, _ = best_date(r)
            card = {"url": r["url"], "domain": urlparse(r["url"]).netloc.removeprefix("www."),
                    "title": r.get("title") or "", "lang": lang, "published": d or None, "search_call": sid,
                    "status": "rejected", "reason": "", "claims": []}
            by_url[r["url"]] = card
            cards.append(card)
            if not d or d > end or d < start:          # no Nano read for pages outside the window
                card["reason"] = ("no publication date" if not d else
                                  f"published {d}, after the cutoff {end}" if d > end else
                                  f"published {d}, before the window ({start})")
                continue
            evs, _ = nem.price_events(nano, f"{r.get('title') or ''}\n{r.get('content') or ''}",
                                      tag=f"v2:{item} nano read", parent=sid)
            card["claims"] = [claim_of(e) for e in evs if e.get("quote")]
            if not card["claims"]:
                card["reason"] = "Nano found no price in the search text"
    # Extract the proposed pages that carry a claim; save and hash the text at fetch time
    todo = [c for c in cards if c["claims"]]
    for k in range(0, len(todo), 5):
        batch = todo[k:k + 5]
        resp, eid = tav.extract([c["url"] for c in batch], extract_depth="basic", tag=f"v2:{item} extract")
        pages = {p["url"]: p.get("raw_content") or "" for p in resp.get("results", [])}
        for c in batch:
            c["extract_call"] = eid
            text = pages.get(c["url"], "")
            if not text:
                c["reason"] = "Tavily Extract could not fetch the page"
                continue
            sha = R.text_hash(text)
            c["page_sha256"], c["page_file"] = sha, LG.save_page(text, sha)
            if E.leak_line(text, month):
                c["reason"] = "the page states the official CPI figure for the month"
                continue
            reasons = []
            for cl in c["claims"]:
                ok, why = R.verify(cl, text, c["published"], month, item, state, context_for(text, cl["line"]))
                eff = normalise_date(cl.get("effective_date"), c["published"]) or None
                change = R.change_of(cl)
                base = None
                if change is None and ok:
                    amount = absolute_change(cl["line"])
                    b = base_price(item, eff or c["published"])
                    if amount is not None and b:
                        base = b[0]
                        change = amount / base
                if ok and not (eff and eff.startswith(month)):
                    ok, why = False, f"effective date {eff or 'not stated'} is not in {month}"
                cl.update({"status": "verified" if ok else "rejected", "reason": why, "effective_date": eff,
                           "change": change, "base_price": base})
                reasons.append(why)
                LG.append({"id": f"{month}:{item}:{sha[:12]}:{R.text_hash(cl['line'])[:8]}", "month": month,
                           "cutoff": end, "cpi_item": cfg["cpi_code"], "cpi_name": cfg["cpi_name"], "item": item,
                           "place": cl.get("region") or "", "state": state, "unit": cl.get("unit") or "",
                           "price_type": "retail price change", "price": cl.get("price"),
                           "old_price": cl.get("old_price"), "new_price": cl.get("new_price"), "change": change,
                           "published_date": c["published"], "effective_date": eff, "found_date": found,
                           "line": cl["line"], "url": c["url"], "page_sha256": sha, "page_file": c["page_file"],
                           "status": "verified" if ok else "rejected", "reason": why, "search_call": c["search_call"],
                           "extract_call": eid, "model": nano})
            if any(cl["status"] == "verified" for cl in c["claims"]):
                c["status"], c["reason"] = "verified", "verified"
            else:
                c["reason"] = reasons[0] if reasons else "no claim to check"
    # one event per item x state x month (v1 Amendment 3 d): median change, earliest effective date
    ok = [cl for c in cards for cl in c["claims"] if cl.get("status") == "verified" and cl.get("change") is not None]
    nd = None
    if ok:
        change = statistics.median(cl["change"] for cl in ok)
        eff = min(cl["effective_date"] for cl in ok)
        days = calendar.monthrange(int(month[:4]), int(month[5:]))[1]
        share = (days - int(eff[8:]) + 1) / days
        before, after, applied = needle(month, cfg["cpi_code"], change, share, state)
        nd = {"before": before, "after": after, "applied_item_change": applied, "change": change,
              "effective_date": eff, "share_of_month": share, "n_verified": len(ok)}
    out = {"month": month, "item": item, "cpi_item": cfg["cpi_code"], "cpi_name": cfg["cpi_name"], "state": state,
           "cutoff": end, "window": [start, end], "queries": QUERIES[item], "model_read": nano,
           "built_utc": datetime.now(timezone.utc).isoformat(), "cards": cards, "needle": nd,
           "trend_only": trend_only(month), "credits_budget": BUDGET, "credits_spent": spent(BUDGET)}
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"run_{month}_{item}_{state.replace(' ', '-')}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    return out, path


if __name__ == "__main__":
    o, p = run(cache_only="--cache-only" in sys.argv)
    print(f"{len(o['cards'])} cards, {sum(c['status'] == 'verified' for c in o['cards'])} verified; "
          f"needle {o['needle']}; credits spent ({BUDGET}) {o['credits_spent']}; wrote {p.relative_to(ROOT)}")
