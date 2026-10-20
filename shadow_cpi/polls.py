"""Economists' poll medians for India's CPI, found with Tavily and read by plain code (no model).

For each target month we search news published between the last days of that month and the day before
MoSPI's release, extract the top pages, and keep only an exact line from the page that states the poll's
median forecast. The number must appear in that line, and the page must carry a publication date before the
release. Months with no such dated source are written as "none" - never filled from an aggregator.
"""
import csv
import math
import re
from datetime import date, timedelta
from pathlib import Path

from . import cpi_math as M
from .official import MONTH_NAMES, POLL_CSV
from .tavily import best_date
from .verify import split_lines

POLL_DOMAINS = ["reuters.com", "economictimes.indiatimes.com", "livemint.com", "business-standard.com",
                "thehindubusinessline.com", "moneycontrol.com", "financialexpress.com", "hindustantimes.com",
                "marketscreener.com", "theprint.in", "ndtvprofit.com", "cnbctv18.com"]
SEARCH_CREDITS, EXTRACT_URLS_PER_CREDIT = 1, 5      # basic search = 1 credit; basic extract = 1 credit per 5 URLs
EXTRACT_TOP = 4

PCT = re.compile(r"(\d{1,2}(?:\.\d{1,2})?)\s?(?:%|per\s?cent|percent)", re.I)
N_ECON = re.compile(r"(?:poll|survey) of (\d{1,3}) economists|(\d{1,3}) economists", re.I)
POLL_WORDS = re.compile(r"\b(poll|polled|survey(?:ed)?)\b", re.I)


def release_date(month):
    """MoSPI releases CPI on the 12th of the next month (next working day if the 12th is a weekend)."""
    y, m = map(int, M.add_months(month, 1).split("-"))
    d = date(y, m, 12)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def search_window(month):
    """(start, end) as YYYY-MM-DD: from the 25th of the target month to the day before the release."""
    return f"{month}-25", (release_date(month) - timedelta(days=1)).isoformat()


POLL_DOMAINS_STRICT = ["reuters.com", "economictimes.indiatimes.com", "m.economictimes.com", "livemint.com",
                       "business-standard.com", "thehindubusinessline.com"]


def queries(month):
    """(query, include_domains, include_domains_mode). The broad query runs first; the targeted one only if it
    finds nothing (the broad one was the first run's query, so it is served from cache)."""
    name, year = MONTH_NAMES[int(month[5:]) - 1], month[:4]
    return [(f"Reuters poll India retail inflation {name} {year} economists median forecast", POLL_DOMAINS, "prefer", "basic"),
            (f"India retail inflation {name} Reuters poll economists", POLL_DOMAINS_STRICT, "restrict", "basic"),
            # Tavily Extract is blocked on reuters.com, so the last try asks Search itself for the most relevant
            # passages of each page (advanced depth = 2 credits, returns content chunks).
            (f"India consumer inflation likely {name} Reuters poll of economists", ["reuters.com"], "restrict", "advanced")]


def estimate_credits(months):
    """Upper bound: every query runs. Basic search = 1 credit + one extract call; advanced search = 2 credits
    and no extract (it already returns the relevant passages)."""
    extract = math.ceil(EXTRACT_TOP / EXTRACT_URLS_PER_CREDIT)
    per_month = sum(2 if depth == "advanced" else SEARCH_CREDITS + extract for *_, depth in queries("2026-01"))
    return len(months) * per_month


def about_india(url, title, text):
    return "india" in (url or "").lower() or "india" in (title or "").lower() or "india" in (text or "")[:1500].lower()


ANCHOR = re.compile(r"inflation|median forecast|forecast", re.I)


