"""v2 rules from v2/PREREGISTRATION.md: the cutoff, the search window, the line-by-line verifier, and Amendment A
(spine vs events; geography). Plain code, no AI. Every check returns a reason a person can read on the card."""
import calendar
import hashlib
import json
import re
from datetime import date, timedelta
from pathlib import Path

from shadow_cpi.event_rules import (CITY_STATE, _states_in, non_consumer_reason, not_retail_context_reason,
                                     premium_fuel_reason, scope, state_share)
from shadow_cpi.verify import norm, price_in_line

CUTOFF_DAY = 29
PRE_DAYS = 10            # announcements made in the last 10 days before the month

# one basket item per entry: the words that name it, the unit, the CPI item code and name (2024 series)
ITEMS = {"milk": {"words": ["milk", "दूध", "doodh", "dudh"], "units": ["litre", "liter", "ltr", "लीटर", "लिटर"],
                  "cpi_code": "01.1.4.1.1.01", "cpi_name": "Milk: liquid"}}

# Amendment A, rule 1: items whose source is the government spine or an official observed series
SPINE_CODES = {"01.1.7.4.1.01": "onion", "01.1.7.2.1.01": "tomato", "01.1.7.5.1.01": "potato",
               "01.1.7.6.1.01": "tur dal", "01.1.5.1": "edible oils", "01.1.1.2.1.01": "atta",
               "01.1.4.1.1.01": "milk", "01.1.4.8.1.01": "eggs"}
OBSERVED_CODES = {"13.2.1.1.1.01": "gold (IBJA)", "13.2.1.1.1.02": "silver (IBJA)",
                  "04.5.2.2.1.01": "LPG (IOCL list)", "07.2.2.2.1.01": "petrol (PPAC)"}
STATEWIDE = ["statewide", "state-wide", "across the state", "all over the state", "throughout the state",
             "प्रदेश भर", "प्रदेशभर", "पूरे प्रदेश", "राज्य भर", "राज्यभर", "पूरे राज्य", "संपूर्ण प्रदेश"]
NARROWER = [r"\bdistrict\b", r"\bcity\b", r"जिले", r"ज़िले", r"शहर"]
CITY_SHARES = Path(__file__).resolve().parent / "city_shares.json"


def cutoff(month):
    """Last day evidence may be published: the 29th, or the month's last day if earlier."""
    y, m = map(int, month.split("-"))
    return date(y, m, min(CUTOFF_DAY, calendar.monthrange(y, m)[1])).isoformat()


def window(month):
    """(start, end) for date-locked searches: 10 days before the month starts, to the cutoff."""
    start = date.fromisoformat(f"{month}-01") - timedelta(days=PRE_DAYS)
    return start.isoformat(), cutoff(month)


def text_hash(text):
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def check(claim, page_text, page_date, month, words, units=None, state=None, context=""):
    """claim: {'line', 'price' (number claimed), 'unit', 'region'}. Returns (True, 'verified') or (False, reason).
    In order: page date known and inside the window; a price is claimed and is in the cited line; the cited line is
    on the fetched page; the line names the item; (if given) the place is in the state; retail, not wholesale;
    (if given) the unit."""
    start, end = window(month)
    line = claim.get("line") or ""
    if not page_date:
        return False, "no publication date on the page"
    if page_date > end:
        return False, f"published {page_date}, after the cutoff {end}"
    if page_date < start:
        return False, f"published {page_date}, before the window starts ({start})"
    if not line:
        return False, "no line cited"
    if claim.get("price") is None:
        return False, "Nano gave no price for this line"
    if not price_in_line(claim.get("price"), line):
        return False, "the price is not in the cited line"
    if norm(line) not in norm(page_text):
        return False, "the cited line is not on the fetched page"
    text = norm(line)
    if not any(norm(w) in text for w in words):
        return False, "the line is not about this item"
    if state:
        places = _states_in(claim.get("region")) | _states_in(line) | _states_in(context)
        if state not in places:
            return False, f"not {state.title()}" + (f" ({', '.join(sorted(places))})" if places else "")
    why = (non_consumer_reason(claim.get("item"), line) or not_retail_context_reason(line, context)
           or premium_fuel_reason(claim.get("kind"), claim.get("item"), line))     # v1 scope rules, unchanged
    if why:
        return False, why
    if units and not any(norm(u) in norm(claim.get("unit") or "") + " " + text for u in units):
        return False, f"not a price per {units[0]}"
    return True, "verified"


def verify(claim, page_text, page_date, month, item, state, context=""):
    """The tracer's check for one basket item (ITEMS) in one state."""
    cfg = ITEMS[item]
    ok, why = check(claim, page_text, page_date, month, cfg["words"], cfg["units"], state, context)
    return ok, (f"the line is not about {item}" if why == "the line is not about this item" else why)


def change_of(claim):
    """The % change the claim states (old and new price, or a % change), as a fraction; None if not stated."""
    old, new, pct = claim.get("old_price"), claim.get("new_price"), claim.get("pct_change")
    if old and new:
        return new / old - 1
    if pct is not None:
        return pct / 100
    return None


# ---------- Amendment A ----------
def source_role(cpi_code, spine_covers=True, observed_covers=True):
    """Rule 1: ('moves', '') if events may move this item, else ('context', why)."""
    if cpi_code in SPINE_CODES and spine_covers:
        return "context", f"the government price spine is the source for {SPINE_CODES[cpi_code]}"
    if cpi_code in OBSERVED_CODES and observed_covers:
        return "context", f"the official series is the source for {OBSERVED_CODES[cpi_code]}"
    return "moves", ""


def city_shares(path=CITY_SHARES):
    return json.loads(Path(path).read_text(encoding="utf-8")).get("shares", {})


def geography(kind, line, region="", seller="", context="", cpi_code="", shares=None):
    """Rule 2. Returns (scope, weight, where, why): scope 'national' | 'state' | 'city' | 'context'.
    weight = the share of the item's all-India weight the event moves."""
    ev = {"kind": kind, "quote": line, "region": region, "seller_or_authority": seller}
    sc, states = scope(ev)
    if sc == "national":
        return "national", 1.0, "India", ""
    if sc == "unknown" or not states:
        return "context", 0.0, region or "", "no state identified"
    t, ctx = norm(line), norm(context)
    statewide = any(norm(w) in t or norm(w) in ctx for w in STATEWIDE)
    cities = [c for c in CITY_STATE if re.search(r"(?<![a-z])" + re.escape(norm(c)) + r"(?![a-z])", t)]
    narrower = cities or any(re.search(p, t) for p in NARROWER)
    if statewide or not narrower:
        return "state", state_share(cpi_code, set(states)), ", ".join(sorted(states)), ""
    shares = city_shares() if shares is None else shares
    for c in cities:
        entry = shares.get(norm(c))
        if entry:
            st = CITY_STATE[c]
            return "city", state_share(cpi_code, {st}) * entry["share"], f"{c} ({st})", ""
    return "context", 0.0, ", ".join(cities) or region or "", (
        "a city or district event with no statewide confirmation and no documented city share")
