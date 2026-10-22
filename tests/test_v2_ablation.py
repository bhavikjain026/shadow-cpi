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
