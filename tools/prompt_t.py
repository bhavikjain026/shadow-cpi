#!/usr/bin/env python3
"""Prompt T: Tavily Map + Crawl of official sites, evidence chasing, and the Tavily report card.

    python tools/prompt_t.py crawl 2026-10     # Map then Crawl 5 official sites for price circulars of the month
    python tools/prompt_t.py fallback 2026-10 merc uperc   # sites where Map found nothing: section search + Crawl
    python tools/prompt_t.py chase             # <= 2 follow-up searches per verified event in the test months
    python tools/prompt_t.py card              # results/tavily_report_card.md (0 credits)

Every Tavily call charges the hard cap 'prompt-t' (90 credits, config/budget.json); chase calls also charge 'chase'.
What the crawl finds is REPORTED (results/prompt_t/), not applied: the frozen event layer (docs/frozen_rules.md §1)
searches news only. Chasing does not change any manifest or scored result. Code decides every match; Nemotron only
extracts lines, and judge_event checks them.
"""
import csv
import json
import re
import statistics
import sys
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from shadow_cpi import evidence as E  # noqa: E402
from shadow_cpi.budget import BudgetExceeded, Budgeted, account_spent, load_budget, read_ledger, spent  # noqa: E402
from shadow_cpi.nemotron import Nemotron  # noqa: E402
from shadow_cpi.recorder import Recorder, read_log  # noqa: E402
from shadow_cpi.settings import models  # noqa: E402
from shadow_cpi.tavily import Tavily, best_date, iso_date  # noqa: E402
from shadow_cpi.verify import norm  # noqa: E402

OUT = ROOT / "results" / "prompt_t"
# 3 state electricity regulators (largest electricity weights among states with a working site), one oil company,
# one dairy co-operative.
SITES = [("merc", "https://merc.gov.in", "electricity"),
         ("derc", "https://www.derc.gov.in", "electricity"),
         ("uperc", "https://www.uperc.org", "electricity"),
         ("iocl", "https://iocl.com", "fuel"),
         ("amul", "https://amul.com", "milk")]
SELECT = [r"(?i).*(tariff|order|circular|price|press|news|notice|notification|rate|media).*"]
MONTH_HI = dict(zip(range(1, 13), E.MONTHS_HI))


def month_patterns(month):
    y, m = month[:4], int(month[5:])
    en = E.MONTHS_EN[m - 1]
    return re.compile(rf"(?i)\b({en}|{en[:3]})\.?,?\s*(\d{{1,2}},?\s*)?{y}\b|\b\d{{1,2}}[./-]0?{m}[./-]{y}\b|"
                      rf"{MONTH_HI[m]}\s*,?\s*{y}")


