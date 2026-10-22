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
    assert tav.last["include_domains"] == ["derc.gov.in"] and tav.last["include_domains_mode"] == "restrict"
    assert s["corroboration"][0]["domain"] == "derc.gov.in"
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
