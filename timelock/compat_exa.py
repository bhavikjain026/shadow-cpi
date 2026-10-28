"""exa_style_search: run code written against Exa's /search point-in-time parameters on the Tavily time lock.

Parameter names checked on 2026-10-28 against Exa's official /search reference, https://exa.ai/docs/reference/search
(docs.exa.ai/reference/search redirects there). Only these are mapped; every other parameter is refused:

    query                     -> query
    contents.snapshotAsOf     -> cutoff ("newest stored version of each page as of this instant"; ISO date-time
                                 or date-only = midnight UTC)
    contents.crawledBeforeDate-> cutoff (documented as a deprecated alias of snapshotAsOf)
    startPublishedDate        -> start_date ("published date after this")
    endPublishedDate          -> end_date ("published date before this"); the cutoff when there is no snapshotAsOf
    includeDomains            -> include_domains
    excludeDomains            -> exclude_domains
    numResults                -> max_results

Strict mode: Tavily filters by whole days and its end_date is a day, so an Exa instant (exclusive) becomes the
UTC day before it: snapshotAsOf 2026-10-07 (midnight UTC) -> cutoff 2026-10-06, and so does 2026-10-07T15:00Z,
since Tavily cannot tell that afternoon's pages from the evening's. startPublishedDate keeps its own UTC day
(widening the start by part of a day reaches no later page). The window always goes through timelocked_search, so
start_date/end_date and filter_by_published_date=true are always sent and the date check labels every result.
"""
from datetime import date, datetime, timedelta, timezone

from timelock.search import TimeLockError, timelocked_search

NOTE = "date-filtered by stated dates; not a historical snapshot of page content; use extract_as_of for content."
TOP_LEVEL = {"query": "query", "startPublishedDate": "start_date", "endPublishedDate": "end_date",
             "includeDomains": "include_domains", "excludeDomains": "exclude_domains", "numResults": "max_results"}
SNAPSHOT = ("snapshotAsOf", "crawledBeforeDate")            # the only `contents` keys accepted


class UnsupportedParameterError(TimeLockError):
    """An Exa-style parameter the adapter does not map. Refused, never dropped."""


def _utc_day(name, value):
    """The UTC calendar day of an ISO 8601 date or date-time (a trailing Z is read as UTC, a naive time as UTC)."""
    text = str(value).strip()
    try:
        if "T" not in text:
            return date.fromisoformat(text), False
        dt = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text)
    except ValueError:
        raise TimeLockError(f"{name} must be an ISO 8601 date or date-time, got {value!r}") from None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
    return dt.date(), True


def _before(name, value):
    """Last whole UTC day strictly before an exclusive Exa instant."""
    return (_utc_day(name, value)[0] - timedelta(days=1)).isoformat()


def map_params(params):
    """(query, cutoff, tavily_kwargs) from Exa-style parameters. Raises before any call."""
    params = dict(params)
    contents = params.pop("contents", None) or {}
    if not isinstance(contents, dict):
        raise UnsupportedParameterError(f"contents must be an object, got {type(contents).__name__}")
    bad = sorted(k for k in params if k not in TOP_LEVEL) + sorted(f"contents.{k}" for k in contents
                                                                    if k not in SNAPSHOT)
    if bad:
        raise UnsupportedParameterError(
            f"not supported by the Tavily time lock adapter: {', '.join(bad)} (supported: {', '.join(TOP_LEVEL)}, "
            f"contents.snapshotAsOf, contents.crawledBeforeDate)")
    if len([k for k in SNAPSHOT if contents.get(k) is not None]) > 1:
        raise UnsupportedParameterError("pass contents.snapshotAsOf or contents.crawledBeforeDate, not both")
    if not params.get("query"):
        raise TimeLockError("query is required")
    snap = next((contents[k] for k in SNAPSHOT if contents.get(k) is not None), None)
    kw = {TOP_LEVEL[k]: v for k, v in params.items() if k not in ("query", "startPublishedDate", "endPublishedDate")}
    if params.get("startPublishedDate") is not None:
        kw["start_date"] = _utc_day("startPublishedDate", params["startPublishedDate"])[0].isoformat()
    end = params.get("endPublishedDate")
    if end is not None:
        kw["end_date"] = _before("endPublishedDate", end)
    if snap is not None:
        cutoff = _before("contents.snapshotAsOf", snap)
    elif end is not None:
        cutoff = kw["end_date"]
    else:
        raise TimeLockError("no cutoff: pass contents.snapshotAsOf (or endPublishedDate); the time lock never "
                            "searches without one")
    return params["query"], cutoff, kw


def exa_style_search(client, **params):
    """timelocked_search driven by Exa-style /search parameters (see the module docstring for the mapping).

    `client` is any timelocked_search client (TavilyHTTP, Replay, tavily-python's TavilyClient). Returns the time
    lock's Results, with `.note` (NOTE) and `.exa_params` (what was passed). Unsupported parameters raise
    UnsupportedParameterError; a missing cutoff, or an endPublishedDate after the snapshot, raises TimeLockError."""
    query, cutoff, kw = map_params(params)
    results = timelocked_search(client, query, cutoff, **kw)
    results.note, results.exa_params = NOTE, params
    return results
