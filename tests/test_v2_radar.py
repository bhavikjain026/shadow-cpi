"""October radar (v2/RADAR_PREREG.md): strategy gate, freeze, tiers, Tavily-only, effect, scoring. Offline with fakes."""
import json
from datetime import datetime, timezone

import pytest

from v2 import ledger as LG
from v2 import radar as RD

LINE = "Delhi electricity tariff up 5% from October 10 for domestic consumers"


def src(domain, line=LINE):
    return {"url": f"https://{domain}/a", "domain": domain, "line": line, "published": "2026-10-05", "via": "tavily"}


def ev(*sources, kind="electricity", states=("nct of delhi",)):
    return {"kind": kind, "effective_date": "2026-10-10", "states": list(states), "change": 0.05,
            "sources": list(sources)}


def test_strategy_line_is_required():
    assert RD.strategy("no decision yet") is None
    assert RD.strategy("...\nSearch strategy decided: C (2026-10-23T10:00Z)\n") == "C"


def test_tiers_primary_or_two_independent_publishers():
    assert RD.tier(ev(src("thehindu.com"))) == "verified"
    assert RD.tier(ev(src("derc.gov.in"))) == "corroborated"                        # primary source
    assert RD.tier(ev(src("thehindu.com"), src("ndtv.com", "Delhi power tariff rises 5 per cent"))) == "corroborated"
    assert RD.tier(ev(src("thehindu.com"), src("ndtv.com"))) == "verified"          # same line: syndicated copy
    assert RD.tier(ev(src("m.economictimes.com"), src("economictimes.com", "other words"))) == "verified"   # one publisher


def test_effect_only_for_tavily_only_kinds_and_uses_the_needle(monkeypatch):
    from v2 import needle as N
    monkeypatch.setattr(N, "yoy", lambda month, changes, inp: 5.0 + sum(v for _, v in changes.values()) * 10)
    monkeypatch.setattr(N, "trend_only", lambda month, inp: 5.0)
    monkeypatch.setattr(RD.R, "geography", lambda *a, **k: ("state", 0.05, "nct of delhi", "state"))
    e = RD.effect_pp(ev(src("thehindu.com")), inp={})
    assert e == pytest.approx(0.05 * (22 / 31) * 0.05 * 10)
    assert RD.effect_pp(ev(src("amul.com"), kind="milk"), inp={}) is None            # context kind: spine moves it


class FakeTav:
    used = 0

    def search(self, query, **kw):
        self.last = kw
        return {"results": [{"url": "https://thehindu.com/a", "title": "Delhi power", "content": LINE,
                             "published_date": "2026-10-05"}], "usage": {"credits": 1}, "response_time": 1.0}, "s"

    def extract(self, urls, **kw):
        return {"results": [{"url": u, "raw_content": "Published: Oct 5, 2026, 09:00\n" + LINE} for u in urls],
                "usage": {"credits": 1}}, "e"


class FakeNem:
    def chat_json(self, model, system, user, schema=None, **kw):
        return {"english": ""}, "g"

    def price_events(self, model, text, **kw):
        return [{"quote": LINE, "line": LINE, "new_price": 5, "pct_change": 5, "effective_date": "2026-10-10",
                 "region": "Delhi"}], "r"


def test_run_refused_without_strategy_or_after_freeze(tmp_path, monkeypatch):
    monkeypatch.setattr(RD, "FROZEN", tmp_path / "f.json")
    monkeypatch.setattr(RD, "PREREG", tmp_path / "prereg.md")
    RD.PREREG.write_text("no decision yet")
    with pytest.raises(SystemExit, match="Search strategy"):
        RD.run(FakeTav(), FakeNem(), "n", "s", now=datetime(2026, 10, 25, tzinfo=timezone.utc))
    with pytest.raises(SystemExit, match="frozen"):
        RD.run(FakeTav(), FakeNem(), "n", "s", now=datetime(2026, 10, 29, 18, 30, tzinfo=timezone.utc), strat="A")


