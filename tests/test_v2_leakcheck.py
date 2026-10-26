"""Leak checks P and E (v2/LEAKCHECK_PREREG.md): sample, span rule, date detector, population and saved text, runs
with fake Tavily, labels and metrics. Offline, no calls (saved results and cached responses only)."""
import json
from pathlib import Path

import pytest

from shadow_cpi.budget import BudgetExceeded
from v2 import leakcheck as LC

ROOT = Path(__file__).resolve().parent.parent
PREREG = ROOT / "v2" / "LEAKCHECK_PREREG.md"


# ---------- Check E: sample and span ----------
def test_sample_is_seeded_forty_and_matches_the_prereg():
    cases = LC.sample()
    assert len(cases) == 40 and len({c["id"] for c in cases}) == 40 and cases == LC.sample()
    assert cases == json.loads(LC.CASES.read_text())["cases"]
    rows = [line.split("|") for line in PREREG.read_text().splitlines() if line.startswith("| Q")]
    assert [r[1].strip() for r in rows] == [c["id"] for c in cases]
    assert [r[6].strip() for r in rows] == [c["span"].replace("|", "/") for c in cases]
    assert len(LC.pool()) == 53 and all(c["source"] != "radar" for c in cases)
    assert all(8 <= c["words"] <= 15 for c in cases)


def test_pool_drops_radar_and_repeated_quotes():
    rows = [{"source": "radar", "month": "2026-10", "quote": "a 5", "page_sha256": "x", "price": 5},
            {"source": "arm A", "month": "2026-04", "quote": "b 5", "page_sha256": "y", "price": 5},
            {"source": "arm B", "month": "2026-04", "quote": "b 5", "page_sha256": "y", "price": 5},
            {"source": "arm B", "month": "2026-05", "quote": "b 5", "page_sha256": "y", "price": 5}]
    p = LC.pool(rows)
    assert [(r["id"], r["source"], r["cutoff"]) for r in p] == [("Q001", "arm A", "2026-04-29"),
                                                                ("Q002", "arm B", "2026-05-29")]


def test_span_rule():
    words = " ".join(f"w{i}" for i in range(30))
    assert LC.span(words + " costs ₹65 now", 65) == (" ".join(f"w{i}" for i in range(17, 30)) + " costs ₹65", "price", 15)
    assert LC.span("Milk at Rs 1,250 per tin", 1250)[1] == "price"                 # commas inside the word ignored
    assert LC.span("fare goes from $7 to $7.25, and more", 7.25)[0] == "fare goes from $7 to $7.25, and more"
    assert LC.span("x " * 30 + "from $7 to $7.25", 7)[0] == "x " * 13 + "from $7"      # 7 is not 7.25
    assert LC.span("up 4 per cent", 9.5)[1] == "number"
    assert LC.span("# **Hike** in [tariff](https://x.in) of 6.12%", 6.12)[0] == "Hike in tariff of 6.12%"
    assert LC.plain(3.0) == "3" and LC.plain(7.25) == "7.25" and LC.plain(65) == "65"


# ---------- Check P: detector ----------
@pytest.mark.parametrize("line,iso", [
    ("on 2026-10-07 at noon", "2026-10-07"),
    ("dated 7/10/2026", "2026-10-07"),
    ("Updated: 7th Oct. 2026", "2026-10-07"),
    ("October 7, 2026 10:00 IST", "2026-10-07"),
    ("Sept 7 2026", "2026-09-07"),
    ("in November 2026", "2026-11-01"),
    ("७ अक्टूबर २०२६ को", "2026-10-07"),
    ("नवम्बर 2026 से", "2026-11-01"),
    ("फ़रवरी 2027", "2027-02-01"),
])
def test_each_date_form(line, iso):
    assert [d[2] for d in LC.find_dates(line)] == [iso]


def test_one_date_read_once_and_impossible_skipped():
    assert LC.find_dates("31/02/2026 and 2026-13-01") == []
    assert len(LC.find_dates("12 March 2026")) == 1                                  # not also "March 2026"
    assert LC.find_dates("we may 5 2026") == [("Month DD, YYYY", "may 5 2026", "2026-05-05")]  # a fixed-rule quirk
    assert LC.find_dates("Mayor said 2026 targets; marching on 2027") == []


def test_detect_ignores_listed_lines_and_the_cutoff_day():
    text = "\n".join(["© 2026-11-01 Times", "Copyright November 2026", "We use cookies (1 Dec 2026)",
                      "Page generated on 2026-12-01", "Published 29 May 2026", "Read next: June 3, 2026 story"])
    hits = LC.detect(text, "2026-05-29")
    assert [(h["line_no"], h["date"]) for h in hits] == [(5, "2026-06-03")] and "Read next" in hits[0]["context"]


