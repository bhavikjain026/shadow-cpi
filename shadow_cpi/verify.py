"""Code-side checks on what the model extracted: exact quotes, units, dates, duplicates."""
import math
import re
import unicodedata

ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍﻿­"), None)
PUNCT_MAP = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-",
                           "—": "-", "₹": "rs ", " ": " "})
MIN_QUOTE = 20


def norm(s):
    s = unicodedata.normalize("NFKC", s or "").translate(ZERO_WIDTH).translate(PUNCT_MAP)
    s = re.sub(r"[*_#>|`]", " ", s)              # markdown noise from extracted pages
    return re.sub(r"\s+", " ", s).strip().lower()


def quote_on_page(quote, page_text, min_len=MIN_QUOTE):
    """True only if a usable quote appears word-for-word on the page (first 120 normalised chars)."""
    q = norm(quote)
    if len(q) < min_len:
        return False
    return q[:120] in norm(page_text)


UNIT_FACTORS = {  # convert a price per <unit> into price per base unit
    "kg": ("kg", 1.0), "kilo": ("kg", 1.0), "kilogram": ("kg", 1.0), "किलो": ("kg", 1.0),
    "g": ("kg", 1000.0), "gram": ("kg", 1000.0), "100g": ("kg", 10.0), "250g": ("kg", 4.0), "500g": ("kg", 2.0),
    "quintal": ("kg", 0.01), "क्विंटल": ("kg", 0.01), "tonne": ("kg", 0.001), "ton": ("kg", 0.001),
    "litre": ("litre", 1.0), "liter": ("litre", 1.0), "l": ("litre", 1.0), "लीटर": ("litre", 1.0),
    "ml": ("litre", 1000.0), "500ml": ("litre", 2.0),
    "10g": ("10g", 1.0), "10 g": ("10g", 1.0), "10 gram": ("10g", 1.0), "10 grams": ("10g", 1.0),
    "dozen": ("dozen", 1.0), "piece": ("piece", 1.0), "cylinder": ("cylinder", 1.0),
}


def to_base_unit(price, unit):
    """Return (price_per_base_unit, base_unit) or (None, None) if the unit is unknown."""
    if price is None:
        return None, None
    u = norm(unit).replace("per ", "").replace("/", " ").strip()
    u = re.sub(r"^(rs\.?|inr)\s*", "", u).strip()
    if u in UNIT_FACTORS:
        base, f = UNIT_FACTORS[u]
        return float(price) * f, base
    return None, None


def in_month(date_str, month):
    """date_str 'YYYY-MM-DD' (or prefix); month 'YYYY-MM'."""
    return bool(date_str) and str(date_str)[:7] == month


def dedupe_quotes(quotes):
    """Syndicated copies count once: identical normalised quote text keeps the first occurrence."""
    seen, out = set(), []
    for q in quotes:
        k = norm(q.get("quote"))[:200]
        if k and k not in seen:
            seen.add(k)
            out.append(q)
    return out


def geometric_mean_change(pairs):
    """pairs: list of (price_now, price_before) for the SAME city/source. Returns change (e.g. 0.05 = +5%)."""
    logs = [math.log(a / b) for a, b in pairs if a and b and a > 0 and b > 0]
    if not logs:
        return None
    return math.exp(sum(logs) / len(logs)) - 1


# ---------- evidence by reference ----------
# The model never copies text. It points to a numbered line of the page; code takes that exact line.
# So every quote is word-for-word by construction, in any language (Hindi included), and tables work.
SENTENCE_END = re.compile(r"(?<=[.!?।])\s+")


def split_lines(text, max_len=400, min_len=3):
    out = []
    for raw in (text or "").splitlines():
        raw = raw.strip()
        if len(raw) < min_len:
            continue
        parts = SENTENCE_END.split(raw) if len(raw) > max_len else [raw]
        for p in parts:
            p = p.strip()
            while len(p) > max_len:
                out.append(p[:max_len])
                p = p[max_len:]
            if len(p) >= min_len:
                out.append(p)
    return out


def number_lines(lines, limit_chars=12000):
    buf, total = [], 0
    for i, l in enumerate(lines, 1):
        s = f"L{i}: {l}"
        total += len(s) + 1
        if total > limit_chars:
            break
        buf.append(s)
    return "\n".join(buf)


NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def price_in_line(price, line, tol=0.005):
    """True if the extracted price number actually appears in the cited line."""
    if price is None:
        return False
    for m in NUM.findall(line or ""):
        try:
            v = float(m.replace(",", ""))
        except ValueError:
            continue
        if v and abs(v - float(price)) <= tol * abs(float(price)) + 1e-9:
            return True
    return False


URL_DATES = [
    (re.compile(r"(20\d{2})[/-](\d{1,2})[/-](\d{1,2})(?!\d)"), ("y", "m", "d")),   # 2026/03/12, 2026-03-12
    (re.compile(r"(?<!\d)(\d{1,2})[/-](\d{1,2})[/-](20\d{2})"), ("d", "m", "y")),   # 13/03/2026 (Indian sites)
    (re.compile(r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)"), ("y", "m", "d")),          # 20260312
]


def date_from_url(url):
    """Publication date written in a page address, as 'YYYY-MM-DD', or ''."""
    for rx, order in URL_DATES:
        for m in rx.finditer(url or ""):
            parts = dict(zip(order, m.groups()))
            y, mo, d = int(parts["y"]), int(parts["m"]), int(parts["d"])
            if 1 <= mo <= 12 and 1 <= d <= 31:
                return f"{y:04d}-{mo:02d}-{d:02d}"
    return ""
