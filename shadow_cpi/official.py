"""Official MoSPI data for the 2024-base CPI: weights, monthly indices, checks and baselines. Plain code, no AI.

Sources (all saved raw under data/official/):
- Weights: MoSPI CPI 2024 Expert Group report, Annex 5.3 (xlsx). Division (5.3a), group (5.3b) and
  item (5.3d, state x sector shares of the all-India basket; summed here to all-India item weights).
- Indices: MoSPI's public CPI API (api.mospi.gov.in/api/cpi/getCPIData, base_year=2024). One call per page
  returns every level at once: CPI (General), 13 divisions, 43 groups, 92 classes, 162 sub-classes,
  358 items. Fetched as the LOGGED direct-download route (Recorder service 'direct'): Tavily cannot call a
  paged JSON API, and Prompt 1 asks to fetch the official files directly from this computer first.

Hierarchy (2024 series, COICOP 2018): division "01" > group "01.1" > class "01.1.1" > sub-class "01.1.1.1"
> item "01.1.1.1.1.01". The old series' "subgroup" corresponds to the new "group" (43 of them).
"""
import csv
import json
import math
import re
import ssl
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from pathlib import Path

from . import cpi_math as M
from .recorder import Recorder
from .settings import ROOT

OFFICIAL_DIR = ROOT / "data" / "official"
RAW_API_DIR = OFFICIAL_DIR / "mospi_api"
WEIGHTS_XLSX = OFFICIAL_DIR / "mospi_cpi2024_weights_Annex_5.3.xlsx"
TIDY_CSV = ROOT / "data" / "cpi_tidy.csv"
ITEM_MAP_CSV = ROOT / "data" / "item_map.csv"
POLL_CSV = ROOT / "data" / "poll.csv"
BASELINES_CSV = ROOT / "results" / "baselines.csv"

API = "https://api.mospi.gov.in/api/cpi/getCPIData"
API_PAGE_SIZE = 100          # the API refuses larger pages
HEADLINE = "CPI"             # code used here for CPI (General); the API leaves it blank
LEVELS = ("general", "division", "group", "class", "sub_class", "item")

CALIBRATION_MONTHS = [f"2025-{m:02d}" for m in range(1, 13)]
TEST_MONTHS = [f"2026-{m:02d}" for m in range(1, 10)]
FIRST_MONTH, LAST_MONTH = "2025-01", "2026-09"

FOOD_2024, FOOD_2012 = 36.75, 45.86     # food and beverages weight, % of the basket
MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
               "October", "November", "December"]


class WrongSeries(Exception):
    """Raised when the weights look like the 2012 series (or anything that is not the 2024 series)."""


# ---------- months ----------
def month_range(first=FIRST_MONTH, last=LAST_MONTH):
    out, m = [], first
    while m <= last:
        out.append(m)
        m = M.add_months(m, 1)
    return out


def level_of(code):
    """Hierarchy level from the shape of a 2024-series code."""
    if not code or code == HEADLINE:
        return "general"
    parts = code.split(".")
    return {1: "division", 2: "group", 3: "class", 4: "sub_class", 6: "item"}.get(len(parts), "unknown")


def parent_code(code, level):
    """Code of the ancestor at `level` (e.g. parent_code('01.1.7.4.1.01', 'group') == '01.1')."""
    n = {"division": 1, "group": 2, "class": 3, "sub_class": 4}[level]
    return ".".join(code.split(".")[:n])


# ---------- weights (stdlib xlsx reader) ----------
_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _col(ref):
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group():
        n = n * 26 + ord(ch) - 64
    return n - 1


