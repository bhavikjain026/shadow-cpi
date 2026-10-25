"""as_of(day): the nowcast, evidence and coverage from items found on or before `day` (0 credits, no API call).

"Found on or before day" means:
  - replay month (the September basket run, v2/evidence/run_2026-09_basket.json): the page's published date <= day.
    The nowcast and coverage are the time machine's row for that day, which v2.basket built from evidence published
    by that day only (the spine enters on the cutoff day, as there are no daily spine prices);
  - live month (the October radar, v2/radar/radar_2026-10.json): published <= day AND fetched by us (card "found")
    <= day, so a page we found later can never appear in an earlier view.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASKET = ROOT / "v2" / "evidence" / "run_2026-09_basket.json"
RADAR = ROOT / "v2" / "radar" / "radar_2026-10.json"


def _verified(cards, ok):
    out = []
    for c in cards:
        if not ok(c):
            continue
        for cl in c.get("claims", []):
            if cl.get("status") == "verified":
                out.append({"url": c["url"], "published": c.get("published"), "found": c.get("found"),
                            "kind": cl.get("kind"), "change": cl.get("change"), "quote": cl.get("line")})
    return out


def as_of(day, month="2026-09", basket=None, radar=None):
    """{'month', 'day', 'nowcast', 'coverage', 'evidence', 'events'} as known on `day` (ISO date)."""
    if month == "2026-10":
        r = radar or json.loads(RADAR.read_text(encoding="utf-8"))
        ok = lambda c: bool(c.get("published")) and c["published"] <= day and (c.get("found") or "9999") <= day  # noqa
        ev = _verified(r["cards"], ok)
        return {"month": month, "day": day, "nowcast": None, "coverage": None, "evidence": ev,
                "events": sorted({(e["kind"], e["url"]) for e in ev}),
                "note": "the October nowcast is sealed on 29 Oct; this view lists radar evidence only"}
    b = basket or json.loads(BASKET.read_text(encoding="utf-8"))
    if b["month"] != month:
        raise ValueError(f"no saved run for {month}")
    rows = [r for r in b["time_machine"] if r["date"] <= day]
    row = rows[-1] if rows else None
    ok = lambda c: bool(c.get("published")) and c["published"] <= day  # noqa: E731
    moving = [{"kind": m["event_kind"], "where": m["where"], "change": m["change"],
               "sources": [s for s in m["sources"] if s["published"] <= day]} for m in b["moving_events"]]
    return {"month": month, "day": day, "nowcast": row["yoy"] if row else None,
            "coverage": row["measured"] if row else None, "evidence": _verified(b["cards"], ok),
            "events": [m for m in moving if m["sources"]],
            "note": "nowcast and coverage from the time machine (evidence published by the day only)"}
