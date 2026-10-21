import json

import pytest

from shadow_cpi import cpi_math as M
from shadow_cpi import seal as S
from shadow_cpi.recorder import Recorder, credits_used, read_log
from shadow_cpi.tavily import Tavily, results_in_window
from shadow_cpi.nemotron import Nemotron, parse_json
from shadow_cpi.http import ApiError
from shadow_cpi.verify import (dedupe_quotes, geometric_mean_change, in_month, norm, quote_on_page,
                               to_base_unit)


# ---------- maths ----------
def test_aggregate_is_weighted_mean_of_levels():
    assert M.aggregate({"a": 100, "b": 200}, {"a": 3, "b": 1}) == pytest.approx(125)


def test_level_aggregation_differs_from_averaging_percent_changes():
    prev = {"food": 150.0, "rest": 100.0}
    w = {"food": 40, "rest": 60}
    ch = {"food": 0.10, "rest": 0.0}
    head_prev = M.aggregate(prev, w)
    head_now = M.aggregate({k: prev[k] * (1 + ch[k]) for k in prev}, w)
    true_mom = head_now / head_prev - 1
    naive = sum(w[k] * ch[k] for k in w) / 100
    assert true_mom == pytest.approx(0.05)      # food's effective weight is larger: 40*150/(120) share
    assert naive == pytest.approx(0.04)
    assert true_mom != pytest.approx(naive)


def test_residual_carve_out_reproduces_subgroup():
    # vegetables subgroup weight 6 at level 120; onion weight 1 at level 200
    lvl, w_res = M.residual_level(120.0, 6.0, {"onion": 200.0}, {"onion": 1.0})
    assert w_res == pytest.approx(5.0)
    assert M.aggregate({"onion": 200.0, "res": lvl}, {"onion": 1.0, "res": w_res}) == pytest.approx(120.0)


def test_carve_out_limits_item_spike():
    series = {"veg": {"2026-09": 120.0}, "onion": {"2026-09": 200.0}, "other": {"2026-09": 110.0}}
    sw = {"veg": 6.0, "other": 94.0}
    comps = M.build_components("2026-09", series, sw, {"veg": {"onion": 1.0}})
    assert set(comps) == {"onion", "veg#residual", "other"}
    head_prev = M.aggregate({c: v[0] for c, v in comps.items()}, {c: v[1] for c, v in comps.items()})
    head, pred = M.predict_headline(comps, {"onion": 0.30}, {})
    # only onion's own weight moves: 1*200*0.3 / (6*120 + 94*110) = 60/11060
    assert head / head_prev - 1 == pytest.approx(60 / 11060)
    cov = M.coverage(pred)
    assert cov["observed"] == pytest.approx(0.01)


def test_contributions_sum_to_headline_yoy():
    now = {"a": 110.0, "b": 103.0}
    ago = {"a": 100.0, "b": 100.0}
    w = {"a": 30, "b": 70}
    head = M.yoy(M.aggregate(now, w), M.aggregate(ago, w))
    assert sum(M.contributions_yoy(now, ago, w).values()) == pytest.approx(head)


def test_months_and_b1():
    assert M.add_months("2026-01", -1) == "2025-12"
    assert M.add_months("2025-12", 13) == "2027-01"
    hs = {"2025-08": 100.0, "2026-08": 104.0}
    assert M.b1_last_yoy(hs, "2026-09") == pytest.approx(4.0)


def test_trend_change_seasonal_blend():
    s = {}
    lvl = 100.0
    for m in range(1, 13):  # 2025: flat except +3% in April (fee season)
        s[f"2025-{m:02d}"] = lvl
        if m == 3:
            lvl *= 1.03
    lvl26 = s["2025-12"]
    for m in range(1, 4):
        lvl26 *= 1.002
        s[f"2026-{m:02d}"] = lvl26
    # predicting April 2026: drift ~0.2% plus half of April's seasonal bump above the 2025 mean
    t = M.trend_change(s, "2026-04")
    april25 = s["2025-04"] / s["2025-03"] - 1
    assert t > 0.002 and t == pytest.approx(0.002 + 0.5 * (april25 - (april25 / 11)), rel=1e-6)


