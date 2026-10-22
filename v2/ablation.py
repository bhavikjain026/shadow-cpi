#!/usr/bin/env python3
"""Amendment E (v2/PREREGISTRATION.md): who should write the Tavily searches? DEVELOPMENT data, report only.

    python -m v2.ablation A          # fixed templates (the 13 Amendment C queries), cache only, 0 new credits
    python -m v2.ablation B          # Nemotron writes 8 searches a month, English + Hindi (cap 'v2-ablation-B')
    python -m v2.ablation C          # Nemotron writes 13 searches a month, + 5 regional languages ('v2-ablation-C')
    python -m v2.ablation T          # Amendment F: B's query texts with Tavily auto_parameters ('v2-ablation-T')
    python -m v2.ablation --metrics  # once all four arms have run: results/v2_ablation.json and .md

Each arm runs once on Jan-Sep 2026 with the same reader and verifier as issue 14 (v2.pipeline). For arms B and C,
Nano (Super as fallback) writes each search's parameters as JSON; code validates every parameter (validate) before
any Tavily call and logs each correction. Nothing here writes the v2 evidence ledger or touches the score locks.
Saves v2/ablation/arm_<arm>_<month>.json.
"""
import json
import re
import statistics
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from shadow_cpi.budget import BudgetExceeded, Budgeted, spent  # noqa: E402
from shadow_cpi.nemotron import Nemotron  # noqa: E402
from shadow_cpi.recorder import provenance  # noqa: E402
from shadow_cpi.recorder import Recorder  # noqa: E402
from shadow_cpi.settings import models  # noqa: E402
from shadow_cpi.tavily import Tavily, best_date  # noqa: E402
from v2 import kinds as K  # noqa: E402
from v2 import pipeline as PL  # noqa: E402
from v2 import recall as RC  # noqa: E402
from v2 import rules as R  # noqa: E402

OUT = ROOT / "v2" / "ablation"
RESULTS = ROOT / "results" / "v2_ablation.json"
MONTHS = RC.MONTHS
REGIONAL = ["mr", "ta", "te", "kn", "bn"]
LANG_NAMES = {"en": "English", "hi": "Hindi", "mr": "Marathi", "ta": "Tamil", "te": "Telugu", "kn": "Kannada",
              "bn": "Bengali"}
ARMS = {
    "A": {"writer": "code (fixed templates)", "langs": list(LANG_NAMES), "n": 13, "budget": None},
    "B": {"writer": "Nemotron", "langs": ["en", "hi"], "n": 8, "min": {"en": 3, "hi": 3}, "budget": "v2-ablation-B"},
    "C": {"writer": "Nemotron", "langs": list(LANG_NAMES), "n": 13,
          "min": {"en": 3, "hi": 3, **{l: 1 for l in REGIONAL}}, "budget": "v2-ablation-C"},
    "T": {"writer": "Tavily auto_parameters (B's query texts)", "langs": ["en", "hi"], "n": 8,
          "budget": "v2-ablation-T"},
}
ARMS["Td"] = {"writer": "Tavily auto_parameters + our date window (exploratory, after scoring)", "langs": ["en", "hi"],
              "n": 8, "budget": "v2-ablation-Td"}
AUTO_MAX_RESULTS = 10                    # Amendment F: Tavily needs max_results from the caller; 10 as in arm A
MOVES = {k for k, v in K.KINDS.items() if v["role"] == "moves"}
CPI_NAMES = {"electricity": "electricity charges", "milk": "liquid milk", "lpg": "LPG cylinder", "diesel": "diesel",
             "petrol": "petrol", "metro": "metro fares", "bus": "bus fares", "rail": "rail fares",
             "mobile": "mobile phone tariffs"}
HOST = re.compile(r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$")
PLAN_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["searches"], "properties": {
    "searches": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["query", "language", "topic", "start_date", "end_date", "include_domains",
                     "include_domains_mode", "max_results"],
        "properties": {"query": {"type": "string"}, "language": {"type": "string"}, "topic": {"type": "string"},
                       "start_date": {"type": "string"}, "end_date": {"type": "string"},
                       "include_domains": {"type": "array", "items": {"type": "string"}},
                       "include_domains_mode": {"type": "string"}, "max_results": {"type": "integer"}}}}}}
PLAN_SYSTEM = ("You plan web searches with the Tavily search API to find ANNOUNCED retail price changes in India "
               "(price hikes or cuts, tariff orders, fare revisions) reported in news. You choose each search's "
               "words and its filters. Reply with JSON only.")


