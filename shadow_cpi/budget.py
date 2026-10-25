"""Hard Tavily credit caps (config/budget.json) and the credit ledger (results/credit_ledger.jsonl).

Every uncached Tavily call made through a Budgeted client is checked BEFORE it is sent:
  - each named budget it charges (e.g. 'replay-layers' and 'replay-layers-month/2026-01') must stay within its cap
    (the cap for 'name/anything' is caps['name']);
  - the account total (spent_before_ledger + everything in the ledger) must stay within plan_limit - reserve.
If any check fails the call is refused with BudgetExceeded and nothing is spent. After the call, Tavily's own
credit count (include_usage) is written to the ledger under every budget it charged. Cached calls are free.
"""
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from .recorder import provenance, request_hash
from .settings import ROOT

BUDGET_FILE = ROOT / "config" / "budget.json"
LEDGER = ROOT / "results" / "credit_ledger.jsonl"


class BudgetExceeded(Exception):
    """Raised BEFORE a Tavily call that would go past a cap. The run stops and asks the owner."""


class CacheMiss(BudgetExceeded):
    """Cache-only mode (frozen re-runs): the call is not in the cache, so it is skipped and nothing is sent."""


def load_budget(path=BUDGET_FILE):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_ledger(path=LEDGER):
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def spent(budget_name, ledger=None, path=LEDGER):
    """Credits charged to one budget name (exact name, e.g. 'replay-layers-month/2026-01')."""
    return sum(e["credits"] for e in (ledger if ledger is not None else read_ledger(path))
               if budget_name in e["budgets"])


def account_spent(cfg=None, ledger=None, path=LEDGER):
    cfg = cfg or load_budget()
    entries = ledger if ledger is not None else read_ledger(path)
    return cfg["spent_before_ledger"] + sum(e["credits"] for e in entries)


def account_limit(cfg):
    """All credits the account can spend: the monthly plan plus add-on credits (e.g. the Nebius builder program)."""
    return cfg["plan_limit"] + cfg.get("addon_credits", 0)


def cap_of(name, cfg):
    return cfg["caps"][name.split("/")[0]]


def call_cost(endpoint, body):
    """Upper bound for one call. Search: basic 1, advanced 2. Extract: 1 (basic) or 2 (advanced) per 5 URLs.
    Map: 1 per 10 pages (2 with instructions). Crawl: map cost + extract cost, for `limit` pages."""
    if endpoint == "/search":
        return 2 if body.get("search_depth") == "advanced" or body.get("auto_parameters") else 1
    if endpoint == "/extract":
        return (2 if body.get("extract_depth") == "advanced" else 1) * math.ceil(len(body.get("urls", [])) / 5)
    limit = body.get("limit", 50)
    mapping = (2 if body.get("instructions") else 1) * math.ceil(limit / 10)
    if endpoint == "/map":
        return mapping
    return mapping + (2 if body.get("extract_depth") == "advanced" else 1) * math.ceil(limit / 5)


