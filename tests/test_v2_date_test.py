"""Date field test (v2/DATE_TEST_PREREG.md): sampling, arm parameters, page date, labels, statistics and a full run
with fake Tavily and Wayback responses. Offline, no calls."""
import json
from pathlib import Path

import pytest

from v2 import date_test as DT

ROOT = Path(__file__).resolve().parent.parent


def test_sample_is_seeded_frozen_and_twenty():
    cases = DT.sample()
    assert len(cases) == 20 and len({c["id"] for c in cases}) == 20
    assert cases == DT.sample()                                           # same seed, same cases
    assert cases == json.loads(DT.CASES.read_text())["cases"]             # matches the committed file
    per = {m: sum(c["month"] == m for c in cases) for m in DT.MONTHS_FULL + DT.MONTHS_ALL}
    assert per["2026-07"] == per["2026-09"] == 3 and all(per[m] >= 4 for m in DT.MONTHS_FULL)


def test_arm_params_differ_only_in_dates_and_filter():
    c = {"month": "2026-05", "cutoff": "2026-05-29"}
    a, b, cc = (DT.arm_params(x, c) for x in "ABC")
    assert "start_date" not in a and a["filter_by_published_date"] is False
    assert (b["start_date"], b["end_date"], b["filter_by_published_date"]) == ("2026-05-01", "2026-05-29", False)
    assert cc["filter_by_published_date"] is True
    common = lambda p: {k: v for k, v in p.items() if k not in ("start_date", "end_date", "filter_by_published_date")}  # noqa: E731
    assert common(a) == common(b) == common(cc) and a["max_results"] == 3 and a["include_published_date"] is True


def test_page_date_explicit_only_later_if_both_unknown_if_ambiguous():
    assert DT.page_date("Published: May 20, 2026 | Updated: 2026-06-02")[0] == "2026-06-02"
    assert DT.page_date("Posted on 12 May 2026")[0] == "2026-05-12"
    assert DT.page_date("Milk up Rs 2 on May 20, 2026")[0] is None                  # no published/updated word
    d, why = DT.page_date("Published: May 20, 2026 ... Published: May 25, 2026")
    assert d is None and "ambiguous" in why


def test_labels_never_use_the_page_date_for_a_leak():
    cut = "2026-05-29"
    assert DT.label(cut, ["2026-05-01", "2026-06-10"], None, None, None) == "P"
    assert DT.label(cut, ["2026-06-10"], "2026-06-05", None, None) == "L"
    assert DT.label(cut, ["2026-06-10"], None, None, "2026-06-05") == "F"          # page date alone: only a flag
    assert DT.label(cut, None, None, None, None) == "U"
    assert DT.label(cut, [], None, "2026-06-03", None) == "F"                      # no Wayback copy: not confirmed


def test_statistics():
    lo, hi = DT.wilson(0, 20)
    assert lo == 0 and 0.16 < hi < 0.17
    assert DT.mcnemar_exact(0, 0) == 1.0 and DT.mcnemar_exact(5, 0) == pytest.approx(0.0625)
    lf = DT.leak_fraction(["L", "P", "P", "F", "U"])
    assert lf["point"] == pytest.approx(1 / 3) and lf["lower"] == pytest.approx(0.2) and lf["upper"] == pytest.approx(0.6)


class FakeTav:
    def __init__(self):
        self.searches, self.extracts = [], []

    def search(self, query, **kw):
        self.searches.append(kw)
        res = [{"url": "https://x.in/2026/05/20/milk", "title": "milk hike", "content": "milk",
                "published_date": "2026-05-20"}]
        if "start_date" not in kw:                                              # arm A also gets a late page
            res.append({"url": "https://x.in/2026/06/05/milk-late", "title": "milk", "content": "milk",
                        "published_date": "2026-06-05"})
        return {"results": res, "usage": {"credits": 1}, "response_time": 1.2, "request_id": "r"}, "sid"

    def extract(self, urls, **kw):
        self.extracts.append(list(urls))
        pages = {"https://x.in/2026/05/20/milk": "Published: May 20, 2026\nmilk up",
                 "https://x.in/2026/06/05/milk-late": "Published: June 5, 2026\nmilk up"}
        return {"results": [{"url": u, "raw_content": pages[u]} for u in urls], "usage": {"credits": 1},
                "response_time": 2.0}, "eid"


class FakeRec:
    def call(self, service, endpoint, body, fn, parent=None, tag=None):
        assert service == "direct"
        caps = {"milk-late": [["timestamp"], ["20260610120000"]]}
        url = body["url"]
        return {"rows": next((v for k, v in caps.items() if k in url), [["timestamp"], ["20260521000000"]])}, "d"


def test_full_run_with_fakes():
    cases = [DT.case({"id": "M3", "kind": "milk", "month": "2026-05", "states": []})]
    tav = FakeTav()
    out = DT.run(tav, FakeRec(), cases)
    row = out["rows"][0]
    assert set(row["arms"]) == {"A", "B", "C", "D"} and len(tav.searches) == 3
    assert sum(len(u) for u in tav.extracts) == 2                                   # each unique URL once
    assert tav.extracts[0] == ["https://x.in/2026/05/20/milk"]                      # C's first (D's check)
    labels = {r["url"][-9:]: r["label"] for r in row["arms"]["A"]["results"]}
    assert labels == {"5/20/milk": "P", "milk-late": "L"}
    m = DT.metrics(out)
    assert m["arms"]["A"]["leak_cases"] == 1 and m["arms"]["C"]["leak_cases"] == 0
    assert m["arms"]["D"]["credits"] == 1 + 1 and m["arms"]["D"]["results"] == 1
    assert "pilot" in DT.report(m, "2026-10-30T00:00").lower()


def test_runs_once(tmp_path, monkeypatch):
    p = tmp_path / "date_field_test.json"
    p.write_text("{}")
    monkeypatch.setattr(DT, "OUT", p)
    monkeypatch.setattr("sys.argv", ["x"])
    with pytest.raises(SystemExit, match="runs once"):
        DT.main()


def test_unreadable_date_after_the_word_is_unknown_not_a_crash():
    assert DT.page_date("Published: Smarch 40, 2026")[0] is None                      # bug fix 2026-10-22
    assert DT.page_date("Updated: Foo 12, 2026 | Published: May 20, 2026")[0] == "2026-05-20"
