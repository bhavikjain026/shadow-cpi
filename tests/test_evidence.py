"""Offline tests for the evidence engine (Prompt 2). No network, no credits."""
import pytest

from shadow_cpi import evidence as E
from shadow_cpi.recorder import Recorder
from shadow_cpi.tavily import Tavily

ONION = {"base_unit": "kg", "min": 5, "max": 200, "names": ["onion", "प्याज"]}
LPG = {"base_unit": "cylinder", "min": 400, "max": 1500, "names": ["lpg", "cylinder", "सिलेंडर"],
       "require_any": ["14.2", "domestic", "घरेलू"], "reject_any": ["commercial", "19 kg"]}


# ---------- credit cap ----------
def test_call_cost():
    assert E.call_cost("/search", {"search_depth": "basic"}) == 1
    assert E.call_cost("/search", {"search_depth": "advanced"}) == 2
    assert E.call_cost("/extract", {"urls": list("abcdef")}) == 2
    assert E.call_cost("/extract", {"urls": ["a"], "extract_depth": "advanced"}) == 2


def test_cap_stops_before_spending_and_cache_is_free(tmp_path):
    calls = []

    def fake(method, url, token, body, timeout):
        calls.append(url)
        return {"results": [], "usage": {"credits": 1}}

    rec = Recorder(tmp_path / "c", tmp_path / "l.jsonl")
    cap = E.CreditCap(Tavily(api_key="t", recorder=rec, transport=fake), cap=1)
    cap.search("onion price", tag="p2-x")                        # spends 1 of 1
    cap.search("onion price", tag="p2-x")                        # cached: free, allowed
    with pytest.raises(E.BudgetExceeded):
        cap.search("tomato price", tag="p2-x")                   # would go past the cap
    assert len(calls) == 1


# ---------- guards ----------
def test_leak_guard_flags_target_month_cpi_only():
    assert E.leak_line("Retail inflation for March 2026 rose to 3.40%, data showed.", "2026-03")
    assert E.leak_line("मार्च में खुदरा महंगाई दर 3.4 प्रतिशत रही", "2026-03")
    assert not E.leak_line("Retail inflation in February was 3.21%.", "2026-03")         # last month: allowed
    assert not E.leak_line("Onion prices rose in March to ₹40 per kg.", "2026-03")


class FakeNem:
    def __init__(self, answer):
        self.answer, self.calls = answer, 0

    def chat_json(self, *a, **k):
        self.calls += 1
        return {"answer": self.answer}, "id"


def test_gatekeeper_backstop(monkeypatch):
    monkeypatch.setattr(E, "models", lambda: {"small": "m"})
    nem = FakeNem("no")
    assert E.gatekeeper(nem, "Big onions retail at ₹33 per kg in Delhi")      # rupee price on page: kept
    assert nem.calls == 0
    assert not E.gatekeeper(nem, "Onion prices in Seoul fell 28%")
    assert nem.calls == 1


# ---------- quotes ----------
def q(**kw):
    base = {"item": "onion", "price": 40, "unit": "kg", "place": "Delhi", "date": None, "verified": True,
            "retail_or_wholesale": "retail", "quote": "Onion sells at ₹40 per kg in Delhi"}
    return {**base, **kw}


def test_judge_quote_rules():
    keep, why = E.judge_quote(q(), "onion", ONION, "2026-03", "2026-03-13")
    assert why == "kept" and keep["price"] == 40 and keep["city"] == "delhi"
    assert E.judge_quote(q(verified=False), "onion", ONION, "2026-03", "2026-03-13")[0] is None
    # the model said onion but the line is about potatoes
    assert E.judge_quote(q(quote="Potatoes at ₹40 per kg"), "onion", ONION, "2026-03", "2026-03-13")[1].startswith("different item")
    assert E.judge_quote(q(unit="quintal", price=4000, retail_or_wholesale="unknown",
                           quote="Onion ₹4000 per quintal at Lasalgaon"), "onion", ONION, "2026-03", "2026-03-13")[1] == "wholesale price"
    assert E.judge_quote(q(price=900), "onion", ONION, "2026-03", "2026-03-13")[1] == "price outside sanity range"
    assert E.judge_quote(q(date="2026-02-27"), "onion", ONION, "2026-03", "2026-03-13")[1] == "quote dated outside the month"


def test_judge_quote_lpg_variety():
    line = "Domestic LPG 14.2 kg cylinder now costs ₹913 in Delhi"
    keep, why = E.judge_quote(q(item="lpg", price=913, unit="cylinder", quote=line), "lpg", LPG, "2026-03", "2026-03-08")
    assert why == "kept"
    bad = "Commercial 19 kg cylinder price raised to ₹1,900"
    assert E.judge_quote(q(item="lpg", price=1900, unit="cylinder", quote=bad), "lpg", LPG, "2026-03", "2026-03-01")[0] is None


def test_hindi_city_names_match():
    assert E.city_key("दिल्ली") == "delhi" and E.city_key("New Delhi") == "delhi"


def test_match_change_needs_three_cities():
    now = [{"item": "onion", "city": c, "price": p} for c, p in [("delhi", 44), ("mumbai", 33), ("patna", 22)]]
    prev = [{"item": "onion", "city": c, "price": p} for c, p in [("delhi", 40), ("mumbai", 30), ("patna", 20)]]
    ch, used = E.match_change("onion", now, prev)
    assert ch == pytest.approx(0.10) and len(used) == 3
    assert E.match_change("onion", now[:2], prev)[0] is None


