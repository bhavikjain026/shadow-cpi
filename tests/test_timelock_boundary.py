"""The cutoff day and time zones, pinned: what timelocked_search sends and how a published_date at the boundary is
labelled. Fake client, no network, no credits."""
import pytest

from timelock import DATE_FLAG, LEAK, SAFE, timelocked_search
from timelock.dates import iso_date

CUT = "2026-10-06"


class Fake:
    def __init__(self, results):
        self.results, self.sent = results, []

    def search(self, query, **params):
        self.sent.append(params)
        return {"results": self.results}


def label(published):
    out = timelocked_search(Fake([{"url": "https://example.com/a", "published_date": published}]), "q", CUT)
    return out[0]["status"]


def test_end_date_sent_is_the_cutoff_itself_never_the_day_after():
    c = Fake([])
    timelocked_search(c, "q", CUT)
    assert c.sent[0]["end_date"] == CUT and c.sent[0]["filter_by_published_date"] is True


@pytest.mark.parametrize("published,expected", [
    ("2026-10-06", SAFE),                                    # the cutoff day is inside
    ("2026-10-07", LEAK),                                    # one day later is not
    ("2026-10-06T23:59:59Z", SAFE),
    ("2026-10-07T00:00:00Z", LEAK),
    ("Tue, 06 Oct 2026 23:59:59 GMT", SAFE),                 # RFC 1123, last second of the cutoff day in UTC
    ("Wed, 07 Oct 2026 00:00:00 GMT", LEAK),                 # first second of the next UTC day
    ("Wed, 07 Oct 2026 00:00:01 GMT", LEAK),
    ("Mon, 05 Oct 2026 00:00:00 GMT", SAFE),
    ("2026-10-07T01:00:00+05:30", SAFE),                     # 1 am IST on the 7th is 19:30 UTC on the 6th
    ("2026-10-07T05:30:00+05:30", LEAK),                     # = 00:00 UTC on the 7th
    ("Wed, 07 Oct 2026 01:00:00 +0530", SAFE),
    ("2026-10-06T20:00:00-08:00", LEAK),                     # = 04:00 UTC on the 7th
    ("", DATE_FLAG),
    (None, DATE_FLAG),
])
def test_published_date_is_compared_by_its_utc_date_against_the_cutoff(published, expected):
    assert label(published) == expected


def test_iso_date_gives_the_utc_calendar_date():
    assert iso_date("Tue, 06 Oct 2026 23:59:59 GMT") == "2026-10-06"
    assert iso_date("2026-10-07T01:00:00+0530") == "2026-10-06"
    assert iso_date("2026-10-06") == "2026-10-06"
    assert iso_date("not a date") == ""