# ---------- Check P: population and saved text (saved results and cached responses) ----------
def test_population_from_the_saved_results():
    units = LC.population()
    by = {s: [u for u in units if u["source"] == s] for s in "abc"}
    assert (len(by["a"]), len(by["b"]), len(by["c"])) == (51, 66, 20)
    assert len({u["url"] for u in by["b"]}) == 65 and all(u["page_file"] for u in by["c"])


@pytest.mark.skipif(not (ROOT / "cache" / "tavily").exists() or not (ROOT / "v2" / "evidence" / "pages").exists(),
                    reason="needs the local page cache (git-ignored: copyrighted article text)")
def test_saved_text_comes_from_the_date_tests_own_extracts_and_the_evidence_pages():
    units, texts = LC.population(), LC.date_test_texts()
    got = {s: sum(bool(LC.saved_text(u, texts)) for u in units if u["source"] == s) for s in "abc"}
    assert got == {"a": 46, "b": 0, "c": 20}


class FakeTav:
    """Extract returns text for every URL except those containing 'fail'; search answers from `answers`."""
    def __init__(self, cap_after=None, answers=None, error_for=None):
        self.calls, self.cap_after, self.answers, self.error_for = [], cap_after, answers or {}, error_for

    def _count(self, what):
        if self.cap_after is not None and len(self.calls) >= self.cap_after:
            raise BudgetExceeded("cap")
        self.calls.append(what)

    def extract(self, urls, **kw):
        self._count(("extract", tuple(urls), kw))
        ok = [u for u in urls if "fail" not in u]
        return {"results": [{"url": u, "raw_content": f"Story\nRelated: 3 June 2026 {u}"} for u in ok],
                "failed_results": [{"url": u} for u in urls if u not in ok], "usage": {"credits": 1},
                "request_id": "r-x"}, f"x{len(self.calls)}"

    def search(self, query, **kw):
        self._count(("search", query, kw))
        if self.error_for and self.error_for in query:
            raise RuntimeError("HTTP 500")
        arm = "dated" if "end_date" in kw else "undated"
        res = [{"url": u, "published_date": "2026-04-01"} for u in self.answers.get((query, arm), [])]
        return {"results": res, "usage": {"credits": 1}, "request_id": f"r{len(self.calls)}",
                "response_time": 0.5}, f"s{len(self.calls)}"


UNITS = [{"source": "a", "cutoff": "2026-05-29", "url": "https://a.in/1", "page_file": None},
         {"source": "b", "cutoff": "2026-05-29", "url": "https://b.in/1", "page_file": None},
         {"source": "b", "cutoff": "2026-05-29", "url": "https://b.in/fail", "page_file": None},
         {"source": "c", "cutoff": "2026-05-29", "url": "https://c.in/1", "page_file": "missing.txt"}]


def test_run_p_uses_saved_text_first_and_extracts_only_the_rest():
    tav = FakeTav()
    out = LC.run_p(tav, UNITS, dt_texts={"https://a.in/1": "Published 2 May 2026\nall good"})
    assert [c[1] for c in tav.calls] == [("https://b.in/1", "https://b.in/fail", "https://c.in/1")]
    assert tav.calls[0][2] == {"extract_depth": "basic", "tag": "leakcheck P extract"}
    u = {x["url"]: x for x in out["units"]}
    assert u["https://a.in/1"]["text_from"] == "saved" and not u["https://a.in/1"]["flagged"]
    assert u["https://b.in/1"]["flagged"] and u["https://b.in/fail"]["text_from"] == "no text"
    assert out["extract_calls"][0]["failed"] == ["https://b.in/fail"] and out["extract_calls"][0]["request_id"] == "r-x"
    m = LC.metrics_p(out)
    assert (m["b"]["units"], m["b"]["with_text"], m["b"]["no_text"], m["b"]["flagged"]) == (2, 1, 1, 1)
    assert m["b"]["later_content"] is None                                          # no labels yet


def test_run_p_cap_stops_cleanly_and_dry_run_sends_nothing():
    out = LC.run_p(FakeTav(cap_after=0), UNITS, dt_texts={})
    assert out["skipped"] and all(u["text_from"] == "no text" for u in out["units"])
    assert LC.run_p(None, UNITS, dt_texts={}, refetch=False)["extract_calls"] == []


