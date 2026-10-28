"""timelock/asof.py: extract_as_of on fakes (no key, no network, 0 credits)."""
import ast
from datetime import datetime, timezone
from pathlib import Path

import pytest

from timelock import LIVE, NO_COPY, UNVERIFIED, URL_MISMATCH, WAYBACK, extract_as_of
from timelock.asof import Wayback, canonical_url, change_signals, html_text

ROOT = Path(__file__).resolve().parent.parent
URL = "https://news.example/tcs-q1-preview.html"
CUT = "2026-07-08"
NOW = datetime(2026, 10, 28, 3, 0, tzinfo=timezone.utc)
LIVE_CHANGED = "TCS Q1 preview. Updated: July 9, 2026. [TCS Q1FY27 results: Net profit rises](https://x/result)"
LIVE_SAME = "TCS Q1 preview. Published: July 7, 2026. Revenue seen flat."
OLD_HTML = "<html><script>x()</script><p>TCS Q1 preview.</p><p>Revenue seen <a href='/a'>flat</a>.</p></html>"


class FakeTavily:
    def __init__(self, text, answer_url=None):
        self.text, self.sent, self.answer_url = text, [], answer_url

    def extract(self, urls, **params):
        self.sent.append((urls, params))
        return {"request_id": "req-1", "results": [{"url": self.answer_url or urls[0], "raw_content": self.text}],
                "failed_results": []}


class FakeWayback(Wayback):
    """Captures and archived pages from a dict; records every address asked for."""

    def __init__(self, captures, pages=None, redirect=None):
        super().__init__()
        self.caps, self.pages, self.redirect, self.asked = captures, pages or {}, redirect, []

    def captures(self, url):
        return self.caps

    def _get(self, address):
        self.asked.append(address)
        ts = self.redirect or address.split("/web/")[1].split("id_")[0]
        if ts not in self.pages:
            raise OSError("not archived")
        return f"https://web.archive.org/web/{ts}id_/{URL}", self.pages[ts]


def test_changed_page_returns_the_wayback_copy_not_the_live_one():
    wb = FakeWayback([("20260707101500", "A"), ("20260709080000", "B")], {"20260707101500": OLD_HTML})
    out = extract_as_of(FakeTavily(LIVE_CHANGED), URL, CUT, published_date="2026-07-07", archive=wb, now=NOW)
    assert out["provenance"]["source"] == WAYBACK
    assert out["provenance"]["capture_time"] == "2026-07-07T10:15:00Z"
    assert "page date 2026-07-09 is after the cutoff" in out["provenance"]["reason"]
    assert "Net profit" not in out["text"] and "Revenue seen [flat](/a)" in out["text"]
    assert "x()" not in out["text"]
    assert out["request_id"] == "req-1" and out["live_sha256"] != out["text_sha256"]
    assert out["evidence"]["first_capture"] == "2026-07-07T10:15:00Z"
    assert out["evidence"]["last_capture"] == "2026-07-09T08:00:00Z"


def test_unchanged_page_returns_the_live_copy():
    wb = FakeWayback([("20260707101500", "A"), ("20260720000000", "A")])
    tav = FakeTavily(LIVE_SAME)
    out = extract_as_of(tav, URL, CUT, published_date="2026-07-07", archive=wb, now=NOW)
    assert out["provenance"] == {"source": LIVE, "capture_time": "2026-10-28T03:00:00Z",
                                 "reason": out["provenance"]["reason"]}
    assert out["text"] == LIVE_SAME and out["evidence"]["changed"] == []
    assert wb.asked == []                                       # no archive download needed
    assert tav.sent == [([URL], {"extract_depth": "basic"})]


def test_no_pre_cutoff_capture_refuses_and_never_falls_back_to_live():
    wb = FakeWayback([("20260709080000", "B"), ("20260822000000", "C")])
    out = extract_as_of(FakeTavily(LIVE_CHANGED), URL, CUT, archive=wb, now=NOW)
    assert out["text"] is None and out["text_sha256"] is None
    assert out["provenance"] == {"source": None, "capture_time": None, "reason": NO_COPY}
    assert "Net profit" not in repr(out)                        # the live text is nowhere in the result
    assert out["evidence"]["last_capture_on_or_before_cutoff"] is None


def test_wayback_serving_a_later_capture_is_refused():
    wb = FakeWayback([("20260707101500", "A"), ("20260709080000", "B")], {"20260709080000": "<p>later</p>"},
                     redirect="20260709080000")
    out = extract_as_of(FakeTavily(LIVE_CHANGED), URL, CUT, archive=wb, now=NOW)
    assert out["text"] is None and out["provenance"]["reason"] == NO_COPY


