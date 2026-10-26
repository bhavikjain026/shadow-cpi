"""Amendment C (v2/PREREGISTRATION.md): the event kinds, their CPI items, roles and words in every language; the
monthly query sets; preferred news domains per language; regional state and city names for geography."""
import re
import unicodedata

from shadow_cpi import evidence as E
from shadow_cpi.event_rules import CITY_STATE, STATE_ALIASES, _states_in, state_item_weights
from shadow_cpi.verify import norm

# order matters: a claim's kind is the first kind whose words appear in its cited line
KINDS = {
    "electricity": {"cpi": "04.5.1.0.2.01", "role": "moves",
                    "words": ["electricity", "power tariff", "बिजली", "वीज", "மின்", "విద్యుత్", "ವಿದ್ಯುತ್", "বিদ্যুৎ"]},
    "milk": {"cpi": "01.1.4.1.1.01", "role": "context",
             "words": ["milk", "दूध", "பால்", "పాల", "ಹಾಲು", "ಹಾಲಿನ", "দুধ"]},
    "lpg": {"cpi": "04.5.2.2.1.01", "role": "context",
            "words": ["lpg", "cylinder", "cooking gas", "सिलेंडर", "सिलिंडर", "गॅस", "சிலிண்டர்", "సిలిండర్", "ಸಿಲಿಂಡರ್",
                      "সিলিন্ডার"]},
    "diesel": {"cpi": "07.2.2.1.1.01", "role": "moves",
               "words": ["diesel", "डीजल", "डिझेल", "டீசல்", "డీజిల్", "ಡೀಸೆಲ್", "ডিজেল"]},
    "petrol": {"cpi": "07.2.2.2.1.01", "role": "context",
               "words": ["petrol", "पेट्रोल", "பெட்ரோல்", "పెట్రోల్", "ಪೆಟ್ರೋಲ್", "পেট্রোল"]},
    "metro": {"cpi": "", "role": "context", "words": ["metro", "मेट्रो", "மெட்ரோ", "మెట్రో", "ಮೆಟ್ರೋ", "মেট্রো"]},
    "bus": {"cpi": "07.3.1.2.2.01", "role": "moves",
            "words": ["bus", "बस", "एसटी", "பேருந்து", "బస్సు", "ಬಸ್", "বাস"]},
    "rail": {"cpi": "07.3.1.1.2.01", "role": "moves",
             "words": ["rail", "railway", "train", "रेल", "रेल्वे", "ரயில்", "రైలు", "ರೈಲು", "রেল", "ট্রেন"]},
    "mobile": {"cpi": "08.3.4.0.2.01", "role": "moves",
               "words": ["mobile tariff", "prepaid", "postpaid", "recharge", "रिचार्ज"]},
}
# Amendment R2 (v2/RADAR_PREREG.md): plural and case forms of words already listed above, for whole-word matching.
# No new items or synonyms. Used by the radar only (whole=True); the substring matcher above is left as it was.
FORMS = {"bus": ["buses", "बसों", "बसें", "बसच्या"], "rail": ["trains", "railways"], "lpg": ["cylinders"],
         "electricity": ["மின்சார", "மின்சாரம்"]}
ALL_WORDS = [w for k in KINDS.values() for w in k["words"]]
WHOLE_WORDS = ALL_WORDS + [w for f in FORMS.values() for w in f]

QUERIES = [
    ("en", "electricity tariff hike per unit regulatory commission order"),
    ("en", "milk price hike per litre"),
    ("en", "bus fare hike metro fare rail fare revision"),
    ("en", "petrol diesel price hike LPG cylinder price mobile tariff hike"),
    ("hi", "बिजली की दरें बढ़ीं प्रति यूनिट"),
    ("hi", "दूध के दाम बढ़े प्रति लीटर"),
    ("hi", "बस किराया बढ़ा मेट्रो किराया रेल किराया"),
    ("hi", "पेट्रोल डीजल के दाम बढ़े एलपीजी सिलेंडर"),
    ("mr", "वीज दरवाढ दूध दरवाढ एसटी बस भाडेवाढ"),
    ("ta", "மின் கட்டண உயர்வு பால் விலை உயர்வு பேருந்து கட்டண உயர்வு"),
    ("te", "విద్యుత్ ఛార్జీల పెంపు పాల ధర పెంపు బస్సు ఛార్జీల పెంపు"),
    ("kn", "ವಿದ್ಯುತ್ ದರ ಏರಿಕೆ ಹಾಲಿನ ದರ ಏರಿಕೆ ಬಸ್ ಪ್ರಯಾಣ ದರ ಏರಿಕೆ"),
    ("bn", "বিদ্যুতের দাম বৃদ্ধি দুধের দাম বৃদ্ধি বাস ভাড়া বৃদ্ধি"),
]
DOMAINS = {
    "en": E.INDIAN_NEWS, "hi": E.HINDI_NEWS,
    "mr": ["lokmat.com", "loksatta.com", "maharashtratimes.com", "esakal.com", "tv9marathi.com", "abpmajha.com"],
    "ta": ["dinamalar.com", "dailythanthi.com", "dinamani.com", "tamil.oneindia.com", "vikatan.com",
           "puthiyathalaimurai.com"],
    "te": ["eenadu.net", "sakshi.com", "andhrajyothy.com", "tv9telugu.com", "ntnews.com"],
    "kn": ["prajavani.net", "vijaykarnataka.com", "kannadaprabha.com", "udayavani.com", "tv9kannada.com"],
    "bn": ["anandabazar.com", "bartamanpatrika.com", "eisamay.com", "sangbadpratidin.in", "tv9bangla.com"],
}
REGIONAL_PLACES = {
    "tamil nadu": ["தமிழ்நாடு", "தமிழகம்", "சென்னை", "கோவை"],
    "telangana": ["తెలంగాణ", "హైదరాబాద్"],
    "andhra pradesh": ["ఆంధ్రప్రదేశ్", "ఆంధ్ర ప్రదేశ్", "విజయవాడ", "విశాఖ"],
    "karnataka": ["ಕರ್ನಾಟಕ", "ಬೆಂಗಳೂರು", "ಮೈಸೂರು"],
    "west bengal": ["পশ্চিমবঙ্গ", "কলকাতা"],
    "maharashtra": ["महाराष्ट्र", "मुंबई", "पुणे", "नागपूर"],
}


