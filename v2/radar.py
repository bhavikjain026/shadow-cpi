#!/usr/bin/env python3
"""October 2026 radar (v2/RADAR_PREREG.md): announced retail price changes taking effect in October, found before
MoSPI publishes, frozen at 29 Oct 23:59 IST, scored afterwards against an independently built list. Report only.

    python -m v2.radar               # one run (cap 'radar-2026-10'); refused without a decided strategy or after the freeze
    python -m v2.radar --freeze      # at the freeze: v2/radar/radar_2026-10.frozen.json + SHA-256
    python -m v2.radar --score       # once, after the scoring list exists
    python -m v2.radar --reclassify R3   # logged bug fix: saved claims, cached page text, 0 credits

Discovery uses the strategy decided in RADAR_PREREG.md ("Search strategy decided: X") with include_domains_mode
prefer; corroboration searches are restricted to a primary source's domain where one is known.
"""
import hashlib
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from shadow_cpi.budget import BudgetExceeded  # noqa: E402
from v2 import ablation as AB  # noqa: E402
from v2 import kinds as K  # noqa: E402
from v2 import pipeline as PL  # noqa: E402
from v2 import recall as RC  # noqa: E402
from v2 import rules as R  # noqa: E402
from v2 import whole as WH  # noqa: E402

MONTH = "2026-10"
BUDGET = "radar-2026-10"
FREEZE_UTC = datetime(2026, 10, 29, 18, 29, tzinfo=timezone.utc)          # 29 Oct 23:59 IST
PREREG = ROOT / "v2" / "RADAR_PREREG.md"
DIR = ROOT / "v2" / "radar"
RADAR = DIR / f"radar_{MONTH}.json"
FROZEN = DIR / f"radar_{MONTH}.frozen.json"
SCORING = DIR / f"scoring_list_{MONTH}.json"
SCORE = ROOT / "results" / f"radar_{MONTH}_score.json"
PRIMARY = json.loads((ROOT / "v2" / "radar_primary.json").read_text(encoding="utf-8"))
TAVILY_ONLY_KINDS = {k for k, v in K.KINDS.items() if v["role"] == "moves"}
SECOND_LEVEL = ("gov.in", "nic.in", "co.in", "org.in", "net.in", "ac.in")
# Amendment R2: distribution licensees whose tariff covers part of a state only (their own licence area), with no
# documented share of the state's CPI weight. Delhi's discoms are left out: DERC sets one tariff for all of Delhi.
LICENSEES = ["bsl", "बीएसएल", "bokaro steel", "बोकारो स्टील", "tata steel", "jusco", "tsuisl", "cesc",
             "tata power", "adani electricity", "best undertaking", "torrent power", "noida power", "npcl"]


def strategy(text=None):
    m = re.search(r"Search strategy decided:\s*([ABCT])\b", text if text is not None else PREREG.read_text())
    return m[1] if m else None


def registrable(domain):
    parts = domain.lower().removeprefix("www.").split(".")
    n = 3 if ".".join(parts[-2:]) in SECOND_LEVEL else 2
    return ".".join(parts[-n:])


def is_primary(domain, kind=None):
    d = domain.lower().removeprefix("www.")
    known = {v for k in PRIMARY if k != "_note" for v in PRIMARY[k].values()}
    return d.endswith((".gov.in", ".nic.in")) or any(d == p or d.endswith("." + p) for p in known)


def primary_for(kind, states):
    m = PRIMARY.get(kind, {})
    return next((m[s] for s in states if s in m), m.get("*"))


# ---------- discovery ----------
def discovery(strat, month, meter, nem, nano, sup, seen, skipped, tag):
    """Cards from the decided strategy, every search in prefer mode where it uses domains."""
    if strat == "A":
        return PL.propose(meter, nem, nano, K.QUERIES, month, tag, seen, domains=K.DOMAINS, max_results=10,
                          skipped=skipped), None
    plan, _, tries = AB.write_plan(nem, month, "B" if strat == "T" else strat, nano, sup, tag)
    cards = []
    for s in plan:
        sent = ({"auto_parameters": True, "max_results": AB.AUTO_MAX_RESULTS} if strat == "T" else
                {**AB.tavily_params(s), **({"include_domains_mode": "prefer"} if s["include_domains"] else {})})
        s["sent"] = sent
        try:
            resp, sid = meter.search(s["query"], **sent, tag=f"{tag} search")
        except BudgetExceeded as e:
            skipped.append({"call": "search", "query": s["query"], "why": str(e)})
            continue
        cards += PL.read_results(resp, sid, s["language"], month, nem, nano, tag, seen)
    return cards, {"plan": plan, "tries": tries}


