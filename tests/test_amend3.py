"""Amendment 3 (after scoring): general bug-fix rules in shadow_cpi/event_rules.py."""
from shadow_cpi import event_rules as R
from shadow_cpi.evidence import line_context


def test_a_wholesale_context_drops_only_without_a_retail_word():
    ctx = "Milk prices rise by Rs 9; wholesale rates jump from Rs 93 to Rs 102"
    assert R.not_retail_context_reason("the milk prices in the city have increased by Rs 9 per litre.", ctx)
    assert not R.not_retail_context_reason("retail milk will cost Rs 2 more for consumers", ctx)
    assert R.not_retail_context_reason("तबेला दूध के दाम 5 रुपये बढ़े", "")                     # Hindi, in the line
    assert R.not_retail_context_reason("दूध दर 3 रुपये वाढ", "घाऊक दरात वाढ")                  # Marathi wholesale
    assert R.not_retail_context_reason("milk up Rs 2", "procurement price paid to dairy farmers raised")
    assert not R.not_retail_context_reason("Amul hikes milk by Rs 2 per litre", "Amul milk price hike across India")


def test_line_context_is_title_and_neighbours():
    text = "# Headline: wholesale up\nfirst sentence here\ncited line here\nnext sentence here\nlater"
    ctx = line_context(text, 3)
    assert "wholesale" in ctx and "first sentence" in ctx and "next sentence" in ctx and "later" not in ctx


def test_b_premium_fuel_grades_rejected_for_fuel_only():
    xp = "IOC's XP100 petrol was hiked by Rs 11; Xtra Green premium diesel to Rs 92.99 from Rs 91.49"
    assert R.premium_fuel_reason("fuel", "premium diesel", xp)
    assert R.premium_fuel_reason("fuel", "", "प्रीमियम पेट्रोल 5 रुपये महंगा")
    assert not R.premium_fuel_reason("fuel", "petrol", "petrol in Delhi will now cost Rs 97.77, up from Rs 94.77")
    assert not R.premium_fuel_reason("fuel", "", "regular petrol up Rs 3, while premium XP95 rose Rs 4")
    assert not R.premium_fuel_reason("electricity", "power tariff", "power tariff up 4.8%")


def test_c_scope_national_needs_nationwide_line_or_national_body():
    nmr = {"kind": "rail", "quote": "COIMBATORE: Passengers on the Nilgiri Mountain Railway will pay more as the "
                                    "Southern Railway has revised fares by 5%", "seller_or_authority": "Southern Railway",
           "region": "India"}
    assert R.scope(nmr) == ("regional", frozenset({"tamil nadu"}))
    omc = {"kind": "fuel", "quote": "petrol in the national capital will now cost Rs 97.77", "region": "Delhi",
           "seller_or_authority": "Oil companies"}
    assert R.scope(omc) == ("national", None)
    rb = {"kind": "rail", "quote": "Indian Railways raises fares by 1 paise per km", "seller_or_authority": ""}
    assert R.scope(rb) == ("national", None)
    metro = {"kind": "rail", "quote": "Indian Railways raises Mumbai suburban fares", "seller_or_authority": ""}
    assert R.scope(metro)[0] == "regional"
    milk = {"kind": "milk", "quote": "Amul hikes milk prices by Rs 2 across the country", "region": "Gujarat"}
    assert R.scope(milk) == ("national", None)


def _ev(change, eff, url, quote):
    return {"kind": "milk", "cpi_code": "01.1.4.1.1.01", "region": "Madhya Pradesh", "quote": quote,
            "change": change, "effective_date": eff, "change_prorated": change, "url": url, "sources": [url]}


def test_d_one_event_per_kind_state_month_median_and_earliest_date():
    kept, dropped = R.apply_rules([_ev(0.0497, "2026-04-01", "a", "Indore milk up Rs 3"),
                                   _ev(0.0663, "2026-04-01", "b", "Dhar milk up Rs 4"),
                                   _ev(0.0900, "2026-04-10", "c", "Bhopal milk up Rs 5")])
    assert len(kept) == 1 and kept[0]["merged_from"] == 3
    assert abs(kept[0]["change"] - 0.0663) < 1e-12 and kept[0]["effective_date"] == "2026-04-01"
    assert kept[0]["days_share"] == 1.0 and set(kept[0]["sources"]) == {"a", "b", "c"}
    assert sum("one event per kind and state" in why for _, why in dropped) == 2