def test_run_freeze_score_end_to_end(tmp_path, monkeypatch):
    for name, p in {"DIR": tmp_path, "RADAR": tmp_path / "r.json", "FROZEN": tmp_path / "r.frozen.json",
                    "SCORE": tmp_path / "score.json"}.items():
        monkeypatch.setattr(RD, name, p)
    monkeypatch.setattr(LG.save_page, "__defaults__", (tmp_path / "pages",))
    monkeypatch.setattr(RD, "effect_pp", lambda e, inp=None: 0.01)
    monkeypatch.setattr(RD.PL, "propose", lambda tav, nem, nano, q, m, tag, seen, **kw:
                        RD.PL.read_results(tav.search("q", **{"include_domains_mode": "prefer"})[0], "s", "en", m, nem,
                                           nano, tag, seen))
    tav = FakeTav()
    s = RD.run(tav, FakeNem(), "nano", "super", now=datetime(2026, 10, 25, tzinfo=timezone.utc), strat="A")
    e = s["events"][0]
    assert e["kind"] == "electricity" and e["tavily_only"] and e["tier"] == "verified"
    # Amendment R1: corroboration is an open news search (arm A's English domains, prefer), not restricted
    assert tav.last["include_domains"] == RD.K.DOMAINS["en"] and tav.last["include_domains_mode"] == "prefer"
    assert s["corroboration"][0]["mode"] == "prefer"
    RD.freeze(now=datetime(2026, 10, 29, 18, 0, tzinfo=timezone.utc))
    assert len(RD.FROZEN.with_suffix(".sha256").read_text().strip()) == 64
    lst = [{"kind": "electricity", "month": "2026-10", "date": "2026-10-11", "states": ["nct of delhi"],
            "first_reported": "2026-10-04"},
           {"kind": "milk", "month": "2026-10", "date": "2026-10-31", "states": [], "first_reported": "2026-10-30"}]
    sc = RD.score(scoring=lst)
    assert sc["counted"] == 1 and sc["tiers"]["verified"]["precision"] == 1.0
    assert sc["tiers"]["verified"]["recall"] == 1.0 and sc["tiers"]["corroborated"]["events"] == 0
    with pytest.raises(SystemExit, match="scored once"):
        RD.score(scoring=lst)


def test_corroboration_is_open_news_search_with_arm_a_settings(monkeypatch):
    """Amendment R1: no restriction to a primary domain; arm A's English domains in prefer mode."""
    sent = {}

    class M:
        def search(self, q, **kw):
            sent.update(q=q, **kw)
            return {"results": []}, "sid"
    monkeypatch.setattr(RD, "verify", lambda *a, **k: None)
    out = RD.corroborate(ev(src("thehindu.com"), kind="milk", states=("madhya pradesh",)), "2026-10", M(), None, None,
                         None, set(), [], "t")
    assert sent["include_domains_mode"] == "prefer" and sent["include_domains"] == RD.K.DOMAINS["en"]
    assert sent["max_results"] == 10 and sent["q"] == "milk price madhya pradesh October 2026" and out["mode"] == "prefer"
    assert RD.corroborate(ev(src("derc.gov.in")), "2026-10", M(), None, None, None, set(), [], "t") is None


# ---------- Amendment R2 (logged bug fix): whole words, page-first states, licence areas, effect baseline ----------
from v2 import kinds as K  # noqa: E402
from v2 import rules as R  # noqa: E402

BOKARO = ("वहीं, उच्च वोल्टेज घरेलू सेवा के उपभोक्ताओं के लिए फिक्स्ड चार्ज 75 रुपये से बढ़कर 85 रुपये प्रति केवीए प्रति माह "
          "कर दिया गया है. ऊर्जा शुल्क 2.85 रुपये से बढ़कर 3.20 रुपये प्रति केवीए हो गया है.")


def test_rail_does_not_match_inside_gharelu():
    assert not K.has_word("घरेलू", "रेल")
    assert K.has_word("रेल किराया बढ़ा", "रेल") and K.has_word("नया किराया: रेल.", "रेल")
    assert K.kind_of(BOKARO, whole=True) is None
    assert K.kind_of(BOKARO) == "rail"                       # the old substring matcher, kept for v1/v2 scored paths
    assert K.kind_of("1 अक्टूबर से रेल किराया बढ़ा", whole=True) == "rail"
    assert K.kind_of("business abuse report", whole=True) is None and K.kind_of("bus fare up", whole=True) == "bus"