def verify(cards, month, meter, nem, nano, sup, skipped, tag):
    PL.fetch_and_verify(meter, nem, nano, cards, month, K.WHOLE_WORDS, None, None, "", tag, super_model=sup,
                        skipped=skipped, whole_words=True)
    for c in cards:
        for cl in c["claims"]:
            if "status" in cl:
                classify(c, cl)


def classify(card, cl):
    """Amendment R2: kind from whole words in the cited line; states from the page, the model's region last."""
    kind = K.kind_of(cl["line"], whole=True)
    cl.update({"kind": kind, "role": K.KINDS.get(kind, {}).get("role", ""),
               "states": sorted(K.page_states(cl["line"], cl.get("context"), card["title"], card["url"],
                                              cl.get("region")))})


def reclassify(state, amendment="R3", pages=None):
    """Amendments R2-R3, 0 credits: re-judge every saved claim from the cached page text with the radar's whole-word
    rules (`v2.pipeline.judge`: the verifier, retail/domestic scope, dates, change), then kind and page-first states.
    The model's reading of each page (line, price, region, gloss) is kept as saved. Pages that failed the leak guard
    or their own date check are left as they were. Returns (events before, events after, per-claim changes)."""
    from shadow_cpi import evidence as E
    pages = pages or (ROOT / "v2" / "evidence")
    before, changes = state.get("events", []), []
    for c in state["cards"] + [cc for co in state["corroboration"] for cc in co["cards"]]:
        claims = [cl for cl in c["claims"] if "status" in cl]
        if not claims or not c.get("page_file"):
            continue
        text = (pages / c["page_file"]).read_text(encoding="utf-8")
        judged = not E.leak_line(text, MONTH) and R.page_date_check(text, MONTH, c.get("tavily_published"))[0]
        for cl in claims:
            old = {f: cl.get(f) for f in ("status", "reason", "price_type", "kind", "states")}
            if judged:
                cl.update(PL.judge(cl, c, text, MONTH, K.WHOLE_WORDS, None, None, "", whole_words=True))
            classify(c, cl)
            new = {f: cl.get(f) for f in old}
            if new != old:
                changes.append({"url": c["url"], "line": cl["line"], "before": old, "after": new})
                if old["status"] != new["status"]:
                    cl.setdefault(f"status_before_{amendment.lower()}", old["status"])
                    cl.setdefault(f"reason_before_{amendment.lower()}", old["reason"])
        if c.get("status") in ("verified", "context") and not any(cl.get("status") in ("verified", "context")
                                                                    for cl in claims):
            c["status"], c["reason"] = "rejected", ""
        PL.card_status(c)
    state["events"] = summarise(state["cards"])
    log = state.get("reclassified", [])
    log = [log] if isinstance(log, dict) else log
    state["reclassified"] = log + [{"amendment": amendment, "utc": datetime.now(timezone.utc).isoformat(),
                                    "credits": 0, "events_before": before, "events_after": state["events"],
                                    "claims_changed": changes}]
    return before, state["events"], changes


def same_event(ev, cl):
    """A corroborating claim: the matcher's rules (kind, +-2 days, shared state) with the event as reference."""
    ref = {"kind": ev["kind"], "month": MONTH, "date": ev["effective_date"], "states": ev["states"]}
    return RC.matches(ref, cl)


def corroborate(ev, month, meter, nem, nano, sup, seen, skipped, tag):
    """Amendment R1: one news search with arm A's settings (English news domains, mode prefer, no restriction to a
    primary domain), so a second independent outlet can be found for a single-source event."""
    if any(is_primary(s["domain"]) for s in ev["sources"]):
        return None
    start, end = R.window(month)
    place = ", ".join(ev["states"]) or "India"
    q = f"{ev['kind']} price {place} {datetime.strptime(month, '%Y-%m'):%B %Y}"
    try:
        resp, sid = meter.search(q, topic="news", search_depth="basic", max_results=10, start_date=start,
                                 end_date=end, include_domains=K.DOMAINS["en"], include_domains_mode="prefer",
                                 tag=f"{tag} corroborate")
    except BudgetExceeded as e:
        skipped.append({"call": "corroborate", "query": q, "why": str(e)})
        return None
    cards = PL.read_results(resp, sid, "en", month, nem, nano, f"{tag} corroborate", seen)
    verify(cards, month, meter, nem, nano, sup, skipped, f"{tag} corroborate")
    return {"domain": None, "mode": "prefer", "query": q, "cards": cards}


