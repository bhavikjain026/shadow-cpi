"""Build the SAMPLE data the app shows until the real pipeline has produced its files.

Every number written here is made up for layout and testing (except the two copies of
real files: results/baselines.csv and a slice of data/cpi_tidy.csv). Nothing calls an API.

Run:  python data/sample/make_sample.py
The folder layout mirrors the repository root, so the app can switch to real data by
pointing SHADOW_CPI_DATA_DIR at the repository root instead of data/sample/.
"""
import csv
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SAMPLE_NOTE = "SAMPLE data for the app layout only - not a real nowcast"
COMMIT = "0000000sample"
MODELS = json.loads((ROOT / "config" / "models.json").read_text(encoding="utf-8"))


def write_json(rel, obj):
    p = HERE / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(rel, rows):
    p = HERE / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def copy_real_files():
    shutil.copyfile(ROOT / "results" / "baselines.csv", HERE / "results" / "baselines.csv")
    # Only the headline and division rows; the app does not need the 600+ items.
    src = (ROOT / "data" / "cpi_tidy.csv").read_text(encoding="utf-8").splitlines(keepends=True)
    (HERE / "data").mkdir(exist_ok=True)
    with (HERE / "data" / "cpi_tidy.csv").open("w", encoding="utf-8", newline="") as f:
        f.write(src[0])
        for line in src[1:]:
            level = line.split(",", 2)[1]
            if level in ("general", "division"):
                f.write(line)


CONTRIBUTORS = [
    {"code": "01", "name": "Food and beverages", "pp": 2.71},
    {"code": "13", "name": "Personal care, social protection and miscellaneous goods and services", "pp": 0.72},
    {"code": "04", "name": "Housing, water, electricity, gas and other fuels", "pp": 0.48},
]


def nowcast(month, yoy, low, high, inside, coverage):
    return {
        "sample": True, "note": SAMPLE_NOTE, "target_month": month, "label": "experimental nowcast",
        "headline_yoy": yoy, "range_low": low, "range_high": high, "range_level": 0.8,
        "replay_inside_range": {"n": inside, "of": 9},
        "coverage": {"observed": coverage, "carried": round(1 - coverage, 4)},
        "contributors": CONTRIBUTORS,
        "tavily_attribution": {"pred_without_tavily": round(yoy - 0.18, 2), "pred_with_tavily": yoy,
                               "coverage_without": round(coverage - 0.09, 4), "coverage_with": coverage},
        "evidence_cutoff_utc": f"{month}-28T23:59:00+00:00",
        "manifest": f"manifests/{month}.json", "code_commit": COMMIT, "model_ids": MODELS,
        "weights_file_sha256": "sample" + "0" * 58,
    }


def seal(month, payload, sealed_at):
    payload = {**payload, "git_tag": f"seal-{month}", "sealed_at_utc": sealed_at}
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))  # = shadow_cpi.seal.canonical
    (HERE / "sealed" / f"{month}.json").write_text(text, encoding="utf-8")
    (HERE / "sealed" / f"{month}.sha256").write_text(hashlib.sha256(text.encode()).hexdigest() + "\n", encoding="utf-8")


