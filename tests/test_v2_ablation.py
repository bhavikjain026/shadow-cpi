"""Amendment E: model-written search parameters, code validation, Super fallback, the arm runner and the metrics.
Offline with fake Tavily and Nemotron, no calls."""
import pytest

from shadow_cpi.budget import BudgetExceeded
from v2 import ablation as AB
from v2 import ledger as LG

M = "2026-09"                                       # window 2026-08-22 to 2026-09-29


def good(lang="en", **kw):
    return {"query": "electricity tariff hike", "language": lang, "topic": "news", "start_date": "2026-08-25",
            "end_date": "2026-09-29", "include_domains": ["thehindu.com"], "include_domains_mode": "prefer",
            "max_results": 8, **kw}


def test_valid_search_passes_unchanged():
    s, fixes = AB.validate(good(), M, ["en", "hi"])
    assert fixes == [] and s["start_date"] == "2026-08-25" and s["include_domains"] == ["thehindu.com"]


def test_dates_are_clamped_to_the_window():
    s, fixes = AB.validate(good(start_date="2026-01-01", end_date="2026-10-15"), M, ["en"])
    assert (s["start_date"], s["end_date"]) == ("2026-08-22", "2026-09-29") and len(fixes) == 2
    s, _ = AB.validate(good(start_date="not a date", end_date=None), M, ["en"])
    assert (s["start_date"], s["end_date"]) == ("2026-08-22", "2026-09-29")
    s, fixes = AB.validate(good(start_date="2026-09-20", end_date="2026-09-01"), M, ["en"])
    assert (s["start_date"], s["end_date"]) == ("2026-08-22", "2026-09-29") and "after end" in fixes[-1]


def test_allowed_values_only():
    s, fixes = AB.validate(good(topic="finance", include_domains_mode="only", max_results=50), M, ["en"])
    assert (s["topic"], s["include_domains_mode"], s["max_results"]) == ("news", "prefer", 10) and len(fixes) == 3
    assert AB.validate(good(lang="ta"), M, ["en", "hi"])[0] is None              # language not in the arm
    assert AB.validate(good(query="  "), M, ["en"])[0] is None
    assert AB.validate(good(query="x" * 401), M, ["en"])[0] is None


def test_domains_cleaned_and_capped_at_20():
    doms = ["https://www.TheHindu.com/news", "not a domain", "thehindu.com"] + [f"site{i}.in" for i in range(25)]
    s, fixes = AB.validate(good(include_domains=doms), M, ["en"])
    assert s["include_domains"][0] == "thehindu.com" and len(s["include_domains"]) == 20
    assert any("invalid or repeated" in f for f in fixes) and any("first 20" in f for f in fixes)


def test_select_meets_language_minimums_first():
    valid = [AB.validate(good(lang=l), M, ["en", "hi"])[0] for l in ["en"] * 6 + ["hi"] * 3]
    picked, complete = AB.select(valid, "B")
    assert len(picked) == 8 and complete and sum(p["language"] == "hi" for p in picked) == 3
    picked, complete = AB.select(valid[:6], "B")                                  # no Hindi: incomplete
    assert not complete


class FakeNem:
    def __init__(self, plans, events=None):
        self.plans, self.events, self.asked = plans, events or {}, []

    def chat_json(self, model, system, user, schema=None, **kw):
        if "plan" in (kw.get("tag") or ""):
            self.asked.append(model)
            p = self.plans[model]
            if isinstance(p, Exception):
                raise p
            return {"searches": p}, f"{model}-plan"
        return {"english": ""}, "gloss"

    def price_events(self, model, text, **kw):
        return self.events.get(text.split("\n")[0], []), "read"


def test_super_writes_the_plan_when_nano_fails():
    sup = [good(lang=l) for l in ["en"] * 4 + ["hi"] * 4]
    nem = FakeNem({"nano": ValueError("model returned no JSON object"), "super": sup})
    picked, complete, tries = AB.write_plan(nem, M, "B", "nano", "super", "t")
    assert nem.asked == ["nano", "super"] and complete and {p["written_by"] for p in picked} == {"super"}
    nem = FakeNem({"nano": sup, "super": AssertionError("not asked")})
    picked, complete, _ = AB.write_plan(nem, M, "B", "nano", "super", "t")
    assert nem.asked == ["nano"] and {p["written_by"] for p in picked} == {"nano"}


def test_tavily_params_language_only_for_hindi_and_no_empty_domains():
    s, _ = AB.validate(good(lang="hi", include_domains=[]), M, ["en", "hi"])
    p = AB.tavily_params(s)
    assert p["language"] == "hi" and "include_domains" not in p and p["search_depth"] == "basic"
    assert "language" not in AB.tavily_params(AB.validate(good(), M, ["en"])[0])


LINE = "Electricity tariff up 6.83% from September 1 in Jammu and Kashmir"


