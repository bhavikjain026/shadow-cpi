"""as_of(day): nothing found after the day can appear. Offline, saved files only."""
import json
from datetime import date, timedelta

import pytest

from v2 import asof as A

BASKET = json.loads(A.BASKET.read_text())


def days(month_start, n):
    d = date.fromisoformat(month_start)
    return [(d + timedelta(k)).isoformat() for k in range(n)]


@pytest.mark.parametrize("day", days("2026-08-20", 45))
def test_nothing_published_after_the_day_appears(day):
    v = A.as_of(day)
    assert all(e["published"] <= day for e in v["evidence"])
    assert all(s["published"] <= day for m in v["events"] for s in m["sources"])
    tm = [r for r in BASKET["time_machine"] if r["date"] <= day]
    assert v["nowcast"] == (tm[-1]["yoy"] if tm else None)


def test_later_evidence_is_excluded_even_if_planted():
    b = json.loads(json.dumps(BASKET))
    b["cards"].append({"url": "https://late.example/x", "published": "2026-09-20", "claims": [
        {"status": "verified", "kind": "milk", "change": 0.5, "line": "late"}]})
    assert not any(e["url"] == "https://late.example/x" for e in A.as_of("2026-09-19", basket=b)["evidence"])
    assert any(e["url"] == "https://late.example/x" for e in A.as_of("2026-09-20", basket=b)["evidence"])


def test_live_month_needs_found_by_the_day_too():
    r = {"cards": [{"url": "u", "published": "2026-09-30", "found": "2026-10-25", "claims": [
        {"status": "verified", "kind": "milk", "change": 0.05, "line": "x"}]}]}
    assert A.as_of("2026-10-24", month="2026-10", radar=r)["evidence"] == []
    assert len(A.as_of("2026-10-25", month="2026-10", radar=r)["evidence"]) == 1
