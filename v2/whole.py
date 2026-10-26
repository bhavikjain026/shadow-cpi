"""Amendment R3 (v2/RADAR_PREREG.md): radar-mode copies of the keyword rules that the radar reaches through v1
(`shadow_cpi.event_rules`: scope, places, retail/domestic, fuel grade) and v2 (`v2.rules`: geography, units), with
every keyword matched as a whole word in every script. The lists themselves are imported, not copied, and the v1 and
locked v2 functions are left as they are; only the matching differs.

Whole word: a keyword (or a pattern's match) may not start or end inside a word, where a word is a run of letters,
combining marks and digits (so 'शहर' is not found in 'दशहरा' and 'देशभर' not in 'प्रदेशभर'). Patterns that already
carry their own \\b keep the author's boundaries, made script-aware. STEMS take plural or case endings in the cached
pages ('उपभोक्ता' → 'उपभोक्ताओं', 'तेल कंपनि' → 'तेल कंपनियों', 'household' → 'households'): like the regional place
names, they must start a word but may end inside one, which still keeps 'शहर' out of 'दशहरा'."""
import re
from functools import lru_cache

from shadow_cpi import event_rules as ER
from shadow_cpi.verify import norm
from v2 import kinds as K

W = r"[^\W_]|[ऀ-ॣ०-ൿ]"          # letters/digits, and Indic letters + marks (not the dandas)
_B = rf"(?:(?<!{W})(?={W})|(?<={W})(?!{W}))"         # \b, aware of combining marks
# Chosen from the cached pages (v2/evidence/pages): entries whose start-of-word hits are their own plural or case forms.
# Left whole-word where the longer words are other words: 'commercial' (commercially), 'industrial' (industrialist),
# 'domestic' (domestically), 'liter' (literature), 'सामान्य' (सामान्यत), 'साधारण' (साधारणतः).
STEMS = {"जिल्ह", "सुट्या दुधा", "देशभर", "राज्यभर", "व्यावसायिक", "शहर", "रूट", "मेट्रो", "तेल कंपनि", "तेल कंपन्या",
         "भारतीय रेल", "दंड", "डीलर", "procurement (price|rate)", "purchase (price|rate)", "खरीद (मूल्य|दर|भाव)",
         "खरेदी दर", "ग्राहक", "उपभोक्ता", "किरकोळ", "household", "litre", "लिटर", "लीटर"}


@lru_cache(maxsize=None)
def _rx(p, stem=False):
    """A keyword or pattern from the v1/v2 lists, compiled for whole-word matching (see the module docstring)."""
    if "\\b" in p:
        return re.compile(p.replace("\\b", _B))
    return re.compile(rf"(?<!{W})(?:{p}){'' if stem else f'(?!{W})'}")


def hit(p, text):
    return bool(_rx(p, p in STEMS).search(text))


def word(w, text):
    """A plain keyword (the lists matched with `in`), whole word (start of word for STEMS)."""
    return bool(_rx(re.escape(norm(w)), w in STEMS or norm(w) in STEMS).search(text))


# ---------- shadow_cpi.event_rules, whole words ----------
def non_consumer_reason(item_or_service, line):
    item, text = norm(item_or_service or ""), norm(line or "")
    if any(word(w, item) for w in ER.NON_DOMESTIC) or (
            any(word(w, text) for w in ER.NON_DOMESTIC) and not any(word(w, text) for w in ER.DOMESTIC)):
        return "not a household/domestic variant (commercial, bulk, 19 kg, 5 kg/FTL, industrial)"
    if any(hit(p, item) or hit(p, text) for p in ER.PENALTY):
        return "penalty or fine, not a price paid by ordinary consumers"
    if any(hit(p, item) or hit(p, text) for p in ER.NOT_RETAIL):
        return "not a retail price (wholesale, mandi, dealer or bulk rate)"
    return ""


def not_retail_context_reason(line, context):
    text, ctx = norm(line or ""), norm(context or "")
    if any(hit(p, text) for p in ER.NOT_RETAIL_CONTEXT):
        return "not a retail price (wholesale, tabela, loose or dairy-farmer rate)"
    if any(hit(p, ctx) for p in ER.NOT_RETAIL_CONTEXT) and not any(hit(p, text) for p in ER.RETAIL_WORDS):
        return "not a retail price (the cited line's context is a wholesale, tabela, loose or dairy-farmer rate)"
    return ""


def premium_fuel_reason(kind, item_or_service, line):
    if kind != "fuel":
        return ""
    item, text = norm(item_or_service or ""), norm(line or "")
    if any(hit(p, item) for p in ER.PREMIUM_FUEL) or (
            any(hit(p, text) for p in ER.PREMIUM_FUEL) and not any(hit(p, text) for p in ER.REGULAR_FUEL)):
        return "not the CPI variety (premium or branded fuel grade, not regular petrol/diesel)"
    return ""


def states_in(text):
    """event_rules._states_in with whole words (state names, aliases, cities, in every script)."""
    return K._places(text or "", regulators=False, regional=False)


def scope(event):
    line = norm(event.get("quote") or "")
    seller = norm(event.get("seller_or_authority") or "")
    region = norm(event.get("region") or "")
    if any(word(w, line) for w in ER.NATIONWIDE_LINE):
        return "national", None
    if event["kind"] in ER.NATIONAL_KINDS:
        local = any(hit(p, t) for p in ER.LOCAL_MARKERS for t in (line, seller, region))
        body = any(hit(p, t) for p in ER.NATIONAL_BODIES.get(event["kind"], []) for t in (line, seller))
        if body and not local:
            return "national", None
    states = states_in(event.get("region")) or states_in(event.get("seller_or_authority")) or states_in(line)
    return ("regional", frozenset(states)) if states else ("unknown", None)


# ---------- v2.rules, whole words ----------
def price_type(line, context="", item=None):
    why = non_consumer_reason(item, line) or not_retail_context_reason(line, context)
    if not why:
        return "retail"
    return "commercial" if why.startswith("not a household") else "wholesale" if why.startswith(
        "not a retail price") else "other"


def unit_ok(units, unit, text):
    return any(word(u, norm(unit or "") + " " + text) for u in units)


def geography(kind, line, region="", seller="", context="", cpi_code="", shares=None, extra_states=None):
    """v2.rules.geography (Amendment A rule 2) with whole words."""
    from v2 import rules as R
    sc, states = scope({"kind": kind, "quote": line, "region": region, "seller_or_authority": seller})
    if sc == "national":
        return "national", 1.0, "India", ""
    states = set(states or ()) | set(extra_states or ())
    if not states:
        return "context", 0.0, region or "", "no state identified"
    t, ctx = norm(line), norm(context)
    statewide = any(word(w, t) or word(w, ctx) for w in R.STATEWIDE)
    cities = [c for c in ER.CITY_STATE if word(c, t)]
    narrower = cities or any(hit(p, t) for p in R.NARROWER)
    if statewide or not narrower:
        return "state", ER.state_share(cpi_code, set(states)), ", ".join(sorted(states)), ""
    shares = R.city_shares() if shares is None else shares
    for c in cities:
        entry = shares.get(norm(c))
        if entry:
            st = ER.CITY_STATE[c]
            return "city", ER.state_share(cpi_code, {st}) * entry["share"], f"{c} ({st})", ""
    return "context", 0.0, ", ".join(cities) or region or "", (
        "a city or district event with no statewide confirmation and no documented city share")
