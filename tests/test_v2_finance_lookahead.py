"""Finance look-ahead check (v2/FINANCE_PREREG.md): labels, arms, metrics both ways. Offline: fake Tavily, no calls."""
import pytest

from v2 import date_test as DT
from v2 import finance_lookahead as F

RBI = F.event(F.EVENTS[4])        # R5, 2026-10-07, cutoff 2026-10-06
TCS = F.event(F.EVENTS[10])       # C6, TCS Q2 FY27, cutoff 2026-10-07


def res(title, content="", tdate=None, url="https://x.in/a", captures=None):
    return {"url": url, "title": title, "content": content, "tavily_date": tdate, "url_date": DT.url_date(url),
            "captures": captures}


def test_fixed_list_and_queries():
    assert len(F.EVENTS) == 14 and [e[0] for e in F.EVENTS][-1] == "C9" and F.FLAGGED == {
        "C4": "date from the board-meeting notice; no official outcome filing found"}
    assert RBI["query"] == "RBI monetary policy repo rate decision October 2026" and RBI["cutoff"] == "2026-10-06"
    assert TCS["query"] == "TCS Q2 FY27 quarterly results"
    assert F.arm_params("D", RBI)["start_date"] == "2026-09-07" and F.arm_params("D", RBI)["end_date"] == "2026-10-06"
    assert F.arm_params("D", RBI)["filter_by_published_date"] and not F.arm_params("N", RBI)["filter_by_published_date"]
    assert "start_date" not in F.arm_params("N", RBI)


def test_outcome_rules():
    assert F.states_outcome(RBI, "RBI hikes repo rate by 25 bps to 5.50%")
    assert not F.states_outcome(RBI, "RBI policy meet begins today, all eyes on the repo rate")
    assert F.states_outcome(TCS, "TCS Q2 FY27 results: net profit rises 5% to ₹12,000 crore")
    assert not F.states_outcome(TCS, "TCS Q1 FY27 results: net profit rises 5% to ₹12,000 crore")   # wrong quarter
    assert not F.states_outcome(TCS, "TCS to announce Q2 FY27 results on October 8")


def test_labels_confirmed_snippet_flag_valid():
    out = "RBI hikes repo rate to 5.50%"
    assert F.label(RBI, res(out, tdate="2026-10-07", captures=["2026-10-08"])) == "confirmed"
    assert F.label(RBI, res(out, tdate="2026-10-07", captures=["2026-10-01"])) == "snippet"   # Wayback has it earlier
    assert F.label(RBI, res(out, tdate="2026-10-07", captures=None)) == "snippet"             # lookup failed
    assert F.label(RBI, res("RBI governor speech", tdate="2026-10-09")) == "flag"
    assert F.label(RBI, res("RBI policy preview", tdate="2026-10-01", captures=["2026-10-02"])) == "valid"
    assert F.label(RBI, res(out, url="https://x.in/2026/10/07/rbi")) == "snippet"             # date from the address


class FakeTav:
    def __init__(self, cap_after=None):
        self.n, self.cap_after, self.sent = 0, cap_after, []

    def search(self, query, **kw):
        from shadow_cpi.budget import BudgetExceeded
        self.n += 1
        if self.cap_after is not None and self.n > self.cap_after:
            raise BudgetExceeded("cap")
        self.sent.append(kw)
        dated = "2026-10-07" if "start_date" not in kw else "2026-10-01"
        return {"request_id": f"r{self.n}", "usage": {"credits": 1}, "response_time": 1.0,
                "results": [{"url": f"https://x.in/{self.n}", "title": "RBI hikes repo rate to 5.50%", "content": "",
                             "published_date": dated}]}, f"s{self.n}"


def test_run_and_metrics_both_ways(monkeypatch):
    monkeypatch.setattr(DT, "wayback", lambda rec, url, tag=None: ["2026-10-08"])
    evs = [F.EVENTS[4], F.EVENTS[8]]                                       # R5 and C4
    out = F.run(FakeTav(), None, events=evs)
    assert all(a["request_id"] and len(a["response_sha256"]) == 64 for row in out["rows"] for a in row["arms"].values())
    m_all, m13 = F.metrics(out), F.metrics(out, drop=("C4",))
    assert m_all["events"] == 2 and m13["events"] == 1 and m13["dropped"] == ["C4"]
    assert m_all["arms"]["N"]["confirmed"]["events"] == 1 and m_all["arms"]["D"]["confirmed"]["events"] == 0
    assert m_all["mcnemar_confirmed"]["N_only"] == 1 and m_all["mcnemar_confirmed"]["p_exact"] == 1.0
    out["built_utc"] = "2026-10-25T00:00:00"
    out["metrics"] = {"all": m_all, "without_C4": m13}
    assert "13 events, without C4" in F.report(out)


def test_cap_stops_cleanly(monkeypatch):
    monkeypatch.setattr(DT, "wayback", lambda rec, url, tag=None: None)
    out = F.run(FakeTav(cap_after=3), None, events=F.EVENTS[:3])
    assert len(out["skipped"]) == 3 and "Incomplete" in F.report({**out, "built_utc": "x", "metrics": {
        "all": F.metrics(out), "without_C4": F.metrics(out, drop=("C4",))}})


def test_runs_once(tmp_path, monkeypatch):
    p = tmp_path / "f.json"
    p.write_text("{}")
    monkeypatch.setattr(F, "OUT", p)
    with pytest.raises(SystemExit, match="runs once"):
        F.main()