def plan_prompt(month, arm):
    start, end = R.window(month)
    cfg = ARMS[arm]
    need = ", ".join(f"at least {n} in {LANG_NAMES[l]} ({l})" for l, n in cfg["min"].items())
    return (f"Month: {datetime.strptime(month, '%Y-%m'):%B %Y}. Search window: {start} to {end} (publication "
            f"dates must be inside it).\n"
            f"Price changes we look for (household retail prices): "
            f"{', '.join(CPI_NAMES[k] for k in K.KINDS)}.\n"
            f"Write exactly {cfg['n']} searches, {need}. Write each query in its language's own script.\n"
            "For each search give: query (at most 400 characters); language (one of "
            f"{', '.join(cfg['langs'])}); topic ('news' or 'general'); start_date and end_date (YYYY-MM-DD, inside "
            "the window); include_domains (0 to 20 news site host names, e.g. example.com, to focus the search); "
            "include_domains_mode ('prefer' ranks those sites first, 'restrict' searches only them); max_results "
            "(1 to 10).\nReturn {\"searches\": [...]}.")


def _date(x):
    try:
        return date.fromisoformat(str(x)[:10]).isoformat() if x else None
    except ValueError:
        return None


def validate(raw, month, langs):
    """(search or None, corrections). Code's rules from Amendment E; the model never sets cost or the window."""
    start, end = R.window(month)
    fixes = []
    q = str(raw.get("query") or "").strip()
    if not q or len(q) > 400:
        return None, ["query empty or over 400 characters: search dropped"]
    lang = str(raw.get("language") or "").strip().lower()
    if lang not in langs:
        return None, [f"language '{lang}' not allowed in this arm: search dropped"]
    topic = raw.get("topic")
    if topic not in ("news", "general"):
        fixes.append(f"topic '{topic}' → 'news'")
        topic = "news"
    s, e = _date(raw.get("start_date")), _date(raw.get("end_date"))
    if s is None or not start <= s <= end:
        fixes.append(f"start_date {raw.get('start_date')!r} → {start if s is None or s < start else end}")
        s = start if s is None or s < start else end
    if e is None or not start <= e <= end:
        fixes.append(f"end_date {raw.get('end_date')!r} → {end if e is None or e > end else start}")
        e = end if e is None or e > end else start
    if s > e:
        fixes.append(f"start {s} after end {e} → window {start} to {end}")
        s, e = start, end
    doms, bad = [], []
    for d in raw.get("include_domains") or []:
        h = re.sub(r"^https?://", "", str(d).strip().lower()).split("/")[0].removeprefix("www.")
        (doms if HOST.match(h) and h not in doms else bad).append(h)
    if bad:
        fixes.append(f"dropped {len(bad)} invalid or repeated domains")
    if len(doms) > 20:
        fixes.append(f"{len(doms)} domains → first 20")
        doms = doms[:20]
    mode = raw.get("include_domains_mode")
    if mode not in ("prefer", "restrict"):
        fixes.append(f"include_domains_mode {mode!r} → 'prefer'")
        mode = "prefer"
    mr = raw.get("max_results")
    try:
        mr_ok = int(mr)
    except (TypeError, ValueError):
        mr_ok = 10
    if mr_ok != mr or not 1 <= mr_ok <= 10:
        fixes.append(f"max_results {mr!r} → {min(10, max(1, mr_ok))}")
    return {"query": q, "language": lang, "topic": topic, "start_date": s, "end_date": e, "include_domains": doms,
            "include_domains_mode": mode, "max_results": min(10, max(1, mr_ok))}, fixes


def select(valid, arm):
    """The arm's searches: language minimums first (in the model's order), then the rest, up to n."""
    cfg = ARMS[arm]
    picked, used = [], set()
    for lang, n in cfg["min"].items():
        for i, v in enumerate(valid):
            if sum(p["language"] == lang for p in picked) >= n:
                break
            if i not in used and v["language"] == lang:
                picked.append(v)
                used.add(i)
    picked += [v for i, v in enumerate(valid) if i not in used][:cfg["n"] - len(picked)]
    complete = len(picked) == cfg["n"] and all(sum(p["language"] == l for p in picked) >= n
                                               for l, n in cfg["min"].items())
    return picked, complete


def write_plan(nem, month, arm, nano, sup, tag):
    """Nano writes the month's searches; Super once if Nano gives no JSON or too few valid searches."""
    tries = []
    for model in (nano, sup):
        try:
            out, cid = nem.chat_json(model, PLAN_SYSTEM, plan_prompt(month, arm), PLAN_SCHEMA, tag=f"{tag} plan")
            raws, err = out.get("searches") or [], ""
        except ValueError as e:
            raws, cid, err = [], None, str(e)
        checked = [(r, *validate(r, month, ARMS[arm]["langs"])) for r in raws if isinstance(r, dict)]
        valid = [{**v, "written_by": model, "model_call": cid, "corrections": fx} for _, v, fx in checked if v]
        picked, complete = select(valid, arm)
        tries.append({"model": model, "call": cid, "error": err, "written": raws, "picked": picked,
                      "dropped": [{"raw": r, "why": fx} for r, v, fx in checked if not v], "complete": complete})
        if complete:
            break
    best = max(tries, key=lambda t: (t["complete"], len(t["picked"])))
    return best["picked"], best["complete"], tries


