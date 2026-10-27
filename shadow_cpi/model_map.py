"""Forced model migration (v2/PREREGISTRATION.md Amendment G): which Nebius model ID a call uses, by the call date in
IST. config/models.json keeps each role's original ID ('small', 'mid') and a dated map; code keeps asking for the
original ID and gets the one for the day of the call. IDs not in the map (the 'large' model, test fakes) pass through."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from .settings import models


def call_day(when=None, tz="Asia/Kolkata"):
    """The calendar day of a call in IST (a naive datetime is taken as UTC)."""
    when = when or datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone(ZoneInfo(tz)).date()


def period(day, cfg=None):
    """The dated-map period holding `day` (a date), or None when the config has no dated map."""
    dated = (cfg if cfg is not None else models()).get("dated")
    if not dated:
        return None
    d = day.isoformat()
    for p in dated["periods"]:
        if (p["from"] is None or p["from"] <= d) and (p["until"] is None or d <= p["until"]):
            return p
    raise ValueError(f"config/models.json: no dated model period covers {d}")


def resolve(model, when=None, cfg=None):
    """The ID to call for `model` (a role's original ID) at time `when`; unchanged if the map does not name it."""
    cfg = cfg if cfg is not None else models()
    dated = cfg.get("dated")
    if not dated:
        return model
    p = period(call_day(when, dated.get("timezone", "Asia/Kolkata")), cfg)
    role = next((r for r in ("small", "mid") if cfg.get(r) == model), None)
    return p.get(role, model) if role else model


def in_use(when=None, cfg=None):
    """{role: ID} for the call date: what a run on that day calls (the original IDs before 2026-11-09 IST)."""
    cfg = cfg if cfg is not None else models()
    return {r: resolve(cfg[r], when, cfg) for r in ("small", "mid") if cfg.get(r)}


def check(cfg=None):
    """The periods are in order, start open, end open, and leave no gap or overlap (raises ValueError)."""
    ps = (cfg if cfg is not None else models())["dated"]["periods"]
    if ps[0]["from"] is not None or ps[-1]["until"] is not None:
        raise ValueError("the first period must have no start and the last no end")
    for a, b in zip(ps, ps[1:]):
        if date.fromisoformat(a["until"]).toordinal() + 1 != date.fromisoformat(b["from"]).toordinal():
            raise ValueError(f"gap or overlap between {a['until']} and {b['from']}")