def test_labels_precedence_missing_and_rates():
    out = LC.run_p(FakeTav(), UNITS, dt_texts={"https://a.in/1": "x\n1 June 2026\n2 June 2026"})
    a, b, c = (next(u for u in out["units"] if u["url"] == x) for x in ("https://a.in/1", "https://b.in/1",
                                                                         "https://c.in/1"))
    labels = {LC.key(a): {"1": {"label": "benign", "reason": "r"}, "2": {"label": "sidebar or related links",
                                                                         "reason": "r"}},
              LC.key(b): {"1": {"label": "later content", "reason": "r"}}}
    assert LC.check_labels(out, labels) == [(LC.key(c), 1)]
    labels[LC.key(c)] = {"1": {"label": "unclear", "reason": "r"}}
    assert LC.check_labels(out, labels) == []
    assert LC.unit_outcome(a, labels) == "sidebar or related links"
    m = LC.metrics_p(out, labels)
    assert m["b"]["later_content"] == 1 and m["b"]["later_content_wilson95"][1] == 1.0
    assert m["c"]["outcomes"]["unclear"] == 1
    out["built_utc"] = "2026-10-26T00:00:00"
    md = LC.report_p(out, labels)
    assert "Claude Code" in md and "https://b.in/1" in md and "| (b) finance check arm D | 2 | 1 | 1 (" in md


# ---------- Check E: run ----------
Q = [{"id": "Q001", "cutoff": "2026-04-29", "url": "https://www.src.in/a/", "span": "one two"},
     {"id": "Q002", "cutoff": "2026-04-29", "url": "https://src.in/b", "span": "three four"},
     {"id": "Q003", "cutoff": "2026-04-29", "url": "https://src.in/c", "span": "five six"},
     {"id": "Q004", "cutoff": "2026-04-29", "url": "https://src.in/d", "span": "seven eight"}]


def test_params_and_no_country():
    d, u = LC.params("dated", Q[0]), LC.params("undated", Q[0])
    assert d == {"exact_match": True, "search_depth": "basic", "max_results": 5, "include_published_date": True,
                 "end_date": "2026-04-29", "filter_by_published_date": True}
    assert u["filter_by_published_date"] is False and "end_date" not in u and "start_date" not in u
    assert "country" not in d and "topic" not in d


def test_run_e_outcomes_provenance_and_errors():
    answers = {('"one two"', "dated"): ["https://src.in/a"], ('"one two"', "undated"): ["https://src.in/a"],
               ('"three four"', "dated"): ["https://other.in/x"],
               ('"five six"', "undated"): ["https://src.in/c"]}
    tav = FakeTav(answers=answers, error_for="seven")
    out = LC.run_e(tav, Q)
    o = {q["id"]: q for q in out["cases"]}
    assert [o[i]["outcome"] for i in ("Q001", "Q002", "Q003", "Q004")] == [
        "found before cutoff", "found before cutoff", "found only without dates", "not run"]
    assert o["Q001"]["found_by"] == "the source page" and o["Q002"]["found_by"] == "another page only"
    assert all(s["request_id"] and len(s["response_sha256"]) == 64 for q in out["cases"] for s in q["searches"].values())
    assert {c[1] for c in tav.calls} >= {'"one two"', '"seven eight"'}                    # span in double quotes
    m = LC.metrics_e(out)
    assert (m["run"], m["not_run"], m["credits"]) == (3, 1, 6) and m["shares"]["found before cutoff"]["x"] == 2
    assert m["undated_finds_source"] == 2 and m["incomplete"]
    out["built_utc"] = "2026-10-26T00:00:00"
    md = LC.report_e(out)
    assert "| found before cutoff | 2 of 3 | 67% (" in md and "Not run:** 1" in md


def test_run_e_order_is_seeded_and_cap_stops_cleanly():
    a, b = LC.run_e(FakeTav(), Q), LC.run_e(FakeTav(), Q)
    assert [q["order"] for q in a["cases"]] == [q["order"] for q in b["cases"]]
    out = LC.run_e(FakeTav(cap_after=3), Q)
    assert [q["outcome"] for q in out["cases"]][1:] == ["not run"] * 3 and len(out["skipped"]) == 5


def test_results_run_once(tmp_path, monkeypatch):
    for name in ("OUT_P", "OUT_E"):
        p = tmp_path / f"{name}.json"
        p.write_text("{}")
        monkeypatch.setattr(LC, name, p)
    with pytest.raises(SystemExit, match="runs once"):
        LC.main(["P"])
    with pytest.raises(SystemExit, match="runs once"):
        LC.main(["E"])


def test_caps_are_in_the_budget_file():
    caps = json.loads((ROOT / "config" / "budget.json").read_text())["caps"]
    assert caps[LC.BUDGET_P] == 100 and caps[LC.BUDGET_E] == 100