def crawl(month):
    rec = Recorder()
    tav = Budgeted(Tavily(recorder=rec), ["prompt-t"])
    nem = Nemotron(recorder=rec)
    cfg = E.load_items()["events"]
    mname = f"{E.MONTHS_EN[int(month[5:]) - 1]} {month[:4]}"
    instr = f"find price circulars or tariff orders published in {mname}"
    pat = month_patterns(month)
    report = {"month": month, "instructions": instr, "sites": []}
    for name, url, kind in SITES:
        site = {"site": name, "url": url, "kind": kind}
        try:
            mresp, mid = tav.map(url, instructions=instr, limit=20, max_depth=2, tag=f"prompt-t:map {name}")
            site["map_urls"] = mresp.get("results", [])
            site["map_credits"] = (mresp.get("usage") or {}).get("credits")
            cresp, cid = tav.crawl(url, instructions=instr, select_paths=SELECT, limit=15, max_depth=2,
                                   extract_depth="basic", tag=f"prompt-t:crawl {name}", parent=mid)
        except BudgetExceeded as e:
            site["stopped"] = str(e)
            report["sites"].append(site)
            print(f"{name}: STOPPED {e}")
            break
        except Exception as e:                                  # site refused / Tavily error: recorded openly
            site["error"] = f"{type(e).__name__}: {e}"[:300]
            report["sites"].append(site)
            print(f"{name}: error {site['error']}")
            continue
        pages = cresp.get("results", [])
        site.update({"crawl_credits": (cresp.get("usage") or {}).get("credits"), "pages": len(pages),
                     "failed": len(cresp.get("failed_results") or []), "month_pages": [], "events": [],
                     "event_verdicts": []})
        for p in pages:
            text = p.get("raw_content") or ""
            hits = [m.group(0) for m in pat.finditer(text)][:3]
            if not hits:
                continue
            site["month_pages"].append({"url": p["url"], "month_mentions": hits})
            if kind not in cfg or cfg[kind].get("disabled"):
                continue
            evs, _ = nem.price_events(models()["mid"], text[:60000], tag=f"prompt-t:events {name}", parent=cid)
            for ev in evs:
                k, why = E.judge_event({**ev, "_url": p["url"], "_page_date": "", "_kind": kind}, month, cfg[kind])
                site["event_verdicts"].append({"url": p["url"], "line": ev.get("quote"), "verdict": why})
                if k:
                    site["events"].append({**k, "url": p["url"]})
        report["sites"].append(site)
        print(f"{name}: map {len(site['map_urls'])} urls, crawl {len(pages)} pages, {len(site['month_pages'])} "
              f"mention {mname}, {len(site['events'])} verified events; prompt-t spent {spent('prompt-t')}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"official_crawl_{month}.json").write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str))
    return report


SECTION_QUERY = {"electricity": "tariff order 2026", "fuel": "petrol diesel LPG price", "milk": "milk price"}


def crawl_fallback(month, names):
    """For sites where Map found nothing: one site-restricted search for the price/tariff section, then a shallow
    Crawl (depth 1, no instructions) from the top result. Same month filter, Nemotron extraction and judge_event."""
    rec = Recorder()
    tav = Budgeted(Tavily(recorder=rec), ["prompt-t"])
    nem = Nemotron(recorder=rec)
    cfg = E.load_items()["events"]
    pat = month_patterns(month)
    p = OUT / f"official_crawl_{month}.json"
    report = json.loads(p.read_text())
    for site in report["sites"]:
        if site["site"] not in names:
            continue
        dom, kind = urlparse(site["url"]).netloc.removeprefix("www."), site["kind"]
        fb = {"query": SECTION_QUERY[kind], "pages": 0, "month_pages": [], "events": [], "event_verdicts": []}
        site["fallback"] = fb
        try:
            sresp, sid = tav.search(SECTION_QUERY[kind], search_depth="basic", max_results=5, include_domains=[dom],
                                    tag=f"prompt-t:section {site['site']}")
            urls = [r["url"] for r in sresp.get("results", [])]
            fb["search_urls"] = urls
            if not urls:
                continue
            cresp, cid = tav.crawl(urls[0], max_depth=1, limit=10, extract_depth="basic",
                                   tag=f"prompt-t:crawl-section {site['site']}", parent=sid)
        except BudgetExceeded as e:
            fb["stopped"] = str(e)
            break
        except Exception as e:
            fb["error"] = f"{type(e).__name__}: {e}"[:300]
            continue
        pages = cresp.get("results", [])
        fb.update({"start": urls[0], "pages": len(pages), "failed": len(cresp.get("failed_results") or [])})
        for pg in pages:
            text = pg.get("raw_content") or ""
            hits = [m.group(0) for m in pat.finditer(text)][:3]
            if not hits:
                continue
            fb["month_pages"].append({"url": pg["url"], "month_mentions": hits})
            if kind not in cfg or cfg[kind].get("disabled"):
                continue
            evs, _ = nem.price_events(models()["mid"], text[:60000], tag=f"prompt-t:events {site['site']}", parent=cid)
            for ev in evs:
                k, why = E.judge_event({**ev, "_url": pg["url"], "_page_date": "", "_kind": kind}, month, cfg[kind])
                fb["event_verdicts"].append({"url": pg["url"], "line": ev.get("quote"), "verdict": why})
                if k:
                    fb["events"].append({**k, "url": pg["url"]})
        print(f"{site['site']}: section search {len(fb.get('search_urls', []))} urls, crawl {fb['pages']} pages from "
              f"{fb.get('start')}, {len(fb['month_pages'])} mention the month, {len(fb['events'])} verified events; "
              f"prompt-t spent {spent('prompt-t')}")
    p.write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str))
    return report


