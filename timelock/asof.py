"""extract_as_of: read a page as it was on a past date, or refuse (standard library only).

    from timelock import TavilyHTTP, extract_as_of
    page = extract_as_of(TavilyHTTP(), url, cutoff="2026-07-08", published_date="2026-07-07")
    page["text"], page["provenance"]      # text is None when no as-of copy exists

Search dates do not freeze page content: Tavily Extract returns the page as it is now, so a page dated before the
cutoff can carry text added after it. extract_as_of extracts the live page and checks its change evidence: Tavily's
date (when the caller passes it), the page's own published/updated date, and the Wayback Machine's capture list (CDX:
first/last capture, and whether captures after the cutoff differ from the last one on or before it). The live copy is
used only when every signal says the page has not changed since the cutoff; otherwise the latest Wayback capture on
or before the cutoff is downloaded and returned. With no such capture the result has no text and the reason
"no as-of copy": it never falls back to the live page.

Two edge cases. If Extract returns results but none is for the requested URL (compared after canonicalisation: the
scheme is ignored, so http and https match, and one trailing slash on the path is dropped), the result has no text
and the reason "url mismatch"; another page's text is never used. If no signal says the page changed but the Wayback
Machine holds no capture on or before the cutoff, nothing confirms the live copy is the cutoff's: it is returned with
the reason "unverified: no archive copy before the cutoff", and with strict=True it is refused ("no as-of copy").

Provenance: {"source": "tavily_live" | "wayback_asof" | None, "capture_time": ISO UTC or None, "reason": ...}.
"""
import hashlib
import json
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from html.parser import HTMLParser

from timelock.dates import iso_date, page_date as read_page_date

LIVE, WAYBACK = "tavily_live", "wayback_asof"
NO_COPY = "no as-of copy"
URL_MISMATCH = "url mismatch"
UNVERIFIED = "unverified: no archive copy before the cutoff"
UA = "Mozilla/5.0 (timelock as-of research)"


def text_sha256(text):
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _iso(name, value):
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError:
        raise ValueError(f"{name} must be an ISO date (YYYY-MM-DD), got {value!r}") from None


def _ts_date(ts):
    """'20260707123456' -> '2026-07-07'."""
    return f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"


def _ts_time(ts):
    """'20260707123456' -> '2026-07-07T12:34:56Z'."""
    ts = (ts + "000000")[:14]
    return f"{_ts_date(ts)}T{ts[8:10]}:{ts[10:12]}:{ts[12:14]}Z"