# ---------- events, tiers, effect ----------
def events(cards):
    out = {}
    for c in cards:
        for cl in c["claims"]:
            if cl.get("status") == "verified" and cl.get("kind"):
                key = (cl["kind"], cl.get("effective_date"), tuple(cl.get("states") or []))
                ev = out.setdefault(key, {"kind": key[0], "effective_date": key[1], "states": list(key[2]),
                                          "change": cl.get("change"), "sources": []})
                ev["sources"].append({"url": c["url"], "domain": c["domain"], "line": cl["line"],
                                      "published": c["published"], "search_request_id": c.get("search_request_id"),
                                      "extract_request_id": c.get("extract_request_id"), "via": "tavily"})
    return list(out.values())


def norm_line(s):
    return re.sub(r"\W+", " ", (s or "").lower()).strip()


def tier(ev):
    """corroborated = a primary source, or 2 publishers (registrable domains) whose cited lines are not the same
    text (a syndicated copy repeats the line, so it does not count as independent)."""
    if any(is_primary(s["domain"]) for s in ev["sources"]):
        return "corroborated"
    pubs = {}
    for s in ev["sources"]:
        pubs.setdefault(registrable(s["domain"]), set()).add(norm_line(s["line"]))
    seen_lines, independent = set(), 0
    for lines in pubs.values():
        independent += not (lines & seen_lines)
        seen_lines |= lines
    return "corroborated" if independent >= 2 else "verified"


def effect_pp(ev, inp=None):
    """needle(item trend + change x share of October x state share) - needle(item trend + 0), percentage points
    (Amendment R2: the baseline carves the item out too, so a zero change gives exactly 0 pp)."""
    from v2 import needle as N
    from v2.score import SCOPE_KIND
    code = K.KINDS.get(ev["kind"], {}).get("cpi")
    if ev["kind"] not in TAVILY_ONLY_KINDS or ev.get("change") is None or not ev.get("effective_date"):
        return None                                  # context kinds move through their spine / official series
    share = (31 - int(ev["effective_date"][8:]) + 1) / 31
    scope, weight, _, _ = WH.geography(SCOPE_KIND[ev["kind"]], " ".join(s["line"] for s in ev["sources"]), "", "",
                                       "", code, extra_states=ev["states"])          # Amendment R3: whole words
    if scope == "context" or licence_area(ev):
        return None                                  # a city or licence-area change with no documented share
    inp = inp or N.P.load_inputs()
    return N.yoy(MONTH, {code: ("add", ev["change"] * share * weight)}, inp) - N.yoy(MONTH, {code: ("add", 0.0)}, inp)


def licence_area(ev):
    """Amendment R2: an electricity tariff for one named distribution licensee (LICENSEES), narrower than the state."""
    return ev["kind"] == "electricity" and any(K.has_word(s["line"], n) for s in ev["sources"] for n in LICENSEES)


# ---------- run, freeze, score ----------
def run(tav, nem, nano, sup, now=None, strat=None):
    now = now or datetime.now(timezone.utc)
    if now > FREEZE_UTC or FROZEN.exists():
        raise SystemExit("the radar is frozen (29 Oct 23:59 IST): no more runs")
    strat = strat or strategy()
    if not strat:
        raise SystemExit("no 'Search strategy decided: X' line in v2/RADAR_PREREG.md: decide it first")
    DIR.mkdir(parents=True, exist_ok=True)
    state = json.loads(RADAR.read_text()) if RADAR.exists() else {"month": MONTH, "strategy": strat, "runs": [],
                                                                    "cards": [], "corroboration": []}
    seen = {c["url"] for c in state["cards"]}
    meter, skipped, tag = AB.Meter(tav), [], f"radar:{now:%Y-%m-%d}"
    cards, plan = discovery(strat, MONTH, meter, nem, nano, sup, seen, skipped, tag)
    verify(cards, MONTH, meter, nem, nano, sup, skipped, tag)
    state["cards"] += cards
    for ev in events(state["cards"]):
        if tier(ev) == "verified":
            co = corroborate(ev, MONTH, meter, nem, nano, sup, seen, skipped, tag)
            if co:
                state["corroboration"].append({**co, "for": [ev["kind"], ev["effective_date"], ev["states"]]})
                state["cards"] += [c for c in co["cards"] if any(same_event(ev, cl) for cl in c["claims"]
                                                                 if cl.get("status") == "verified")]
    state["runs"].append({"utc": now.isoformat(), "plan": plan, "calls": meter.calls, "skipped": skipped,
                          "complete": not skipped})
    state["events"] = summarise(state["cards"])
    RADAR.write_text(json.dumps(state, ensure_ascii=False, indent=1, default=float))
    return state