def _word_char(ch):
    return unicodedata.category(ch)[0] in "LMN"          # letters, combining marks (matras, viramas), digits


def has_word(text, word, start_only=False):
    """Amendment R2: `word` occurs in `text` as a whole word (after norm), in any script. A word is a run of letters,
    marks and digits, so 'रेल' is not found in 'घरेलू' and 'bus' is not found in 'business'. start_only: the word
    must begin at a word boundary but may carry a suffix (regional place stems such as 'சென்னை' in 'சென்னையில்')."""
    t, w = norm(text or ""), norm(word or "")
    for m in re.finditer(re.escape(w), t) if w else ():
        a, b = m.start(), m.end()
        if (a == 0 or not _word_char(t[a - 1])) and (start_only or b == len(t) or not _word_char(t[b])):
            return True
    return False


def kind_of(line, whole=False):
    """The first kind whose words appear in the line. whole=True (the radar, Amendment R2): whole words only, with
    the listed plural and case forms (FORMS)."""
    if whole:
        return next((k for k, v in KINDS.items() if any(has_word(line, w) for w in v["words"] + FORMS.get(k, []))),
                    None)
    t = norm(line or "")
    return next((k for k, v in KINDS.items() if any(norm(w) in t for w in v["words"])), None)


def states_of(*texts):
    """v1's state lookup plus the regional-language names (Amendment C)."""
    found = set()
    for t in texts:
        found |= _states_in(t or "")
        n = norm(t or "")
        found |= {s for s, names in REGIONAL_PLACES.items() if any(norm(x) in n for x in names)}
    return found



# Amendment R2: state regulators (abbreviation and Hindi name) -> state. A page naming one names the state.
REGULATORS = {
    "jserc": "jharkhand", "berc": "bihar", "merc": "maharashtra", "tnerc": "tamil nadu", "kerc": "karnataka",
    "kserc": "kerala", "uperc": "uttar pradesh", "derc": "nct of delhi", "gerc": "gujarat", "rerc": "rajasthan",
    "herc": "haryana", "pserc": "punjab", "mperc": "madhya pradesh", "cserc": "chhattisgarh", "oerc": "odisha",
    "wberc": "west bengal", "aperc": "andhra pradesh", "tserc": "telangana", "tgerc": "telangana",
    "hperc": "himachal pradesh", "uerc": "uttarakhand", "aerc": "assam", "jkerc": "jammu and kashmir",
}
URL_STATES = {s: s.replace(" ", "-") for s in STATE_ALIASES} | {"nct of delhi": "delhi"}


def _places(text):
    """States named in one text, whole words in every script (Amendment R2); regional-language place stems
    (REGIONAL_PLACES) match at a word start, since their case endings attach to the name."""
    found = set()
    names = {s: [s] for s in {s for v in state_item_weights().values() for s in v}}
    for s, aliases in STATE_ALIASES.items():
        names.setdefault(s, []).extend(aliases)
    for city, s in CITY_STATE.items():
        names.setdefault(s, []).append(city)
    for s, ws in names.items():
        if any(has_word(text, w) for w in ws):
            found.add(s)
    found |= {s for s, ws in REGIONAL_PLACES.items() if any(has_word(text, w, start_only=True) for w in ws)}
    found |= {s for r, s in REGULATORS.items() if has_word(text, r)}
    return found


def page_states(line, context="", title="", url="", region=""):
    """Amendment R2: the claim's states come from the page (place names and regulators in the cited line, its
    context and the title), then from the source URL (a /<state>/ path segment, e.g. /state/jharkhand/bokaro/); the
    model's region field is used only when the page names no state."""
    found = set()
    for t in (line, context, title):
        found |= _places(t)
    if not found and url:
        segs = set(re.split(r"[/?#]", url.lower()))
        found = {s for s, slug in URL_STATES.items() if slug in segs}
    return found or _places(region)
