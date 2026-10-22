"""Tavily client: the ONLY way outside-world web data enters Shadow CPI.

Every call asks Tavily for its credit usage (include_usage=true), is cached, and is written
to the Flight Recorder. Extract always reports failed_results (Tavily returns them even on HTTP 200).
"""
import re
import time
import urllib.request
from email.utils import parsedate_to_datetime

from .http import ApiError, request_json
from .recorder import Recorder
from .settings import TAVILY_BASE, tavily_key


class Tavily:
    def __init__(self, api_key=None, recorder=None, base=TAVILY_BASE, transport=request_json):
        self.api_key = api_key or tavily_key()
        self.rec = recorder or Recorder()
        self.base = base.rstrip("/")
        self.transport = transport

    def _post(self, endpoint, body, parent=None, tag=None, timeout=120):
        body = {**body, "include_usage": True}
        return self.rec.call("tavily", endpoint, body,
                             lambda: self.transport("POST", self.base + endpoint, self.api_key, body, timeout),
                             parent=parent, tag=tag)

    def search(self, query, *, parent=None, tag=None, **params):
        """Common params: topic ('general'|'news'|'finance'), search_depth ('basic'|'advanced'|'fast'),
        max_results, start_date/end_date (YYYY-MM-DD), filter_by_published_date, language,
        filter_by_language, country (general topic only), include_domains, include_domains_mode
        ('restrict'|'prefer'), exclude_domains, exact_match, chunks_per_source, include_raw_content."""
        if not params.get("auto_parameters"):          # with auto_parameters Tavily chooses the depth
            params.setdefault("search_depth", "basic")
        return self._post("/search", {"query": query, **params}, parent, tag)

    def extract(self, urls, *, parent=None, tag=None, **params):
        """params: extract_depth ('basic'|'advanced' - advanced reads tables/JS pages), query,
        chunks_per_source (1-5, needs query), format ('markdown'|'text'), timeout."""
        urls = list(urls)[:20]
        resp, cid = self._post("/extract", {"urls": urls, **params}, parent, tag, timeout=90)
        resp.setdefault("results", [])
        resp.setdefault("failed_results", [])
        return resp, cid

    def extract_or_download(self, url, *, parent=None, tag=None, **params):
        """Tavily Extract first; if Tavily can't fetch the page (some .nic.in sites block it), download it
        directly as a LOGGED fallback (same cache + Flight Recorder, service 'direct').
        Returns (text, route) where route is 'tavily', 'direct' or None (both failed)."""
        try:
            resp, cid = self.extract([url], parent=parent, tag=tag, **params)
            text = (resp["results"][0].get("raw_content") or "") if resp["results"] else ""
            if text:
                return text, "tavily"
            parent = cid
        except ApiError:
            pass

        def download():
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (ShadowCPI research)"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return {"url": url, "raw_content": r.read().decode("utf-8", "replace")}

        try:
            resp, _ = self.rec.call("direct", "GET", {"url": url}, download, parent=parent, tag=tag)
        except OSError:  # covers network, HTTP and timeout errors from urllib
            return "", None
        return resp.get("raw_content") or "", "direct"

    def usage(self, tag="usage"):
        """GET /usage: the account's credit balance (free). Never served from the cache: a balance must be fresh."""
        rec = Recorder(self.rec.cache_dir, self.rec.log_file, use_cache=False)
        resp, _ = rec.call("tavily", "/usage", {"at": time.time()},
                           lambda: self.transport("GET", self.base + "/usage", self.api_key, None, 30), tag=tag)
        return resp

    def map(self, url, *, parent=None, tag=None, **params):
        """params: instructions, max_depth, max_breadth, limit, select_paths, select_domains,
        exclude_paths, allow_external (set False on government sites)."""
        params.setdefault("allow_external", False)
        return self._post("/map", {"url": url, **params}, parent, tag, timeout=160)

    def crawl(self, url, *, parent=None, tag=None, **params):
        params.setdefault("allow_external", False)
        params.setdefault("max_depth", 1)
        return self._post("/crawl", {"url": url, **params}, parent, tag, timeout=160)


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


def best_date(result):
    """(date, source). Prefer the date written in the page address; Tavily's published_date is only a
    best estimate (we have seen many different articles stamped with the same placeholder time)."""
    from .verify import date_from_url
    d = date_from_url(result.get("url", ""))
    if d:
        return d, "url"
    d = iso_date(result.get("published_date"))
    return (d, "tavily") if d else ("", "none")


def results_in_window(results, start, end):
    """Split search results into (inside, outside, undated) using best_date()
    (page-address date first, then Tavily's best-estimate published_date)."""
    inside, outside, undated = [], [], []
    for r in results:
        d, _src = best_date(r)
        if not d:
            undated.append(r)
        elif start <= d <= end:
            inside.append(r)
        else:
            outside.append(r)
    return inside, outside, undated
