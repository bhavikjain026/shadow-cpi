"""Amendment C (v2/PREREGISTRATION.md): the event kinds, their CPI items, roles and words in every language; the
monthly query sets; preferred news domains per language; regional state and city names for geography."""
import re

from shadow_cpi import evidence as E
from shadow_cpi.event_rules import _states_in
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
ALL_WORDS = [w for k in KINDS.values() for w in k["words"]]

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


def kind_of(line):
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


SCRIPTS = {"mr": r"[ऀ-ॿ]", "hi": r"[ऀ-ॿ]", "ta": r"[஀-௿]", "te": r"[ఀ-౿]",
           "kn": r"[ಀ-೿]", "bn": r"[ঀ-৿]"}


def script_lang(text):
    return next((k for k, p in SCRIPTS.items() if re.search(p, text or "")), "en")
