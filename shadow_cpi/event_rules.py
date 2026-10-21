"""Event rules decided before any scoring (owner, 2026-10-21). Plain code, no AI.

1. Scope by kind. Prices set nationally (LPG, petrol/diesel, rail fares, mobile tariffs, NPPA medicine prices, GST)
   apply to all of India whatever city a page quotes. Prices set regionally (milk, electricity, school fees) apply
   only to the state(s) named.
2. Regional weight = the state's share of that CPI item, from MoSPI's official 2024-series item weights by state
   (Annex 5.3d: 'Share in All India', summed over rural + urban). Several states: shares are added. A regional event
   whose state cannot be found is NOT applied (reason recorded).
3. Duplicates: events of the same kind, the same effective date, the same scope (cities mapped to their state, e.g.
   Mumbai -> Maharashtra), and % changes within 0.5 percentage points are one event; sources are pooled.
"""
import re
from collections import defaultdict
from functools import lru_cache

from .verify import norm

NATIONAL_KINDS = {"lpg", "fuel", "rail", "mobile", "medicine", "gst"}
REGIONAL_KINDS = {"milk", "electricity", "school_fee"}
DUP_PP = 0.5
SOURCE = "MoSPI CPI 2024 Expert Group report, Annex 5.3d (item weights by state, rural + urban)"

STATE_ALIASES = {
    "uttar pradesh": ["uttar pradesh", "u.p.", "uppcl", "उत्तर प्रदेश", "उत्तरप्रदेश", "यूपी"],
    "madhya pradesh": ["madhya pradesh", "m.p.", "मध्य प्रदेश", "मध्यप्रदेश"],
    "jammu and kashmir": ["jammu & kashmir", "jammu and kashmir", "j&k", "जम्मू"],
    "nct of delhi": ["delhi", "दिल्ली", "ncr"],
    "west bengal": ["west bengal", "पश्चिम बंगाल"], "tamil nadu": ["tamil nadu", "तमिलनाडु"],
    "andhra pradesh": ["andhra pradesh"], "himachal pradesh": ["himachal pradesh", "हिमाचल"],
    "arunachal pradesh": ["arunachal pradesh"],
    "bihar": ["bihar", "बिहार"], "jharkhand": ["jharkhand", "झारखंड"], "rajasthan": ["rajasthan", "राजस्थान"],
    "gujarat": ["gujarat", "गुजरात"], "maharashtra": ["maharashtra", "महाराष्ट्र"], "karnataka": ["karnataka", "कर्नाटक"],
    "punjab": ["punjab", "पंजाब"], "haryana": ["haryana", "हरियाणा"], "uttarakhand": ["uttarakhand", "उत्तराखंड"],
    "odisha": ["odisha", "orissa", "ओडिशा"], "kerala": ["kerala", "केरल"], "telangana": ["telangana", "तेलंगाना"],
    "assam": ["assam", "असम"], "chhattisgarh": ["chhattisgarh", "छत्तीसगढ़"],
}
CITY_STATE = {
    "mumbai": "maharashtra", "मुंबई": "maharashtra", "pune": "maharashtra", "nagpur": "maharashtra",
    "nashik": "maharashtra", "thane": "maharashtra", "kolkata": "west bengal", "chennai": "tamil nadu",
    "coimbatore": "tamil nadu", "bengaluru": "karnataka", "bangalore": "karnataka", "hyderabad": "telangana",
    "ahmedabad": "gujarat", "surat": "gujarat", "vadodara": "gujarat", "anand": "gujarat",
    "lucknow": "uttar pradesh", "noida": "uttar pradesh", "kanpur": "uttar pradesh", "varanasi": "uttar pradesh",
    "agra": "uttar pradesh", "ghaziabad": "uttar pradesh", "indore": "madhya pradesh", "इंदौर": "madhya pradesh",
    "dhar": "madhya pradesh", "धार": "madhya pradesh", "bhopal": "madhya pradesh", "jaipur": "rajasthan",
    "patna": "bihar", "ranchi": "jharkhand", "gurugram": "haryana", "gurgaon": "haryana", "faridabad": "haryana",
    "srinagar": "jammu and kashmir", "dehradun": "uttarakhand", "bhubaneswar": "odisha", "guwahati": "assam",
    "kochi": "kerala", "thiruvananthapuram": "kerala", "raipur": "chhattisgarh", "ludhiana": "punjab",
    "amritsar": "punjab", "shimla": "himachal pradesh", "panaji": "goa", "new delhi": "nct of delhi",
}
NATIONWIDE_LINE = ["nationwide", "across the country", "across india", "all over india", "all over the country",
                   "देशभर", "पूरे देश", "देश भर"]