class Meter:
    """Wraps the budgeted Tavily client and records every call the arm makes: what was sent, Tavily's own credits
    for it (counted even when served from the cache), new credits charged now, and Tavily's response_time."""
    def __init__(self, tav):
        self.tav, self.calls = tav, []

    def _record(self, endpoint, params, fn):
        before = self.tav.used
        resp, cid = fn()
        self.calls.append({"endpoint": endpoint, "call_id": cid, "sent": params,
                           "credits": (resp.get("usage") or {}).get("credits") or 0,
                           "new_credits": self.tav.used - before, "response_time": resp.get("response_time"),
                           "n_results": len(resp.get("results", [])), **provenance(resp),
                           "auto_parameters": resp.get("auto_parameters")})
        return resp, cid

    def search(self, query, **params):
        sent = {"query": query, **{k: v for k, v in params.items() if k != "tag"}}
        return self._record("/search", sent, lambda: self.tav.search(query, **params))

    def extract(self, urls, **params):
        return self._record("/extract", {"urls": list(urls), **{k: v for k, v in params.items() if k != "tag"}},
                            lambda: self.tav.extract(urls, **params))


def dates_kept(resp, start, end):
    """Did Tavily keep a supplied window? (auto_parameters' own time_range and dates, and how many dated results fall
    inside the window). For arm T (no window sent) it records the same counts against the pre-registered window."""
    ap = resp.get("auto_parameters") or {}
    dated = [d for d in (best_date(r)[0] for r in resp.get("results", [])) if d]
    return {"auto_time_range": ap.get("time_range"), "auto_start_date": ap.get("start_date"),
            "auto_end_date": ap.get("end_date"), "dated_results": len(dated),
            "inside_window": sum(start <= d <= end for d in dated)}


def tavily_params(s):
    """What is sent to Tavily for a validated search (Amendment E: language sent only for Hindi, as arm A)."""
    p = {"topic": s["topic"], "search_depth": "basic", "max_results": s["max_results"], "start_date": s["start_date"],
         "end_date": s["end_date"]}
    if s["include_domains"]:
        p.update(include_domains=s["include_domains"], include_domains_mode=s["include_domains_mode"])
    if s["language"] == "hi":
        p["language"] = "hi"
    return p


def run_month(arm, month, meter, nem, nano, sup):
    tag, skipped, seen = f"v2:ablation {arm}", [], set()
    plan, complete, tries = None, True, []
    if arm == "A":
        cards = PL.propose(meter, nem, nano, K.QUERIES, month, tag, seen, domains=K.DOMAINS, max_results=10,
                           skipped=skipped)
    elif arm in ("T", "Td"):
        b = json.loads((OUT / f"arm_B_{month}.json").read_text(encoding="utf-8"))
        plan, cards = [], []
        start, end = R.window(month)
        dates = {"start_date": start, "end_date": end} if arm == "Td" else {}   # Td: arm A's window, nothing else
        for bs in b["plan"]:
            s = {"query": bs["query"], "language": bs["language"], "from_arm_b": True,
                 "sent": {"auto_parameters": True, "max_results": AUTO_MAX_RESULTS, **dates}}
            plan.append(s)
            try:
                resp, sid = meter.search(s["query"], **s["sent"], tag=f"{tag} search")
            except BudgetExceeded as e:
                skipped.append({"call": "search", "lang": s["language"], "query": s["query"], "why": str(e)})
                continue
            s.update(search_call=sid, n_results=len(resp.get("results", [])),
                     auto_parameters=resp.get("auto_parameters"), dates_kept=dates_kept(resp, start, end))
            cards += PL.read_results(resp, sid, s["language"], month, nem, nano, tag, seen)
    else:
        plan, complete, tries = write_plan(nem, month, arm, nano, sup, tag)
        cards = []
        for s in plan:
            s["sent"] = tavily_params(s)
            try:
                resp, sid = meter.search(s["query"], **s["sent"], tag=f"{tag} search")
            except BudgetExceeded as e:
                skipped.append({"call": "search", "lang": s["language"], "query": s["query"], "why": str(e)})
                continue
            s["search_call"], s["n_results"] = sid, len(resp.get("results", []))
            cards += PL.read_results(resp, sid, s["language"], month, nem, nano, tag, seen)
    PL.fetch_and_verify(meter, nem, nano, cards, month, K.ALL_WORDS, None, None, "", tag, super_model=sup,
                        skipped=skipped)
    for c in cards:                                      # kind and places, as v2.events.run_month
        for cl in c["claims"]:
            if "status" in cl:
                kind = K.kind_of(cl["line"])
                cl.update({"kind": kind, "cpi": K.KINDS.get(kind, {}).get("cpi", ""),
                           "role": K.KINDS.get(kind, {}).get("role", ""),
                           "states": sorted(K.states_of(cl.get("region"), cl["line"], cl.get("context"),
                                                        c["title"]))})
    return {"arm": arm, "month": month, "window": list(R.window(month)), "writer": ARMS[arm]["writer"],
            "plan": plan, "plan_complete": complete, "plan_tries": tries, "cards": cards, "skipped": skipped,
            "complete": complete and not skipped}


