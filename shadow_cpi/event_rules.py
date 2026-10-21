"""Event rules decided before any scoring (owner, 2026-10-21). Plain code, no AI.

1. Scope by kind. Prices set nationally (LPG, petrol/diesel, rail fares, mobile tariffs, NPPA medicine prices, GST)
   apply to all of India whatever city a page quotes. Prices set regionally (milk, electricity, school fees) apply
   only to the state(s) named.
2. Regional weight = the state's share of that CPI item, from MoSPI's official 2024-series item weights by state
   (Annex 5.3d: 'Share in All India', summed over rural + urban). Several states: shares are added. A regional event
   whose state cannot be found is NOT applied (reason recorded).
3. Duplicates: events of the same kind, the same effective date, the same scope (cities mapped to their state, e.g.
   Mumbai -> Maharashtra), and % changes within 0.5 percentage points are one event; sources are pooled.
Amendment 3 (after scoring, bug fixes enforcing scope already written down): (a) wholesale/tabela/loose/farmer-rate
wording in the line or its context, (b) premium fuel grades, (c) national only by a nationwide line or a national
body, (d) one event per kind x state x month. See docs/after_scoring_changes.md.
"""
import calendar
import re
import statistics
from collections import defaultdict
from functools import lru_cache

from .verify import norm

NATIONAL_KINDS = {"lpg", "fuel", "rail", "mobile", "medicine", "gst"}
REGIONAL_KINDS = {"milk", "electricity", "school_fee"}
DUP_PP = 0.5
DUP_DAYS = 15          # Amendment 1 (e)
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


# Amendment 3 (c): national bodies or operators that set one all-India price, per kind.
NATIONAL_BODIES = {
    "fuel": ["indian oil", "iocl", r"\bioc\b", "hpcl", "hindustan petroleum", "bpcl", "bharat petroleum",
             "oil marketing compan", "oil compan", r"\bomcs?\b", "ministry of petroleum", "petroleum ministry",
             "तेल कंपनि", "तेल विपणन", "तेल कंपन्या"],
    "rail": ["railway board", "indian railways", "ministry of railways", "railways ministry", "रेल मंत्रालय",
             "भारतीय रेल", "रेलवे बोर्ड"],
    "mobile": [r"\btrai\b", r"\bjio\b", "airtel", "vodafone", r"\bvi\b", "bsnl"],
    "medicine": [r"\bnppa\b", "national pharmaceutical pricing"],
    "gst": ["gst council", "जीएसटी काउंसिल", "जीएसटी परिषद", r"\bcbic\b", "finance ministry", "वित्त मंत्रालय"],
}
NATIONAL_BODIES["lpg"] = NATIONAL_BODIES["fuel"]
# A single line, route, zone, metro, city district: never national, whoever sets it.
LOCAL_MARKERS = [r"\broute\b", r"mountain railway", r"toy train", r"\bmetro\b", r"suburban", r"local trains?\b",
                 r"\bheritage\b", r"\bzonal\b", r"\bdistrict\b",
                 r"\b(southern|northern|eastern|western|central|south central|south eastern|south western|"
                 r"north eastern|north western|east central|west central|north central|east coast|"
                 r"northeast frontier|konkan) railway\b", r"रूट", r"मेट्रो", r"जिले", r"ज़िले", r"जिल्ह"]