# ---------- events ----------
def test_judge_event():
    ev = {"old_price": 853, "new_price": 913, "pct_change": None, "effective_date": "2026-03-07",
          "quote": "Domestic LPG cylinder price hiked from ₹853 to ₹913 with effect from March 7"}
    keep, why = E.judge_event(ev, "2026-03")
    assert why == "kept" and keep["change"] == pytest.approx(913 / 853 - 1)
    assert keep["days_share"] == pytest.approx(25 / 31)
    assert E.judge_event({**ev, "effective_date": "2026-04-01"}, "2026-03")[1] == "effective date outside the month"
    assert E.judge_event({**ev, "new_price": 999, "old_price": None}, "2026-03")[0] is None     # 999 not in line


# ---------- observed series ----------
IBJA_TEXT = ("Daily Bullion Physical Market Report Date: 23rd March 2026 Description Purity AM PM Gold 999 147340 147218 "
             "Daily India Spot Market Rates Date GOLD* SILVER* 20th March 2026 147218 232364 19th March 2026 147889 "
             "229873 18th March 2026 154879 249907 17th March 2026 155668 252340 Gold and Silver 999 Watch")


def test_parse_ibja_and_monthly_average():
    r = E.parse_ibja(IBJA_TEXT)
    assert set(r) == {"2026-03-20", "2026-03-19", "2026-03-18", "2026-03-17"}
    assert r["2026-03-20"] == {"gold": 147218.0, "silver": 232364.0, "line": "20th March 2026 147218 232364"}
    avg, n = E.monthly_average(r, "gold", "2026-03")
    assert n == 4 and avg == pytest.approx((147218 + 147889 + 154879 + 155668) / 4)
    assert E.ibja_report_dates(["2026-03"])[0].isoformat() == "2026-03-02"


IOCL_TEXT = ("| Month | Delhi | Kolkata | Mumbai | Chennai |\n| --- | --- | --- | --- | --- |\n"
             "| March 7, 2026 | 913.00 | 939.00 | 912.50 | 928.50 |\n| April 8, 2025 | 853.00 | 879.00 | 852.50 | 868.50 |\n")


def test_iocl_lpg_day_weighted():
    rev = E.parse_iocl_lpg(IOCL_TEXT)
    assert [r[0] for r in rev] == ["2025-04-08", "2026-03-07"]
    feb = E.lpg_monthly(rev, "2026-02")
    mar = E.lpg_monthly(rev, "2026-03")
    assert feb == pytest.approx((853 + 879 + 852.5 + 868.5) / 4)
    assert mar == pytest.approx((6 * feb + 25 * (913 + 939 + 912.5 + 928.5) / 4) / 31)


def test_passthrough_is_2025_only():
    off = {"2025-04": 0.02, "2025-05": 0.01}
    obs = {"2025-04": 0.04, "2025-05": 0.02}
    f, n, _ = E.fit_passthrough(off, obs, ["2025-04", "2025-05"])
    assert f == pytest.approx(0.5) and n == 2
    with pytest.raises(ValueError):
        E.fit_passthrough(off, obs, ["2026-03"])
    assert E.fit_passthrough({"2025-04": 0.0}, {"2025-04": 0.0}, ["2025-04"])[0] is None   # no movement


def test_spine_change(tmp_path):
    p = tmp_path / "spine.csv"
    p.write_text("month,item,centre,avg_price,unit,n_days\n2026-02,onion,Delhi,40,kg,28\n2026-03,onion,Delhi,44,kg,31\n"
                 "2026-02,onion,Patna,20,kg,28\n2026-03,onion,Patna,22,kg,31\n2026-03,onion,Pune,30,kg,31\n", encoding="utf-8")
    ch, n = E.spine_change(E.load_spine(p), "onion", "2026-03")
    assert n == 2 and ch == pytest.approx(0.10)


# ---------- filters added after the March audit ----------
def test_audit_filters():
    assert E.foreign("प्याज की कीमत 7 दिरहम (करीब 175 रुपये) प्रति किलो", None)
    assert E.foreign("tomatoes at Rs135 per kg", None, "https://kathmandupost.com/money/2026/02/13/x")
    assert not E.foreign("Onion ₹33 per kg in Delhi", "Delhi")
    assert E.other_month("फरवरी 2026 में टमाटर की कीमत 33 रुपए प्रति किलो", "2026-03")
    assert E.other_month("even at the end of Dec, tomato was Rs 55 per kg", "2026-03")
    assert not E.other_month("Prices may rise; onion at ₹40 per kg", "2026-03")
    assert E.range_mid("प्याज 25 से 30 रुपये प्रति किलो", 25) == 27.5
    assert E.range_mid("hovered between ₹8 and ₹10 per kg", 8) == 9
    assert E.range_mid("increased from Rs 853 to Rs 913", 853) == 853       # a change, not a range
    assert E.table_retail("| Tomato | ₹16 | ₹19 - ₹24 |", ["tomato"]) == 21.5
    assert E.table_retail("| 1 | Tomato | 10 | 13.5 | 1 Kg |", ["tomato"]) == 13.5
    assert E.city_key("retail") == ""


def test_event_kind_filter():
    lpg = {"match": ["lpg", "cylinder"], "reject": ["commercial", "atf", "aviation"]}
    atf = {"item_or_service": "Aviation Turbine Fuel (ATF)", "old_price": 91393.39, "new_price": 96638.14,
           "pct_change": None, "effective_date": "2026-03-01",
           "quote": "1 मार्च 2026 से एटीएफ प्राइस 91,393.39 रुपये से बढ़कर 96,638.14 रुपये"}
    assert E.judge_event(atf, "2026-03", lpg)[0] is None
    com = {"item_or_service": "Commercial LPG cylinder", "old_price": 1720.5, "new_price": 1835, "pct_change": None,
           "effective_date": "2026-03-07", "quote": "19 kg commercial LPG cylinder up from 1720.5 to 1835"}
    assert E.judge_event(com, "2026-03", lpg)[1].startswith("not the CPI variety")
