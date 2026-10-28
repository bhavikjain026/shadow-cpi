"""Leak-free research trajectories: every search an agent made for a task, what the time lock said about each result,
and which results were kept as evidence, sealed with a SHA-256 "retrieval receipt" (standard library only).

    from timelock.trajectories import CachedTavily, generate
    traj = generate({"question": "RBI repo rate decision", "searches": [{"query": "RBI repo rate", "topic": "news"}]},
                    "2026-10-06", client=CachedTavily("cache"))        # replay only: 0 credits, no network
    traj["evidence"]["kept"], traj["receipt"]["sha256"]

Replay only in this version: generate() takes a CachedTavily client (or the caller's own search_fn) and has no path
that calls Tavily or the Wayback Machine. CachedTavily serves saved responses from a Recorder cache
(cache/<service>/<request hash>.json) and raises CacheMiss when a request was never saved: a replay never quietly makes
a live call or skips a step. A live run belongs behind the repository's Recorder and budget caps (shadow_cpi.budget).

A result is kept only if code's own look-ahead check (timelock.check_result) says "safe" for every date it can see:
Tavily's date, a date in the address, and the page's own date read by extract_as_of. Undated (date_flag) and
post-cutoff (leak) results are dropped with the reason. A page edited after the cutoff is kept when extract_as_of
serves a Wayback copy from on or before it; the quote then comes from that copy. Kept evidence is split: "as-of
verified" (a page copy as of the cutoff) and "not checked" (dates safe, but no as-of copy could be checked: snippet
level only). The search_fn's own labels are recorded but never trusted, and
a last check refuses to return a trajectory whose kept evidence carries any date after the cutoff.

No page text is written: each result carries a short quote (at most QUOTE_WORDS words of the snippet, else the title)
and, when a page was read, only the SHA-256 of its text.
"""
import functools
from html.parser import HTMLParser
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

from timelock.asof import URL_MISMATCH, WAYBACK, Wayback, extract_as_of
from timelock.check import DATE_FLAG, LEAK, SAFE, check_result
from timelock.dates import iso_date, page_date as read_page_date, url_date
from timelock.search import _iso, timelocked_search

FORMAT = "timelock-trajectory/1"
QUOTE_WORDS = 25
NOT_RUN = "not_run"                     # extract status when no extract_fn was given
SKIPPED = "skipped"                     # extract status for a result the search check already dropped
NO_ARCHIVE = "no cached archive lookup"                              # the CDX capture list was never saved
NO_DOWNLOAD = "archive copy found but download not cached"           # CDX saved, the capture's page was not
VERIFIED, NOT_CHECKED = "as-of verified", "not checked"
QUOTE_NOT_MATCHED = "archived copy found, quote not matched"
_AUTO = object()


class CacheMiss(LookupError):
    """A replay asked for a response that was never saved. Never caught here: a replay with a gap fails loudly."""


class AsOfNotChecked(RuntimeError):
    """require_as_of=True and a result's page could not be checked as of the cutoff."""