def manifest(month):
    q = lambda i, query, lang, endpoint, n_res: {
        "call_id": f"s{month[-2:]}{i:02d}", "endpoint": endpoint, "query": query, "language": lang,
        "params": {"topic": "news", "search_depth": "basic", "max_results": 8,
                   "start_date": f"{month}-01", "end_date": f"{month}-31", "include_domains_mode": "prefer",
                   "exclude_domains": ["mospi.gov.in"]},
        "retrieved_at": f"{month}-27T10:{i:02d}:00+00:00", "n_results": n_res}
    return {
        "sample": True, "note": SAMPLE_NOTE, "month": month, "created_utc": f"{month}-28T12:00:00+00:00",
        "code_commit": COMMIT, "model_ids": MODELS,
        "queries": [q(1, "onion price per kg", "en", "search", 8), q(2, "प्याज का भाव", "hi", "search", 6),
                    q(3, "milk price hike effective", "en", "search", 8), q(4, "LPG cylinder price revised", "en", "search", 7),
                    q(5, "gold rate today IBJA", "en", "search", 5)],
        "counts": {"pages_seen": 41, "pages_kept": 17, "quotes_extracted": 38, "quotes_verified": 24,
                   "events_extracted": 6, "events_verified": 4},
        "dropped": [{"reason": "outside the month (date check)", "count": 9},
                    {"reason": "states an official CPI figure for the target month (leak guard)", "count": 2},
                    {"reason": "gatekeeper said: no Indian price on page", "count": 8},
                    {"reason": "quote not verified (number not in cited line)", "count": 14},
                    {"reason": "syndicated copy (duplicate)", "count": 5}],
        "quotes": [
            {"item": "onion", "price": 42.0, "unit": "Rs/kg", "place": "Delhi", "date": f"{month}-14", "tier": "strict",
             "source": "spine", "line": "Onion | Delhi | 42.00", "url": "https://fcainfoweb.nic.in/reports/report_menu_web.aspx", "verified": True},
            {"item": "onion", "price": 45.0, "unit": "Rs/kg", "place": "Nashik (Lasalgaon)", "date": f"{month}-12", "tier": "exploratory",
             "source": "tavily", "line": "Retail onion prices in Nashik touched Rs 45 a kg on Monday, traders said.",
             "url": "https://example.com/sample-news/onion-nashik", "verified": True},
            {"item": "tomato", "price": 38.0, "unit": "Rs/kg", "place": "Mumbai", "date": f"{month}-09", "tier": "exploratory",
             "source": "tavily", "line": "टमाटर का खुदरा भाव 38 रुपये प्रति किलो रहा।",
             "url": "https://example.com/sample-news/tamatar-mumbai", "verified": True},
            {"item": "tur dal", "price": 148.0, "unit": "Rs/kg", "place": "Chennai", "date": f"{month}-15", "tier": "strict",
             "source": "spine", "line": "Tur/Arhar Dal | Chennai | 148.00", "url": "https://fcainfoweb.nic.in/reports/report_menu_web.aspx", "verified": True},
            {"item": "gold", "price": 12450.0, "unit": "Rs/g (24K)", "place": "India (IBJA)", "date": f"{month}-20", "tier": "strict",
             "source": "tavily", "line": "Fine Gold (999) 124500 per 10 grams", "url": "https://example.com/sample-rates/ibja", "verified": True},
            {"item": "silver", "price": 158.0, "unit": "Rs/g", "place": "India (IBJA)", "date": f"{month}-20", "tier": "strict",
             "source": "tavily", "line": "Silver (999) 158000 per kg", "url": "https://example.com/sample-rates/ibja", "verified": True},
        ],
        "events": [
            {"item": "milk", "seller": "Sample Dairy Co-op", "place": "Gujarat", "pct_change": 3.6, "old_price": 56.0, "new_price": 58.0,
             "unit": "Rs/litre", "announced_date": f"{month}-03", "effective_date": f"{month}-05", "days_in_month_share": 0.871,
             "line": "The new price of Rs 58 per litre will be effective from 5th of this month.",
             "url": "https://example.com/sample-news/milk-hike", "verified": True, "confirmed_by_2_sources": True},
            {"item": "LPG (14.2 kg)", "seller": "Oil marketing companies", "place": "Delhi", "pct_change": 0.0, "old_price": 853.0,
             "new_price": 853.0, "unit": "Rs/cylinder", "announced_date": f"{month}-01", "effective_date": f"{month}-01",
             "days_in_month_share": 1.0, "line": "Domestic LPG cylinder price unchanged at Rs 853 in Delhi.",
             "url": "https://example.com/sample-news/lpg", "verified": True, "confirmed_by_2_sources": True},
        ],
        "failed_sources": [
            {"url": "https://fcainfoweb.nic.in/reports/report_menu_web.aspx", "via": "tavily extract",
             "reason": "blocked for Tavily; used the logged direct download instead (fallback 1 of 1)"},
            {"url": "https://example.com/sample-regulator/tariff-order.pdf", "via": "tavily crawl",
             "reason": "scanned PDF, no text found"},
        ],
    }


def spine():
    rows = []
    for item, base in (("onion", 38.0), ("tomato", 34.0), ("potato", 26.0), ("tur dal", 145.0)):
        for centre, f in (("Delhi", 1.0), ("Mumbai", 1.06), ("Chennai", 0.97), ("Kolkata", 0.95)):
            for month, g in (("2026-09", 1.0), ("2026-10", 1.07 if item == "onion" else 1.02)):
                rows.append({"month": month, "item": item, "centre": centre, "avg_price": round(base * f * g, 2),
                             "unit": "Rs/kg", "n_days": 22, "tier": "strict"})
    return rows


