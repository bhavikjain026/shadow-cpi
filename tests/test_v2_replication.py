"""Date test replication (v2/REPLICATION_PREREG.md): the case pool, sampling, arms, labels by case type, metrics,
the Wayback retry and the pooled secondary. Offline: fake Tavily and fake Wayback, no calls."""
import json
import re
from pathlib import Path

import pytest

from v2 import date_test as DT
from v2 import finance_lookahead as F
from v2 import replication as R

ROOT = Path(__file__).resolve().parent.parent


def test_pool_is_frozen_new_and_all_taken():
    cases, dropped = R.pool()
    frozen = json.loads(R.CASES.read_text())
    assert R.sample() == frozen["cases"] == R.sample()                    # same rule, same cases, matches the file
    assert len(cases) == frozen["eligible"] == 22 and len(frozen["cases"]) == 22   # fewer than 60: all taken
    assert len(dropped) == 108 and frozen["seed"] == R.SEED == 20261028
    pilot, tl = R.excluded()
    assert len(pilot) == 20 and len(tl) == 34
    ids = [c["id"] for c in cases]
    assert len(set(ids)) == 22 and not {c.get("ref") for c in cases} & (pilot | tl)
    assert sum(i.startswith("RR-") for i in ids) == 9 and sum(i.startswith("VE") for i in ids) == 13
    assert all(c["type"] == "price" for c in cases)                       # every finance event is in timelock34
    for c in cases:
        assert "2026-01-01" <= c["event_date"] <= "2026-09-30"
        assert c["cutoff"] < c["event_date"] and R.date.fromisoformat(c["event_date"]).toordinal() - \
            R.date.fromisoformat(c["cutoff"]).toordinal() == 1
        assert c["query"].startswith(R.WORDS[c["kind"]] + " ")


def test_prereg_table_lists_exactly_the_frozen_cases():
    text = (ROOT / "v2" / "REPLICATION_PREREG.md").read_text()
    rows = re.findall(r"^\| (RR-\w+|VE\d+) \| (\w+) \| ([\d-]+) \| ([\d-]+) \| ([\d-]+) → ([\d-]+) \| ([^|]+) \|", text, re.M)
    frozen = json.loads(R.CASES.read_text())["cases"]
    assert [(r[0], r[1], r[2], r[3], r[4], r[6].strip()) for r in rows] == [
        (c["id"], c["kind"], c["event_date"], c["cutoff"], R.arm_params("C", c)["start_date"], c["query"])
        for c in frozen]
    assert "**N = 60**" in text and "20261028" in text and "200" in text


def test_same_event_rule():
    a = {"kind": "lpg", "states": [], "date": "2026-03-07", "month": "2026-03"}
    assert R.same_event(a, {**a, "states": ["nct of delhi"], "date": "2026-03-08"})        # national overlaps all
    assert not R.same_event(a, {**a, "date": "2026-03-20"})                               # 13 days apart
    assert R.same_event(a, {**a, "date": "2026-03-14"})                                   # 7 days: same
    assert not R.same_event(a, {**a, "kind": "milk"})
    b = {"kind": "bus", "states": ["odisha"], "date": None, "month": "2026-06"}
    assert not R.same_event(b, {**b, "states": ["uttar pradesh"], "date": "2026-06-12"})  # no state in common
    assert R.same_event(b, {**b, "date": "2026-06-30"})                                   # no day: same month


def test_more_than_sixty_are_sampled_with_the_seed():
    many = [R.price_case(f"X{k:02d}", "test", "milk", [], f"2026-0{1 + k % 9}-{1 + k % 27:02d}") for k in range(70)]
    s = R.sample(cases=many)
    assert len(s) == 60 and s == R.sample(cases=many) and s != R.sample(seed=1, cases=many)
    assert s == sorted(s, key=lambda c: (c["event_date"], c["id"]))


def test_arms_and_credit_estimate():
    c = json.loads(R.CASES.read_text())["cases"][0]
    a, cc = R.arm_params("A", c), R.arm_params("C", c)
    assert "start_date" not in a and a["filter_by_published_date"] is False
    assert (cc["start_date"], cc["end_date"], cc["filter_by_published_date"]) == ("2025-12-02", "2025-12-31", True)
    common = lambda p: {k: v for k, v in p.items() if k not in ("start_date", "end_date", "filter_by_published_date")}  # noqa: E731
    assert common(a) == common(cc) == DT.BASE                             # the date test's parameters
    fin = {**F.event(F.EVENTS[0]), "type": "finance"}
    assert common(R.arm_params("C", fin)) == F.BASE and R.arm_params("C", fin)["start_date"] == F.arm_params(
        "D", fin)["start_date"]
    assert R.credit_estimate(json.loads(R.CASES.read_text())["cases"]) == 44
    assert json.loads((ROOT / "config" / "budget.json").read_text())["caps"]["replication"] == 200


