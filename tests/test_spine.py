"""Spine parsing and the event rules (offline)."""
import pytest

from shadow_cpi import event_rules as R
from shadow_cpi import spine as S

REPORT = ("<span>Zonewise Monthly Average Retail Prices of&nbsp;&nbsp;<b> Rice </b></span><b>Unit: (Rs./Kg.)</b>"
          "<table><tr><th>Zone</th><th>Jan 2026</th><th>Feb 2026</th><th>Average</th></tr>"
          "<tr><td>NORTH ZONE</td><td>40</td><td>41</td><td>40.5</td></tr>"
          "<tr><td>SOUTH ZONE</td><td>50</td><td></td><td>50</td></tr>"
          "<tr><td>All India Average</td><td>45</td><td>41</td><td></td></tr></table>")


def test_parse_report_reads_zones_and_skips_blanks():
    (name, unit, zones), = S.parse_report(REPORT)
    assert name == "Rice" and unit == "Rs./Kg."
    assert zones == {"NORTH ZONE": {"2026-01": 40.0, "2026-02": 41.0}, "SOUTH ZONE": {"2026-01": 50.0}}


def test_build_adds_simple_mean_only_with_all_zones(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    rows = "".join(f"<tr><td>{z}</td><td>{10 * (k + 1)}</td></tr>" for k, z in enumerate(S.ZONES))
    (raw / "a.html").write_text("Prices of <b> Onion </b> Unit: (Rs./Kg.)<table><tr><th>Zone</th><th>Mar 2026</th>"
                                f"</tr>{rows}</table>", encoding="utf-8")
    out = S.build(raw, tmp_path / "spine.csv")
    mean = [r for r in out if r["centre"] == S.ALL_INDIA]
    assert len(mean) == 1 and mean[0]["avg_price"] == pytest.approx(30.0) and mean[0]["item"] == "onion"



def _onion(month_label, price):
    rows = "".join(f"<tr><td>{z}</td><td>{price}</td></tr>" for z in S.ZONES)
    return (f"Prices of <b> Onion </b> Unit: (Rs./Kg.)<table><tr><th>Zone</th><th>{month_label}</th></tr>{rows}"
            "</table>")


def test_superseded_month_is_skipped_only_in_the_named_file(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "old.html").write_text(_onion("Oct 2026", 30), encoding="utf-8")     # partial month, earlier fetch
    (raw / "new.html").write_text(_onion("Oct 2026", 32), encoding="utf-8")     # same month, later fetch
    with pytest.raises(ValueError):
        S.build(raw, tmp_path / "a.csv", superseded={})                         # disagreeing overlap: refused
    out = S.build(raw, tmp_path / "b.csv", superseded={"old.html": {"2026-10": "partial"}})
    assert {r["avg_price"] for r in out if r["centre"] != S.ALL_INDIA} == {32.0}
    (raw / "other.html").write_text(_onion("Oct 2026", 31), encoding="utf-8")   # any other overlap must still agree
    with pytest.raises(ValueError):
        S.build(raw, tmp_path / "c.csv", superseded={"old.html": {"2026-10": "partial"}})


def test_superseded_names_only_the_21_oct_files_and_october():
    assert S.SUPERSEDED.keys() == {"2026AB.html", "2025H2-2026fill.html"}
    assert all(set(v) == {"2026-10"} for v in S.SUPERSEDED.values())


def ev(**kw):
    base = {"kind": "electricity", "region": "Uttar Pradesh", "seller_or_authority": "UPPCL",
            "effective_date": "2026-06-01", "change": 0.10, "change_prorated": 0.10, "cpi_code": "04.5.1.0.2.01",
            "url": "u1"}
    return {**base, **kw}


def test_regional_events_use_official_state_share():
    (e,), _ = R.apply_rules([ev(region="India")])          # seller names UP: regional, not national
    assert e["scope"] == "regional" and e["states"] == ["uttar pradesh"]
    assert 0.12 < e["weight"] < 0.15 and e["applied_change"] == pytest.approx(0.10 * e["weight"])


def test_national_kinds_ignore_the_quoted_city():
    (e,), _ = R.apply_rules([ev(kind="lpg", region="Delhi", seller_or_authority="IOCL", cpi_code="04.5.2.2.1.01")])
    assert e["scope"] == "national" and e["weight"] == 1.0


def test_duplicates_merge_after_city_to_state():
    a = ev(kind="milk", region="Mumbai", seller_or_authority="", change=0.0968, change_prorated=0.0968,
           cpi_code="01.1.4.1.1.01", url="u1")
    b = {**a, "region": "Maharashtra", "change": 0.1000, "url": "u2"}       # within 0.5 pp
    c = {**a, "region": "Maharashtra", "change": 0.1100, "url": "u3"}       # 1.3 pp away: separate
    kept, dropped = R.apply_rules([a, b, c])
    # a + b merge as duplicates (Amendment 1 e); c then joins them under Amendment 3 (d): one event per kind x state
    assert sum(why.startswith("duplicate of an event") for _, why in dropped) == 1
    assert len(kept) == 1 and kept[0]["sources"] == ["u1", "u2", "u3"]
    assert kept[0]["change"] == pytest.approx((0.0968 + 0.1100) / 2)        # median of the two left after pass 2


def test_unknown_region_is_not_applied():
    kept, dropped = R.apply_rules([ev(region="the city", seller_or_authority="a dairy")])
    assert not kept and dropped[0][1].startswith("regional event: state not identified")


def test_2025_audit_rules():
    assert R.normalise_date("April 8", "2025-04-07") == "2025-04-08"
    assert R.normalise_date("Wednesday (today)", "2025-04-30") == "2025-04-30"
    assert R.normalise_date("आज (बुधवार)", "2025-04-30") == "2025-04-30"
    assert R.normalise_date("Tuesday", "2025-04-07") == "2025-04-08"
    assert R.normalise_date("soon", "2025-04-07") == ""
    assert R.announced_date("Tue, Oct 20, 2026", "2026-03-31") == "2026-03-31"     # site header 'today', not the news
    assert R.announced_date("2026-05-30", "2026-05-31") == "2026-05-30"
    assert R.announced_date(None, "2026-03-30") == "2026-03-30"
    assert R.absolute_change("a hike in the price of domestic LPG cylinders by Rs 50, effective from April 8") == 50
    assert R.absolute_change("दूध की कीमत में इजाफा: अब 2 रुपये प्रति लीटर ज्यादा") == 2
    assert R.absolute_change("prices of 19 kg cylinders cut by Rs 41") == -41
    assert R.absolute_change("price of Rs 50 per kg") is None            # no direction: not usable


def test_same_line_range_is_one_event_and_national_needs_the_line():
    line = "सुधा दूध की कीमतों में दो से तीन रुपये प्रति लीटर तक की वृद्धि, बिहार"
    a = ev(kind="milk", region="", seller_or_authority="", quote=line, change=0.0484, change_prorated=0.0484,
           cpi_code="01.1.4.1.1.01")
    b = {**a, "change": 0.0364, "change_prorated": 0.0364}
    kept, dropped = R.apply_rules([a, b])
    assert len(kept) == 1 and kept[0]["change"] == pytest.approx(0.0424) and kept[0]["states"] == ["bihar"]
    brand_only = ev(kind="milk", region="India", seller_or_authority="Mother Dairy", cpi_code="01.1.4.1.1.01",
                    quote="Mother Dairy cut UHT milk prices by Rs 2")
    assert not R.apply_rules([brand_only])[0]                              # 'India' in region alone: not national
    nationwide = {**brand_only, "quote": "Amul raised milk prices by Rs 2 per litre across the country"}
    assert R.apply_rules([nationwide])[0][0]["scope"] == "national"


# ---------- Amendment 1 (before any scoring) ----------
def test_amendment1_consumer_prices_only():
    f = R.non_consumer_reason
    assert f("Commercial LPG cylinders (19 kg)", "cut by Rs 41").startswith("not a household")
    assert f("LPG", "19 किलो वाले वाणिज्यिक एलपीजी सिलेंडर 202 रुपये सस्ता").startswith("not a household")
    assert f("milk", "bulk supply rate up Rs 3").startswith("not a household")
    assert f("domestic LPG", "domestic up Rs 60; commercial up Rs 115") == ""          # domestic named: kept
    assert f("rail", "minimum penalty for passengers travelling without a valid ticket").startswith("penalty")
    assert f("मेट्रो", "बिना टिकट यात्रा पर जुर्माना बढ़ा").startswith("penalty")
    assert f("milk", "The wholesale milk rate in Mumbai will move from Rs 93 to Rs 102").startswith("not a retail")
    assert f("onion", "मंडी में प्याज 20 रुपये").startswith("not a retail")
    assert f("electricity", "UPPCL announced a 10% surcharge in electricity bills") == ""    # tariff surcharge
    assert f("finance", "fees refined for consumers") == ""                                 # no false 'fine'


def test_amendment1_duplicates_within_15_days_keep_earliest():
    a = ev(kind="milk", region="Mumbai", seller_or_authority="", change=0.0968, change_prorated=0.0968,
           cpi_code="01.1.4.1.1.01", effective_date="2026-09-12", url="u1", quote="line a")
    b = {**a, "effective_date": "2026-09-01", "url": "u2", "quote": "line b"}
    c = {**a, "effective_date": "2026-09-30", "url": "u3", "quote": "line c", "change": 0.20, "change_prorated": 0.2}
    kept, dropped = R.apply_rules([a, b, c])
    assert sum(why.startswith("duplicate of an event") for _, why in dropped) == 1   # a + b only (c > 0.5 pp)
    assert len(kept) == 1                                  # Amendment 3 (d): then one event per kind x state x month
    assert kept[0]["effective_date"] == "2026-09-01" and kept[0]["change"] == pytest.approx((0.0968 + 0.20) / 2)


def test_amendment1_duplicates_more_than_15_days_apart_stay_separate():
    a = ev(kind="milk", region="Mumbai", seller_or_authority="", change=0.0968, change_prorated=0.0968,
           cpi_code="01.1.4.1.1.01", effective_date="2026-09-20", url="u1", quote="line a")
    b = {**a, "effective_date": "2026-09-01", "url": "u2", "quote": "line b"}         # 19 days apart
    kept, dropped = R.apply_rules([a, b])
    assert not any(why.startswith("duplicate of an event") for _, why in dropped)   # not Amendment 1 (e) twins
    assert len(kept) == 1 and kept[0]["effective_date"] == "2026-09-01"            # Amendment 3 (d) merges them


def test_same_line_average_is_then_checked_for_duplicates():
    tn = dict(kind="milk", region="Chennai", seller_or_authority="", cpi_code="01.1.4.1.1.01",
              effective_date="2026-07-23")
    arokya = ev(**tn, change=0.0488, change_prorated=0.0488, quote="Arokya raised milk by Rs 3", url="u1")
    notice = [ev(**tn, change=c, change_prorated=c, quote="toned Rs 57 from 54, standardised 69 from 66", url="u2")
              for c in (0.0556, 0.0455, 0.0411)]                 # same line, mean 4.74% -> within 0.5 pp of 4.88%
    kept, _ = R.apply_rules([arokya] + notice)
    assert len(kept) == 1 and kept[0]["sources"] == ["u1", "u2"]