class FakeTav:
    used = 0

    def __init__(self, cap_after=None):
        self.n, self.cap_after = 0, cap_after

    def search(self, query, **kw):
        self.n += 1
        if self.cap_after is not None and self.n > self.cap_after:
            raise BudgetExceeded("budget 'v2-ablation-B': cap")
        return {"results": [{"url": f"https://x.in/{self.n}", "title": "JK power", "content": LINE,
                             "published_date": "2026-08-24"}], "usage": {"credits": 1}, "response_time": 1.5}, "sid"

    def extract(self, urls, **kw):
        return {"results": [{"url": u, "raw_content": "Published: Aug 24, 2026, 09:00\n" + LINE} for u in urls],
                "usage": {"credits": 1}, "response_time": 3.0}, "eid"


def test_arm_b_month_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setattr(LG.save_page, "__defaults__", (tmp_path / "pages",))
    plan = [good(lang=l) for l in ["en"] * 4 + ["hi"] * 4]
    ev = [{"quote": LINE, "line": LINE, "new_price": 6.83, "pct_change": 6.83, "effective_date": "2026-09-01",
           "region": "Jammu and Kashmir"}]
    nem = FakeNem({"nano": plan}, {"JK power": ev})
    meter = AB.Meter(FakeTav(cap_after=6))
    out = AB.run_month("B", M, meter, nem, "nano", "super")
    assert len(out["plan"]) == 8 and out["plan"][0]["sent"]["include_domains"] == ["thehindu.com"]
    assert len(out["skipped"]) == 2 and not out["complete"]                      # stopped cleanly at the cap
    assert meter.calls[0]["sent"]["query"] == "electricity tariff hike" and meter.calls[0]["credits"] == 1
    out["calls"] = meter.calls
    m = AB.metrics([out], reference=[{"id": "E9", "kind": "electricity", "month": M, "date": "2026-09-01",
                                      "states": ["jammu and kashmir"], "v1": "MISSED"}])
    assert m["recall"] == 1 and m["false_events_upper_bound"] == 0 and m["verified_events"] == 1
    assert m["credits"] == 6 + 2 and m["credits_per_verified_event"] == 8 and m["median_latency_s"] == 1.5
    assert m["incomplete_months"] == [M]


def test_each_arm_runs_once(tmp_path, monkeypatch):
    monkeypatch.setattr(AB, "OUT", tmp_path)
    (tmp_path / "arm_B_2026-01.json").write_text("{}")
    with pytest.raises(SystemExit, match="runs once"):
        AB.run("B", ["2026-01"])


def test_metrics_computed_once(tmp_path, monkeypatch):
    p = tmp_path / "v2_ablation.json"
    p.write_text("{}")
    monkeypatch.setattr(AB, "RESULTS", p)
    with pytest.raises(SystemExit, match="computed once"):
        AB.summarise()


def test_diagnostics_and_structured_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(LG.save_page, "__defaults__", (tmp_path / "pages",))
    plan = [good(lang=l) for l in ["en"] * 4 + ["hi"] * 4] + [good(lang="ta")]
    nem = FakeNem({"nano": plan}, {"JK power": [{"quote": LINE, "line": LINE, "new_price": 6.83, "pct_change": 6.83,
                                                  "effective_date": "2026-09-01", "region": "Jammu and Kashmir"}]})
    meter = AB.Meter(FakeTav())
    out = AB.run_month("B", M, meter, nem, "nano", "super")
    out["calls"] = meter.calls
    bodies = [{"query": c["sent"]["query"], **{k: v for k, v in c["sent"].items() if k != "query"},
               "include_usage": True} for c in meter.calls if c["endpoint"] == "/search"]
    d = AB.diagnostics([out], bodies)
    assert d["searches_dropped_by_code"] == 1 and d["plan_retries_super"] == 0 and d["plan_abstentions"] == 0
    assert d["duplicate_verified_claims"] == 7                  # 8 pages, the same change: one event
    sf = d["structured_fields"]
    assert sf["searches_checked"] == 8 and sf["with_dates_as_fields"] == 8 and sf["hindi_with_language_field"] == 4
    assert sf["with_domains_as_fields"] == 8 and sf["parameter_names_inside_query_text"] == 0


def test_arm_t_sends_b_queries_with_auto_parameters_only(tmp_path, monkeypatch):
    import json
    monkeypatch.setattr(LG.save_page, "__defaults__", (tmp_path / "pages",))
    monkeypatch.setattr(AB, "OUT", tmp_path)
    plan = [{**AB.validate(good(lang=l, query=f"q{i}"), M, ["en", "hi"])[0], "written_by": "nano", "corrections": []}
            for i, l in enumerate(["en"] * 4 + ["hi"] * 4)]
    (tmp_path / f"arm_B_{M}.json").write_text(json.dumps({"plan": plan}))

    class AutoTav(FakeTav):
        def search(self, query, **kw):
            resp, sid = super().search(query, **kw)
            return {**resp, "auto_parameters": {"topic": "news", "search_depth": "advanced"},
                    "request_id": f"r{self.n}"}, sid
    meter = AB.Meter(AutoTav())
    out = AB.run_month("T", M, meter, FakeNem({}), "nano", "super")
    sent = [c["sent"] for c in meter.calls if c["endpoint"] == "/search"]
    assert [x["query"] for x in sent] == [f"q{i}" for i in range(8)]
    assert all(set(x) == {"query", "auto_parameters", "max_results"} and x["auto_parameters"] is True for x in sent)
    assert meter.calls[0]["auto_parameters"]["search_depth"] == "advanced" and meter.calls[0]["request_id"] == "r1"
    assert len(meter.calls[0]["response_sha256"]) == 64 and out["plan"][0]["auto_parameters"]["topic"] == "news"