def test_plan_mode_makes_no_calls(monkeypatch, capsys):
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: pytest.fail("network call in plan mode"))
    monkeypatch.setattr("sys.argv", ["replication", "--plan"])
    R.main()
    out = capsys.readouterr().out
    assert "eligible 22; fewer than 60, so all are taken" in out and "Credit estimate: 44" in out
    assert "Cap 'replication': 200" in out and len(re.findall(r"^(RR-|VE)\S+ +price +event", out, re.M)) == 22


# ---------- a full run with fakes ----------
CASE_P = R.price_case("RR-T", "test", "milk", ["maharashtra"], "2026-05-15")       # cutoff 2026-05-14
CASE_Q = R.price_case("VE99", "test", "lpg", [], "2026-07-01", url="https://x.in/src")  # cutoff 2026-06-30
CASE_F = {**F.event(F.EVENTS[1]), "id": "FE-R2", "type": "finance", "source": "test", "month": "2026-04"}


class FakeTav:
    """A: one post-cutoff page per case; C: one pre-cutoff page (or a post-cutoff one if c_leaks)."""
    def __init__(self, c_leaks=False, cap_after=None):
        self.n, self.c_leaks, self.cap_after, self.sent = 0, c_leaks, cap_after, []

    def search(self, query, tag="", **kw):
        from shadow_cpi.budget import BudgetExceeded
        self.n += 1
        if self.cap_after is not None and self.n > self.cap_after:
            raise BudgetExceeded("cap")
        self.sent.append((tag, kw))
        cut = kw.get("end_date")
        late = "start_date" not in kw or self.c_leaks
        day = "2026-12-01" if late else cut
        title = "RBI holds repo rate at 5.25%" if "RBI" in query else "Milk price hike Rs 2 per litre, LPG up"
        return {"request_id": f"r{self.n}", "usage": {"credits": 1}, "response_time": 1.0,
                "results": [{"url": f"https://x.in/{'late' if late else 'early'}/{tag.split()[1]}", "title": title,
                             "content": "", "published_date": day}]}, f"s{self.n}"


def fake_wayback(fail=()):
    calls = []

    def wb(rec, url, tag=""):
        calls.append((url, tag))
        if url in fail and "retry" not in tag:
            return None
        return ["2026-12-02"] if "/late/" in url else ["2026-01-01"]
    return wb, calls


def test_run_labels_by_case_type_and_c_holds(monkeypatch):
    wb, calls = fake_wayback()
    monkeypatch.setattr(DT, "wayback", wb)
    tav = FakeTav()
    out = R.run(tav, None, [CASE_P, CASE_Q, CASE_F])
    assert len(tav.sent) == 6 and {t.split()[2] for t, _ in tav.sent} == {"A", "C"}
    assert all("include_domains" in kw for t, kw in tav.sent if "FE-" not in t)            # price: date test's params
    assert all("include_domains" not in kw for t, kw in tav.sent if "FE-" in t)            # finance: finance params
    m = R.all_metrics(out)
    p, f = m["price"], m["finance"]
    assert (p["cases"], p["arms"]["A"]["leak_cases"], p["arms"]["C"]["leak_cases"]) == (2, 2, 0)
    assert (f["cases"], f["arms"]["A"]["leak_cases"], f["arms"]["C"]["leak_cases"]) == (1, 1, 0)   # never added
    assert p["a_vs_c_mcnemar"] == {"A_only": 2, "C_only": 0, "p_exact": 0.5} and p["c_leaks"] == []
    assert p["arms"]["A"]["valid_lost"] == 2 and p["arms"]["C"]["valid_lost"] == 0         # C's pages are valid
    assert all(r["label"] in "LP" for row in out["rows"] if row["type"] == "price"
               for a in row["arms"].values() for r in a["results"])
    out["built_utc"], out["metrics"] = "2026-11-01T00:00:00", m
    out["sensitivity"] = R.sensitivity(out)
    assert out["sensitivity"]["cases"] == 1                                               # RR- cases only
    out["pooled"] = R.pooled(m)
    md = R.report(out)
    assert "arm C leaked in **0 of 2** cases" in md and "Sensitivity" in md