def poll_line(text, month, url="", title=""):
    """Find the exact line stating the poll median for `month`. Returns dict or None. Code decides:
    - tier A: the line mentions a poll/survey of economists, and the target month is named in the line or in
      the page address;
    - tier B: the line is a forecast ('forecast'/'median') naming the target month, on a Reuters poll-preview
      page ('likely' in its address or title) - used when the passage is cut off before the poll size.
    The median is the first percentage after 'inflation'/'forecast' that is not introduced by 'from' (last
    month's figure) and is not a share of economists ('80% of economists')."""
    name = MONTH_NAMES[int(month[5:]) - 1]
    preview = "likely" in (url or "").lower() or "likely" in (title or "").lower()
    for tier in ("A", "B"):
        for line in split_lines(text):
            named = re.search(name, line) or name.lower() in (url or "").lower()
            if tier == "A" and not (POLL_WORDS.search(line) and re.search(r"economist", line, re.I) and named):
                continue
            if tier == "B" and not (preview and re.search(name, line) and re.search(r"forecast|median", line, re.I)
                                    and re.search(r"inflation", line, re.I)):
                continue
            anchor = ANCHOR.search(line)
            if not anchor:
                continue
            for mp in PCT.finditer(line, anchor.start()):
                before = line[max(0, mp.start() - 12):mp.start()].lower()
                after = line[mp.end():mp.end() + 4].lower()
                if any(w in before for w in ("from", "target", "above", "below")) or after.strip().startswith("of"):
                    continue
                n = N_ECON.search(line)
                return {"median_forecast": float(mp.group(1)), "line": line, "tier": tier,
                        "n_economists": int(n.group(1) or n.group(2)) if n else ""}
    return None


def find_month(tav, month, parent=None):
    """Search + extract for one month. Returns (row, notes). row has the poll.csv columns plus evidence."""
    start, end = search_window(month)
    rel = release_date(month).isoformat()
    notes = []
    for q, domains, mode, depth in queries(month):
        extra = {"chunks_per_source": 3} if depth == "advanced" else {}
        resp, cid = tav.search(q, topic="news", search_depth=depth, max_results=8, start_date=start,
                               end_date=end, include_domains=domains, include_domains_mode=mode,
                               exclude_domains=["mospi.gov.in"], parent=parent, tag=f"poll-{month}", **extra)
        dated = []
        for r in resp.get("results", []):
            d, src = best_date(r)
            if d and start <= d < rel:
                dated.append((r, d, src))
            else:
                notes.append(f"dropped {r.get('url')} (date {d or 'unknown'})")
        if not dated:
            continue
        by_url = {}
        if depth != "advanced":      # advanced search already returns the relevant passages
            ext, _ = tav.extract([r["url"] for r, _, _ in dated[:EXTRACT_TOP]], query=q, chunks_per_source=5,
                                 parent=cid, tag=f"poll-{month}")
            by_url = {p.get("url"): p.get("raw_content") or "" for p in ext["results"]}
        for r, d, src in dated[:EXTRACT_TOP]:
            text = by_url.get(r["url"]) or r.get("content") or ""
            evidence_from = "tavily extract" if by_url.get(r["url"]) else f"tavily search ({depth}) page passage"
            if not about_india(r["url"], r.get("title"), text):
                continue
            hit = poll_line(text, month, r["url"], r.get("title"))
            if hit:
                return {"month": month, "median_forecast": hit["median_forecast"],
                        "n_economists": hit["n_economists"], "source_url": r["url"], "published_at": d,
                        "date_source": src, "release_date": rel, "evidence_from": evidence_from,
                        "note": "" if hit["tier"] == "A" else "forecast line in a Reuters poll preview; poll size "
                                                               "not in the retrieved passage",
                        "evidence_line": hit["line"]}, notes
        notes.append(f"query '{q}': {len(dated)} dated pages, no poll line found")
    return {"month": month, "median_forecast": "none", "n_economists": "none", "source_url": "none",
            "published_at": "none", "date_source": "", "release_date": rel, "evidence_line": ""}, notes


def write_poll(rows, path=POLL_CSV):
    cols = ["month", "median_forecast", "n_economists", "source_url", "published_at", "date_source",
            "release_date", "evidence_from", "note", "evidence_line"]
    with Path(path).open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})