def flight_log():
    # Same keys as shadow_cpi/recorder.py writes to logs/flight_recorder.jsonl
    def e(i, minute, service, endpoint, params, cached, ms, parent, tag, **counts):
        return {"id": f"c{i:011d}", "time": f"2026-10-27T10:{minute:02d}:00+00:00", "service": service,
                "endpoint": endpoint, "params": params, "cached": cached, "latency_ms": ms, "parent": parent,
                "tag": tag, "cache_key": hashlib.sha256(f"sample{i}".encode()).hexdigest(), **counts}
    win = {"start_date": "2026-10-01", "end_date": "2026-10-31"}
    return [
        e(1, 1, "tavily", "search", {"query": "onion price per kg", "topic": "news", "search_depth": "basic", **win}, False, 1840, None, "item:onion", n_results=8, credits=1),
        e(2, 2, "tavily", "extract", {"urls": ["https://example.com/sample-news/onion-nashik"], "extract_depth": "basic"}, False, 2310, "c00000000001", "item:onion", n_results=6, n_failed=0, credits=1),
        e(3, 3, "nebius", "chat/completions", {"model": MODELS["small"]}, False, 620, "c00000000002", "item:onion gatekeeper"),
        e(4, 3, "nebius", "chat/completions", {"model": MODELS["mid"]}, False, 3900, "c00000000002", "item:onion quotes"),
        e(5, 5, "tavily", "search", {"query": "milk price hike effective", "topic": "news", "search_depth": "basic", **win}, False, 1720, None, "event:milk", n_results=8, credits=1),
        e(6, 6, "tavily", "extract", {"urls": ["https://example.com/sample-news/milk-hike"], "extract_depth": "basic"}, False, 2050, "c00000000005", "event:milk", n_results=5, n_failed=1, credits=1),
        e(7, 7, "nebius", "chat/completions", {"model": MODELS["mid"]}, False, 4100, "c00000000006", "event:milk events"),
        e(8, 8, "tavily", "search", {"query": "milk price hike other dairies October 2026", "topic": "news", "search_depth": "basic", **win}, False, 1650, "c00000000007", "chase:milk other sellers", n_results=7, credits=1),
        e(9, 9, "tavily", "search", {"query": "dairy co-operative price circular", "topic": "general", "search_depth": "basic", **win}, False, 1580, "c00000000007", "chase:milk official circular", n_results=4, credits=1),
        e(10, 10, "tavily", "map", {"url": "https://example.com/sample-regulator", "instructions": "find price circulars or tariff orders published in 2026-10"}, False, 3300, None, "circulars:regulator", n_results=24, credits=1),
        e(11, 12, "tavily", "crawl", {"url": "https://example.com/sample-regulator", "extract_depth": "advanced", "instructions": "find price circulars or tariff orders published in 2026-10"}, False, 9800, "c00000000010", "circulars:regulator", n_results=12, n_failed=1, credits=4),
        e(12, 14, "tavily", "search", {"query": "gold rate today IBJA", "topic": "general", "search_depth": "basic", **win}, True, 4, None, "item:gold", n_results=5, credits=1),
        e(13, 15, "tavily", "extract", {"urls": ["https://example.com/sample-rates/ibja"], "extract_depth": "advanced"}, False, 2700, "c00000000012", "item:gold", n_results=1, n_failed=0, credits=2),
    ]


def replay():
    # month, actual from the real baselines file; (a)/(b)/(c) predictions are SAMPLE offsets.
    base = list(csv.DictReader((HERE / "results" / "baselines.csv").open(encoding="utf-8")))
    offs = [(-0.21, -0.12, -0.05), (-0.15, -0.10, 0.04), (-0.12, -0.08, -0.03), (-0.03, 0.06, 0.02), (-0.50, -0.31, -0.22),
            (-0.43, -0.25, -0.11), (0.10, 0.07, 0.05), (0.25, 0.14, 0.09), (0.11, -0.18, -0.36)]
    rows = []
    for r, (a, b, c) in zip(base, offs):
        act = float(r["actual_yoy"])
        pc = round(act + c, 2)
        lo, hi = round(pc - 0.32, 2), round(pc + 0.32, 2)
        rows.append({"month": r["month"], "actual_yoy": act, "a_trend_pred": round(act + a, 2), "b_spine_pred": round(act + b, 2),
                     "c_tavily_pred": pc, "c_range_low": lo, "c_range_high": hi, "c_inside_range": lo <= act <= hi,
                     "b_coverage_observed": 0.19, "c_coverage_observed": 0.28, "tier": "strict+exploratory",
                     "note": ("Sample explanation: vegetable prices fell faster in the last ten days than the news quotes showed, "
                              "and gold eased after the 20th, so the nowcast ran 0.36 pp too high.") if r["month"] == "2026-09" else ""})
    return rows


def attribution(rows):
    return [{"month": r["month"], "pred_without_tavily": r["b_spine_pred"], "pred_with_tavily": r["c_tavily_pred"],
             "coverage_without": r["b_coverage_observed"], "coverage_with": r["c_coverage_observed"], "actual_yoy": r["actual_yoy"],
             "miss_without": round(r["b_spine_pred"] - r["actual_yoy"], 2), "miss_with": round(r["c_tavily_pred"] - r["actual_yoy"], 2),
             "tavily_calls": 46, "credits": 61} for r in rows]


