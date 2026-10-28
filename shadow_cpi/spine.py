"""The government price spine: Dept of Consumer Affairs (DoCA) zone-wise monthly average retail prices.

Source files: data/official/doca/raw/<chunk>.html, saved by tools/fetch_doca.py (the report is behind a CAPTCHA that a
person types). Parsed into data/spine.csv: month, item, centre, avg_price, unit, n_days.

- centre = DoCA zone (NORTH / WEST / EAST / NORTH-EAST / SOUTH ZONE). DoCA has published only state and national
  levels since Sep 2023; the zone report is the finest monthly report on its site.
- 'All India (simple mean of 5 zones)' rows are a SIMPLE (unweighted) mean of the zone prices, added here. DoCA's own
  'All India Average' row in the report is not stored (its weighting is not documented in the report).
- n_days is blank: the report gives monthly averages without the number of reporting days.
"""
import csv
import html as H
import re
from pathlib import Path

from .settings import ROOT

RAW = ROOT / "data" / "official" / "doca" / "raw"
SPINE_CSV = ROOT / "data" / "spine.csv"
ALL_INDIA = "All India (simple mean of 5 zones)"
ZONES = ("NORTH ZONE", "WEST ZONE", "EAST ZONE", "NORTH-EAST ZONE", "SOUTH ZONE")
MON = {m: i + 1 for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov",
                                       "Dec"])}
# DoCA commodity name -> spine item name. Tracked foods use the names in shadow_cpi.evidence.SPINE_FOODS;
# the six packed oils are kept separately and combined as 'edible oils' when changes are computed.
ITEM = {"Rice": "rice", "Atta (Wheat)": "atta", "Tur/Arhar Dal": "tur dal", "Gram Dal": "gram dal",
        "Moong Dal": "moong dal", "Urad Dal": "urad dal", "Masoor Dal": "masoor dal", "Sugar": "sugar",
        "Milk @": "milk", "Eggs": "eggs", "Groundnut Oil (Packed)": "groundnut oil",
        "Mustard Oil (Packed)": "mustard oil", "Soya Oil (Packed)": "soya oil", "Sunflower Oil (Packed)": "sunflower oil",
        "Palm Oil (Packed)": "palm oil", "Vanaspati (Packed)": "vanaspati", "Potato": "potato", "Onion": "onion",
        "Tomato": "tomato"}
# Months that were partial when a file was fetched and have since been re-fetched from the same report: their values
# in that file are skipped (the file itself is kept untouched). A data-vintage fix, not a rule change: seal_checklist.md
# §1 ("October is a partial month (data up to the fetch date)"); docs/after_scoring_changes.md §9.
SUPERSEDED = {
    "2026AB.html": {"2026-10": "partial October at the 2026-10-21 fetch; replaced by 2026A/2026B, fetched 2026-10-28"},
    "2025H2-2026fill.html": {"2026-10": "partial October at the 2026-10-21 fetch; replaced by 2026A/2026B, fetched "
                                        "2026-10-28"},
}
OILS = ("groundnut oil", "mustard oil", "soya oil", "sunflower oil", "palm oil", "vanaspati")

_BLOCK = re.compile(r"Prices of(?:&nbsp;|\s)*<b>\s*(.*?)\s*</b>.*?Unit:\s*\(([^)]*)\)(.*?)</table>", re.S | re.I)
_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
_CELL = re.compile(r"<t[hd][^>]*>(.*?)</t[hd]>", re.S | re.I)


def _cells(row_html):
    return [H.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in _CELL.findall(row_html)]


def parse_report(text):
    """[(doca_commodity, unit, {zone: {YYYY-MM: price}})] from one saved report. Code reads every number."""
    out = []
    for name, unit, table in _BLOCK.findall(text):
        rows = [_cells(r) for r in _ROW.findall(table)]
        head = rows[0]
        months = []
        for h in head[1:]:
            m = re.fullmatch(r"(\w{3}) (\d{4})", h)
            months.append(f"{m.group(2)}-{MON[m.group(1)]:02d}" if m else None)
        zones = {}
        for r in rows[1:]:
            if r and r[0].upper() in ZONES:
                zones[r[0].upper()] = {mo: float(v) for mo, v in zip(months, r[1:])
                                       if mo and re.fullmatch(r"\d+(\.\d+)?", v or "")}
        out.append((H.unescape(name).strip(), unit.strip(), zones))
    return out


def build(raw_dir=RAW, out=SPINE_CSV, superseded=None):
    """Parse every saved report into data/spine.csv. Overlapping months must agree (else refuse), except the months
    listed for a file in SUPERSEDED, which are skipped in that file."""
    superseded = SUPERSEDED if superseded is None else superseded
    prices, units = {}, {}
    for f in sorted(Path(raw_dir).glob("*.html")):
        skip = superseded.get(f.name, {})
        for name, unit, zones in parse_report(f.read_text(encoding="utf-8", errors="replace")):
            item = ITEM.get(name)
            if not item:
                continue
            units[item] = unit
            for zone, series in zones.items():
                for month, p in series.items():
                    if month in skip:
                        continue
                    key = (month, item, zone)
                    if key in prices and abs(prices[key] - p) > 1e-9:
                        raise ValueError(f"{key}: {prices[key]} in one file, {p} in {f.name}")
                    prices[key] = p
    rows = [{"month": m, "item": i, "centre": z, "avg_price": p, "unit": units[i], "n_days": ""}
            for (m, i, z), p in prices.items()]
    for (m, i) in sorted({(m, i) for m, i, _ in prices}):
        zs = [prices[(m, i, z)] for z in ZONES if (m, i, z) in prices]
        if len(zs) == len(ZONES):
            rows.append({"month": m, "item": i, "centre": ALL_INDIA, "avg_price": sum(zs) / len(zs),
                         "unit": units[i], "n_days": ""})
    order = {z: k for k, z in enumerate(ZONES + (ALL_INDIA,))}
    rows.sort(key=lambda r: (r["month"], r["item"], order[r["centre"]]))
    with Path(out).open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["month", "item", "centre", "avg_price", "unit", "n_days"])
        w.writeheader()
        for r in rows:
            w.writerow({**r, "avg_price": repr(r["avg_price"])})
    return rows