def read_xlsx(path):
    """{sheet_name: [[cell, ...], ...]} using only the standard library (xlsx is zipped XML)."""
    z = zipfile.ZipFile(path)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", _NS):
            shared.append("".join(t.text or "" for t in si.iter("{%s}t" % _NS["m"])))
    names = [s.get("name") for s in ET.fromstring(z.read("xl/workbook.xml")).find("m:sheets", _NS)]
    sheets = sorted((n for n in z.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n)),
                    key=lambda n: int(re.findall(r"\d+", n)[0]))
    out = {}
    for name, path_in_zip in zip(names, sheets):
        rows = []
        for r in ET.fromstring(z.read(path_in_zip)).iter("{%s}row" % _NS["m"]):
            row = {}
            for c in r.findall("m:c", _NS):
                v, t = c.find("m:v", _NS), c.get("t")
                if t == "inlineStr":
                    val = "".join(x.text or "" for x in c.iter("{%s}t" % _NS["m"]))
                elif v is None:
                    continue
                else:
                    val = shared[int(v.text)] if t == "s" else v.text
                row[_col(c.get("r"))] = val
            if row:
                rows.append([row.get(i, "") for i in range(max(row) + 1)])
        out[name] = rows
    return out


def load_weights(path=WEIGHTS_XLSX):
    """Returns (weights, names): weights {code: % of all-India Combined basket} for every level.
    Items come from Annex 5.3d (summed over states and sectors); class / sub-class / division are sums of
    their items; groups are read from Annex 5.3b and must agree with the item sums."""
    book = read_xlsx(path)
    items, names = defaultdict(float), {}
    for r in book["5.3d"][3:]:
        if len(r) < 14 or not re.fullmatch(r"\d\d(\.\d+){3}\.\d\.\d\d", (r[4] or "").strip()):
            continue
        code = r[4].strip()
        items[code] += float(r[13] or 0)
        names[code] = r[3].strip()
        names[r[5]], names[r[7]], names[r[9]], names[r[11]] = r[6].strip(), r[8].strip(), r[10].strip(), r[12].strip()
    w = dict(items)
    for level in ("sub_class", "class", "group", "division"):
        for code, v in items.items():
            p = parent_code(code, level)
            w[p] = w.get(p, 0.0) + v
    w[HEADLINE] = sum(items.values())
    names[HEADLINE] = "CPI (General)"
    published_groups = {r[0]: float(r[4]) for r in book["5.3b"][4:] if len(r) > 4 and re.fullmatch(r"\d\d\.\d", r[0] or "")}
    for g, v in published_groups.items():
        if abs(w.get(g, 0.0) - v) > 1e-6:
            raise WrongSeries(f"group {g}: item weights sum to {w.get(g)} but Annex 5.3b says {v}")
    published_div = {r[0].strip(): float(r[3]) for r in book["5.3a"][4:] if len(r) > 3 and r[0] and r[0] != "Grand Total"}
    for code, v in w.items():
        if level_of(code) == "division" and names.get(code) in published_div:
            if abs(v - published_div[names[code]]) > 1e-6:
                raise WrongSeries(f"division {code}: item sum {v} vs Annex 5.3a {published_div[names[code]]}")
    return w, names


def guard_2024_weights(weights, names=None):
    """Refuse to run on 2012-series weights. Food and beverages must be ~36.75% (2012 series: ~45.86%)."""
    food = weights.get("01")
    total = weights.get(HEADLINE) or sum(v for c, v in weights.items() if level_of(c) == "division")
    if food is None or not total:
        raise WrongSeries("no food-and-beverages weight found")
    share = food / total * 100
    if abs(share - FOOD_2012) < 2.0:
        raise WrongSeries(f"food weight {share:.2f}% looks like the 2012 series ({FOOD_2012}%) - refusing to run")
    if abs(share - FOOD_2024) > 0.5:
        raise WrongSeries(f"food weight {share:.2f}% is not the 2024 series ({FOOD_2024}%) - refusing to run")
    return share


# ---------- indices (MoSPI API, logged direct route) ----------
def _get_json(url):
    # api.mospi.gov.in needs TLS legacy renegotiation, which Python 3.12+ refuses by default.
    # Certificates are still verified; only that one handshake option is relaxed.
    ctx = ssl.create_default_context()
    ctx.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (ShadowCPI research)",
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
        return json.load(r)