def _num(x):
    s = f"{float(x):.2f}".rstrip("0").rstrip(".")
    return re.escape(s)


def confirms(event, result, kind_words):
    """Code check: another site's result (title + snippet) names the item, is about India (not a foreign country,
    and names India or the event's place/seller), and states the same change WITH its unit: the rupee amount
    (Rs/₹/रुपये), the % change (%/per cent/फीसदी/प्रतिशत, as written to 1 decimal), or the exact new/old price."""
    raw = " ".join([result.get("title") or "", result.get("content") or ""])
    text = norm(raw)
    if urlparse(result["url"]).netloc == urlparse(event["url"]).netloc:
        return False
    if not any(norm(w) in text for w in kind_words) or E.foreign(raw, "", result["url"]):
        return False
    where = [w for w in re.findall(r"[^\W\d_]{4,}", norm(f"{event.get('place') or ''} {event.get('seller') or ''}"))]
    if not any(w in text for w in where + ["india", "भारत"]):
        return False
    pats = []
    if event.get("abs_change"):
        n = _num(abs(event["abs_change"]))
        pats += [rf"(rs\.?|₹|inr)\s?{n}(?![\d.])", rf"(?<![\d.]){n}\s?(rupees?|रुपये|रुपए|/-)"]
    if event.get("pct_change") is not None:
        n = _num(round(abs(event["pct_change"]), 1))
        pats.append(rf"(?<![\d.]){n}\s?(%|per ?cent|फीसदी|प्रतिशत)")
    for v in ("new_price", "old_price"):
        if event.get(v):
            pats.append(rf"(?<![\d.]){_num(event[v])}(?![\d])")
    return any(re.search(x, text) for x in pats)


def chase():
    rec = Recorder()
    tav = Budgeted(Tavily(recorder=rec), ["prompt-t", "chase"])
    cfg = E.load_items()["events"]
    tree = []
    for m in E.REPLAY_MONTHS:
        for ev in json.loads((ROOT / "manifests" / f"{m}.json").read_text())["events"]:
            kind = ev["item"]
            words = cfg.get(kind, {}).get("match", [kind])
            mname = f"{E.MONTHS_EN[int(m[5:]) - 1]} {m[:4]}"
            start = (date.fromisoformat(E.month_window(m)[0]) - timedelta(days=E.EVENT_PRE_DAYS)).isoformat()
            end = E.month_window(m)[1]
            seller = (ev.get("seller") or "").split(",")[0].strip()
            pct = f"{ev['pct_change']:.1f}%" if ev.get("pct_change") is not None else ""
            queries = [("same change, other sellers or states",
                        f"{kind} price {'hike' if (ev.get('pct_change') or 0) > 0 else 'cut'} {mname} India",
                        {"topic": "news"}),
                       ("the official circular",
                        f"{seller or kind} {kind} price revision {pct} notification order {mname}",
                        {"topic": "general"})]
            node = {"month": m, "event": {k: ev.get(k) for k in ("item", "seller", "place", "pct_change",
                                                                  "abs_change", "effective_date", "line", "url",
                                                                  "confirmed_by_2_sources")},
                    "parent_call_id": None, "children": []}
            for why, q, extra in queries:
                try:
                    resp, cid = tav.search(q, search_depth="basic", max_results=8, start_date=start, end_date=end,
                                           tag=f"chase:{m} {kind}", **extra)
                except BudgetExceeded as e:
                    node["children"].append({"why": why, "query": q, "stopped": str(e)})
                    tree.append(node)
                    _save_chase(tree)
                    print(f"STOPPED: {e}")
                    return tree
                hits = [r for r in resp.get("results", []) if confirms(ev, r, words)]
                node["children"].append({"why": why, "query": q, "call_id": cid, "n_results": len(resp["results"]),
                                         "confirming": [{"url": r["url"], "date": iso_date(r.get("published_date"))}
                                                        for r in hits]})
            node["confirmed_by_chase"] = any(c.get("confirming") for c in node["children"])
            tree.append(node)
            print(f"{m} {kind}: confirming results {sum(len(c.get('confirming', [])) for c in node['children'])}; "
                  f"prompt-t spent {spent('prompt-t')}")
    _save_chase(tree)
    return tree


