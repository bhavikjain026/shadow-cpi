"""Look-ahead check for one search result: safe / date_flag / leak against a cutoff (pure code, no API call).

    from timelock import check_result
    check_result({"url": "...", "published_date": "2026-10-08"}, cutoff="2026-10-07")   # -> "leak"

Date signals: Tavily's `published_date`, a date in the address (/2026/10/08/), and an optional page date (the
page's own published/updated date, timelock.page_date). Optional Wayback captures (ISO dates).
  - leak:      any date signal is after the cutoff (and no Wayback capture shows the page before it);
  - date_flag: no date signal at all (undated pages are flagged, not rejected), or a post-cutoff date conflicts with a
               Wayback capture on or before the cutoff (the page existed then; its date may be an update);
  - safe:      every date signal is on or before the cutoff.
"""
from timelock.dates import iso_date, url_date

SAFE, DATE_FLAG, LEAK = "safe", "date_flag", "leak"


def check_result(result, cutoff, page_date=None, captures=None):
    dates = [d for d in (iso_date(result.get("published_date")), url_date(result.get("url")), page_date) if d]
    if not dates:
        return DATE_FLAG
    if any(d > cutoff for d in dates):
        return DATE_FLAG if captures and min(captures) <= cutoff else LEAK
    return SAFE


def check_results(results, cutoff, **kw):
    """{label: count} and the labelled results, for a whole Tavily response's `results` list."""
    labelled = [(r, check_result(r, cutoff, **kw)) for r in results]
    return {lab: sum(x == lab for _, x in labelled) for lab in (SAFE, DATE_FLAG, LEAK)}, labelled
