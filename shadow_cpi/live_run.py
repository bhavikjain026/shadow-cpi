"""'Run live' for the app: one live event scan of the last 7 days, capped in code.

Off unless RUN_LIVE_ENABLED is set (a Streamlit Cloud secret). Caps (config/budget.json, plans.app_live): at
most `per_session` runs per visitor session, `per_day` runs per UTC day for the whole app, none when the ledger balance
would fall below `credit_floor`, and none unless the plan credits left by Tavily's own GET /usage plus the add-on
credits left (config minus ledger) come to at least `usage_floor`
(checked before every run; a failed check or a missing limit refuses the run). Each run is also held to
the hard caps 'run-now' (total) and 'run-now-scan' (one scan) by shadow_cpi.budget. A run that is refused or fails
never raises to the page: the app shows the saved run with the message.

Keys and the switch are read from environment variables (Streamlit Community Cloud exposes root-level secrets as
environment variables), with a read-only fallback to Streamlit's secrets: SCPI_TAVILY_API_KEY, SCPI_NEBIUS_API_KEY,
RUN_LIVE_ENABLED. Nothing is ever written to them.
"""
import json
import os
import time
from datetime import datetime, timedelta, timezone

from .budget import BudgetExceeded, Budgeted, account_limit, account_spent, cap_of, load_budget, read_ledger
from .settings import ROOT

STATE_FILE = ROOT / "logs" / "live_runs.jsonl"
KEY_VARS = ("SCPI_TAVILY_API_KEY", "SCPI_NEBIUS_API_KEY")


def limits(cfg=None):
    return (cfg or load_budget())["plans"]["app_live"]


def setting(name):
    """An environment variable, else (read-only) the root-level Streamlit secret of that name, else None.
    Streamlit copies root-level secrets into the environment only once it has loaded them; the fallback covers the
    time before that. Never raises."""
    if os.environ.get(name):
        return os.environ[name]
    try:
        from streamlit.runtime.secrets import secrets_singleton
        if secrets_singleton.load_if_toml_exists():
            v = secrets_singleton.get(name)
            return None if v is None or isinstance(v, dict) else str(v)
    except Exception:
        pass
    return None


def keys():
    """(tavily, nebius) from setting(), or None."""
    vals = tuple(setting(k) for k in KEY_VARS)
    return vals if all(vals) else None


def credits_left(cfg=None, ledger=None):
    cfg = cfg or load_budget()
    return account_limit(cfg) - account_spent(cfg, read_ledger() if ledger is None else ledger)


def runs_on(day, path=STATE_FILE):
    if not path.exists():
        return 0
    return sum(json.loads(l)["day"] == day for l in path.read_text().splitlines() if l.strip())


def enabled():
    """RUN_LIVE_ENABLED (a Streamlit Cloud secret, via setting()). Default OFF; on only for 1/true/yes/on."""
    return (setting("RUN_LIVE_ENABLED") or "").strip().lower() in ("1", "true", "yes", "on")


def addon_left(cfg, ledger, plan_limit):
    """Add-on credits (config/budget.json `addon_credits`) not yet used. Assumption (docs/deploy.md): Tavily spends
    plan credits first, so add-on credits count as used only for spending beyond the plan limit; spending comes from
    the ledger (account_spent, reconciled to the billing page). The ledger is cumulative, so after a monthly plan
    reset add-on credits already counted as used stay used (the safe direction)."""
    used = max(0, account_spent(cfg, ledger) - plan_limit)
    return max(0, cfg.get("addon_credits", 0) - used)


def usage_remaining(tavily_key, fetch=None, cfg=None, ledger=None):
    """(remaining credits, '') = plan credits left from Tavily's GET /usage (account.plan_limit - account.plan_usage)
    + add-on credits left (addon_left). (None, reason) when the call fails or returns no limit: fail closed.
    fetch: for tests (returns the parsed response)."""
    try:
        if fetch:
            resp = fetch()
        else:
            from .tavily import Tavily
            resp = Tavily(api_key=tavily_key).usage(tag="live:usage check")
        acc = (resp or {}).get("account") or {}
        limit, used = acc.get("plan_limit"), acc.get("plan_usage")
        if not isinstance(limit, (int, float)) or not isinstance(used, (int, float)):
            return None, "Tavily's usage check returned no credit limit"
        cfg = cfg or load_budget()
        led = read_ledger() if ledger is None else ledger
        return max(0, limit - used) + addon_left(cfg, led, limit), ""
    except Exception as e:                                      # fail closed
        return None, f"Tavily's usage check failed ({type(e).__name__})"