def run(arm, months=MONTHS):
    OUT.mkdir(parents=True, exist_ok=True)
    rec = Recorder()
    cfg = ARMS[arm]
    tav = Budgeted(Tavily(recorder=rec), [cfg["budget"] or "v2-ablation-A (cache only)"], cache_only=cfg["budget"] is None)
    nem, nano, sup = Nemotron(recorder=rec), models()["small"], models()["mid"]
    for m in months:
        p = OUT / f"arm_{arm}_{m}.json"
        if p.exists():
            raise SystemExit(f"{p} exists: each arm runs once (Amendment E)")
        meter = Meter(tav)
        out = run_month(arm, m, meter, nem, nano, sup)
        out["calls"] = meter.calls
        out["finished_utc"] = datetime.now(timezone.utc).isoformat()
        p.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float))
        ver = sum(cl.get("status") == "verified" for c in out["cards"] for cl in c["claims"])
        print(f"{arm} {m}: {len(out['cards'])} pages, {ver} verified claims, "
              f"{'complete' if out['complete'] else 'INCOMPLETE'}; new credits "
              f"{sum(c['new_credits'] for c in meter.calls)}" + (f" (budget total {spent(cfg['budget'])})"
                                                                 if cfg["budget"] else ""), flush=True)
    if cfg["budget"]:
        from shadow_cpi.budget import usage_check
        print(usage_check(tav.tav)[1], flush=True)


def events(claims):
    """Distinct verified events: (kind, effective date, states) among verified claims that have a kind."""
    out = {}
    for cl in claims:
        if cl.get("status") == "verified" and cl.get("kind"):
            out.setdefault((cl["kind"], cl.get("effective_date"), tuple(sorted(cl.get("states") or []))), cl)
    return out


def metrics(runs, reference=None):
    """Amendment E metrics for one arm from its month files."""
    ref = reference or json.loads(RC.REFERENCE.read_text(encoding="utf-8"))["changes"]
    by_month = {r["month"]: [{**cl, "url": c["url"]} for c in r["cards"] for cl in c["claims"] if "status" in cl]
                for r in runs}
    rows = RC.score(by_month, ref)
    evs = events([cl for cls in by_month.values() for cl in cls])
    moving = {k: cl for k, cl in evs.items() if k[0] in MOVES}
    false = [k for k, cl in moving.items() if not any(RC.matches(r, cl) for r in ref)]
    calls = [c for r in runs for c in r["calls"]]
    times = [c["response_time"] for c in calls if c.get("response_time") is not None]
    credits = sum(c["credits"] for c in calls)
    return {"recall": sum(r["v2"] == "FOUND" for r in rows), "total": len(rows),
            "found": [r["id"] for r in rows if r["v2"] == "FOUND"],
            "verified_events": len(evs), "moving_events": len(moving), "false_events_upper_bound": len(false),
            "false_events": [list(k) for k in false],
            "credits": credits, "new_credits": sum(c["new_credits"] for c in calls),
            "credits_per_verified_event": credits / len(evs) if evs else None,
            "median_latency_s": statistics.median(times) if times else None,
            "searches": sum(c["endpoint"] == "/search" for c in calls),
            "extracts": sum(c["endpoint"] == "/extract" for c in calls),
            "corrections": sum(len(s.get("corrections", [])) for r in runs for s in (r["plan"] or [])),
            "written_by": {m: sum(s.get("written_by") == m for r in runs for s in (r["plan"] or []))
                           for m in {s.get("written_by") for r in runs for s in (r["plan"] or [])} if m},
            "incomplete_months": [r["month"] for r in runs if not r["complete"]]}


STRUCTURED = ("language", "topic", "start_date", "end_date", "include_domains", "include_domains_mode")


def sent_bodies(runs, read_log=None, cache_dir=None):
    """The exact JSON bodies POSTed to Tavily /search for an arm (from the recorder's cache, found through the flight
    recorder's cache_key for each call id). The API key travels in the Authorization header, never in the body."""
    from shadow_cpi import recorder as RCD
    log = {e["id"]: e for e in (read_log or RCD.read_log)()}
    cache = Path(cache_dir or RCD.CACHE_DIR) / "tavily"
    out = []
    for r in runs:
        for c in r["calls"]:
            e = log.get(c["call_id"])
            if c["endpoint"] == "/search" and e and (cache / f"{e['cache_key']}.json").exists():
                out.append(json.loads((cache / f"{e['cache_key']}.json").read_text(encoding="utf-8"))["request"])
    return out