def test_extract_result_for_another_url_is_refused_never_used():
    """Extract answered, but for a different page: no text, reason "url mismatch", and no archive lookup made."""
    wb = FakeWayback([("20260707101500", "A")], {"20260707101500": OLD_HTML})
    out = extract_as_of(FakeTavily(LIVE_SAME, answer_url="https://news.example/other-story.html"), URL, CUT,
                        published_date="2026-07-07", archive=wb, now=NOW)
    assert out["text"] is None and out["text_sha256"] is None
    assert out["provenance"] == {"source": None, "capture_time": None, "reason": URL_MISMATCH}
    assert out["evidence"]["extract_urls"] == ["https://news.example/other-story.html"]
    assert "Revenue seen flat" not in repr(out) and wb.asked == []


@pytest.mark.parametrize("answer", ["http://news.example/tcs-q1-preview.html", URL + "/"])
def test_scheme_and_trailing_slash_still_match(answer):
    wb = FakeWayback([("20260707101500", "A"), ("20260720000000", "A")])
    out = extract_as_of(FakeTavily(LIVE_SAME, answer_url=answer), URL, CUT, published_date="2026-07-07", archive=wb,
                        now=NOW)
    assert out["provenance"]["source"] == LIVE and out["text"] == LIVE_SAME


def test_canonical_url():
    assert canonical_url("https://a.example/x/") == canonical_url("http://a.example/x") == "//a.example/x"
    assert canonical_url("https://a.example/x?q=1") != canonical_url("https://a.example/y?q=1")


@pytest.mark.parametrize("caps", [[], [("20260720000000", "A"), ("20260801000000", "A")]])
def test_no_pre_cutoff_capture_and_no_change_signal_is_unverified(caps):
    """Nothing says the page changed, but no capture on or before the cutoff confirms it: the live copy comes back
    labelled unverified; strict=True refuses it."""
    out = extract_as_of(FakeTavily(LIVE_SAME), URL, CUT, published_date="2026-07-07", archive=FakeWayback(caps),
                        now=NOW)
    assert out["evidence"]["changed"] == [] and out["evidence"]["last_capture_on_or_before_cutoff"] is None
    assert out["text"] == LIVE_SAME
    assert out["provenance"] == {"source": LIVE, "capture_time": "2026-10-28T03:00:00Z", "reason": UNVERIFIED}
    assert UNVERIFIED == "unverified: no archive copy before the cutoff"
    strict = extract_as_of(FakeTavily(LIVE_SAME), URL, CUT, published_date="2026-07-07", archive=FakeWayback(caps),
                           now=NOW, strict=True)
    assert strict["text"] is None and strict["provenance"] == {"source": None, "capture_time": None, "reason": NO_COPY}
    assert "Revenue seen flat" not in repr(strict)


def test_strict_keeps_a_confirmed_live_copy():
    wb = FakeWayback([("20260707101500", "A"), ("20260720000000", "A")])
    out = extract_as_of(FakeTavily(LIVE_SAME), URL, CUT, published_date="2026-07-07", archive=wb, now=NOW, strict=True)
    assert out["provenance"]["source"] == LIVE and out["provenance"]["reason"].startswith("no sign the page changed")


@pytest.mark.parametrize("td,pd,caps,expect", [
    ("2026-07-07", "2026-07-07", [("20260701000000", "A")], []),
    ("2026-07-10", "2026-07-07", [], ["Tavily date 2026-07-10 is after the cutoff"]),
    (None, None, [], ["the live page states no published/updated date"]),
    (None, "2026-07-07", None, ["Wayback lookup failed"]),
    (None, "2026-07-07", [("20260701000000", "A"), ("20260801000000", "B")],
     ["Wayback captures after the cutoff differ from the last one on or before it"]),
])
def test_change_signals(td, pd, caps, expect):
    assert change_signals(CUT, td, pd, caps) == expect


def test_unknown_dates_count_as_changed():
    """An undated page with no Wayback copy is refused, not served live."""
    out = extract_as_of(FakeTavily("no dates here"), URL, CUT, archive=FakeWayback([]), now=NOW)
    assert out["text"] is None and out["provenance"]["reason"] == NO_COPY


def test_cdx_parse_and_failure():
    class Cdx(Wayback):
        def __init__(self, body):
            super().__init__()
            self.body = body

        def _get(self, address):
            if self.body is None:
                raise OSError("down")
            return address, self.body

    assert Cdx('[["timestamp","digest"],["20260709080000","B"],["20260707101500","A"]]').captures(URL) == \
        [("20260707101500", "A"), ("20260709080000", "B")]
    assert Cdx(None).captures(URL) is None and Cdx("not json").captures(URL) is None
    assert "statuscode%3A200" in Cdx("[]").cdx_url(URL)


def test_html_text_keeps_links_and_drops_scripts():
    assert html_text(OLD_HTML) == "TCS Q1 preview.\nRevenue seen [flat](/a)."


def test_timelock_stays_standard_library_only():
    src = ast.parse((ROOT / "timelock" / "asof.py").read_text())
    mods = {(n.module or "").split(".")[0] for n in ast.walk(src) if isinstance(n, ast.ImportFrom)} | \
           {a.name.split(".")[0] for n in ast.walk(src) if isinstance(n, ast.Import) for a in n.names}
    assert mods <= {"hashlib", "json", "re", "urllib", "datetime", "html", "timelock"}