def gate(session_runs, now=None, path=STATE_FILE, cfg=None, ledger=None, have_keys=None, usage_fetch=None,
         tavily_only=False):
    """(allowed, message). The message is shown with the saved run when a run is not allowed. Checks run cheapest
    first; the Tavily /usage check (a free call) runs last and fails closed. tavily_only: the leak demo's live
    search, which needs only the Tavily key (no Nemotron)."""
    cfg = cfg or load_budget()
    lim = limits(cfg)
    now = now or datetime.now(timezone.utc)
    day = now.date().isoformat()
    if not enabled():
        return False, "Live runs open on 1 Dec (judging period). Showing the saved run."
    if have_keys is not None:
        k = ("test", "test") if have_keys else None
    elif tavily_only:
        k = (setting(KEY_VARS[0]),) if setting(KEY_VARS[0]) else None
    else:
        k = keys()
    if not k:
        return False, "Live runs are switched off on this copy of the app (no API keys). Showing the saved run."
    if session_runs >= lim["per_session"]:
        return False, (f"You have used this visit's {lim['per_session']} live runs. Showing the saved run.")
    if runs_on(day, path) >= lim["per_day"]:
        return False, (f"Today's {lim['per_day']} live runs for the whole app are used up (resets at 00:00 UTC). "
                       "Showing the saved run.")
    left = credits_left(cfg, ledger)
    if left - cap_of("run-now-scan", cfg) < lim["credit_floor"]:
        return False, (f"Live runs are paused: the Tavily balance is close to the floor of {lim['credit_floor']} "
                       "credits kept in reserve. Showing the saved run.")
    spent_live = sum(e["credits"] for e in (read_ledger() if ledger is None else ledger) if "run-now" in e["budgets"])
    if spent_live + cap_of("run-now-scan", cfg) > cap_of("run-now", cfg):
        return False, f"The app's live-run credit budget is used up ({spent_live} credits). Showing the saved run."
    remaining, why = usage_remaining(k[0], usage_fetch, cfg, ledger)
    if remaining is None:
        return False, f"Live runs are paused: {why}. Showing the saved run."
    if remaining < lim["usage_floor"]:
        return False, (f"Live runs are paused: fewer than {lim['usage_floor']} credits left (Tavily plan plus add-on "
                       "credits). Showing the saved run.")
    return True, ""


def run_live(tavily_key, nebius_key, now=None, path=STATE_FILE, transport=None, nem_transport=None, cfg=None):
    """One live scan: the event layer over the last 7 days, English, the kinds in plans.cut5_run_now. Returns a
    result in the saved-run format plus a receipt. Records the run before any call is made."""
    from . import evidence as E
    from .event_rules import apply_rules
    from .nemotron import Nemotron
    from .recorder import Recorder
    from .settings import models
    from .tavily import Tavily
    cfg = cfg or load_budget()
    now = now or datetime.now(timezone.utc)
    day = now.date().isoformat()
    n = runs_on(day, path) + 1
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps({"day": day, "n": n, "started_utc": now.isoformat()}) + "\n")
    start, end = (now - timedelta(days=7)).date().isoformat(), now.date().isoformat()
    month = end[:7]
    rec = Recorder()
    kw = {"transport": transport} if transport else {}
    tav = Budgeted(Tavily(api_key=tavily_key, recorder=rec, **kw), ["run-now", f"run-now-scan/{day}#{n}"])
    nem = Nemotron(api_key=nebius_key, recorder=rec, **({"transport": nem_transport} if nem_transport else {}))
    items = E.load_items()["events"]
    t0, stopped, kept = time.time(), "", []
    stats = {"_month": month, "drops": {}, "leak_drops": 0, "leak_examples": []}

    def drop(reason, k=1):
        stats["drops"][reason] = stats["drops"].get(reason, 0) + k

    try:
        for kind in cfg["plans"]["cut5_run_now"]["event_kinds"]:
            kcfg = items.get(kind, {})
            if kcfg.get("disabled") or "en" not in kcfg.get("queries", {}):
                continue
            for r, d, _, text, eid in E.fetch_pages(tav, nem, kcfg["queries"]["en"], "en", start, end,
                                                    f"live:{kind}", stats, drop, set()):
                evs, _ = nem.price_events(models().get("mid"), text, tag=f"live:{kind} events", parent=eid)
                for ev in evs:
                    k, why = E.judge_event({**ev, "_url": r["url"], "_page_date": d, "_kind": kind,
                                            "_context": E.line_context(text, ev.get("line"))}, month, kcfg)
                    if k:
                        k.pop("_context", None)
                        kept.append({**k, "kind": kind, "cpi_code": kcfg.get("cpi_code", ""), "url": r["url"],
                                     "page_date": d})
                    else:
                        drop(why)
    except BudgetExceeded as e:
        stopped = f"stopped at the credit cap: {e}"
    events, _ = apply_rules([{**e, "sources": [e["url"]]} for e in kept])
    from .recorder import read_log
    calls = [e for e in read_log(rec.log_file) if e["time"] >= now.isoformat()
             and (e.get("tag") or "").startswith("live:")]
    return {"label": f"Live run {now.strftime('%Y-%m-%d %H:%M')} UTC, window {start} to {end}",
            "live": True, "window": [start, end], "stopped": stopped,
            "events": [{"item": e["kind"], "place": e.get("region") or "", "pct_change": e["change"] * 100,
                        "effective_date": e["effective_date"], "line": e.get("quote") or "", "url": e["url"]}
                       for e in events],
            "receipt": {"tavily_calls": sum(e["service"] == "tavily" for e in calls),
                        "nemotron_calls": sum(e["service"] == "nebius" for e in calls),
                        "credits": tav.used, "seconds": round(time.time() - t0), "drops": stats["drops"]}}