def scope(event):
    """('national', None) or ('regional', frozenset(states)) or ('unknown', None).
    Amendment 3 (c): national only if the cited line says nationwide, or (national kinds) a national body or operator
    sets an all-India price and the event is not about a single line, route, zone or district. Everything else is
    regional, weighted by its state(s): region field first, then the seller/authority, then the line."""
    line = norm(event.get("quote") or "")
    seller = norm(event.get("seller_or_authority") or "")
    # 2025 audit: 'India' in the model's region field made brand-only changes national (Mother Dairy UHT, Sanchi).
    if any(norm(w) in line for w in NATIONWIDE_LINE):
        return "national", None
    if event["kind"] in NATIONAL_KINDS:
        local = any(re.search(p, t) for p in LOCAL_MARKERS for t in (line, seller, norm(event.get("region") or "")))
        body = any(re.search(p, t) for p in NATIONAL_BODIES.get(event["kind"], []) for t in (line, seller))
        if body and not local:
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
    # pass 1 (2025 audit): events from the same cited line are one event, at the mean change
    lines = []
    for e in kept:
        same_line = next((m for m in lines if e.get("quote") and norm(m.get("quote") or "") == norm(e["quote"])
                          and m["kind"] == e["kind"]), None)
        if same_line:
            n = same_line.get("_n", 1)
            for k in ("change", "change_prorated", "applied_change"):
                same_line[k] = (same_line[k] * n + e[k]) / (n + 1)
            same_line["_n"] = n + 1
            dropped.append((e, "same cited line as an event already kept (merged, mean change)"))
        else:
            lines.append(dict(e))
    # pass 2 (Amendment 1 e): same kind and scope, % within 0.5 pp, effective dates within 15 days -> one event,
    # using the earliest effective date. Runs AFTER pass 1 so averaged same-line events are compared too.
    merged = []
    for e in lines:
        twin = next((m for m in merged if m["kind"] == e["kind"] and m["scope"] == e["scope"]
                     and m["states"] == e["states"] and abs(m["change"] - e["change"]) * 100 <= DUP_PP
                     and abs((date.fromisoformat(m["effective_date"]) -
                              date.fromisoformat(e["effective_date"])).days) <= DUP_DAYS), None)
        if twin:
            pooled = sorted(set(twin["sources"]) | set(e.get("sources", [e.get("url")])))
            if e["effective_date"] < twin["effective_date"]:          # keep the earliest dated effective date
                twin.clear()
                twin.update({**e, "sources": pooled})
            else:
                twin["sources"] = pooled
            dropped.append((e, "duplicate of an event already kept (same kind and scope, % within 0.5 pp, "
                               "effective dates within 15 days)"))
        else:
            merged.append({**e, "sources": list(e.get("sources", [e.get("url")]))})
    # pass 3 (Amendment 3 d): at most one event per kind x scope/state(s) x month. Several -> one, at the median %
    # change and the earliest effective date (day share recomputed from it).
    groups = defaultdict(list)
    for e in merged:
        groups[(e["kind"], e["scope"], tuple(e["states"]))].append(e)
    final = []
    for evs in groups.values():
        if len(evs) == 1:
            final.append(evs[0])
            continue
        first = min(evs, key=lambda x: x["effective_date"])
        change = statistics.median(x["change"] for x in evs)
        d = date.fromisoformat(first["effective_date"])
        days = calendar.monthrange(d.year, d.month)[1]
        share = (days - d.day + 1) / days
        one = {**first, "change": change, "days_share": share, "change_prorated": change * share,
               "applied_change": change * share * first["weight"],
               "sources": sorted({s for x in evs for s in x["sources"]}), "merged_from": len(evs),
               "merged_changes": [x["change"] for x in evs]}
        if one.get("pct_change") is not None:
            one["pct_change"] = change * 100
        for x in evs:
            if x is not first:
                dropped.append((x, "one event per kind and state per month (merged: median change, earliest date)"))
        final.append(one)
    return final, dropped


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


def announced_date(text, page_date):
    """The announcement date as YYYY-MM-DD: the date written in the page if it reads and is not after the page's own
    date, else the page's date. Record only; no rule reads it. (Audit: the model copied a site header's 'today',
    'Tue, Oct 20, 2026', from a page dated 2026-03-31.)"""
    d = normalise_date(text, page_date)
    return d if d and (not page_date or d <= page_date) else (page_date or None)


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


# ---------- Amendment 1 (2026-10-21): consumer retail prices only, every kind, English + Hindi ----------
NON_DOMESTIC = ["commercial", "19 kg", "19-kg", "19kg", "5 kg", "5-kg", "5kg", "ftl", "free trade", "industrial",
                "bulk", "non-domestic", "वाणिज्यिक", "व्यावसायिक", "कमर्शियल", "कॉमर्शियल", "औद्योगिक"]
DOMESTIC = ["domestic", "household", "residential", "घरेलू"]
PENALTY = [r"\bpenalt(y|ies)\b", r"\bfines?\b", r"\bfined\b", r"\bticketless\b", r"without (a )?(valid )?ticket",
           r"\bviolation", r"जुर्माना", r"जुर्माने", r"दंड", r"पेनल्टी"]