@lru_cache(maxsize=1)
def state_item_weights():
    """{item_code: {state (lower case): weight}} from Annex 5.3d."""
    from .official import WEIGHTS_XLSX, read_xlsx
    w = defaultdict(lambda: defaultdict(float))
    for r in read_xlsx(WEIGHTS_XLSX)["5.3d"][3:]:
        if len(r) > 13 and r[4] and re.fullmatch(r"\d\d(\.\d+){3}\.\d\.\d\d", r[4].strip()):
            w[r[4].strip()][r[1].strip().lower()] += float(r[13] or 0)
    return {k: dict(v) for k, v in w.items()}


def _states_in(text):
    t = " " + norm(text or "") + " "
    found = set()
    weights = state_item_weights()
    all_states = {s for v in weights.values() for s in v}
    for s in all_states:
        if re.search(r"(?<![a-z])" + re.escape(s) + r"(?![a-z])", t):
            found.add(s)
    for s, aliases in STATE_ALIASES.items():
        if any(re.search(r"(?<![a-z])" + re.escape(norm(a)) + r"(?![a-z])", t) for a in aliases):
            found.add(s)
    for city, s in CITY_STATE.items():
        if re.search(r"(?<![a-z])" + re.escape(norm(city)) + r"(?![a-z])", t):
            found.add(s)
    return found


def scope(event):
    """('national', None) or ('regional', frozenset(states)) or ('unknown', None). Region field first, then the
    seller/authority (e.g. UPPCL), for regional kinds only."""
    if event["kind"] in NATIONAL_KINDS:
        return "national", None
    line = norm(event.get("quote") or "")
    # 2025 audit: 'India' in the model's region field made brand-only changes national (Mother Dairy UHT, Sanchi).
    # National now needs the cited LINE to say nationwide; states are looked for in region, seller and the line.
    if any(norm(w) in line for w in NATIONWIDE_LINE):
        return "national", None
    states = _states_in(event.get("region")) or _states_in(event.get("seller_or_authority")) or _states_in(line)
    if states:
        return "regional", frozenset(states)
    return "unknown", None


def state_share(item_code, states):
    """Official share of the CPI item in these states (0..1)."""
    w = state_item_weights().get(item_code, {})
    tot = sum(w.values())
    return sum(w.get(s, 0.0) for s in states) / tot if tot else 0.0


def apply_rules(events):
    """Adds scope, states, weight and applied change; merges duplicates. Returns (kept, dropped[(event, reason)])."""
    kept, dropped = [], []
    for e in events:
        kind_scope, states = scope(e)
        if kind_scope == "unknown":
            dropped.append((e, "regional event: state not identified"))
            continue
        weight = 1.0 if kind_scope == "national" else state_share(e.get("cpi_code", ""), states)
        kept.append({**e, "scope": kind_scope, "states": sorted(states) if states else [],
                     "weight": weight, "weight_source": "national (weight 1)" if kind_scope == "national" else SOURCE,
                     "applied_change": e["change_prorated"] * weight})
    merged = []
    for e in kept:
        # 2025 audit: one sentence with a range ('दो से तीन रुपये') gave two events. Same cited line -> one event.
        same_line = next((m for m in merged if e.get("quote") and norm(m.get("quote") or "") == norm(e["quote"])
                          and m["kind"] == e["kind"]), None)
        if same_line:
            n = same_line.get("_n", 1)
            for k in ("change", "change_prorated", "applied_change"):
                same_line[k] = (same_line[k] * n + e[k]) / (n + 1)
            same_line["_n"] = n + 1
            dropped.append((e, "same cited line as an event already kept (merged, mean change)"))
            continue
        twin = next((m for m in merged if m["kind"] == e["kind"] and m["effective_date"] == e["effective_date"]
                     and m["scope"] == e["scope"] and m["states"] == e["states"]
                     and abs(m["change"] - e["change"]) * 100 <= DUP_PP), None)
        if twin:
            twin["sources"] = sorted(set(twin["sources"]) | set(e.get("sources", [e.get("url")])))
            dropped.append((e, "duplicate of an event already kept (same kind, date, scope, % within 0.5 pp)"))
        else:
            merged.append({**e, "sources": list(e.get("sources", [e.get("url")]))})
    return merged, dropped


