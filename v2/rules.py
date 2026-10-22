"""v2 rules from v2/PREREGISTRATION.md: the cutoff, the search window, and the line-by-line verifier.
Plain code, no AI. Every check returns a reason a person can read on the evidence card."""
import calendar
import hashlib
from datetime import date, timedelta

from shadow_cpi.event_rules import _states_in, not_retail_context_reason
from shadow_cpi.verify import norm, price_in_line

CUTOFF_DAY = 29
PRE_DAYS = 10            # announcements made in the last 10 days before the month

# one basket item per entry: the words that name it, the unit, the CPI item code and name (2024 series)
ITEMS = {"milk": {"words": ["milk", "दूध", "doodh", "dudh"], "units": ["litre", "liter", "ltr", "लीटर", "लिटर"],
                  "cpi_code": "01.1.4.1.1.01", "cpi_name": "Milk: liquid"}}


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


def verify(claim, page_text, page_date, month, item, state, context=""):
    """claim: {'line', 'price' (number claimed), 'unit', 'region'}. Returns (True, 'verified') or (False, reason).
    Checks, in order: page date known and inside the window; the price is in the cited line; the cited line is on
    the fetched page; the line names the item; the place is in the state; retail, not wholesale; per-unit."""
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
    cfg = ITEMS[item]
    text = norm(line)
    if not any(norm(w) in text for w in cfg["words"]):
        return False, f"the line is not about {item}"
    places = _states_in(claim.get("region")) | _states_in(line) | _states_in(context)
    if state not in places:
        return False, f"not {state.title()}" + (f" ({', '.join(sorted(places))})" if places else "")
    why = not_retail_context_reason(line, context)
    if why:
        return False, why
    unit = norm(claim.get("unit") or "") + " " + text
    if not any(norm(u) in unit for u in cfg["units"]):
        return False, "not a price per litre"
    return True, "verified"


def change_of(claim):
    """The % change the claim states (old and new price, or a % change), as a fraction; None if not stated."""
    old, new, pct = claim.get("old_price"), claim.get("new_price"), claim.get("pct_change")
    if old and new:
        return new / old - 1
    if pct is not None:
        return pct / 100
    return None

