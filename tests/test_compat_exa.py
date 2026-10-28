"""timelock/compat_exa.py: Exa-style parameters on the Tavily time lock. Saved Tavily responses only, mocked client,
no network, no key."""
import json
from pathlib import Path

import pytest

from timelock import DATE_FLAG, LEAK, SAFE, TimeLockError
from timelock.compat_exa import NOTE, UnsupportedParameterError, exa_style_search, map_params

FIX = Path(__file__).resolve().parent / "fixtures" / "timelock"
LOCKED = json.loads((FIX / "rbi_2026-10-06_locked.json").read_text(encoding="utf-8"))["response"]
UNLOCKED = json.loads((FIX / "rbi_2026-10-06_unlocked.json").read_text(encoding="utf-8"))["response"]
Q = "RBI monetary policy repo rate decision October 2026"


class Fake:
    def __init__(self, response):
        self.response, self.sent = response, []

    def search(self, query, **params):
        self.sent.append({"query": query, **params})
        return self.response


def test_maps_every_supported_parameter_onto_the_time_lock():
    c = Fake(LOCKED)
    results = exa_style_search(c, query=Q, numResults=5, includeDomains=["rbi.org.in"], excludeDomains=["x.com"],
                               startPublishedDate="2026-09-07T00:00:00.000Z", endPublishedDate="2026-10-07",
                               contents={"snapshotAsOf": "2026-10-07T00:00:00Z"})
    assert c.sent == [{"query": Q, "start_date": "2026-09-07", "end_date": "2026-10-06",
                       "filter_by_published_date": True, "max_results": 5, "include_domains": ["rbi.org.in"],
                       "exclude_domains": ["x.com"]}]
    assert results.cutoff == "2026-10-06" and results.window == ["2026-09-07", "2026-10-06"]
    assert results.counts[SAFE] == 5 and results.note == NOTE
    assert results.request_id == LOCKED["request_id"]


@pytest.mark.parametrize("snap,cutoff", [("2026-10-07", "2026-10-06"), ("2026-10-07T00:00:00Z", "2026-10-06"),
                                         ("2026-10-07T15:30:00Z", "2026-10-06"),
                                         ("2026-10-07T03:00:00+05:30", "2026-10-05"),   # 21:30 UTC on 6 Oct
                                         ("2026-10-07T12:00:00", "2026-10-06")])        # naive = UTC
def test_snapshot_becomes_the_last_whole_utc_day_before_it(snap, cutoff):
    assert map_params({"query": "q", "contents": {"snapshotAsOf": snap}})[1] == cutoff
    assert map_params({"query": "q", "contents": {"crawledBeforeDate": snap}})[1] == cutoff


def test_date_objects_and_none_values():
    from datetime import date, datetime, timezone
    c = Fake({"results": []})
    exa_style_search(c, query="q", numResults=None, includeDomains=None, startPublishedDate=date(2026, 10, 1),
                     contents={"snapshotAsOf": datetime(2026, 10, 7, tzinfo=timezone.utc)})
    assert c.sent == [{"query": "q", "start_date": "2026-10-01", "end_date": "2026-10-06",
                       "filter_by_published_date": True}]


def test_end_published_date_is_the_cutoff_when_there_is_no_snapshot():
    c = Fake({"results": []})
    exa_style_search(c, query="q", endPublishedDate="2026-10-07T00:00:00Z")
    assert (c.sent[0]["start_date"], c.sent[0]["end_date"]) == ("2026-09-07", "2026-10-06")


@pytest.mark.parametrize("params", [
    {"type": "deep"}, {"category": "news"}, {"startCrawlDate": "2026-01-01"}, {"endCrawlDate": "2026-10-01"},
    {"includeText": ["rbi"]}, {"userLocation": "IN"}, {"moderation": True}, {"num_results": 5},
    {"contents": {"snapshotAsOf": "2026-10-07", "text": True}}, {"contents": {"maxAgeHours": 0}},
    {"contents": {"livecrawl": "never"}}, {"contents": "text"},
    {"contents": {"snapshotAsOf": "2026-10-07", "crawledBeforeDate": "2026-10-07"}}])
def test_unsupported_parameters_are_refused_before_any_call(params):
    c = Fake(LOCKED)
    base = {"query": "q", "contents": {"snapshotAsOf": "2026-10-07"}}
    with pytest.raises(UnsupportedParameterError) as e:
        exa_style_search(c, **{**base, **params})
    assert c.sent == []
    name, value = next(iter(params.items()))
    if isinstance(value, dict):
        named = [f"contents.{k}" for k in value if k != "snapshotAsOf"]
        assert all(n in str(e.value).split(" (supported")[0] for n in named) or "not both" in str(e.value)
    else:
        assert name in str(e.value).split(" (supported")[0] or "contents must be" in str(e.value)


@pytest.mark.parametrize("params", [
    {"query": "q"},                                                                 # no cutoff at all
    {"query": "q", "startPublishedDate": "2026-09-01"},                             # a start is not a cutoff
    {"query": "q", "contents": {"snapshotAsOf": None}},
    {"query": "q", "contents": {"snapshotAsOf": "2026-10-07"}, "endPublishedDate": "2026-10-09"},   # end past it
    {"query": "q", "contents": {"snapshotAsOf": "2026-10-07"}, "startPublishedDate": "2026-10-08"},
    {"query": "q", "contents": {"snapshotAsOf": "7 Oct 2026"}},
    {"contents": {"snapshotAsOf": "2026-10-07"}}])                                  # no query
def test_a_cutoff_is_always_enforced(params):
    c = Fake(LOCKED)
    with pytest.raises(TimeLockError):
        exa_style_search(c, **params)
    assert c.sent == []


def test_end_published_date_after_the_snapshot_says_how_to_fix_it():
    c = Fake(LOCKED)
    with pytest.raises(TimeLockError) as e:
        exa_style_search(c, query="q", endPublishedDate="2026-10-09", contents={"snapshotAsOf": "2026-10-07"})
    assert str(e.value) == ("endPublishedDate (2026-10-09) is after the snapshot date (2026-10-07); set it on or "
                            "before 2026-10-07, or drop it.")
    assert c.sent == []
    exa_style_search(c, query="q", endPublishedDate="2026-10-07T15:00:00Z", contents={"snapshotAsOf": "2026-10-07"})
    assert c.sent[0]["end_date"] == "2026-10-06"                                    # same UTC day is on or before


def test_every_call_carries_the_window_and_the_filter():
    for params in ({"query": "q", "contents": {"snapshotAsOf": "2026-10-07"}},
                   {"query": "q", "endPublishedDate": "2026-10-07", "numResults": 3},
                   {"query": "q", "startPublishedDate": "2026-10-01", "contents": {"crawledBeforeDate": "2026-10-07"}}):
        c = Fake({"results": []})
        exa_style_search(c, **params)
        sent = c.sent[0]
        assert sent["filter_by_published_date"] is True and sent["end_date"] <= "2026-10-06"
        assert sent["start_date"] <= sent["end_date"]


def test_post_cutoff_pages_that_slip_through_are_still_labelled_leaks():
    results = exa_style_search(Fake(UNLOCKED), query=Q, contents={"snapshotAsOf": "2026-10-07"})
    assert results.counts == {SAFE: 2, DATE_FLAG: 0, LEAK: 3} and results.note == NOTE
    assert sorted(r["published_date"] for r in results if r["status"] == LEAK) == ["2026-10-07", "2026-10-07",
                                                                                   "2026-10-09"]