def diagnostics(runs, bodies=None):
    """Reported only (Amendment E addendum): no target, and they change none of the pre-registered metrics."""
    plans = [s for r in runs for s in (r["plan"] or [])]
    tries = [t for r in runs for t in r["plan_tries"]]
    searches = [c for r in runs for c in r["calls"] if c["endpoint"] == "/search"]
    claims = [cl for r in runs for c in r["cards"] for cl in c["claims"] if cl.get("status") == "verified"
              and cl.get("kind")]
    in_window = [c for r in runs for c in r["cards"] if not c["reason"].startswith(("published", "no publication"))]
    out = {"duplicate_results": sum(c["n_results"] for c in searches) - sum(len(r["cards"]) for r in runs),
           "duplicate_verified_claims": len(claims) - len(events(claims)),
           "params_corrected_by_code": sum(len(s.get("corrections", [])) for s in plans),
           "searches_dropped_by_code": sum(len(t["dropped"]) for t in tries),
           "plan_retries_super": sum(max(0, len(r["plan_tries"]) - 1) for r in runs),
           "super_rereads": sum(bool(c.get("super_reread")) for r in runs for c in r["cards"]),
           "plan_abstentions": sum(len(t["picked"]) < ARMS[r["arm"]]["n"] for r in runs for t in r["plan_tries"]),
           "reader_abstentions": sum(c["reason"] == "Nano found no price in the search text" for c in in_window),
           "pages_read": len(in_window),
           "auto_parameters_returned": sum(c.get("auto_parameters") is not None for c in searches)}
    if bodies is not None and plans:
        leaks = [b["query"] for b in bodies for k in STRUCTURED if f"{k}" in b["query"]]
        out["structured_fields"] = {
            "searches_checked": len(bodies),
            "with_dates_as_fields": sum("start_date" in b and "end_date" in b for b in bodies),
            "with_topic_field": sum("topic" in b for b in bodies),
            "with_domains_as_fields": sum("include_domains" in b and "include_domains_mode" in b for b in bodies),
            "hindi_with_language_field": sum(b.get("language") == "hi" for b in bodies),
            "parameter_names_inside_query_text": len(leaks)}
    return out


def equivalence(arms):
    """Amendment F: arms within 1 of the best recall are about equal; rank them by credits per verified event (lower
    first), then false events (lower first)."""
    best = max(a["recall"] for a in arms.values())
    top = [k for k, a in arms.items() if a["recall"] >= best - 1]
    rank = sorted(top, key=lambda k: (arms[k]["credits_per_verified_event"] is None,
                                      arms[k]["credits_per_verified_event"] or 0,
                                      arms[k]["false_events_upper_bound"]))
    return {"margin": 1, "best_recall": best, "top_group": top, "ranking": rank,
            "lower_recall": [k for k in arms if k not in top]}


