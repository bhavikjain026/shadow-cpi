"""v2 issue 14 scorer pieces (offline, no calls): measured share, moving events, the once-only lock."""
import pytest

from v2 import score as S

W = {"01": 50.0, "04": 50.0, "01.1.4.1.1.01": 5.0, "04.5.1.0.2.01": 2.0}


def test_measured_share_counts_events_by_their_state_share(monkeypatch):
    monkeypatch.setattr(S.O, "codes_at", lambda level, w: ["01", "04"])
    assert S.measured(W, [("01.1.4.1.1.01", 1.0)]) == pytest.approx(0.05)
    assert S.measured(W, [("04.5.1.0.2.01", 0.0117)]) == pytest.approx(2.0 * 0.0117 / 100)
    assert S.measured(W, [("04.5.1.0.2.01", 0.7), ("04.5.1.0.2.01", 0.7)]) == pytest.approx(0.02)   # capped at 1


def card(line, kind="electricity", status="verified", states=("jammu and kashmir",), region="Jammu & Kashmir"):
    return {"title": "t", "url": "u", "published": "2026-08-24",
            "claims": [{"status": status, "kind": kind, "line": line, "region": region, "seller": "JERC",
                        "states": list(states), "change": 0.0683, "effective_date": "2026-09-01",
                        "read_by": "super", "context": ""}]}


def test_moving_events_follow_amendments_a_and_c():
    jk = card("जम्मू-कश्मीर में बिजली की दरों में औसतन 6.83 फीसदी बढ़ोतरी की गई है।")
    milk = card("Milk up Rs 2 per litre", kind="milk")
    rejected = card("x", status="rejected")
    ev = S.moving_events([jk, milk, rejected], "2026-09")
    assert len(ev) == 1 and ev[0]["event_kind"] == "electricity" and ev[0]["share_of_month"] == 1.0
    assert ev[0]["weight_share"] == pytest.approx(S.R.state_share("04.5.1.0.2.01", {"jammu and kashmir"}))
    assert milk["claims"][0]["use"].startswith("context")


def test_city_event_without_a_documented_share_is_context():
    city = card("Chennai bus fares up 10% from September 1", kind="bus", states=("tamil nadu",), region="Chennai")
    assert S.moving_events([city], "2026-09") == []
    assert "no documented city share" in city["claims"][0]["use"]


def test_scored_once(tmp_path, monkeypatch):
    lock = tmp_path / "v2_score_lock.json"
    lock.write_text("{}")
    monkeypatch.setattr(S, "LOCK", lock)
    with pytest.raises(SystemExit, match="scored once"):
        S.main()