def summarise(cards, inp=None):
    out = []
    for ev in events(cards):
        ev["tier"] = tier(ev)
        ev["tavily_only"] = ev["kind"] in TAVILY_ONLY_KINDS and all(s["via"] == "tavily" for s in ev["sources"])
        try:
            ev["effect_pp"] = effect_pp(ev, inp)
        except Exception as e:                       # report the reason; the radar never fails on a display number
            ev["effect_pp"], ev["effect_error"] = None, type(e).__name__
        out.append(ev)
    return out


def freeze(now=None):
    now = now or datetime.now(timezone.utc)
    if FROZEN.exists():
        raise SystemExit("already frozen")
    if not RADAR.exists():
        raise SystemExit("nothing to freeze")
    data = json.loads(RADAR.read_text())
    data["frozen_utc"] = now.isoformat()
    text = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    FROZEN.write_text(text)
    FROZEN.with_suffix(".sha256").write_text(hashlib.sha256(text.encode("utf-8")).hexdigest() + "\n")
    return data


def score(frozen=None, scoring=None):
    if SCORE.exists():
        raise SystemExit("the radar is scored once")
    frozen = frozen or json.loads(FROZEN.read_text())
    lst = scoring or json.loads(SCORING.read_text())["changes"]
    cutoff = (FREEZE_UTC + timedelta(hours=5, minutes=30)).date().isoformat()
    counted = [c for c in lst if c["first_reported"] <= cutoff]                  # later reports are not misses
    out = {"scored_utc": datetime.now(timezone.utc).isoformat(), "list_size": len(lst), "counted": len(counted),
           "tiers": {}}
    for t in ("verified", "corroborated"):
        evs = [e for e in frozen["events"] if t == "verified" or e["tier"] == "corroborated"]
        claims = [{"status": "verified", "kind": e["kind"], "effective_date": e["effective_date"],
                   "states": e["states"]} for e in evs]
        hit = sum(any(RC.matches({**c, "month": MONTH}, cl) for c in lst) for cl in claims)
        found = sum(any(RC.matches({**c, "month": MONTH}, cl) for cl in claims) for c in counted)
        out["tiers"][t] = {"events": len(evs), "precision": hit / len(evs) if evs else None,
                           "matched_events": hit, "recall": found / len(counted) if counted else None,
                           "found": found}
    SCORE.write_text(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    if "--freeze" in sys.argv:
        print(freeze()["frozen_utc"])
    elif "--reclassify" in sys.argv:                 # Amendment R2: saved claims, cached text, 0 credits
        st = json.loads(RADAR.read_text())
        b, a, ch = reclassify(st, sys.argv[sys.argv.index("--reclassify") + 1])
        RADAR.write_text(json.dumps(st, ensure_ascii=False, indent=1, default=float))
        for name, evs in (("before", b), ("after", a)):
            print(name, [(e["kind"], e["effective_date"], e["states"], e["tier"], e["effect_pp"]) for e in evs])
        for x in ch:
            print("claim", x["url"][:70], x["before"], "->", x["after"])
    elif "--score" in sys.argv:
        print(json.dumps(score(), indent=1))
    else:
        from shadow_cpi.budget import Budgeted
        from shadow_cpi.nemotron import Nemotron
        from shadow_cpi.recorder import Recorder
        from shadow_cpi.settings import models
        from shadow_cpi.tavily import Tavily
        rec = Recorder()
        from shadow_cpi.budget import usage_check
        # Amendment R1: Tavily calls are sent fresh each day (saved and logged, never served from the cache) and charged
        tav = Budgeted(Tavily(recorder=Recorder(use_cache=False)), [BUDGET], fresh=True)
        s = run(tav, Nemotron(recorder=rec), models()["small"], models()["mid"])
        print(usage_check(tav.tav)[1])
        print(f"{len(s['events'])} events; {sum(e['tier'] == 'corroborated' for e in s['events'])} corroborated")