def test_verifier_whole_words_rejects_the_bokaro_line():
    page = "Published: Sep 27, 2026\n" + BOKARO
    claim = {"line": BOKARO, "price": 3.2, "old_price": 2.85, "new_price": 3.2, "effective_date": "2026-10-01"}
    assert R.check(claim, page, "2026-09-27", "2026-10", K.WHOLE_WORDS, whole_words=True) == (
        False, "the line is not about this item")
    assert R.check(claim, page, "2026-09-27", "2026-10", K.ALL_WORDS)[1] != "the line is not about this item"


@pytest.mark.parametrize("kind,form", [(k, f) for k, fs in K.FORMS.items() for f in fs])
def test_added_forms_match_whole_and_not_inside_a_longer_word(kind, form):
    assert K.has_word(f"x {form} y", form) and K.kind_of(f"किराया {form} में", whole=True) == kind
    assert not K.has_word(f"ab{form}", form) and not K.has_word(f"{form}ab", form)
    assert not K.has_word(f"क{form}", form) and not K.has_word(f"{form}क", form)


def test_state_from_the_page_then_domain_then_region():
    assert K.page_states("झारखंड राज्य विद्युत नियामक आयोग (JSERC) ने मंजूरी दी", region="Bihar") == {"jharkhand"}
    assert K.page_states("tariff order by JSERC", region="Bihar") == {"jharkhand"}
    url = "https://www.prabhatkhabar.com/state/jharkhand/bokaro/bokaro-residents-prepare-higher-electricity-bills"
    assert K.page_states(BOKARO, "# बोकारो में BSL की बिजली", "बोकारो में BSL बिजली", url, "Bihar") == {"jharkhand"}
    assert K.page_states(BOKARO, region="Bihar") == {"bihar"}            # the page names no state: region is used
    assert K.page_states("आधार कार्ड से जुड़ी सुधार प्रक्रिया") == set()        # 'धार' (Dhar, MP) not inside a word
    assert K.page_states("சென்னையில் பால் விலை") == {"tamil nadu"}        # regional stems take case endings


def test_licence_area_tariff_is_context_with_no_effect():
    e = ev(src("prabhatkhabar.com", "झारखंड में बीएसएल के बिजली टैरिफ में 12% बढ़ोतरी"), states=("jharkhand",))
    assert RD.licence_area(e) and RD.effect_pp(e, inp={}) is None
    assert not RD.licence_area(ev(src("thehindu.com")))


def test_zero_change_gives_exactly_zero_pp():
    from v2 import needle as N
    inp = N.P.load_inputs()
    e = {**ev(src("thehindu.com")), "change": 0.0}
    assert RD.effect_pp(e, inp) == 0.0
    assert RD.effect_pp({**e, "change": 0.05}, inp) > 0                  # a rise moves the needle up


def test_reclassify_rejects_substring_only_claims_and_keeps_the_rest():
    url = "https://www.prabhatkhabar.com/state/jharkhand/bokaro/a"
    bad = {"line": BOKARO, "status": "verified", "reason": "verified", "region": "Bihar", "context": "",
           "effective_date": "2026-10-01", "change": 0.12}
    good = {"line": "इंदौर में 1 अक्टूबर से दूध के दाम 62 से 65 रुपए प्रति लीटर", "status": "verified",
            "reason": "verified", "region": "इंदौर", "context": "", "effective_date": "2026-10-01", "change": 0.048}
    st = {"cards": [{"url": url, "domain": "prabhatkhabar.com", "title": "बोकारो", "published": "2026-09-27",
                     "claims": [bad]},
                    {"url": "https://navbharattimes.indiatimes.com/b", "domain": "navbharattimes.indiatimes.com",
                     "title": "Indore Milk Price", "published": "2026-09-30", "claims": [good]}],
          "corroboration": [], "events": [{"kind": "rail"}, {"kind": "milk"}]}
    before, after = RD.reclassify(st)
    assert [e["kind"] for e in before] == ["rail", "milk"]
    assert bad["status"] == "rejected" and bad["status_before_r2"] == "verified" and bad["states"] == ["jharkhand"]
    assert [(e["kind"], e["states"]) for e in after] == [("milk", ["madhya pradesh"])]
    assert st["reclassified"]["credits"] == 0
