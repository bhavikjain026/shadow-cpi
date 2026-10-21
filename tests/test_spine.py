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
    assert len(kept) == 2 and kept[0]["sources"] == ["u1", "u2"] and len(dropped) == 1


def test_unknown_region_is_not_applied():
    kept, dropped = R.apply_rules([ev(region="the city", seller_or_authority="a dairy")])
    assert not kept and dropped[0][1].startswith("regional event: state not identified")


def test_2025_audit_rules():
    assert R.normalise_date("April 8", "2025-04-07") == "2025-04-08"
    assert R.normalise_date("Wednesday (today)", "2025-04-30") == "2025-04-30"
    assert R.normalise_date("आज (बुधवार)", "2025-04-30") == "2025-04-30"
    assert R.normalise_date("Tuesday", "2025-04-07") == "2025-04-08"
    assert R.normalise_date("soon", "2025-04-07") == ""
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
