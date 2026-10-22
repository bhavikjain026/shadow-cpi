"""v2 issue 4 (Amendment C): kinds and words in every language, regional places, the recall reference, and the
recall matching rule. Offline, no calls."""
import json
import re
from pathlib import Path

from v2 import kinds as K
from v2 import recall as RC

ROOT = Path(__file__).resolve().parent.parent


def test_query_sets_are_the_preregistered_thirteen():
    assert len(K.QUERIES) == 13
    langs = [l for l, _ in K.QUERIES]
    assert langs.count("en") == 4 and langs.count("hi") == 4 and {"mr", "ta", "te", "kn", "bn"} <= set(langs)
    assert set(K.DOMAINS) == {"en", "hi", "mr", "ta", "te", "kn", "bn"}
    pre = (ROOT / "v2" / "PREREGISTRATION.md").read_text(encoding="utf-8")
    assert all(q in pre for _, q in K.QUERIES)                                # every query is in Amendment C


def test_kind_from_the_line_in_every_language():
    cases = {"मध्य प्रदेश में बिजली महंगी": "electricity", "வீட்டு மின் கட்டணம் உயர்வு": "electricity",
             "ಹಾಲಿನ ದರ ಏರಿಕೆ": "milk", "দুধের দাম বাড়ল": "milk", "एसटी बस भाडेवाढ १० टक्के": "bus",
             "బస్సు ఛార్జీల పెంపు": "bus", "डिझेल दर वाढले": "diesel", "Petrol price up Rs 3": "petrol",
             "Metro fares revised": "metro", "Railway fare up 5%": "rail", "Jio prepaid plans costlier": "mobile",
             "The weather was fine": None}
    for line, kind in cases.items():
        assert K.kind_of(line) == kind, line
    assert K.KINDS["bus"]["cpi"] == "07.3.1.2.2.01" and K.KINDS["metro"]["role"] == "context"


def test_regional_place_names():
    assert K.states_of("சென்னையில் பால் விலை") == {"tamil nadu"}
    assert K.states_of("ಬೆಂಗಳೂರು ಹಾಲು") == {"karnataka"} and K.states_of("কলকাতায় বাস ভাড়া") == {"west bengal"}
    assert "maharashtra" in K.states_of("MSRTC Maharashtra bus fare")


def test_recall_reference_matches_the_audit():
    ref = json.loads((ROOT / "v2" / "recall_reference.json").read_text(encoding="utf-8"))["changes"]
    audit = (ROOT / "audit" / "missed_events.md").read_text(encoding="utf-8")
    ids = re.findall(r"^\|\s*([MLFET]\d+)\s*\|", audit, re.M)
    assert [r["id"] for r in ref] == ids and len(ref) == 29
    found = {i for i in ids if re.search(rf"^\|\s*{i}\s*\|.*\*\*FOUND\*\*", audit, re.M)}
    assert {r["id"] for r in ref if r["v1"] == "FOUND"} == found and len(found) == 9


def claim(**kw):
    return {"status": "verified", "kind": "electricity", "effective_date": "2026-04-01", "states": ["maharashtra"],
            **kw}


def test_matching_rule():
    e2 = {"id": "E2", "kind": "electricity", "month": "2026-04", "date": "2026-04-01", "states": ["maharashtra"]}
    assert RC.matches(e2, claim())
    assert not RC.matches(e2, claim(status="rejected"))
    assert not RC.matches(e2, claim(states=["punjab"]))                      # wrong state
    assert not RC.matches(e2, claim(effective_date="2026-04-05"))            # more than 2 days off
    assert not RC.matches(e2, claim(kind="milk"))
    nat = {"id": "M3", "kind": "milk", "month": "2026-05", "date": "2026-05-14", "states": []}
    assert RC.matches(nat, claim(kind="milk", effective_date="2026-05-14", states=["gujarat"]))   # national: any place
    e5 = {"id": "E5", "kind": "electricity", "month": "2026-06", "date": None, "states": ["uttar pradesh"]}
    assert RC.matches(e5, claim(effective_date="2026-06-20", states=["uttar pradesh"]))         # month only
    rows = RC.score({"2026-04": [claim()]}, [e2, nat])
    assert [r["v2"] for r in rows] == ["FOUND", "MISSED"] and rows[0]["v2_match"]["month"] == "2026-04"