def api_url(month, page):
    y, m = month.split("-")
    return (f"{API}?base_year=2024&series=Current&year={y}&month_code={int(m)}&state_code=1&sector_code=3"
            f"&limit={API_PAGE_SIZE}&page={page}&Format=JSON")


def fetch_month(month, rec=None, fetch=_get_json, raw_dir=RAW_API_DIR):
    """All rows for one month (all pages), via the Recorder (cache + Flight Recorder). Raw pages are also
    saved to data/official/mospi_api/ so the official files sit next to the code that reads them."""
    rec = rec or Recorder()
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    rows, page, pages = [], 1, 1
    while page <= pages:
        url = api_url(month, page)
        resp, _ = rec.call("direct", "GET", {"url": url}, lambda u=url: fetch(u), tag="official-mospi-api")
        if not resp.get("statusCode") or "data" not in resp:
            raise RuntimeError(f"MoSPI API error for {month} page {page}: {str(resp)[:200]}")
        (raw_dir / f"cpi2024_allindia_combined_{month}_p{page}.json").write_text(
            json.dumps(resp, ensure_ascii=False, indent=0), encoding="utf-8")
        pages = int(resp.get("meta_data", {}).get("totalPages") or 1)
        rows.extend(resp["data"])
        page += 1
    return rows


def published_headline_yoy_2012(month, rec=None, fetch=_get_json, raw_dir=RAW_API_DIR):
    """MoSPI's published headline YoY on the OLD 2012 base for one month. Used only as B1's input for
    January 2026 (B1 = last month's YoY; December 2025 was published on the 2012 base, before the new series
    started). Only a published headline number is read here - never 2012-series weights."""
    rec = rec or Recorder()
    y, m = month.split("-")
    url = ("https://api.mospi.gov.in/api/cpi/getCPIIndex?base_year=2012&series=Current"
           f"&year={y}&month_code={int(m)}&state_code=99&sector_code=3&limit=100&Format=JSON")
    resp, _ = rec.call("direct", "GET", {"url": url}, lambda: fetch(url), tag="official-mospi-api")
    Path(raw_dir).mkdir(parents=True, exist_ok=True)
    (Path(raw_dir) / f"cpi2012_allindia_combined_{month}.json").write_text(
        json.dumps(resp, ensure_ascii=False, indent=0), encoding="utf-8")
    for r in resp.get("data", []):
        if r.get("group") == "General" and r.get("subgroup") == "General-Overall":
            return float(r["inflation"])
    raise RuntimeError(f"no 2012-series General index for {month}")


def tidy_rows(month, api_rows, weights, names):
    """API records -> tidy rows (month, level, code, name, weight, index, published_yoy, imputed).
    The index is kept as a string-exact float (no rounding)."""
    out, seen = [], set()
    y, mnum = month.split("-")
    for r in api_rows:
        if str(r.get("year")) != y or r.get("month") != MONTH_NAMES[int(mnum) - 1]:
            raise RuntimeError(f"API returned {r.get('year')} {r.get('month')} when asked for {month}")
        if r.get("state") != "All India" or r.get("sector") != "Combined":
            raise RuntimeError(f"API returned {r.get('state')}/{r.get('sector')}, expected All India/Combined")
        code = (r.get("code") or "").strip() or HEADLINE
        lvl = level_of(code)
        if code in seen:
            raise RuntimeError(f"duplicate code {code} in {month}")
        seen.add(code)
        name = r.get({"general": "division"}.get(lvl, lvl))   # the API puts 'CPI (General)' in 'division'
        out.append({"month": month, "level": lvl, "code": code, "name": name or names.get(code, ""),
                    "weight": weights.get(code, ""), "index": float(r["index"]),
                    "published_yoy": "" if r.get("inflation") in (None, "") else float(r["inflation"]),
                    "imputed": r.get("imputation") or ""})
    return out