# ---------- calibrated on the 2025 recall audit (results/recall_audit/) ----------
from datetime import date, timedelta  # noqa: E402

MONTHS_EN = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
             "november", "december"]
MONTHS_HI = ["जनवरी", "फरवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"]
WEEKDAYS_EN = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
WEEKDAYS_HI = ["सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"]


def normalise_date(text, page_date):
    """An effective date written in words -> YYYY-MM-DD, using the page's date for the year / 'today' / weekdays.
    Returns '' if it cannot be read. (Audit: 'April 8', 'Tuesday', 'आज (बुधवार)' were all dropped before.)"""
    t = (text or "").strip().lower()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", t):
        return t
    if not page_date:
        return ""
    pd = date.fromisoformat(page_date)
    for i, (en, hi) in enumerate(zip(MONTHS_EN, MONTHS_HI)):
        m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+(?:" + en + "|" + en[:3] + "|" + hi + r")\b", t) or \
            re.search(r"(?:" + en + "|" + en[:3] + "|" + hi + r")\s+(\d{1,2})(?!\d)", t)
        if m:
            y = int(re.search(r"(20\d\d)", t).group(1)) if re.search(r"20\d\d", t) else pd.year
            try:
                return date(y, i + 1, int(m.group(1))).isoformat()
            except ValueError:
                return ""
    if re.search(r"\btoday\b|आज|midnight", t):
        return pd.isoformat()
    for k, (en, hi) in enumerate(zip(WEEKDAYS_EN, WEEKDAYS_HI)):
        if en in t or hi in t:
            return (pd + timedelta(days=(k - pd.weekday()) % 7)).isoformat()
    return ""


ABS = re.compile(r"(?:by|of|hike of|cut of)\s*(?:rs\.?|₹|inr)\s*(\d+(?:\.\d+)?)|(?:₹|rs\.?)\s*(\d+(?:\.\d+)?)\s*(?:per|a)\s"
                 r"|(\d+(?:\.\d+)?)\s*(?:रुपये|रुपए)", re.I)
UP_WORDS = re.compile(r"hike|increase|raise|costlier|बढ़|इजाफा|महंगा", re.I)
DOWN_WORDS = re.compile(r"cut|reduc|lower|cheaper|घट|सस्ता|कटौती", re.I)


def absolute_change(line):
    """'+50' from 'hike ... by Rs 50' (sign from hike/cut words in the same line), or None. The number must be in the
    cited line by construction."""
    m = ABS.search(line or "")
    if not m:
        return None
    v = float(next(g for g in m.groups() if g))
    up, down = bool(UP_WORDS.search(line)), bool(DOWN_WORDS.search(line))
    if up == down:
        return None                     # no direction, or both: not usable
    return v if up else -v


def base_price(kind, effective_date):
    """Official price just before the change, to turn an absolute change into %. LPG: IOCL domestic 14.2 kg, 4-metro
    mean in force the day before. Milk: DoCA all-India simple mean of zones, previous month. Else None."""
    import json as _json
    from .settings import ROOT
    day_before = (date.fromisoformat(effective_date) - timedelta(days=1)).isoformat()
    if kind == "lpg":
        f = ROOT / "data" / "evidence" / "iocl_lpg.json"
        if f.exists():
            rev = [r for r in _json.loads(f.read_text()) if r[0] <= day_before]
            if rev:
                return sum(rev[-1][1].values()) / len(rev[-1][1]), "IOCL domestic 14.2 kg, 4-metro mean"
    if kind == "milk":
        import csv as _csv
        f = ROOT / "data" / "spine.csv"
        prev = f"{int(effective_date[:4]) - (effective_date[5:7] == '01')}-" \
               f"{(int(effective_date[5:7]) - 2) % 12 + 1:02d}"
        if f.exists():
            for r in _csv.DictReader(f.open(encoding="utf-8")):
                if r["item"] == "milk" and r["month"] == prev and r["centre"].startswith("All India"):
                    return float(r["avg_price"]), "DoCA milk, all-India simple mean of zones, previous month"
    return None