# ---------- verification ----------
def test_quote_on_page_rules():
    page = "Onion prices in Delhi rose to ₹56 per kg on Tuesday, traders said."
    assert quote_on_page("onion prices in Delhi rose to ₹56 per kg", page)
    assert not quote_on_page("", page)                       # empty quote never passes
    assert not quote_on_page("rose to", page)                # too short to prove anything
    assert not quote_on_page("Onion prices in Mumbai rose to ₹56 per kg", page)


def test_quote_on_page_hindi():
    page = "दिल्ली में प्याज के दाम बढ़कर 56 रुपये प्रति किलो हो गए हैं।"
    assert quote_on_page("प्याज के दाम बढ़कर 56 रुपये प्रति किलो", page)


def test_units():
    assert to_base_unit(5600, "quintal") == (56.0, "kg")
    assert to_base_unit(14, "250g") == (56.0, "kg")
    assert to_base_unit(56, "Rs/kg") == (56.0, "kg")
    assert to_base_unit(30, "500 ml".replace(" ", "")) == (60.0, "litre")
    assert to_base_unit(1, "bushel") == (None, None)


def test_dates_dedupe_geomean():
    assert in_month("2026-10-03", "2026-10") and not in_month("2026-11-01", "2026-10")
    qs = [{"quote": "Onion ₹56/kg in Delhi"}, {"quote": "onion  ₹56/kg in delhi"}, {"quote": "Tomato ₹40"}]
    assert len(dedupe_quotes(qs)) == 2
    assert geometric_mean_change([(110, 100), (121, 110)]) == pytest.approx(0.10)
    assert geometric_mean_change([]) is None


# ---------- recorder, Tavily, Nemotron (fake network) ----------
def test_tavily_cache_and_flight_recorder(tmp_path):
    calls = []

    def fake(method, url, token, body, timeout):
        calls.append((url, body))
        return {"results": [{"url": "u1", "published_date": "2026-03-10"},
                            {"url": "u2", "published_date": "2026-04-02"}, {"url": "u3"}],
                "usage": {"credits": 1}}

    rec = Recorder(tmp_path / "cache", tmp_path / "log.jsonl")
    t = Tavily(api_key="tvly-test", recorder=rec, transport=fake)
    r1, _ = t.search("onion price", topic="news", start_date="2026-03-01", end_date="2026-03-31")
    r2, _ = t.search("onion price", topic="news", start_date="2026-03-01", end_date="2026-03-31")
    assert len(calls) == 1                               # second call served from cache
    assert calls[0][1]["include_usage"] is True and calls[0][1]["search_depth"] == "basic"
    log = read_log(tmp_path / "log.jsonl")
    assert [e["cached"] for e in log] == [False, True]
    assert credits_used(log) == 1
    assert "tvly-test" not in (tmp_path / "log.jsonl").read_text()     # key never written
    inside, outside, undated = results_in_window(r1["results"], "2026-03-01", "2026-03-31")
    assert [len(inside), len(outside), len(undated)] == [1, 1, 1]


def test_results_in_window_reads_news_date_format():
    res = [{"published_date": "Tue, 24 Mar 2026 14:00:00 GMT"}, {"published_date": "Wed, 01 Apr 2026 00:00:00 GMT"},
           {"published_date": "not a date"}, {}]
    inside, outside, undated = results_in_window(res, "2026-03-01", "2026-03-31")
    assert [len(inside), len(outside), len(undated)] == [1, 1, 2]


def test_extract_or_download_falls_back_and_logs(tmp_path, monkeypatch):
    import io
    import urllib.request
    rec = Recorder(tmp_path / "c", tmp_path / "l.jsonl")
    fail = {"results": [], "failed_results": [{"url": "u", "error": "Failed to fetch url"}]}
    t = Tavily(api_key="k", recorder=rec, transport=lambda *a: fail)
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: io.BytesIO(b"<td>Onion</td><td>30</td>"))
    text, route = t.extract_or_download("https://govt.example/prices")
    assert route == "direct" and "Onion" in text
    assert [e["service"] for e in read_log(tmp_path / "l.jsonl")] == ["tavily", "direct"]