REPORT_CARD = """# Tavily report card (SAMPLE)

> SAMPLE numbers for the app layout only.

| Measure | Value |
| --- | --- |
| Tavily calls (all months) | 412 |
| Credits used | 548 |
| Credits per sealed prediction | 61 |
| Results inside the date window | 78% |
| Quotes verified word-for-word | 63% |
| Events confirmed by 2 sources | 4 of 6 |
| Median latency | 1.9 s |
| Direct-download fallbacks | 1 (government price table) |

## Honest notes
- The government daily price site blocks Tavily, so the spine used the logged direct download.
- One regulator tariff order was a scanned PDF with no text.
"""

BRIEF = """# Reporter brief - October 2026 (SAMPLE, experimental nowcast)

> SAMPLE text for the app layout only. The real brief is written by the large model from computed numbers and verified quotes.

**Experimental nowcast:** 5.31% year-on-year (80% range 4.86% to 5.82%). The actual figure was inside the range in 8 of 9 replay months.
**Coverage:** 31% of the basket is measured this month; 69% is carried on trend.

## What moved
- Food and beverages added 2.71 pp, mostly vegetables (onion up about 7% month-on-month on the government price spine).
- Gold and silver (personal care group) added 0.72 pp.

## What we observed
- "The new price of Rs 58 per litre will be effective from 5th of this month." (milk, Gujarat; confirmed by 2 sources)
- "Retail onion prices in Nashik touched Rs 45 a kg on Monday, traders said."

## What's uncertain
- Vegetable prices can turn quickly in the last week of the month.
- 69% of the basket is not measured and follows the trend.
"""


def main():
    copy_real_files()
    rows = replay()
    write_csv("results/replay.csv", rows)
    write_csv("results/tavily_attribution.csv", attribution(rows))
    (HERE / "results" / "tavily_report_card.md").write_text(REPORT_CARD, encoding="utf-8")
    (HERE / "results" / "reporter_brief_2026-10.md").write_text(BRIEF, encoding="utf-8")
    write_csv("data/spine.csv", spine())
    write_csv("data/official_releases.csv", [{"month": "2026-09", "official_yoy": 5.54, "released_on": "2026-10-12",
                                              "source_url": "https://www.mospi.gov.in/"}])
    oct_nc = nowcast("2026-10", 5.31, 4.86, 5.82, 8, 0.31)
    write_json("results/nowcast_latest.json", oct_nc)
    seal("2026-10", oct_nc, "2026-10-29T06:30:00+00:00")
    seal("2026-09", nowcast("2026-09", 5.18, 4.86, 5.50, 7, 0.28), "2026-09-29T06:30:00+00:00")
    for m in ("2026-09", "2026-10"):
        write_json(f"manifests/{m}.json", manifest(m))
    with (HERE / "logs" / "flight_recorder.jsonl").open("w", encoding="utf-8") as f:
        for entry in flight_log():
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    receipt = {"tavily_calls": 9, "credits": 14, "seconds": 38.2, "nemotron_calls": 11}
    write_json("results/run_now_cached.json", {
        "sample": True, "note": SAMPLE_NOTE, "ran_at_utc": "2026-10-19T08:15:00+00:00",
        "window_start": "2026-10-12", "window_end": "2026-10-18", "daily_cap": 2, "credit_cap": 20,
        "events": [{"item": "milk", "place": "Gujarat", "pct_change": 3.6, "effective_date": "2026-10-05",
                    "line": "The new price of Rs 58 per litre will be effective from 5th of this month.",
                    "url": "https://example.com/sample-news/milk-hike", "verified": True}],
        "receipt": receipt})
    write_json("results/skeptic_2026-10.json", {
        "sample": True, "note": SAMPLE_NOTE, "month": "2026-10", "ran_at_utc": "2026-10-19T08:20:00+00:00",
        "checked": [{"contributor": "Food and beverages", "counter_query": "onion prices fall October 2026",
                     "contrary_verified_quotes": 1},
                    {"contributor": "Personal care (gold)", "counter_query": "gold price drops October 2026",
                     "contrary_verified_quotes": 0},
                    {"contributor": "Housing, electricity, gas", "counter_query": "electricity tariff cut October 2026",
                     "contrary_verified_quotes": 0}],
        "widened": False, "reason": "No contributor had 2 or more verified contrary quotes, so the range stays as it is.",
        "receipt": {"tavily_calls": 3, "credits": 3, "seconds": 12.4, "nemotron_calls": 4}})


if __name__ == "__main__":
    main()