class Budgeted:
    """Wraps a Tavily client; every call charges `budgets` (list of names). Hard caps, see module docstring."""

    def __init__(self, tav, budgets, cfg=None, ledger_path=LEDGER, cache_only=False, fresh=False):
        self.tav, self.budgets, self.cache_only = tav, list(budgets), cache_only
        # fresh: every call is sent and charged even if a cached copy exists (a recorder that does not read its cache
        # forces this, so a real call can never pass as a free cache hit)
        self.fresh = fresh or (getattr(tav, "rec", None) is not None and not tav.rec.use_cache)
        self.cfg = cfg or load_budget()
        self.ledger_path = Path(ledger_path)
        self.used = 0
        self.rec = tav.rec

    def charge(self, *budgets):
        """A copy charging these budgets instead (same ledger, same client)."""
        return Budgeted(self.tav, budgets, self.cfg, self.ledger_path, self.cache_only, self.fresh)

    def _cached(self, endpoint, body):
        body = {**body, "include_usage": True}
        return (self.tav.rec.cache_dir / "tavily" / f"{request_hash('tavily', endpoint, body)}.json").exists()

    def check(self, cost):
        ledger = read_ledger(self.ledger_path)
        for b in self.budgets:
            s, cap = spent(b, ledger), cap_of(b, self.cfg)
            if s + cost > cap:
                raise BudgetExceeded(f"budget '{b}': {s} spent + {cost} for the next call > cap {cap}")
        # the reserve is kept for the seal runs: only budgets in 'reserve_for' may spend it
        seal = any(b.split("/")[0] in self.cfg.get("reserve_for", []) for b in self.budgets)
        reserve = 0 if seal else self.cfg["reserve"]
        total, limit = account_spent(self.cfg, ledger), account_limit(self.cfg) - reserve
        if total + cost > limit:
            raise BudgetExceeded(f"account: {total} spent + {cost} > {limit} (plan {self.cfg['plan_limit']} + add-on "
                                 f"{self.cfg.get('addon_credits', 0)} minus reserve {reserve})")

    def _write(self, cid, endpoint, resp, real, cached):
        """One ledger row: `credits` = `real_spent` (what the caps count), `original_cost` = Tavily's own count
        for the call when first made (what the credits-per-event metrics use; cached rows keep it at 0 real)."""
        original = (resp.get("usage") or {}).get("credits") or 0
        row = {"time": datetime.now(timezone.utc).isoformat(), "call_id": cid, "endpoint": endpoint,
               "credits": real, "real_spent": real, "original_cost": original, "budgets": self.budgets,
               **provenance(resp)}
        if cached:
            row["cached"] = True
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")

    def _run(self, endpoint, body, fn):
        if not self.fresh and self._cached(endpoint, body):
            resp, cid = fn()
            if not self.cache_only:                 # frozen re-runs spend nothing and leave the ledger alone
                self._write(cid, endpoint, resp, 0, cached=True)
            return resp, cid
        if self.cache_only:
            raise CacheMiss(f"cache-only run: {endpoint} not in the cache, skipped (no call sent)")
        self.check(call_cost(endpoint, body))
        resp, cid = fn()
        credits = (resp.get("usage") or {}).get("credits") or 0
        self.used += credits
        self._write(cid, endpoint, resp, credits, cached=False)
        return resp, cid

    @staticmethod
    def _body(params):
        return {k: v for k, v in params.items() if k not in ("parent", "tag")}

    def search(self, query, **params):
        p = self._body(params)
        if not p.get("auto_parameters"):        # as Tavily.search, so the cache check hashes the body actually sent
            p.setdefault("search_depth", "basic")
        return self._run("/search", {"query": query, **p}, lambda: self.tav.search(query, **params))

    def extract(self, urls, **params):
        return self._run("/extract", {"urls": list(urls)[:20], **self._body(params)},
                         lambda: self.tav.extract(urls, **params))

    def map(self, url, **params):
        p = self._body(params)
        p.setdefault("allow_external", False)
        return self._run("/map", {"url": url, **p}, lambda: self.tav.map(url, **params))

    def crawl(self, url, **params):
        p = self._body(params)
        p.setdefault("allow_external", False)
        p.setdefault("max_depth", 1)
        return self._run("/crawl", {"url": url, **p}, lambda: self.tav.crawl(url, **params))


def run_now_allowed(day, ledger=None, cfg=None, path=LEDGER):
    """'Run now' daily cap: at most scans_per_day scans on `day` (YYYY-MM-DD), counted from the ledger budget
    'run-now-scan/<day>#<n>'. Returns the next scan's budget name, or None if the day's scans are used up."""
    cfg = cfg or load_budget()
    entries = ledger if ledger is not None else read_ledger(path)
    per_day = cfg["plans"]["cut5_run_now"]["scans_per_day"]
    used = {b for e in entries if not e.get("cached") for b in e["budgets"] if b.startswith(f"run-now-scan/{day}#")}
    return f"run-now-scan/{day}#{len(used) + 1}" if len(used) < per_day else None


USAGE_CHECKS = ROOT / "logs" / "usage_checks.jsonl"
USAGE_SLACK = 30            # Tavily's /usage lags; more than this above our ledger means spending we did not log


def usage_check(tav, cfg=None, ledger=None, slack=USAGE_SLACK, log=USAGE_CHECKS):
    """After a run: compare Tavily's GET /usage (free) with our ledger. Warns if /usage's plan + pay-as-you-go usage
    exceeds the ledger's account total by more than `slack` credits (e.g. a key used outside this repo), or if any
    pay-as-you-go usage appears. Appends one line to logs/usage_checks.jsonl and returns (ok, message). Never prints
    or stores a key; never raises."""
    cfg = cfg or load_budget()
    ours = account_spent(cfg, read_ledger() if ledger is None else ledger)
    try:
        acc = (tav.usage(tag="usage check after run") or {}).get("account") or {}
        theirs = (acc.get("plan_usage") or 0) + (acc.get("paygo_usage") or 0)
        ok = theirs <= ours + slack and not acc.get("paygo_usage")
        msg = (f"Tavily /usage {theirs} (plan {acc.get('plan_usage')}, pay-as-you-go {acc.get('paygo_usage')}) vs "
               f"ledger {ours}: " + ("OK" if ok else f"WARNING: /usage is more than {slack} credits above the ledger "
                                                      "or pay-as-you-go was used. Check for spending outside this repo."))
    except Exception as e:                                     # the check never breaks a run
        ok, theirs, msg = None, None, f"Tavily /usage check failed ({type(e).__name__}); ledger {ours}"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"time": datetime.now(timezone.utc).isoformat(), "usage": theirs, "ledger": ours,
                            "ok": ok, "message": msg}) + "\n")
    return ok, msg
