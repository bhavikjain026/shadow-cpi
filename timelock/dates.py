"""Date signals for one search result, as ISO 'YYYY-MM-DD' (standard library only)."""
import re
from datetime import date, datetime
from email.utils import parsedate_to_datetime


def iso_date(s):
    """Tavily's published_date as 'YYYY-MM-DD', or '' if missing/unreadable.
    Accepts ISO ('2026-03-24...') and the news format ('Tue, 24 Mar 2026 14:00:00 GMT')."""
    s = (s or "").strip()
    if re.match(r"\d{4}-\d{2}-\d{2}", s):
        return s[:10]
    try:
        return parsedate_to_datetime(s).date().isoformat()
    except (TypeError, ValueError, IndexError):
        return ""


def url_date(url):
    """A /YYYY/MM/DD/ (or YYYY-MM-DD) date in the address, as ISO, or None."""
    m = re.search(r"/(20\d{2})[/-](\d{1,2})[/-](\d{1,2})/", url or "")
    try:
        return date(int(m[1]), int(m[2]), int(m[3])).isoformat() if m else None
    except ValueError:
        return None


DATE_WORDS = r"(published|updated|posted|last updated|प्रकाशित|अपडेट)"
_DATES = [(r"(\d{4})-(\d{2})-(\d{2})", lambda m: date(int(m[1]), int(m[2]), int(m[3]))),
          (r"(\d{1,2})\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})", lambda m: _dmy(m[1], m[2], m[3])),
          (r"([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})", lambda m: _dmy(m[2], m[1], m[3]))]


def _dmy(d, mon, y):
    return datetime.strptime(f"{int(d)} {mon[:3].title()} {y}", "%d %b %Y").date()


def page_date(text):
    """(ISO date or None, why). Only a date right after 'published'/'updated' (or Hindi) counts; the later if both;
    two different dates for the same word, or none, = unknown."""
    found = {}
    text = text or ""
    for m in re.finditer(DATE_WORDS + r"\s*(?:on|at)?\s*:?\s*", text, re.I):
        word = "updated" if m[1].lower() in ("updated", "last updated", "अपडेट") else "published"
        after = re.split(DATE_WORDS, text[m.end():m.end() + 40], flags=re.I)[0]   # stop at the next date word
        for pat, mk in _DATES:
            d = re.search(pat, after)
            if d:
                try:
                    iso = mk(d).isoformat()
                except ValueError:                      # e.g. "May 32, 2026" or a month name we cannot read
                    break
                found.setdefault(word, set()).add(iso)
                break
    if not found:
        return None, "no explicit published/updated date"
    if any(len(v) > 1 for v in found.values()):
        return None, "ambiguous: more than one date for the same word"
    return max(next(iter(v)) for v in found.values()), "published/updated date on the page"