class _Text(HTMLParser):
    """Visible text of an archived page; links kept as [text](href) so they can be compared with Extract's output."""
    SKIP = {"script", "style", "noscript", "template", "svg"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip, self.href = [], 0, None

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag == "a":
            self.href, self.out = dict(attrs).get("href"), self.out + ["["]
        elif tag in ("p", "br", "div", "li", "h1", "h2", "h3", "h4", "tr"):
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag == "a":
            self.out.append(f"]({self.href})" if self.href else "]")
            self.href = None

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def html_text(html):
    p = _Text()
    p.feed(html or "")
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n\n", "".join(p.out))).strip()


class Wayback:
    """Wayback Machine access: capture list (CDX) and one capture's original page. A direct download, outside Tavily:
    callers that log their calls override _get (see tools/asof_demo_r196.py)."""

    CDX = "https://web.archive.org/cdx/search/cdx"

    def __init__(self, timeout=30):
        self.timeout = timeout

    def _get(self, url):
        """(final URL after redirects, body text). Raises OSError on a network or HTTP failure."""
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return r.geturl(), r.read().decode("utf-8", "replace")

    def cdx_url(self, url):
        return self.CDX + "?" + urllib.parse.urlencode({"url": url, "output": "json", "fl": "timestamp,digest",
                                                        "filter": "statuscode:200"})

    def captures(self, url):
        """[(timestamp, digest), ...] oldest to newest, or None if the lookup failed."""
        try:
            _, body = self._get(self.cdx_url(url))
            rows = json.loads(body or "[]")
        except (OSError, ValueError):
            return None
        return sorted((r[0], r[1] if len(r) > 1 else "") for r in rows[1:] if r and len(r[0]) >= 8)

    def fetch(self, url, timestamp):
        """(served timestamp, page text) for one capture, or None. The served timestamp is read from the final
        address: Wayback answers with the nearest capture, which may not be the one asked for."""
        try:
            final, body = self._get(f"https://web.archive.org/web/{timestamp}id_/{url}")
        except (OSError, ValueError):
            return None
        m = re.search(r"/web/(\d{8,14})", final or "")
        return (m[1] if m else None), html_text(body)


def canonical_url(url):
    """The address compared with Extract's result URLs: scheme dropped, one trailing slash on the path dropped."""
    p = urllib.parse.urlsplit(url or "")
    path = p.path[:-1] if p.path.endswith("/") else p.path
    return urllib.parse.urlunsplit(("", p.netloc, path, p.query, p.fragment))


def change_signals(cutoff, tavily_date, page_date, captures):
    """Reasons the page may have changed after the cutoff ([] = none). Unknown counts as a reason: the live copy is
    used only on positive evidence that it is the cutoff's copy."""
    why = []
    if tavily_date and tavily_date > cutoff:
        why.append(f"Tavily date {tavily_date} is after the cutoff")
    if page_date is None:
        why.append("the live page states no published/updated date")
    elif page_date > cutoff:
        why.append(f"page date {page_date} is after the cutoff")
    if captures is None:
        why.append("Wayback lookup failed")
    else:
        before = [d for t, d in captures if _ts_date(t) <= cutoff]
        after = {d for t, d in captures if _ts_date(t) > cutoff}
        if before and after - {before[-1]}:
            why.append("Wayback captures after the cutoff differ from the last one on or before it")
    return why


def extract_as_of(client, url, cutoff, *, published_date=None, archive=None, now=None, strict=False,
                  **extract_kwargs):
    """The page at `url` as it was on `cutoff` (ISO date), or no text. Returns a dict: url, cutoff, text (None when
    refused), provenance {source, capture_time, reason}, evidence (dates, captures, change signals), request_id and
    live_sha256 of the Extract call, text_sha256 of the text returned.

    `client` is anything with .extract(urls, **kwargs) -> dict (timelock.TavilyHTTP, tavily-python's TavilyClient).
    `published_date` is Tavily's date for the page from the search that found it, if any. `archive` defaults to a
    Wayback(); tests pass a fake. The live text is never returned when the page may have changed. `strict=True` also
    refuses the live text when no Wayback capture on or before the cutoff confirms it (reason "unverified: ...")."""
    cut = _iso("cutoff", cutoff)
    archive = archive or Wayback()
    taken = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    resp = client.extract([url], **{"extract_depth": "basic", **extract_kwargs})
    results = resp.get("results") or []
    got = next((r for r in results if canonical_url(r.get("url")) == canonical_url(url)), None)
    if results and got is None:                    # Extract answered for another address: never use its text
        return {"url": url, "cutoff": cut, "evidence": {"extract_urls": [r.get("url") for r in results]},
                "request_id": resp.get("request_id"), "live_sha256": None, "text": None, "text_sha256": None,
                "provenance": {"source": None, "capture_time": None, "reason": URL_MISMATCH}}
    live = (got or {}).get("raw_content") or ""
    pd = read_page_date(live)[0]
    captures = archive.captures(url)
    td = iso_date(published_date) or None
    signals = change_signals(cut, td, pd, captures)
    before = [t for t, _ in captures or [] if _ts_date(t) <= cut]
    evidence = {"tavily_date": td, "page_date": pd, "captures": None if captures is None else len(captures),
                "first_capture": _ts_time(captures[0][0]) if captures else None,
                "last_capture": _ts_time(captures[-1][0]) if captures else None,
                "last_capture_on_or_before_cutoff": _ts_time(before[-1]) if before else None,
                "changed": signals}
    out = {"url": url, "cutoff": cut, "evidence": evidence, "request_id": resp.get("request_id"),
           "live_sha256": text_sha256(live)}

    def done(text, source, capture_time, reason):
        return {**out, "text": text, "text_sha256": text_sha256(text) if text is not None else None,
                "provenance": {"source": source, "capture_time": capture_time, "reason": reason}}

    if not signals and not before:                 # nothing says it changed, but no archive copy confirms it
        return done(None, None, None, NO_COPY) if strict else done(live, LIVE, taken, UNVERIFIED)
    if not signals:
        return done(live, LIVE, taken, f"no sign the page changed after the cutoff (page date {pd}; "
                                       f"{len(captures)} Wayback captures, none differing after the cutoff)")
    if not before:
        return done(None, None, None, NO_COPY)
    served = archive.fetch(url, before[-1])
    if not served or not served[0] or _ts_date(served[0]) > cut or not served[1]:
        return done(None, None, None, NO_COPY)
    return done(served[1], WAYBACK, _ts_time(served[0]), "may have changed after the cutoff: " + "; ".join(signals))