def test_a_c_leak_is_in_the_headline_with_case_and_quote(monkeypatch):
    monkeypatch.setattr(DT, "wayback", fake_wayback()[0])
    out = R.run(FakeTav(c_leaks=True), None, [CASE_P, CASE_Q])
    out["built_utc"], out["metrics"] = "2026-11-01T00:00:00", R.all_metrics(out)
    out["pooled"] = R.pooled(out["metrics"])
    m = out["metrics"]["price"]
    assert m["arms"]["C"]["leak_cases"] == 2 and [x["case"] for x in m["c_leaks"]] == ["RR-T", "VE99"]
    head = "\n".join(R.headline(out["metrics"]))
    assert "arm C leaked in **2 of 2**" in head and "C leak, RR-T" in head and "Milk price hike" in head
    assert "first Wayback copy 2026-12-02" in head


def test_first_pass_is_primary_and_retry_is_once_by_the_logged_rule(monkeypatch):
    late = "https://x.in/late/RR-T"
    wb, calls = fake_wayback(fail={late})
    monkeypatch.setattr(DT, "wayback", wb)
    out = R.run(FakeTav(), None, [CASE_P])
    first = R.all_metrics(out)["price"]
    assert first["arms"]["A"]["leak_cases"] == 0 and first["arms"]["A"]["wayback_failed"] == 1   # unknown, not a leak
    waits = []
    after, log = R.wayback_retry(None, out, sleep=waits.append)
    assert (log["failed_urls"], log["recovered"], log["still_failed"]) == (1, 1, 0) and waits == []
    assert R.all_metrics(after)["price"]["arms"]["A"]["leak_cases"] == 1
    assert R.all_metrics(out)["price"] == first                                            # first pass untouched
    assert "3 tries, 5 s apart" in log["rule"] and (R.RETRY_TRIES, R.RETRY_WAIT) == (3, 5)


def test_retry_gives_up_after_three_tries(monkeypatch):
    calls = []
    monkeypatch.setattr(DT, "wayback", lambda rec, url, tag="": calls.append(tag) or None)
    out = R.run(FakeTav(), None, [CASE_P])
    n_first = len(calls)
    waits = []
    _, log = R.wayback_retry(None, out, sleep=waits.append)
    assert log["still_failed"] == 2 and len(calls) - n_first == 6 and waits == [5, 5, 5, 5]


def test_cap_stops_cleanly(monkeypatch):
    monkeypatch.setattr(DT, "wayback", fake_wayback()[0])
    out = R.run(FakeTav(cap_after=3), None, [CASE_P, CASE_Q])
    assert len(out["skipped"]) == 1 and out["skipped"][0]["case"] == "VE99"
    out["built_utc"], out["metrics"] = "2026-11-01T00:00:00", R.all_metrics(out)
    out["pooled"] = R.pooled(out["metrics"])
    assert "Incomplete" in R.report(out)


def test_pooled_uses_the_pilots_first_passes_per_rule():
    zero = {"cases": 0, "arms": {a: {"leak_cases": 0} for a in R.ARMS},
            "a_vs_c_mcnemar": {"A_only": 0, "C_only": 0}}
    p = R.pooled({"price": zero, "finance": zero})
    dt = json.loads(DT.OUT.read_text())["metrics"]["arms"]
    fin = json.loads(F.OUT.read_text())["metrics"]["all"]["arms"]
    assert p["price"]["arms"]["A"]["leak_cases"] == dt["A"]["leak_cases"] == 9
    assert p["price"]["arms"]["C"]["leak_cases"] == dt["C"]["leak_cases"] == 0
    assert p["finance"]["arms"]["A"]["leak_cases"] == fin["N"]["confirmed"]["events"] == 2
    assert p["finance"]["arms"]["C"]["leak_cases"] == fin["D"]["confirmed"]["events"] == 0
    assert (p["price"]["pilot_cases"], p["finance"]["pilot_cases"]) == (20, 14)


def test_runs_once_and_only_on_the_frozen_cases(monkeypatch, tmp_path):
    monkeypatch.setattr(R, "OUT", tmp_path / "replication.json")
    (tmp_path / "replication.json").write_text("{}")
    monkeypatch.setattr("sys.argv", ["replication"])
    with pytest.raises(SystemExit, match="runs once"):
        R.main()
    (tmp_path / "replication.json").unlink()
    bad = tmp_path / "cases.json"
    bad.write_text(json.dumps({"cases": []}))
    monkeypatch.setattr(R, "CASES", bad)
    with pytest.raises(SystemExit, match="does not match"):
        R.main()