def test_extract_always_has_failed_results(tmp_path):
    rec = Recorder(tmp_path / "c", tmp_path / "l.jsonl")
    t = Tavily(api_key="k", recorder=rec, transport=lambda *a: {"results": [{"url": "a", "raw_content": "x"}]})
    resp, _ = t.extract(["a", "b"])
    assert resp["failed_results"] == []


def test_nemotron_schema_fallback(tmp_path):
    seen = []

    def fake(method, url, token, body, timeout):
        seen.append(body["response_format"]["type"])
        if body["response_format"]["type"] == "json_schema":
            raise ApiError(400, "schema not supported")
        return {"choices": [{"message": {"content": '<think>x</think>{"quotes": []}'}}]}

    n = Nemotron(api_key="k", recorder=Recorder(tmp_path / "c", tmp_path / "l.jsonl"), transport=fake)
    q, _ = n.price_quotes("nvidia/some-model", "page text")
    assert q == [] and seen == ["json_schema", "json_object"]


def test_parse_json():
    assert parse_json('text {"a": 1} more') == {"a": 1}
    with pytest.raises(ValueError):
        parse_json("no json here")


# ---------- seal ----------
def test_seal_and_verify(tmp_path):
    d = S.seal("2026-10", {"prediction": 5.31, "range": [5.0, 5.6]}, seal_dir=tmp_path)
    assert len(d) == 64 and S.verify("2026-10", seal_dir=tmp_path)
    p = tmp_path / "2026-10.json"
    data = json.loads(p.read_text())
    data["prediction"] = 5.5
    p.write_text(S.canonical(data))
    assert not S.verify("2026-10", seal_dir=tmp_path)    # any change breaks the fingerprint


def test_evidence_by_reference_and_url_dates():
    from shadow_cpi.verify import split_lines, number_lines, price_in_line, date_from_url
    from shadow_cpi.nemotron import _attach_lines
    page = "Delhi vegetable prices\n| Onion Big | ₹22 | ₹26 - ₹33 |\nदिल्ली में प्याज 56 रुपये प्रति किलो।"
    lines = split_lines(page)
    assert number_lines(lines).startswith("L1: Delhi vegetable prices")
    facts = _attach_lines([{"line": 2, "price": 22}, {"line": 3, "price": 56}, {"line": 3, "price": 99},
                           {"line": 40, "price": 1}], lines, "price")
    assert [f["verified"] for f in facts] == [True, True, False, False]
    assert facts[1]["quote"] == "दिल्ली में प्याज 56 रुपये प्रति किलो।"       # exact Hindi line, never translated
    assert price_in_line(1250, "LPG now Rs 1,250 per cylinder")
    assert date_from_url("https://m.economictimes.com/x/delhi-vegetable-price-today-13/03/2026-check/a.cms") == "2026-03-13"
    assert date_from_url("https://www.aajtak.in/story/tomato-dskc-2493034-2026-03-12") == "2026-03-12"
    assert date_from_url("https://www.manilatimes.net/2026/03/31/business/x") == "2026-03-31"
    assert date_from_url("https://example.com/news/onion") == ""
    from shadow_cpi.tavily import best_date
    assert best_date({"url": "https://x.com/2026/03/31/a", "published_date": "Tue, 24 Mar 2026 14:00:00 GMT"}) == ("2026-03-31", "url")
    assert best_date({"url": "https://x.com/a", "published_date": "Tue, 24 Mar 2026 14:00:00 GMT"}) == ("2026-03-24", "tavily")


def test_http_retries_read_timeouts(monkeypatch):
    import urllib.request
    from shadow_cpi import http as H
    calls = []

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, *a):
            return b'{"ok": true}'

    def fake_urlopen(req, timeout):
        calls.append(1)
        if len(calls) < 3:
            raise TimeoutError("The read operation timed out")
        return Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(H.time, "sleep", lambda s: None)
    assert H.request_json("POST", "https://x", "k", {}) == {"ok": True}
    assert len(calls) == 3
    calls.clear()
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout: (_ for _ in ()).throw(TimeoutError("t")))
    with pytest.raises(H.ApiError):
        H.request_json("POST", "https://x", "k", {}, retries=1)