def summarise():
    if RESULTS.exists():
        raise SystemExit(f"{RESULTS} exists: the ablation metrics are computed once (Amendment E)")
    out = {"computed_utc": datetime.now(timezone.utc).isoformat(), "label": "DEVELOPMENT data (Amendment E)",
           "matcher": "v2/recall.py at db2984c, unchanged", "arms": {}}
    for arm in ARMS:
        runs = [json.loads((OUT / f"arm_{arm}_{m}.json").read_text(encoding="utf-8")) for m in MONTHS
                if (OUT / f"arm_{arm}_{m}.json").exists()]
        if len(runs) != len(MONTHS):
            raise SystemExit(f"arm {arm} has {len(runs)} of {len(MONTHS)} months; run every arm first")
        out["arms"][arm] = {"writer": ARMS[arm]["writer"], "languages": ARMS[arm]["langs"], **metrics(runs),
                            "diagnostics": diagnostics(runs, sent_bodies(runs))}
    out["equivalence"] = equivalence(out["arms"])
    RESULTS.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    lines = ["# Search-parameter ablation (Amendment E)", "",
             f"**DEVELOPMENT data**, Jan–Sep 2026, computed {out['computed_utc'][:16]} UTC by `python -m v2.ablation "
             "--metrics` from `v2/ablation/`. Pre-registered in `v2/PREREGISTRATION.md` (Amendment E); matcher "
             "unchanged since db2984c; 29 known changes.", "",
             "| Arm | Searches written by | Recall | False events (upper bound) | Credits per verified event | "
             "Median Tavily latency | Credits (new now) | Incomplete months |", "|---|---|---|---|---|---|---|---|"]
    for arm, a in out["arms"].items():
        cpe = f"{a['credits_per_verified_event']:.1f}" if a["credits_per_verified_event"] is not None else "—"
        lat = f"{a['median_latency_s']:.2f} s" if a["median_latency_s"] is not None else "—"
        lines.append(f"| {arm} | {a['writer']} ({', '.join(a['languages'])}) | {a['recall']} of {a['total']} | "
                     f"{a['false_events_upper_bound']} of {a['moving_events']} | {cpe} | {lat} | {a['credits']} "
                     f"({a['new_credits']}) | {', '.join(a['incomplete_months']) or 'none'} |")
    eq = out["equivalence"]
    lines += ["", f"**Verdict (Amendment F, margin ±1 known change):** about equal on recall: "
              f"{', '.join(eq['top_group'])}; ranked within that group by credits per verified event, then false "
              f"events: {' > '.join(eq['ranking'])}." + (f" Lower recall: {', '.join(eq['lower_recall'])}."
                                                         if eq["lower_recall"] else "")]
    lines += ["", "**Diagnostics (reported only, addendum to Amendment E; no target):**", "",
              "| Arm | Duplicate results | Duplicate verified claims | Params corrected by code | Searches dropped "
              "by code | Plan retries (Super) | Super re-reads | Plan abstentions | Reader abstentions (of pages "
              "read) |", "|---|---|---|---|---|---|---|---|---|"]
    for arm, a in out["arms"].items():
        d = a["diagnostics"]
        lines.append(f"| {arm} | {d['duplicate_results']} | {d['duplicate_verified_claims']} | "
                     f"{d['params_corrected_by_code']} | {d['searches_dropped_by_code']} | {d['plan_retries_super']} | "
                     f"{d['super_rereads']} | {d['plan_abstentions']} | {d['reader_abstentions']} of "
                     f"{d['pages_read']} |")
    lines += ["", "False events: distinct CPI-moving verified events that match none of the 29 known changes; the "
              "reference list is the audit's, so this is an upper bound. Credits are Tavily's own per-call counts, "
              "including calls served from the cache (arm A is costed as when first run)."]
    RESULTS.with_suffix(".md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def reconcile(runs, ref):
    """One row per arm, every figure from the arm files: the reconciliation table (no new call)."""
    calls = [c for r in runs for c in r["calls"]]
    claims = [{**cl, "_card": c, "_month": r["month"]} for r in runs for c in r["cards"] for cl in c["claims"]
              if cl.get("status") == "verified" and cl.get("kind")]
    evs = events(claims)
    matched = {k: cl for k, cl in evs.items() if any(RC.matches(x, cl) for x in ref)}
    unmatched = {k: cl for k, cl in evs.items() if k not in matched}
    rows = RC.score({r["month"]: [cl for cl in claims if cl["_month"] == r["month"]] for r in runs}, ref)
    return {"credits": sum(c["credits"] for c in calls), "search_calls": sum(c["endpoint"] == "/search" for c in calls),
            "verified_claims": len(claims), "events": len(evs), "matched_events": len(matched),
            "unmatched_events": len(unmatched), "moving_events": sum(k[0] in MOVES for k in evs),
            "moving_unmatched": sum(k[0] in MOVES for k in unmatched),
            "recall": sum(r["v2"] == "FOUND" for r in rows),
            "with_provenance": sum(bool(c.get("request_id")) and bool(c.get("response_sha256")) for c in calls),
            "calls": len(calls), "unmatched": [
                {"month": cl["_month"], "item": k[0], "effective_date": k[1], "states": list(k[2]),
                 "quote": cl["line"], "url": cl["_card"]["url"], "page_date": cl["_card"].get("published"),
                 "printed_date": cl["_card"].get("printed_date")} for k, cl in unmatched.items()]}


def t_dates_section(ref):
    """The exploratory arm T+dates, in its own labelled section (results/v2_ablation_t_dates.json); empty until all
    nine months have run."""
    files = [OUT / f"arm_Td_{m}.json" for m in MONTHS]
    if not all(f.exists() for f in files):
        return []
    from collections import Counter
    runs = [json.loads(f.read_text(encoding="utf-8")) for f in files]
    m, r = metrics(runs), reconcile(runs, ref)
    plan = [x for run in runs for x in run["plan"] if "auto_parameters" in x]
    chose = Counter((str((x["auto_parameters"] or {}).get("topic")), str((x["auto_parameters"] or {}).get("search_depth")),
                     str((x["auto_parameters"] or {}).get("time_range"))) for x in plan)
    dk = [x["dates_kept"] for x in plan if x.get("dates_kept")]
    dated, inside = sum(d["dated_results"] for d in dk), sum(d["inside_window"] for d in dk)
    kept = sum(d["dated_results"] == d["inside_window"] and not d["auto_time_range"] for d in dk)
    out = {"label": "EXPLORATORY, added after scoring; cannot change the winner or any verdict", **m,
           "reconciliation": {k: v for k, v in r.items() if k != "unmatched"},
           "auto_parameters_chosen": [{"topic": t, "search_depth": d, "time_range": tr, "searches": n}
                                      for (t, d, tr), n in chose.most_common()],
           "dates_kept_searches": kept, "searches": len(dk), "dated_results": dated, "inside_window": inside}
    (ROOT / "results" / "v2_ablation_t_dates.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    return ["", "## Exploratory: arm T + dates (added after scoring; cannot change the winner or any verdict)", "",
            "Same query texts as arm T, `auto_parameters: true`, plus arm A's `start_date`/`end_date` window; no other "
            "field from us (dated line in v2/PREREGISTRATION.md).", "",
            "| Credits spent | Search calls | Verified claims | Distinct verified events | Matched to the 29 | Not "
            "matched (unchecked) | Recall | False events (upper bound) | Credits per verified event |",
            "|---|---|---|---|---|---|---|---|---|",
            f"| {r['credits']} | {r['search_calls']} | {r['verified_claims']} | {r['events']} | {r['matched_events']} | "
            f"{r['unmatched_events']} | {r['recall']} of 29 | {r['moving_unmatched']} of {r['moving_events']} | "
            + (f"{r['credits'] / r['events']:.1f} |" if r["events"] else "— |"), "",
            "**What auto_parameters chose** (topic, depth, time range → searches): "
            + "; ".join(f"{t}, {d}, {tr} → {n}" for (t, d, tr), n in chose.most_common()) + ".",
            f"**Did Tavily keep our dates?** {kept} of {len(dk)} searches returned only results inside the window with no "
            f"auto time range; {inside} of {dated} dated results fell inside the window."]


def write_report():
    """Rewrites results/v2_ablation.md from results/v2_ablation.json and the arm files: corrected labels, the
    reconciliation table, provenance, notes. No metric is recomputed and no number in the JSON changes."""
    out = json.loads(RESULTS.read_text(encoding="utf-8"))
    ref = json.loads(RC.REFERENCE.read_text(encoding="utf-8"))["changes"]
    rec = {arm: reconcile([json.loads((OUT / f"arm_{arm}_{m}.json").read_text(encoding="utf-8")) for m in MONTHS],
                          ref) for arm in out["arms"]}
    f = lambda x, d=1: "—" if x is None else f"{x:.{d}f}"  # noqa: E731
    L = ["# Search-parameter ablation (Amendments E and F)", "",
         f"**DEVELOPMENT data**, Jan–Sep 2026. Metrics computed once, {out['computed_utc'][:16]} UTC (commit 5b1eec0); "
         "this page re-presents them with corrected labels (see the label fix below). Matcher unchanged since "
         "db2984c; 29 known changes.", "",
         "## Reconciliation (every number below comes from this table)", "",
         "| Arm | Credits spent | Search calls | Verified claims | Distinct verified events | Events matched to the 29 "
         "| Not matched (unchecked; may include real changes missing from the 29) | Recall (of the 29) |",
         "|---|---|---|---|---|---|---|---|"]
    for arm, r in rec.items():
        L.append(f"| {arm} | {r['credits']} | {r['search_calls']} | {r['verified_claims']} | {r['events']} | "
                 f"{r['matched_events']} | {r['unmatched_events']} | {r['recall']} of 29 |")
    L += ["", "- **Distinct verified event:** a distinct (item, effective date, set of states) among an arm's verified "
          "claims. **Recall** counts the 29 known changes found by any verified claim; one event can match one change "
          "and several pages can report it, so recall and matched events differ.",
          "- **False events (upper bound)** = verified events of an item that moves CPI by itself (electricity, "
          "diesel, bus, rail, mobile) that match none of the 29, out of all such events (pre-registered, Amendment E "
          "metric 2). Milk, LPG and petrol events are left out because their spine or official series moves the "
          "number.",
          "- **Credits per verified event** = credits spent ÷ distinct verified events of any item (Amendment E "
          "metric 3).", "",
          "## Result", "",
          "| Arm | Searches written by | Recall | False events (upper bound): unmatched of CPI-moving events | "
          "Credits per verified event | Credits per known change found (added after scoring; descriptive) | "
          "Median Tavily latency (descriptive; pre-registered with no target, not used in the verdict) | "
          "Incomplete months |",
          "|---|---|---|---|---|---|---|---|"]
    for arm, a in out["arms"].items():
        r = rec[arm]
        L.append(f"| {arm} | {a['writer']} ({', '.join(a['languages'])}) | {r['recall']} of 29 | "
                 f"{r['moving_unmatched']} of {r['moving_events']} | "
                 f"{f(r['credits'] / r['events']) if r['events'] else '—'} ({r['credits']} ÷ {r['events']}) | "
                 f"{f(r['credits'] / r['recall']) if r['recall'] else '—'} ({r['credits']} ÷ {r['recall']}) | "
                 f"{f(a['median_latency_s'], 2)} s | {', '.join(a['incomplete_months']) or 'none'} |")
    eq = out["equivalence"]
    wb = out["arms"]["C"]["written_by"]
    sup_c, all_c = sum(v for k, v in wb.items() if "super" in k), sum(wb.values())
    L += ["", f"**Verdict (Amendment F, margin ±1 known change), unchanged:** top group {', '.join(eq['top_group'])}; "
          f"ranking {' > '.join(eq['ranking'])}; lower recall {', '.join(eq['lower_recall'])}.", "",
          "Arm A's credits are those of its calls when first made, in the issue 4 and issue 14 runs: the flight "
          "recorder has 213 uncached Tavily calls tagged `v2:events`, 205 credits, equal to the credit ledger's "
          "`v2-issue4` (150) + `v2-issue14` (55). Arm A itself re-ran them from the cache at 0 new credits.", "",
          "**Provenance (Amendment F):** request IDs + response hashes on every call of arms C and T "
          f"({rec['C']['with_provenance'] + rec['T']['with_provenance']} of {rec['C']['calls'] + rec['T']['calls']}); "
          "A and B ran before this logging existed (their responses are still in the recorder's cache).", "",
          "**Label fix (logged; no number changed).** Before: \"False events (upper bound) | 6 of 8\" next to "
          "\"Recall 6 of 29\" for arm A, which read as 6 false of 8 found. After: the column says it counts "
          "unmatched events among CPI-moving items only (8 for arm A, 2 of them matched: E1 and E4), and the "
          "reconciliation table shows all events. The formula is the pre-registered one; the code was right.", "",
          "## Diagnostics (reported only; addendum to Amendment E)", "",
          "| Arm | Duplicate results | Duplicate verified claims | Params corrected by code | Searches dropped by code "
          "| Plan retries (Super) | Super re-reads | Plan abstentions | Reader abstentions (of pages read) |",
          "|---|---|---|---|---|---|---|---|---|"]
    for arm, a in out["arms"].items():
        d = a["diagnostics"]
        L.append(f"| {arm} | {d['duplicate_results']} | {d['duplicate_verified_claims']} | "
                 f"{d['params_corrected_by_code']} | {d['searches_dropped_by_code']} | {d['plan_retries_super']} | "
                 f"{d['super_rereads']} | {d['plan_abstentions']} | {d['reader_abstentions']} of {d['pages_read']} |")
    L += ["", "## Notes", "",
          f"- Super wrote {sup_c} of C's {all_c} searches (Nano's plan failed in "
          f"{out['arms']['C']['diagnostics']['plan_retries_super']} of 9 months).",
          "- Model-written queries were sometimes poor, e.g. arm C, June: \"ವಿದ್ಯುತ್ ತರiffe ಜೂನ್ 2026 Karnataka Wisconsin "
          "growth\"; arm B, January: \"बस कि Fahrpreiserhöhung news\".",
          "- Arm T: Tavily's auto_parameters chose `time_range: \"w\"` (the past week), topic news and advanced depth for "
          "every search. Amendment F sends no dates, so every result was from October 2026, after every cutoff, and "
          "the verifier rejected all of them: 0 of 29 is the pre-registered result.",
          "- Median latency was pre-registered as Amendment E metric 4, with no target; it is descriptive only and "
          "plays no part in the verdict.",
          "- Credits per known change found (credits ÷ recall) was added after scoring, as a second credit column; "
          "it is descriptive and cannot change the verdict.",
          "- Every verified event that matches none of the 29 is listed in `audit/arms_unmatched.md` for a hand check."]
    L += t_dates_section(ref)
    RESULTS.with_suffix(".md").write_text("\n".join(L) + "\n")
    A = ["# Verified events not matched to the 29 known changes (four search arms)", "",
         "From `v2/ablation/` (Amendments E and F, development data). For a hand check: each is either a real change "
         "missing from the audit list or a false event. Page date = the date used by the verifier (address or "
         "Tavily); printed = the date printed on the page, if any.", "",
         "| Arm | Month | Item | Effective | States | Quote | URL | Page date | Printed | Hand check |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for arm, r in rec.items():
        for u in r["unmatched"]:
            q = u["quote"].replace("|", "/").replace("\n", " ")[:220]
            A.append(f"| {arm} | {u['month']} | {u['item']} | {u['effective_date']} | {', '.join(u['states']) or '—'} "
                     f"| {q} | {u['url']} | {u['page_date'] or '—'} | {u['printed_date'] or '—'} | |")
    (ROOT / "audit" / "arms_unmatched.md").write_text("\n".join(A) + "\n")
    return rec


if __name__ == "__main__":
    if "--metrics" in sys.argv:
        summarise()
    elif "--report" in sys.argv:
        write_report()
    else:
        run(sys.argv[1], sys.argv[2:] or MONTHS)