def request_hash(service, endpoint, body):
    """The Recorder's cache key (same formula as shadow_cpi.recorder.request_hash; timelock does not import it)."""
    blob = json.dumps({"s": service, "e": endpoint, "b": body}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class CachedTavily:
    """Replay-only Tavily client over a Recorder cache directory. .search/.extract return the saved response for
    exactly this request (include_usage added, as shadow_cpi.tavily does for every call) or raise CacheMiss."""

    def __init__(self, cache_dir):
        self.cache_dir = Path(cache_dir)
        self.retrieved_at = None                    # retrieved_at of the last response served (ISO UTC)
        self._index = None                          # multi-url /extract calls by (url, other params), built once

    def load(self, service, endpoint, body):
        path = self.cache_dir / service / f"{request_hash(service, endpoint, body)}.json"
        if not path.exists():
            what = body.get("query") or body.get("urls") or body.get("url")
            raise CacheMiss(f"no saved {service} {endpoint} response for {what!r} in {self.cache_dir}")
        saved = json.loads(path.read_text(encoding="utf-8"))
        self.retrieved_at = saved.get("retrieved_at")
        return saved["response"]

    def search(self, query, **params):
        return self.load("tavily", "/search", {"query": query, **params, "include_usage": True})

    def extract(self, urls, **params):
        """The saved response for exactly these urls; else, for one url, that page's result out of a saved call
        with the same other parameters that asked for several urls at once (the date test extracted in batches)."""
        body = {"urls": list(urls), **params, "include_usage": True}
        try:
            return self.load("tavily", "/extract", body)
        except CacheMiss:
            if len(body["urls"]) != 1:
                raise
        url, rest = body["urls"][0], {k: v for k, v in body.items() if k != "urls"}
        for path in self._batches().get((url, json.dumps(rest, sort_keys=True)), []):
            saved = json.loads(path.read_text(encoding="utf-8"))
            resp = saved["response"]
            hit = [r for r in resp.get("results") or [] if r.get("url") == url]
            if hit:
                self.retrieved_at = saved.get("retrieved_at")
                return {"results": hit[:1], "request_id": resp.get("request_id"), "batch_of": len(saved["request"]
                                                                                                 ["urls"])}
        raise CacheMiss(f"no saved tavily /extract response for {url!r} in {self.cache_dir}")

    def _batches(self):
        """{(url, other params as JSON): [cache files, earliest retrieval first]} over every saved multi-url
        /extract call; the earliest copy is the one served, so the choice does not depend on file names."""
        if self._index is not None:
            return self._index
        out, when = {}, {}
        for path in sorted((self.cache_dir / "tavily").glob("*.json")):
            saved = json.loads(path.read_text(encoding="utf-8"))
            req = saved.get("request") or {}
            if saved.get("endpoint") == "/extract" and len(req.get("urls") or []) > 1:
                rest = json.dumps({k: v for k, v in req.items() if k != "urls"}, sort_keys=True)
                when[path] = saved.get("retrieved_at") or ""
                for u in req["urls"]:
                    out.setdefault((u, rest), []).append(path)
        self._index = {k: sorted(v, key=lambda p: (when[p], p.name)) for k, v in out.items()}
        return self._index


class CachedWayback(Wayback):
    """Wayback lookups from the same cache (service 'direct', as tools/asof_demo_r196.py records them). Never fetches.
    A lookup that was never saved is remembered in `missed` with its kind: the capture list (CDX) or one capture's
    download. The page is then marked "not checked (...)" with that kind: a gap in the archive cache is never shown
    as a page with no archive copy. `last_html` keeps the last capture's HTML for the quote check."""

    def __init__(self, cache):
        super().__init__()
        self.cache, self.missed, self.last_html = cache, [], None

    def _get(self, url):
        kind = NO_ARCHIVE if url.startswith(self.CDX) else NO_DOWNLOAD
        try:
            resp = self.cache.load("direct", "GET", {"url": url})
        except CacheMiss:
            self.missed.append(kind)
            raise OSError(f"Wayback {kind}: {url}") from None
        if "final_url" not in resp:                 # saved by another tool in another shape: not usable here
            self.missed.append(kind)
            raise OSError(f"cached Wayback response has no final_url: {url}")
        if kind == NO_DOWNLOAD:
            self.last_html = resp["text"]
        return resp["final_url"], resp["text"]


def cached_extract_fn(cache):
    """extract_fn for replay: the saved Tavily Extract response, cached Wayback lookups, strict as-of rules, and the
    saved response's own retrieval time as 'now', so the same cache always gives the same trajectory. Adds
    'not_checked' (which archive entry was missing) when one was not in the cache, and 'archived_html' (used for the
    quote check, never stored) when a Wayback copy was served."""
    archive = CachedWayback(cache)

    def fn(url, cutoff, published_date=None):
        cache.extract([url], extract_depth="basic")             # CacheMiss here if the page was never extracted
        now = datetime.fromisoformat(cache.retrieved_at) if cache.retrieved_at else None
        archive.missed, archive.last_html = [], None
        page = extract_as_of(cache, url, cutoff, published_date=published_date, archive=archive, now=now,
                             strict=True)
        if archive.missed:
            return {**page, "not_checked": NO_ARCHIVE if NO_ARCHIVE in archive.missed else NO_DOWNLOAD}
        return {**page, "archived_html": archive.last_html} if page["provenance"]["source"] == WAYBACK else page
    return fn


def clip(text, n=QUOTE_WORDS):
    words = (text or "").split()
    return " ".join(words[:n]) + ("…" if len(words) > n else "")


def short_quote(result):
    """(quote, 'snippet' | 'title'): the first sentence of Tavily's snippet, else the title; at most QUOTE_WORDS."""
    first = next((s for s in re.split(r"(?<=[.!?।])\s+|\n+", result.get("content") or "") if s.strip()), "")
    return (clip(first), "snippet") if first else (clip(result.get("title")), "title")


def receipt_sha256(trajectory):
    """SHA-256 of the trajectory without its 'receipt' field: JSON, sorted keys, no spaces, UTF-8."""
    body = {k: v for k, v in trajectory.items() if k != "receipt"}
    blob = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def verify_receipt(trajectory):
    return trajectory.get("receipt", {}).get("sha256") == receipt_sha256(trajectory)


def _task(task):
    """{'question', 'searches': [{'query', **tavily params}]}; a plain string is one search for that string."""
    if isinstance(task, str):
        return {"question": task, "searches": [{"query": task}]}
    searches = task.get("searches") or [{"query": task["question"]}]
    return {**task, "searches": [dict(s) for s in searches]}


def _extract_record(page):
    prov = page.get("provenance") or {}
    ev = page.get("evidence") or {}
    source = prov.get("source")
    if source:
        as_of = f"{VERIFIED} ({source})"
    elif page.get("not_checked"):
        as_of = f"{NOT_CHECKED} ({page['not_checked']})"
    elif prov.get("reason") == URL_MISMATCH:
        as_of = f"{NOT_CHECKED} (Extract returned another address)"
    elif ev.get("captures") is None:
        as_of = f"{NOT_CHECKED} (Wayback lookup failed)"
    else:
        as_of = f"refused: {prov.get('reason')}"              # archive checked: no copy on or before the cutoff
    return {"status": source or "refused", "as_of": as_of, "reason": prov.get("reason"),
            "capture_time": prov.get("capture_time"), "live_page_date": ev.get("page_date"),
            "change_signals": ev.get("changed"), "request_id": page.get("request_id"),
            "text_sha256": page.get("text_sha256")}


class _MainText(HTMLParser):
    """An archived page's main text: nav, header, footer, aside, forms and scripts dropped; links reduced to their
    text (no addresses)."""
    SKIP = {"script", "style", "noscript", "template", "svg", "nav", "header", "footer", "aside", "form", "button"}
    BLOCK = {"p", "br", "div", "li", "h1", "h2", "h3", "h4", "tr", "section", "article"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def main_text(html=None, text=None):
    """Main text of an archived page: from its HTML when we have it, else from extract_as_of's text with link
    addresses removed ([text](href) -> text; nav cannot be told apart there)."""
    if html is not None:
        p = _MainText()
        p.feed(html)
        raw = "".join(p.out)
    else:
        raw = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text or "")
    return "\n".join(" ".join(line.split()) for line in raw.splitlines() if line.strip())


def _norm(s):
    return " ".join((s or "").replace("…", " ").split())


def quote_in(quote, main):
    """True if the stored quote (its "…" dropped) appears word for word in the main text."""
    q = _norm(quote)
    return bool(q) and q in _norm(main)


def _as_of_quote(main, snippet_quote):
    """A quote for an archived copy, from its main text only: the snippet's own quote if the copy contains it word for
    word; else the copy's sentence sharing the most words with it, if that covers at least half of them. None if
    neither, or if the chosen quote is not found word for word in the main text."""
    if quote_in(snippet_quote, main):
        return snippet_quote
    want = set(re.findall(r"\w+", snippet_quote.lower()))
    best, score = None, 0
    for s in re.split(r"(?<=[.!?।])\s+|\n+", main or ""):
        n = len(want & set(re.findall(r"\w+", s.lower())))
        if n > score:
            best, score = s, n
    if not best or score * 2 < len(want):
        return None
    quote = clip(best)
    return quote if quote_in(quote, main) else None


def _decide(verdict, extract):
    if verdict == LEAK:
        return "dropped", "leak: a date after the cutoff"
    if verdict == DATE_FLAG:
        return "dropped", "date_flag: no date we can check"
    if extract["as_of"].startswith("refused"):
        return "dropped", f"dates safe, but the page may have changed and no copy as of the cutoff exists ({extract['reason']})"
    if extract["as_of"].startswith(VERIFIED):
        return "kept", f"safe by every date; page read as of the cutoff ({extract['status']})"
    return "kept", f"safe by every date; {extract['as_of']}: snippet-level evidence only"


def _dates(row):
    return [d for d in (row["published_date"], row["url_date"], row["page_date"]) if d]


def generate(task, cutoff, search_fn=None, extract_fn=_AUTO, *, client=None, require_as_of=False):
    """One trajectory (a JSON-ready dict) for `task` under `cutoff` (ISO date). Replay only in this version.

    task: a question string, or {'question': ..., 'searches': [{'query': ..., **tavily params}, ...]}.
    client: a CachedTavily. search_fn(query, cutoff, **params) -> list of Tavily results with 'request_id' /
      'response_sha256' (a timelock.Results); defaults to timelocked_search on `client`. A caller's own search_fn is
      the caller's to log; its labels are recorded but never trusted.
    extract_fn(url, cutoff, published_date) -> an extract_as_of dict, run only on results the search check called
      safe; defaults to cached_extract_fn(client); None = pages not read (every kept result "not checked").
    require_as_of: raise AsOfNotChecked if any result that passed the date check could not be checked as of the
      cutoff. Off by default: such results are kept under "not checked".
    Raises CacheMiss (replay gap) and TimeLockError (a search tried to leave the window) without catching them."""
    cut = _iso("cutoff", cutoff)
    task = _task(task)
    if client is not None and not isinstance(client, CachedTavily):
        raise TypeError("replay only in this version: client must be a CachedTavily (no live calls from here)")
    if search_fn is None:
        if client is None:
            raise ValueError("replay only: pass client=CachedTavily(cache_dir) or your own search_fn")
        search_fn = functools.partial(timelocked_search, client)
    if extract_fn is _AUTO:
        extract_fn = cached_extract_fn(client) if client is not None else None
    mode = "replay" if client is not None else "custom"

    searches, rows = [], []
    for step, spec in enumerate(task["searches"], 1):
        params = {k: v for k, v in spec.items() if k != "query"}
        res = search_fn(spec["query"], cut, **params)
        searches.append({"step": step, "query": spec["query"], "params": params,
                         "window": getattr(res, "window", None),
                         "request_id": getattr(res, "request_id", None) or (res[0].get("request_id") if res else None),
                         "response_sha256": (getattr(res, "response_sha256", None) or
                                             (res[0].get("response_sha256") if res else None)),
                         "n_results": len(res)})
        for rank, r in enumerate(res, 1):
            pub = iso_date(r.get("published_date")) or None
            dated = {**r, "published_date": pub}
            first = check_result(dated, cut, page_date=r.get("page_date"))
            q, qfrom = short_quote(r)
            if first != SAFE:
                extract = {"status": SKIPPED, "as_of": "skipped (dropped by the date check)"}
                page_date = r.get("page_date")
            elif extract_fn is None:
                extract = {"status": NOT_RUN, "as_of": f"{NOT_CHECKED} (page not read)"}
                page_date = r.get("page_date")
            else:
                page = extract_fn(r.get("url"), cut, pub)
                extract = _extract_record(page)
                if extract["status"] == WAYBACK:
                    # the archived copy is the evidence: its own date counts, the later live edit does not; it is
                    # as-of verified only if the stored quote is found word for word in the copy's main text
                    page_date = read_page_date(page.get("text"))[0]
                    aq = _as_of_quote(main_text(page.get("archived_html"), page.get("text")), q)
                    if aq:
                        q, qfrom = aq, "as_of_copy"
                    else:                       # the snippet may be the later text: no quote enters evidence
                        extract["as_of"] = QUOTE_NOT_MATCHED
                        q, qfrom = None, "withheld: not found in the as-of copy"
                else:
                    page_date = r.get("page_date") or extract["live_page_date"]
            verdict = check_result(dated, cut, page_date=page_date)
            decision, why = _decide(verdict, extract)
            rows.append({"step": step, "rank": rank, "url": r.get("url"), "title": clip(r.get("title")),
                         "published_date": pub, "url_date": url_date(r.get("url")), "page_date": page_date,
                         "search_label": r.get("status"), "verdict": verdict, "as_of": extract["as_of"],
                         "extract": extract, "decision": decision, "reason": why, "quote": q, "quote_from": qfrom})

    leaked = [r["url"] for r in rows if r["decision"] == "kept" and any(d > cut for d in _dates(r))]
    if leaked:                                     # cannot happen through _decide; refuse rather than emit it
        raise AssertionError(f"kept evidence dated after the cutoff {cut}: {leaked}")
    unchecked = [r["url"] for r in rows if r["decision"] == "kept" and not r["as_of"].startswith(VERIFIED)]
    if require_as_of and unchecked:
        raise AsOfNotChecked(f"{len(unchecked)} kept result(s) not checked as of {cut}: {unchecked}")

    def item(r):
        return {"step": r["step"], "rank": r["rank"], "url": r["url"], "quote": r["quote"],
                "quote_from": r["quote_from"], "dates": sorted(set(_dates(r))), "as_of": r["as_of"], "why": r["reason"]}
    kept = [r for r in rows if r["decision"] == "kept"]
    verified = [item(r) for r in kept if r["as_of"].startswith(VERIFIED)]
    not_checked = [item(r) for r in kept if not r["as_of"].startswith(VERIFIED)]
    dropped = [{"step": r["step"], "rank": r["rank"], "url": r["url"], "why": r["reason"]}
               for r in rows if r["decision"] == "dropped"]
    traj = {"format": FORMAT, "mode": mode, "require_as_of": require_as_of,
            "task": {k: v for k, v in task.items() if k != "searches"}, "cutoff": cut,
            "searches": searches, "results": rows,
            "evidence": {"kept_as_of_verified": verified, "kept_not_checked": not_checked, "dropped": dropped},
            "counts": {"results": len(rows), "kept": len(kept), "kept_as_of_verified": len(verified),
                       "kept_not_checked": len(not_checked), "dropped": len(dropped),
                       **{lab: sum(r["verdict"] == lab for r in rows) for lab in (SAFE, DATE_FLAG, LEAK)}}}
    traj["receipt"] = {"algorithm": "sha256", "over": "the trajectory without 'receipt', JSON sorted keys, no spaces",
                       "sha256": receipt_sha256(traj)}
    return traj


def dumps(trajectory):
    return json.dumps(trajectory, ensure_ascii=False, sort_keys=True, indent=1) + "\n"
