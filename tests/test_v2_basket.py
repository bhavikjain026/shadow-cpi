"""v2 Amendment A rules, the gloss check, the needle and the treemap (offline, no calls)."""
import json
from pathlib import Path

import pytest

from v2 import rules as R
from v2.pipeline import gloss_ok
from v2.treemap import layout, squarify

ROOT = Path(__file__).resolve().parent.parent
MILK, ELEC, RAIL = "01.1.4.1.1.01", "04.5.1.0.2.01", "07.3.1.1.2.01"


def test_rule_1_spine_and_official_series_lead_their_items():
    assert R.source_role(MILK)[0] == "context" and "spine" in R.source_role(MILK)[1]
    assert R.source_role("13.2.1.1.1.01")[0] == "context"                    # gold: IBJA series
    assert R.source_role(ELEC) == ("moves", "")
    assert R.source_role(MILK, spine_covers=False) == ("moves", "")          # a month the spine misses


def test_rule_2_city_events_need_statewide_confirmation_or_a_documented_share():
    city = "इंदौर में दूध अब 63 रुपये प्रति लीटर के भाव पर मिलेगा।"
    sc, w, _, why = R.geography("milk", city, "Indore", "", "", MILK, shares={})
    assert (sc, w) == ("context", 0.0) and "no documented city share" in why
    sc, w, where, _ = R.geography("milk", city, "Indore", "", "", MILK, shares={"इंदौर": {"share": 0.1}})
    assert sc == "city" and w == pytest.approx(R.state_share(MILK, {"madhya pradesh"}) * 0.1)
    statewide = "पूरे प्रदेश में बिजली की दरें 5 फीसदी बढ़ीं, इंदौर में भी"
    assert R.geography("electricity", statewide, "Madhya Pradesh", "", "", ELEC)[0] == "state"
    jk = "जम्मू-कश्मीर में बिजली की दरों में औसतन 6.83 फीसदी बढ़ोतरी की गई है।"
    sc, w, _, _ = R.geography("electricity", jk, "Jammu & Kashmir", "JERC", "", ELEC)
    assert sc == "state" and w == pytest.approx(R.state_share(ELEC, {"jammu and kashmir"}))
    assert R.geography("rail", "Indian Railways raises fares by 1 paise per km", "", "Indian Railways", "",
                       RAIL)[:2] == ("national", 1.0)


def test_documented_city_share_table_is_empty_until_sourced():
    assert R.city_shares() == {}


def test_gloss_must_keep_every_number_and_never_feeds_a_number():
    assert gloss_ok("दूध ₹60 से ₹64", "milk from ₹60 to ₹64") and not gloss_ok("दूध ₹60 से ₹64", "₹60 per litre")
    claim = {"line": "इंदौर में दूध अब 63 रुपये प्रति लीटर।", "price": 63, "unit": "litre",
             "gloss": "In Indore milk is now 99 rupees per litre."}         # a wrong gloss changes nothing
    page = "इंदौर में दूध अब 63 रुपये प्रति लीटर।"
    assert R.verify(claim, page, "2026-03-30", "2026-04", "milk", "madhya pradesh") == (True, "verified")
    assert R.change_of({**claim, "old_price": 60, "new_price": 63}) == pytest.approx(0.05)


def test_needle_reproduces_v1_government_prices_only():
    from shadow_cpi import predict as P
    from shadow_cpi.evidence import SPINE_FOODS, spine_change
    from v2.needle import path
    inp = P.load_inputs()
    steps = [(code, "level", inp["factors"][f]["factor"] * spine_change(inp["spine"], f, "2026-09")[0])
             for f, code in SPINE_FOODS.items() if inp["factors"][f].get("use_spine")]
    start, out = path("2026-09", steps, inp)
    preds = json.loads((ROOT / "results" / "replay_predictions.json").read_text())["2026-09"]
    assert start == preds["a"]["yoy"] and out[-1] == pytest.approx(preds["b"]["yoy"], abs=1e-12)


def test_treemap_is_proportional_and_fills_the_box():
    vals = [36.75, 15.0, 7.2, 3.1, 0.6]
    boxes = squarify(vals, 0, 0, 100, 60)
    areas = [(c - a) * (d - b) for a, b, c, d in boxes]
    assert sum(areas) == pytest.approx(6000) and all(a == pytest.approx(v / sum(vals) * 6000)
                                                     for a, v in zip(areas, vals))
    tiles = layout([{"code": "01", "name": "Food", "weight": 36.75,
                     "items": [{"code": MILK, "name": "Milk", "weight": 5.0}]},
                    {"code": "04", "name": "Housing", "weight": 15.0}])
    assert {t["code"] for t in tiles} == {MILK, "01#rest", "04#rest"}


def test_september_run_is_consistent():
    run = json.loads((ROOT / "v2" / "evidence" / "run_2026-09_basket.json").read_text(encoding="utf-8"))
    assert run["cutoff"] == "2026-09-29" and run["credits_spent"] <= 120
    assert len(run["timeline"]) == sum(c["status"] == "verified" for c in run["item_cards"]) + len(run["moving_events"])
    assert run["needle"]["end"] == run["timeline"][-1]["yoy_after"]
    assert run["measured_share"] == pytest.approx(run["timeline"][-1]["measured_after"])
    assert all(c["reason"] for c in run["cards"] if c["status"] == "rejected")   # every rejection says why
