"""v2 Amendment D: the page's printed date (after the cutoff, or edited after its date), price types and context
cards. Offline: fake Tavily and Nemotron objects, no calls."""
import pytest

from v2 import ledger as LG
from v2 import pipeline as PL
from v2 import rules as R

LINE = "Electricity tariff raised by 6.83% from September 1 in Jammu and Kashmir"


def test_printed_date_reads_stamps_not_effective_dates():
    page = ("Updated: Oct 20, 2026, 10:30 IST\nRates apply from 1 September 2026 to 31 March 2027.\n"
            "Published on 24 August 2026")
    assert R.printed_date(page) == "2026-10-20"
    assert R.printed_date("अपडेट: 25 अगस्त 2026\nदाम बढ़े") == "2026-08-25"
    assert R.printed_date("Posted 2026-08-24 09:15") == "2026-08-24"
    assert R.printed_date("effective from 1 September 2026; valid till 31 March 2027") is None


@pytest.mark.parametrize("page, tavily, flag", [
    ("Updated: Oct 20, 2026, 10:30 IST\n" + LINE, "2026-08-24", "after cutoff"),
    ("Published: Aug 24, 2026 | Updated: Aug 31, 2026, 11:00\n" + LINE, "2026-08-24", "edited after its date"),
    ("Published: Aug 24, 2026 | Updated: Aug 26, 2026, 11:00\n" + LINE, "2026-08-24", ""),     # within 2 days
    (LINE, "2026-08-24", ""),                                                                     # no printed date
])
def test_page_date_check(page, tavily, flag):
    ok, why, _, got = R.page_date_check(page, "2026-09", tavily)
    assert got == flag and ok == (flag == "")


def test_price_types():
    assert R.price_type("Wholesale rate for buffalo milk raised to Rs 102 per litre") == "wholesale"
    assert R.price_type("19 kg commercial LPG cylinder up Rs 50") == "commercial"
    assert R.price_type("Fine of Rs 500 for ticketless travel") == "other"
    assert R.price_type("Milk up Rs 2 per litre") == "retail"


class FakeTav:
    def __init__(self, pages):
        self.pages = pages

    def extract(self, urls, **kw):
        return {"results": [{"url": u, "raw_content": self.pages[u]} for u in urls]}, "eid"


class FakeNem:
    def price_events(self, model, text, **kw):
        raise AssertionError("no Super re-read expected: every claim has a number")

    def chat_json(self, *a, **kw):
        return {"english": ""}, "g"


def card(url, line, price, published="2026-08-24", tavily="2026-08-24", **claim):
    return {"url": url, "domain": "x.in", "title": "t", "lang": "en", "published": published, "search_call": "s",
            "tavily_published": tavily, "status": "rejected", "reason": "",
            "claims": [{"line": line, "price": price, "pct_change": price, "effective_date": "2026-09-01",
                        "read_by": "nano", **claim}]}


def run(tmp_path, monkeypatch, pages, cards):
    monkeypatch.setattr(LG, "PAGES", tmp_path / "pages")
    monkeypatch.setattr(LG.save_page, "__defaults__", (tmp_path / "pages",))
    PL.fetch_and_verify(FakeTav(pages), FakeNem(), "nano", cards, "2026-09", ["electricity", "milk", "lpg"], None,
                        None, "", "t", super_model="super")
    return cards


def test_page_edited_after_its_date_is_rejected_and_flagged(tmp_path, monkeypatch):
    edited = "Published: Aug 24, 2026 | Updated: Aug 31, 2026, 11:00\n" + LINE
    c = run(tmp_path, monkeypatch, {"u1": edited}, [card("u1", LINE, 6.83)])[0]
    assert c["date_flag"] == "edited after its date" and c["claims"][0]["status"] == "rejected"
    assert "edited after its date" in c["reason"]


def test_page_after_cutoff_is_rejected(tmp_path, monkeypatch):
    late = "Updated: Oct 20, 2026, 10:30 IST\n" + LINE
    c = run(tmp_path, monkeypatch, {"u2": late}, [card("u2", LINE, 6.83)])[0]
    assert c["date_flag"] == "after cutoff" and c["claims"][0]["status"] == "rejected"


def test_wholesale_is_kept_as_context_never_verified(tmp_path, monkeypatch):
    line = "The wholesale rate of milk rises 9.7% from September 1"
    c = run(tmp_path, monkeypatch, {"u3": "Published: Aug 28, 2026, 09:00\n" + line},
            [card("u3", line, 9.7, published="2026-08-28", tavily="2026-08-28")])[0]
    cl = c["claims"][0]
    assert cl["status"] == "context" and cl["price_type"] == "wholesale" and c["status"] == "context"
    assert "never in the number" in cl["reason"]


def test_retail_claim_on_a_good_page_is_verified(tmp_path, monkeypatch):
    c = run(tmp_path, monkeypatch, {"u4": "Published: Aug 24, 2026, 09:00\n" + LINE}, [card("u4", LINE, 6.83)])[0]
    assert c["claims"][0]["status"] == "verified" and c["claims"][0]["price_type"] == "retail"
    assert c["printed_date"] == "2026-08-24" and c["date_flag"] == ""
