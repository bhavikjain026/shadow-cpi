"""v2 issue 1: the cutoff, the line-by-line verifier and the evidence ledger (offline, no calls)."""
import json

import pytest

from v2 import ledger as LG
from v2 import rules as R

PAGE = ("# इंदौर में दूध के दाम बढ़े\n"
        "नए वित्तीय वर्ष यानी 1 अप्रैल से इंदौर सहित मध्य प्रदेश के कई शहरों में दूध के दामों में बढ़ोतरी होगी।\n"
        "इंदौर में दूध अब 63 रुपये प्रति लीटर के भाव पर मिलेगा।\n")
LINE = "इंदौर में दूध अब 63 रुपये प्रति लीटर के भाव पर मिलेगा।"


def claim(**kw):
    return {"line": LINE, "price": 63, "unit": "litre", "region": "Indore", **kw}


def test_cutoff_is_the_29th_or_the_last_day():
    assert R.cutoff("2026-04") == "2026-04-29" and R.cutoff("2026-02") == "2026-02-28"
    assert R.window("2026-04") == ("2026-03-22", "2026-04-29")


def test_verifies_a_good_claim():
    assert R.verify(claim(), PAGE, "2026-03-30", "2026-04", "milk", "madhya pradesh") == (True, "verified")


@pytest.mark.parametrize("page_date, why", [(None, "no publication date"), ("2026-04-30", "after the cutoff"),
                                            ("2026-03-21", "before the window")])
def test_page_date_must_be_inside_the_window(page_date, why):
    ok, reason = R.verify(claim(), PAGE, page_date, "2026-04", "milk", "madhya pradesh")
    assert not ok and why in reason


def test_cutoff_day_itself_is_allowed():
    assert R.verify(claim(), PAGE, "2026-04-29", "2026-04", "milk", "madhya pradesh")[0]


def test_price_must_be_in_the_cited_line():
    ok, why = R.verify(claim(price=65), PAGE, "2026-03-30", "2026-04", "milk", "madhya pradesh")
    assert not ok and "price is not in the cited line" in why


def test_no_claimed_price_is_rejected_with_its_own_reason():
    ok, why = R.verify(claim(price=None), PAGE, "2026-03-30", "2026-04", "milk", "madhya pradesh")
    assert not ok and why == "Nano gave no price for this line"


def test_cited_line_must_be_on_the_fetched_page():
    other = "भोपाल में दूध अब 63 रुपये प्रति लीटर।"
    ok, why = R.verify(claim(line=other), PAGE, "2026-03-30", "2026-04", "milk", "madhya pradesh")
    assert not ok and "not on the fetched page" in why


def test_item_place_retail_and_unit():
    page = PAGE + "Mumbai milk now Rs 63 per litre.\nLoose buffalo milk wholesale rate Rs 63 per litre in Indore.\n"
    assert "not about milk" in R.verify(claim(line="इंदौर में चीनी 63 रुपये।", price=63),
                                        page + "इंदौर में चीनी 63 रुपये।", "2026-03-30", "2026-04", "milk",
                                        "madhya pradesh")[1]
    assert "not Madhya Pradesh" in R.verify(claim(line="Mumbai milk now Rs 63 per litre.", region="Mumbai"),
                                            page, "2026-03-30", "2026-04", "milk", "madhya pradesh")[1]
    assert "not a retail price" in R.verify(
        claim(line="Loose buffalo milk wholesale rate Rs 63 per litre in Indore."), page, "2026-03-30", "2026-04",
        "milk", "madhya pradesh")[1]
    assert "per litre" in R.verify(claim(line="इंदौर में दूध 63 रुपये का पैकेट।", unit="packet"),
                                   page + "इंदौर में दूध 63 रुपये का पैकेट।", "2026-03-30", "2026-04", "milk",
                                   "madhya pradesh")[1]


def test_change_from_old_new_or_pct():
    assert R.change_of({"old_price": 60, "new_price": 63}) == pytest.approx(0.05)
    assert R.change_of({"pct_change": 5}) == pytest.approx(0.05)
    assert R.change_of({"new_price": 63}) is None


def test_page_hash_and_save(tmp_path):
    sha = R.text_hash(PAGE)
    assert len(sha) == 64 and sha == R.text_hash(PAGE) and sha != R.text_hash(PAGE + " ")
    rel = LG.save_page(PAGE, sha, pages=tmp_path / "pages")
    assert rel == f"pages/{sha}.txt" and (tmp_path / "pages" / f"{sha}.txt").read_text(encoding="utf-8") == PAGE


def rec(**kw):
    return {"id": "x", "month": "2026-04", "cutoff": "2026-04-29", "cpi_item": "01.1.4.1.1.01", "cpi_name": "Milk",
            "item": "milk", "place": "Indore", "state": "madhya pradesh", "unit": "litre",
            "price_type": "retail price change", "price": 63, "published_date": "2026-03-30",
            "effective_date": "2026-04-01", "found_date": "2026-10-22", "line": LINE, "url": "https://a.in/x",
            "page_sha256": "a" * 64, "status": "verified", "reason": "verified", **kw}


def test_ledger_appends_once_and_keeps_every_field(tmp_path):
    p = tmp_path / "ledger.jsonl"
    assert LG.append(rec(), p) and not LG.append(rec(), p)            # same claim twice -> one line
    assert LG.append(rec(line="other line"), p)
    rows = LG.read(p)
    assert len(rows) == 2 and set(rows[0]) == set(LG.FIELDS)
    for f in ("published_date", "effective_date", "found_date", "place", "unit", "price_type", "cpi_item"):
        assert rows[0][f]
    assert json.loads(p.read_text(encoding="utf-8").splitlines()[0])["line"] == LINE      # Hindi kept as text


@pytest.mark.parametrize("bad", [{"status": "maybe"}, {"published_date": None}, {"url": ""}, {"extra": 1}])
def test_ledger_rejects_bad_records(tmp_path, bad):
    with pytest.raises(ValueError):
        LG.append(rec(**bad), tmp_path / "ledger.jsonl")