def test_equivalence_margin_and_ranking():
    arms = {"A": {"recall": 6, "credits_per_verified_event": 20.0, "false_events_upper_bound": 3},
            "B": {"recall": 5, "credits_per_verified_event": 10.0, "false_events_upper_bound": 1},
            "C": {"recall": 7, "credits_per_verified_event": 30.0, "false_events_upper_bound": 2},
            "T": {"recall": 4, "credits_per_verified_event": 5.0, "false_events_upper_bound": 0}}
    eq = AB.equivalence(arms)
    assert eq["top_group"] == ["A", "C"] and eq["ranking"] == ["A", "C"] and eq["lower_recall"] == ["B", "T"]


def test_tavily_auto_parameters_leaves_depth_to_tavily_and_is_budgeted_at_2():
    from shadow_cpi.budget import call_cost
    from shadow_cpi.tavily import Tavily
    seen = {}

    class Rec:
        def call(self, service, endpoint, body, fn, parent=None, tag=None):
            seen.update(body)
            return {}, "id"
    Tavily(api_key="test", recorder=Rec()).search("q", auto_parameters=True, max_results=10)
    assert "search_depth" not in seen and seen["auto_parameters"] is True
    assert call_cost("/search", {"query": "q", "auto_parameters": True}) == 2


def test_recorder_stores_request_id_and_response_sha256(tmp_path):
    import json
    from shadow_cpi.recorder import Recorder, response_sha256
    rec = Recorder(cache_dir=tmp_path / "c", log_file=tmp_path / "log.jsonl")
    resp = {"request_id": "abc", "results": [], "usage": {"credits": 1}}
    rec.call("tavily", "/search", {"query": "q"}, lambda: resp)
    e = json.loads((tmp_path / "log.jsonl").read_text())
    assert e["request_id"] == "abc" and e["response_sha256"] == response_sha256(resp)
    assert rec.provenance[0]["request_id"] == "abc" and rec.provenance[0]["service"] == "tavily"
    assert response_sha256({"b": 1, "a": 2}) == response_sha256({"a": 2, "b": 1})


def test_reconcile_counts_events_matches_and_provenance(tmp_path, monkeypatch):
    monkeypatch.setattr(LG.save_page, "__defaults__", (tmp_path / "pages",))
    plan = [good(lang=l) for l in ["en"] * 4 + ["hi"] * 4]
    ev = [{"quote": LINE, "line": LINE, "new_price": 6.83, "pct_change": 6.83, "effective_date": "2026-09-01",
           "region": "Jammu and Kashmir"}]
    meter = AB.Meter(FakeTav())
    out = AB.run_month("B", M, meter, FakeNem({"nano": plan}, {"JK power": ev}), "nano", "super")
    out["calls"] = meter.calls
    ref = [{"id": "E9", "kind": "electricity", "month": M, "date": "2026-09-01", "states": ["jammu and kashmir"]}]
    r = AB.reconcile([out], ref)
    assert (r["verified_claims"], r["events"], r["matched_events"], r["unmatched_events"], r["recall"]) == (8, 1, 1, 0, 1)
    assert r["search_calls"] == 8 and r["calls"] == 10 and r["credits"] == 10
    r = AB.reconcile([out], [{**ref[0], "states": ["punjab"]}])
    assert r["unmatched_events"] == 1 and r["unmatched"][0]["url"].startswith("https://x.in/")


def test_arm_t_dates_sends_window_with_auto_and_records_if_kept(tmp_path, monkeypatch):
    import json
    monkeypatch.setattr(LG.save_page, "__defaults__", (tmp_path / "pages",))
    monkeypatch.setattr(AB, "OUT", tmp_path)
    plan = [{**AB.validate(good(lang="en", query=f"q{i}"), M, ["en"])[0], "written_by": "nano", "corrections": []}
            for i in range(8)]
    (tmp_path / f"arm_B_{M}.json").write_text(json.dumps({"plan": plan}))

    class AutoTav(FakeTav):
        def search(self, query, **kw):
            resp, sid = super().search(query, **kw)
            return {**resp, "auto_parameters": {"topic": "news", "search_depth": "advanced"}}, sid
    meter = AB.Meter(AutoTav())
    out = AB.run_month("Td", M, meter, FakeNem({}), "nano", "super")
    sent = meter.calls[0]["sent"]
    assert set(sent) == {"query", "auto_parameters", "max_results", "start_date", "end_date"}
    assert (sent["start_date"], sent["end_date"]) == ("2026-08-22", "2026-09-29")
    assert out["plan"][0]["dates_kept"] == {"auto_time_range": None, "auto_start_date": None, "auto_end_date": None,
                                            "dated_results": 1, "inside_window": 1}