NOT_RETAIL = [r"\bwholesale\b", r"\bmandi\b", r"\bdealers?\b", r"bulk rate", r"थोक", r"मंडी", r"डीलर"]


def non_consumer_reason(item_or_service, line):
    """Amendment 1 (b) non-domestic variants, (c) penalties and fines, (d) retail only. Returns a drop reason or ''."""
    item, text = norm(item_or_service or ""), norm(line or "")
    if any(norm(w) in item for w in NON_DOMESTIC) or (
            any(norm(w) in text for w in NON_DOMESTIC) and not any(norm(w) in text for w in DOMESTIC)):
        return "not a household/domestic variant (commercial, bulk, 19 kg, 5 kg/FTL, industrial)"
    if any(re.search(p, item) or re.search(p, text) for p in PENALTY):
        return "penalty or fine, not a price paid by ordinary consumers"
    if any(re.search(p, item) or re.search(p, text) for p in NOT_RETAIL):
        return "not a retail price (wholesale, mandi, dealer or bulk rate)"
    return ""


# ---------- Amendment 3 (2026-10-21, after scoring; bug fixes that enforce scope already in frozen_rules.md) ----------
# (a) retail only: wholesale, tabela, loose and dairy-farmer-rate wording, in English, Hindi and Marathi. Checked in
#     the cited line (always drops) and in its context (the sentences before and after it and the page title: drops
#     only when the cited line itself names no retail price).
NOT_RETAIL_CONTEXT = [r"\bwholesale\b", r"\btabela\b", r"\bloose\b", r"procurement (price|rate)",
                      r"purchase (price|rate)", r"farm.?gate", r"(paid|pay|payment) to (the )?(dairy )?farmers",
                      r"farmers?'? (price|rate)", r"(price|rate)s? (paid )?to (dairy )?farmers",
                      r"थोक", r"तबेला", r"तबेले", r"खुला दूध", r"खुले दूध", r"खरीद (मूल्य|दर|भाव)",
                      r"(किसानों|पशुपालकों|दुग्ध उत्पादकों) को", r"घाऊक", r"सुटे दूध", r"सुट्या दुधा",
                      r"खरेदी दर", r"(शेतकऱ्यांना|उत्पादकांना)"]
RETAIL_WORDS = [r"\bretail\b", r"\bconsumers?\b", r"\bcustomers?\b", r"\bmrp\b", r"\bhouseholds?\b",
                r"खुदरा", r"ग्राहक", r"उपभोक्ता", r"किरकोळ", r"ग्राहकांना"]

# (b) the CPI variety: petrol and diesel are regular grades. Premium or branded grades are not (all languages).
PREMIUM_FUEL = [r"\bxp ?\d{2,3}\b", r"\bxtra (green|premium)\b", r"\bspeed( ?97)?\b", r"\bpower( ?99| ?100)?\b",
                r"\bpremium\b", r"\bbranded\b", r"\bturbojet\b", r"प्रीमियम", r"ब्रांडेड", r"ब्रँडेड"]
REGULAR_FUEL = [r"\bregular\b", r"\bnormal\b", r"\bordinary\b", r"सामान्य", r"साधारण", r"नियमित"]


def not_retail_context_reason(line, context):
    """(a): '' or a drop reason. context = neighbouring sentences + page title (not the line itself)."""
    text, ctx = norm(line or ""), norm(context or "")
    hit = lambda pats, t: any(re.search(p, t) for p in pats)          # noqa: E731
    if hit(NOT_RETAIL_CONTEXT, text):
        return "not a retail price (wholesale, tabela, loose or dairy-farmer rate)"
    if hit(NOT_RETAIL_CONTEXT, ctx) and not hit(RETAIL_WORDS, text):
        return "not a retail price (the cited line's context is a wholesale, tabela, loose or dairy-farmer rate)"
    return ""


def premium_fuel_reason(kind, item_or_service, line):
    """(b): '' or a drop reason, fuel only."""
    if kind != "fuel":
        return ""
    item, text = norm(item_or_service or ""), norm(line or "")
    if any(re.search(p, item) for p in PREMIUM_FUEL) or (
            any(re.search(p, text) for p in PREMIUM_FUEL) and not any(re.search(p, text) for p in REGULAR_FUEL)):
        return "not the CPI variety (premium or branded fuel grade, not regular petrol/diesel)"
    return ""