def _save_chase(tree):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "chase.json").write_text(json.dumps(tree, ensure_ascii=False, indent=1))


def card():
    log = read_log()
    tav = [e for e in log if e["service"] == "tavily"]
    live = [e for e in tav if not e["cached"]]
    led = read_ledger()
    cfg = load_budget()
    lat = [e["latency_ms"] for e in live]
    direct = [e for e in log if e["service"] == "direct" and not e["cached"]]
    # results inside the requested date window (searches with start/end dates, from the cached responses)
    inside = total = undated = 0
    for e in live:
        if e["endpoint"] != "/search":
            continue
        p = ROOT / "cache" / "tavily" / f"{e['cache_key']}.json"
        if not p.exists():
            continue
        c = json.loads(p.read_text())
        s, t = c["request"].get("start_date"), c["request"].get("end_date")
        if not (s and t):
            continue
        for r in c["response"].get("results", []):
            d, _ = best_date(r)
            total += 1
            if not d:
                undated += 1
            elif s <= d <= t:
                inside += 1
    qx = qv = 0
    for p in sorted((ROOT / "manifests").glob("*.json")):
        c = json.loads(p.read_text())["counts"]
        qx += c.get("quotes_extracted", 0)
        qv += c.get("quotes_verified", 0)
    q_src = "all manifests"
    if not qx:      # test-month re-runs are events-only; the quote counts are from Prompt 2's March run
        import subprocess
        c = json.loads(subprocess.run(["git", "show", "f00bd45:manifests/2026-03.json"], cwd=ROOT,
                                      capture_output=True, text=True).stdout)["counts"]
        qx, qv, q_src = c["quotes_extracted"], c["quotes_verified"], "Prompt 2 March run, manifest at f00bd45"
    evs = [e for p in sorted((ROOT / "manifests").glob("2026-0*.json")) for e in json.loads(p.read_text())["events"]]
    two = sum(bool(e.get("confirmed_by_2_sources")) for e in evs)
    chase_p = OUT / "chase.json"
    chased = json.loads(chase_p.read_text()) if chase_p.exists() else []
    by_chase = sum(bool(n.get("confirmed_by_chase")) for n in chased)
    att = list(csv.DictReader((ROOT / "results" / "tavily_attribution.csv").open()))
    per_pred = statistics.mean(int(r["credits"]) for r in att) if att else 0
    crawl_p = sorted(OUT.glob("official_crawl_*.json"))
    lines = ["# Tavily report card", "",
             f"Computed by `tools/prompt_t.py card` from `logs/flight_recorder.jsonl`, `results/credit_ledger.jsonl` "
             f"and the manifests on {date.today().isoformat()}. Credits are Tavily's own per-call `include_usage` "
             "counts (the `/usage` endpoint did not update; see FEEDBACK_NOTES.md).", "",
             "| Measure | Value |", "| --- | --- |",
             f"| Tavily calls sent (uncached) | {len(live)} (plus {len(tav) - len(live)} served from the cache) |",
             f"| Credits used (ledger + {cfg['spent_before_ledger']} before it) | {account_spent(cfg, led)} of "
             f"{cfg['plan_limit']} |",
             f"| Credits per replay prediction (events + skeptic, mean of 9 months) | {per_pred:.1f} |",
             f"| Search results inside the requested date window | {inside} of {total} "
             f"({inside / total:.0%}); {undated} undated |" if total else "| Search results inside the window | n/a |",
             f"| Price quotes verified word-for-word ({q_src}) | {qv} of {qx} ({qv / qx:.0%}) |" if qx else
             "| Price quotes verified | n/a |",
             f"| Events confirmed by 2 sources (replay months) | {two} of {len(evs)} |",
             f"| Events with a confirming result from evidence chasing | {by_chase} of {len(chased)} |",
             f"| Median latency, uncached calls | {statistics.median(lat) / 1000:.1f} s |" if lat else "",
             f"| Direct downloads (logged; MoSPI API, DoCA by hand, failed Extracts) | {len(direct)} uncached calls |",
             "",
             "## Official sites (Map + Crawl)", ""]
    for p in crawl_p:
        rep = json.loads(p.read_text())
        lines.append(f"**{rep['month']}** (instructions: \"{rep['instructions']}\")")
        lines.append("")
        for s in rep["sites"]:
            if s.get("error") or s.get("stopped"):
                lines.append(f"- {s['site']} ({s['url']}): {s.get('error') or s.get('stopped')}")
                continue
            lines.append(f"- {s['site']} ({s['url']}): map {len(s['map_urls'])} addresses, crawl {s['pages']} pages "
                         f"({s['failed']} failed), {len(s['month_pages'])} mention the month, "
                         f"{len(s['events'])} verified price events")
            fb = s.get("fallback")
            if fb:
                lines.append(f"  - fallback (site search \"{fb['query']}\", then Crawl depth 1): "
                             f"{len(fb.get('search_urls', []))} addresses found; crawl from {fb.get('start')} read "
                             f"{fb['pages']} pages, {len(fb['month_pages'])} mention the month, "
                             f"{len(fb['events'])} verified events" + (f"; {fb['error']}" if fb.get('error') else ""))
        lines.append("")
    lines += ["## Honest notes", "",
              "- Map + Crawl results are reported, not used in the nowcast: the frozen event layer searches news only.",
              "- Evidence chasing ran on the 9 scored months after scoring; it does not change any scored number.",
              "- Map returned 0 addresses on all four government/PSU sites (merc.gov.in, derc.gov.in, uperc.org, "
              "iocl.com) with no error and 0 credits; only amul.com mapped (17 addresses, all marketing pages). "
              "Crawl from a section page found by a site search read 0 pages when that page was a PDF.",
              "- DERC's tariff-order index was read: its newest order is dated 31/12/2025, so nothing for October 2026.",
              "- A chase \"confirmation\" is a code text match (another site names the item and states the same "
              "amount or %), not a Nemotron-verified quote. "
              "Spot check: 13 of 14 confirming results are the same change; 1 is a generic all-India milk article.",
              "- Failed sources are listed on the Evidence page and in FEEDBACK_NOTES.md (Reuters, JavaScript data "
              "portals, the Consumer Affairs price site)."]
    (ROOT / "results" / "tavily_report_card.md").write_text("\n".join(x for x in lines if x is not None) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    print(f"prompt-t spent so far: {spent('prompt-t')} of cap 90")
    if cmd == "crawl":
        crawl(sys.argv[2])
    elif cmd == "fallback":
        crawl_fallback(sys.argv[2], sys.argv[3:])
    elif cmd == "chase":
        chase()
    elif cmd == "card":
        card()
    else:
        raise SystemExit(__doc__)