def write_tidy(rows, path=TIDY_CSV):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = ["month", "level", "code", "name", "weight", "index", "published_yoy", "imputed"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in sorted(rows, key=lambda r: (r["month"], LEVELS.index(r["level"]) if r["level"] in LEVELS else 9, r["code"])):
            w.writerow({k: (repr(v) if isinstance(v, float) else v) for k, v in r.items()})


def load_tidy(path=TIDY_CSV):
    """Returns (series {code: {month: index}}, weights {code: weight}, published_yoy {code: {month: yoy}}, meta)."""
    series, weights, pub, meta = defaultdict(dict), {}, defaultdict(dict), {}
    with Path(path).open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            series[r["code"]][r["month"]] = float(r["index"])
            if r["weight"]:
                weights[r["code"]] = float(r["weight"])
            if r["published_yoy"]:
                pub[r["code"]][r["month"]] = float(r["published_yoy"])
            meta[r["code"]] = {"level": r["level"], "name": r["name"]}
    return dict(series), weights, dict(pub), meta


# ---------- checks ----------
def codes_at(level, weights):
    return [c for c in weights if level_of(c) == level]


def aggregation_check(series, weights, level, months):
    """For each month, aggregate the published LEVELS at `level` with the official weights and compare
    with the published CPI (General). Returns [(month, aggregated, published, gap)]."""
    out = []
    codes = codes_at(level, weights)
    for m in months:
        lv = {c: series[c][m] for c in codes if m in series.get(c, {})}
        missing = [c for c in codes if c not in lv]
        if missing:
            raise RuntimeError(f"{m}: {len(missing)} {level} indices missing, e.g. {missing[:3]}")
        agg = M.aggregate(lv, {c: weights[c] for c in codes})
        pub = series[HEADLINE][m]
        out.append((m, agg, pub, agg - pub))
    return out


def yoy_check(series, published_yoy, months):
    """YoY of CPI (General) from the index levels vs MoSPI's published YoY. Returns [(month, ours, published, diff)]."""
    out = []
    for m in months:
        ours = M.yoy(series[HEADLINE][m], series[HEADLINE][M.add_months(m, -12)])
        pub = published_yoy[HEADLINE][m]
        out.append((m, ours, pub, ours - pub))
    return out


# ---------- baselines ----------
def actual_yoy(series, published_yoy, month):
    """The official figure we score against: MoSPI's published YoY for CPI (General)."""
    return published_yoy[HEADLINE][month]


def b1(series, published_yoy, month, older_prints=None):
    """B1 = last month's YoY. Computed from 2024-series levels when both exist; otherwise (Jan 2026 needs
    Dec 2024, which is before the series starts) the official print for last month: the 2024-series published
    YoY if there is one, else `older_prints` (e.g. {'2025-12': 1.33}, published on the 2012 base)."""
    prev = M.add_months(month, -1)
    if M.add_months(prev, -12) in series[HEADLINE]:
        return M.b1_last_yoy(series[HEADLINE], month), "2024-series levels"
    if prev in published_yoy.get(HEADLINE, {}):
        return published_yoy[HEADLINE][prev], "2024-series published YoY"
    return (older_prints or {})[prev], "2012-series published YoY (last print before the new series)"


def b2(series, weights, month, level="group", seasonal_weight=0.5):
    """B2 = each component follows its own trend (cpi_math.trend_change, seasonal weight 0.5, fixed in advance);
    predicted LEVELS are aggregated with the official weights. The aggregate is anchored to the published
    headline: predicted headline = published(last month) x agg(predicted) / agg(last month's levels), so the
    small rounding gap of aggregating published indices does not leak into the forecast.
    Uses only data up to last month. Returns (predicted YoY, predicted headline level)."""
    prev = M.add_months(month, -1)
    codes = codes_at(level, weights)
    w = {c: weights[c] for c in codes}
    hist = {c: {k: v for k, v in series[c].items() if k <= prev} for c in codes}   # nothing from `month` on
    last = {c: hist[c][prev] for c in codes}
    pred = {c: last[c] * (1 + M.trend_change(hist[c], month, seasonal_weight=seasonal_weight)) for c in codes}
    head = series[HEADLINE][prev] * M.aggregate(pred, w) / M.aggregate(last, w)
    return M.yoy(head, series[HEADLINE][M.add_months(month, -12)]), head


def read_poll(path=POLL_CSV):
    """{month: median_forecast} for months with a dated source; months marked 'none' are left out."""
    out = {}
    p = Path(path)
    if not p.exists():
        return out
    with p.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            v = (r.get("median_forecast") or "").strip().lower()
            if v and v != "none" and (r.get("source_url") or "").strip().lower() not in ("", "none") \
                    and (r.get("published_at") or "").strip().lower() not in ("", "none"):
                out[r["month"]] = float(v)
    return out


def run_baselines(series, weights, published_yoy, months=TEST_MONTHS, poll=None, older_prints=None):
    poll = poll or {}
    rows = []
    for m in months:
        act = actual_yoy(series, published_yoy, m)
        b1v, b1src = b1(series, published_yoy, m, older_prints)
        b2v, _ = b2(series, weights, m)
        pv = poll.get(m)
        rows.append({"month": m, "actual_yoy": act, "b1_pred": b1v, "b1_source": b1src, "b1_miss": b1v - act,
                     "b2_pred": b2v, "b2_miss": b2v - act, "poll_pred": "" if pv is None else pv,
                     "poll_miss": "" if pv is None else pv - act})
    return rows


def mean_abs(xs):
    xs = [abs(x) for x in xs if x != "" and x is not None]
    return (sum(xs) / len(xs), len(xs)) if xs else (math.nan, 0)


def write_baselines(rows, path=BASELINES_CSV):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        for r in rows:
            w.writerow({k: (repr(v) if isinstance(v, float) else v) for k, v in r.items()})


# ---------- tracked items ----------
# tracked name -> (codes whose weights add up to the tracked item, note). Codes come from Annex 5.3d.
TRACKED = {
    "onion": (["01.1.7.4.1.01"], ""),
    "tomato": (["01.1.7.2.1.01"], ""),
    "potato": (["01.1.7.5.1.01"], ""),
    "tur dal": (["01.1.7.6.1.01"], "MoSPI item 'Arhar, tur'"),
    "edible oils": (["01.1.5.1"], "no single item: sub-class 'Vegetable oils' (refined, mustard, groundnut, "
                                  "coconut, other edible oil, edible oil PDS); each oil also has its own item index"),
    "rice": (["01.1.1.1.1.01"], "market rice; 'Rice PDS' (01.1.1.1.1.11) is a separate item"),
    "atta": (["01.1.1.2.1.01"], "market 'Wheat atta'; 'Wheat atta PDS' (01.1.1.2.1.03) is a separate item"),
    "milk": (["01.1.4.1.1.01"], "MoSPI item 'Milk: liquid'"),
    "eggs": (["01.1.4.8.1.01"], ""),
    "gold": (["13.2.1.1.1.01"], "MoSPI item is 'Gold /diamond /platinum jewellery' (not gold alone)"),
    "silver": (["13.2.1.1.1.02"], "MoSPI item 'Silver jewellery'"),
    "lpg": (["04.5.2.2.1.01"], "MoSPI item is 'LPG cylinder and piped natural gas' (LPG and PNG together)"),
    "petrol": (["07.2.2.2.1.01"], "petrol for vehicles"),
}


def item_map_rows(series, weights, names):
    rows = []
    for name, (codes, note) in TRACKED.items():
        code = codes[0]
        lvl = level_of(code)
        monthly = all(m in series.get(code, {}) for m in month_range())
        rows.append({"tracked_item": name, "subgroup_code": parent_code(code, "group"),
                     "subgroup_name": names.get(parent_code(code, "group"), ""),
                     "sub_class_code": parent_code(code, "sub_class"),
                     "item_index_code": code if lvl == "item" and monthly else "",
                     "finest_level": lvl, "finest_code": code, "finest_name": names.get(code, ""),
                     "weight": weights[code], "monthly_index_published": monthly, "note": note})
    return rows


def write_item_map(rows, path=ITEM_MAP_CSV):
    path = Path(path)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        for r in rows:
            w.writerow({k: (repr(v) if isinstance(v, float) else v) for k, v in r.items()})
