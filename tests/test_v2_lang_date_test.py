"""Language date test (v2/LANG_DATE_PREREG.md): sampling frame, arm parameters, Wayback retries, metrics, the
English comparison and the FEEDBACK trigger, with fake Tavily and Wayback responses. Offline, no calls."""
import json

import pytest

from v2 import kinds as K
from v2 import lang_date_test as LT


def test_sample_is_seeded_frozen_and_stratified():
    cases = LT.sample()
    assert cases == LT.sample() == json.loads(LT.CASES.read_text())["cases"]       # seeded and committed
    per = {l: sum(c["lang"] == l for c in cases) for l in LT.LANGS}
    assert per == {"hi": 4, "mr": 4, "ta": 4, "kn": 0, "bn": 0, "te": 0}           # kn/bn/te: none available
    assert len({c["id"] for c in cases}) == 12


def test_frame_language_by_state_only():
    f = {l: [r["id"] for r in v] for l, v in LT.frame().items()}
    assert "M7" not in sum(f.values(), []) and "T3" not in sum(f.values(), [])     # Kerala, Odisha: not eligible
    assert "M6" in f["hi"] and "M3" in f["hi"]                                     # Bihar+Jharkhand; national
    assert LT.lang_of(["maharashtra", "bihar"]) is None


def test_arm_params_differ_only_in_dates_and_filter_language_set():
    c = {"month": "2026-07", "cutoff": "2026-07-29", "lang": "ta"}
    a, cc = LT.arm_params("A", c), LT.arm_params("C", c)
    assert a["language"] == cc["language"] == "ta" and a["include_domains"] == K.DOMAINS["ta"]
    assert "start_date" not in a and a["filter_by_published_date"] is False
    assert (cc["start_date"], cc["end_date"], cc["filter_by_published_date"]) == ("2026-07-01", "2026-07-29", True)
    common = lambda p: {k: v for k, v in p.items() if k not in ("start_date", "end_date", "filter_by_published_date")}  # noqa: E731
    assert common(a) == common(cc) and a["max_results"] == 3 and "filter_by_language" not in a


def test_wayback_retries_only_failures():
    calls = []

    class Rec:
        def call(self, service, endpoint, body, fn, parent=None, tag=None):
            calls.append(1)
            if len(calls) < 3:
                raise OSError("down")
            return {"rows": [["timestamp"], ["20260701000000"]]}, "d"
    assert LT.wayback(Rec(), "https://x.in/a", sleep=lambda s: None) == ["2026-07-01"] and len(calls) == 3


class FakeTav:
    def __init__(self, late_in_c=False):
        self.searches, self.extracts, self.late_in_c = [], [], late_in_c

    def search(self, query, **kw):
        self.searches.append(kw)
        res = [{"url": "https://x.in/2026/07/10/paal", "title": "பால் விலை உயர்வு", "content": "",
                "published_date": "2026-07-10"}]
        if "start_date" not in kw or self.late_in_c:
            res.append({"url": "https://x.in/2026/08/05/paal-late", "title": "பால்", "content": "",
                        "published_date": "2026-08-05"})
        return {"results": res, "usage": {"credits": 1}, "response_time": 1.0, "request_id": "r"}, "sid"

    def extract(self, urls, **kw):
        self.extracts.append(list(urls))
        return {"results": [{"url": u, "raw_content": "Published: July 10, 2026"} for u in urls],
                "usage": {"credits": 1}, "response_time": 2.0}, "eid"


class FakeRec:
    def call(self, service, endpoint, body, fn, parent=None, tag=None):
        assert service == "direct"
        late = "paal-late" in body["url"]
        return {"rows": [["timestamp"], ["20260810000000" if late else "20260711000000"]]}, "d"


def english(rows=None):
    r = {"url": "https://e.in/2026/07/10/milk", "tavily_date": "2026-07-10", "label": "P", "on_topic": True,
         "page_date": "2026-07-10"}
    return {"rows": rows or [{"id": "M8", "month": "2026-07", "cutoff": "2026-07-29",
                              "arms": {a: {"results": [dict(r)], "credits": 1, "response_time": 1.0}
                                       for a in "ABCD"}}]}


def run_one(late_in_c=False):
    cases = [LT.case({"id": "M8", "kind": "milk", "month": "2026-07", "states": ["tamil nadu"]}, "ta")]
    tav = FakeTav(late_in_c)
    out = LT.run(tav, FakeRec(), cases, sleep=lambda s: None)
    return tav, out, LT.metrics(out, english())


def test_full_run_with_fakes():
    tav, out, m = run_one()
    row = out["rows"][0]
    assert set(row["arms"]) == {"A", "C", "D"} and len(tav.searches) == 2
    assert all(s["language"] == "ta" for s in tav.searches)
    assert sum(len(u) for u in tav.extracts) == 2                                  # each unique URL once
    assert {r["url"][-9:]: r["label"] for r in row["arms"]["A"]["results"]} == {"7/10/paal": "P", "paal-late": "L"}
    assert m["arms"]["A"]["leak_cases"] == 1 and m["arms"]["C"]["leak_cases"] == 0
    assert m["arms"]["A"]["outside_window"] == 1 and m["arms"]["C"]["outside_window"] == 0
    assert m["by_lang"]["ta"]["C"]["valid_total"] == 1                             # Tamil topic word counts
    assert m["paired_with_english"]["A"] == {"english_only": 0, "language_only": 1, "p_exact": 1.0}
    assert m["differs_from_english"] == []
    md = LT.report(m, "2026-10-27T00:00")
    assert "pilot" in md.lower() and "English (date test)" in md and "no pre-registered difference" in md


def test_feedback_trigger_when_filter_leaks():
    _, _, m = run_one(late_in_c=True)
    assert any("outside the window" in w for w in m["differs_from_english"])
    assert any("confirmed-leak" in w for w in m["differs_from_english"])


def test_runs_once(tmp_path, monkeypatch):
    p = tmp_path / "lang_date_test.json"
    p.write_text("{}")
    monkeypatch.setattr(LT, "OUT", p)
    monkeypatch.setattr("sys.argv", ["x"])
    with pytest.raises(SystemExit, match="runs once"):
        LT.main()
