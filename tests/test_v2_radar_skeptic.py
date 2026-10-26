"""October radar skeptic (v2/DRIFT_PREREG.md, part B): model query in the page's language, time lock, code's flag,
cap, freeze, and nothing else changes. Offline with fakes."""
import copy
from datetime import datetime, timezone

import pytest

from shadow_cpi.budget import BudgetExceeded
from v2 import radar_skeptic as S

NOW = datetime(2026, 10, 27, 4, 40, tzinfo=timezone.utc)
SRC = "https://navbharattimes.indiatimes.com/indore-milk"
EV = {"kind": "milk", "effective_date": "2026-10-01", "states": ["madhya pradesh"], "change": 0.048,
      "sources": [{"url": SRC, "domain": "navbharattimes.indiatimes.com", "line": "..."}], "tier": "verified",
      "tavily_only": False, "effect_pp": None}
RADAR = {"cards": [{"url": SRC, "lang": "hi"}], "corroboration": [], "events": [EV]}


class FakeNem:
    def __init__(self, answers):
        self.answers, self.prompts = list(answers), []

    def chat_json(self, model, system, user, schema=None, **kw):
        self.prompts.append((model, user))
        a = self.answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return a, f"n{len(self.prompts)}"


class FakeTav:
    def __init__(self, results, cap=None):
        self.results, self.cap, self.sent = results, cap, []

    def search(self, query, **kw):
        if self.cap is not None and len(self.sent) >= self.cap:
            raise BudgetExceeded("cap")
        self.sent.append((query, kw))
        return {"results": self.results, "usage": {"credits": 1}, "request_id": "q"}, "s1"


def res(url, content, date="2026-10-10", title=""):
    return {"url": url, "title": title, "content": content, "published_date": date}


def test_query_in_the_page_language_and_inside_the_radar_window():
    nem, tav = FakeNem([{"query": "इंदौर दूध दाम बढ़ोतरी वापस"}]), FakeTav([])
    row = S.check_event(tav, nem, ["small", "mid"], EV, RADAR)
    assert "Language: Hindi" in nem.prompts[0][1] and row["lang"] == "hi"
    q, kw = tav.sent[0]
    assert q == "इंदौर दूध दाम बढ़ोतरी वापस"
    assert (kw["start_date"], kw["end_date"], kw["topic"], kw["max_results"]) == ("2026-09-21", "2026-10-29", "news", 10)
    assert row["status"] == "not challenged"


def test_flag_needs_a_reversal_word_and_the_kind_and_skips_own_source_and_out_of_window():
    tav = FakeTav([res(SRC, "Milk price hike withdrawn."),                                      # own source
                   res("https://a.com/x", "Milk price hike rolled back.", date="2026-11-02"),   # after the window
                   res("https://b.com/x", "Bus fares postponed. Diesel up."),                   # wrong kind
                   res("https://c.com/x", "Prices rise. इंदौर में दूध के दाम की बढ़ोतरी वापस ली गई। Other.")])
    row = S.check_event(tav, FakeNem([{"query": "q"}]), ["small"], EV, RADAR)
    assert row["status"] == "challenged" and row["dropped"] == 2 and row["kept"] == 2
    assert row["challenged"] == [{"url": "https://c.com/x", "quote": "इंदौर में दूध के दाम की बढ़ोतरी वापस ली गई",
                                  "date": "2026-10-10"}]


def test_whole_words_only():
    assert S.challenge(res("u", "Milk sales stayed strong"), EV)                     # 'stayed' is listed
    assert not S.challenge(res("u", "Milkshake prices withdrawn"), EV)               # 'milk' not a whole word
    assert not S.challenge(res("u", "Milk price restayed"), EV)


def test_bad_model_answer_falls_back_then_skips_the_search():
    nem = FakeNem([RuntimeError("timeout"), {"query": "x" * 301}])
    tav = FakeTav([])
    row = S.check_event(tav, nem, ["small", "mid"], EV, RADAR)
    assert row["status"] == "skeptic not run (no valid query)" and tav.sent == []
    assert [t["model"] for t in row["model_tries"]] == ["small", "mid"]


def test_once_per_event_cap_and_freeze():
    radar = copy.deepcopy(RADAR)
    radar["events"].append({**EV, "kind": "electricity", "effective_date": "2026-10-10"})
    st = S.run(FakeTav([], cap=1), FakeNem([{"query": "a"}, {"query": "b"}]), ["small"], radar,
               {"events": {}}, NOW)
    assert len(st["events"]) == 1 and st["runs"][-1]["complete"] is False
    st = S.run(FakeTav([]), FakeNem([{"query": "b"}]), ["small"], radar, st, NOW)
    assert len(st["events"]) == 2 and st["runs"][-1]["complete"] is True
    assert S.todo(radar, st) == []
    with pytest.raises(SystemExit, match="frozen"):
        S.run(FakeTav([]), FakeNem([]), ["small"], radar, st, datetime(2026, 10, 29, 18, 30, tzinfo=timezone.utc))


def test_never_changes_the_radar_events():
    radar = copy.deepcopy(RADAR)
    S.run(FakeTav([res("https://c.com/x", "Milk price hike withdrawn")]), FakeNem([{"query": "q"}]), ["small"],
          radar, {"events": {}}, NOW)
    assert radar == RADAR


def test_cap_in_config():
    from shadow_cpi.budget import cap_of, load_budget
    assert cap_of(S.BUDGET, load_budget()) == 40


def test_an_api_error_keeps_the_other_events_and_retries_next_run():
    radar = copy.deepcopy(RADAR)
    radar["events"].append({**EV, "kind": "electricity", "effective_date": "2026-10-10"})

    class Flaky(FakeTav):
        def search(self, query, **kw):
            if query == "a":
                raise ConnectionResetError("reset")
            return super().search(query, **kw)

    st = S.run(Flaky([]), FakeNem([{"query": "a"}, {"query": "b"}]), ["small"], radar, {"events": {}}, NOW)
    assert len(st["events"]) == 1 and st["runs"][-1]["errors"][0]["error"].startswith("ConnectionResetError")
    assert len(S.todo(radar, st)) == 1
