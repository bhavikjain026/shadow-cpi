#!/usr/bin/env python3
"""October radar skeptic (v2/DRIFT_PREREG.md, part B). A flag only: it never changes tiers, effects or the freeze.

    python -m v2.radar_skeptic          # one search per radar event not searched yet (cap 'radar-skeptic-2026-10')
    python -m v2.radar_skeptic --dry    # events still to search and the credit estimate (0 credits)

Nemotron writes one search query per event, in the language of its first source page, looking for a reversal
(withdrawn, rolled back, stayed, postponed). Tavily searches inside the radar's own time lock. Code, not the model,
picks the quote: the first sentence of a kept result naming a reversal word and a word of the event's kind.
Output: v2/radar/skeptic_2026-10.json.
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from shadow_cpi.budget import BudgetExceeded, cap_of, load_budget, spent
from shadow_cpi.recorder import provenance
from shadow_cpi.tavily import best_date
from v2 import kinds as K
from v2 import radar as RD
from v2 import rules as R

BUDGET = "radar-skeptic-2026-10"
OUT = RD.DIR / "skeptic_2026-10.json"
MAX_QUERY = 300
REVERSAL = {
    "en": ["withdrawn", "withdraw", "withdraws", "withdrew", "rolled back", "roll back", "rolls back", "rollback",
           "stayed", "stays", "stay order", "postponed", "postpone", "postpones", "deferred", "put on hold",
           "reversed", "revoked", "scrapped"],
    "hi": ["वापस", "वापसी", "रोक", "स्थगित", "टाला", "टाली", "टल"],
}
REVERSAL_WORDS = REVERSAL["en"] + REVERSAL["hi"]
LANG_NAME = {"en": "English", "hi": "Hindi"}
SYSTEM = ("You write one web search query. Return JSON {\"query\": \"...\"}. The query looks for news that an "
          "announced price change in India was withdrawn, rolled back, stayed (e.g. by a court or regulator) or "
          "postponed. Write it in the language asked for. No dates, no site: operators, at most 20 words.")
SCHEMA = {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"],
          "additionalProperties": False}


def key(ev):
    return f"{ev['kind']}|{ev['effective_date']}|{','.join(sorted(ev['states']))}"


def lang_of(ev, radar):
    """The language of the event's first source page (its card's 'lang'), 'en' if unknown."""
    first = ev["sources"][0]["url"]
    for c in radar["cards"] + [cc for co in radar.get("corroboration", []) for cc in co["cards"]]:
        if c["url"] == first:
            return c.get("lang") or "en"
    return "en"


def prompt(ev, lang):
    change = "" if ev.get("change") is None else f" by {ev['change']:+.1%}"
    return (f"Language: {LANG_NAME.get(lang, 'English')}.\nPrice change: {ev['kind']}{change} in "
            f"{', '.join(ev['states']) or 'India'}, effective {ev['effective_date']}.\nWrite one search query, in "
            f"{LANG_NAME.get(lang, 'English')}, for news that this change was withdrawn, rolled back, stayed or "
            "postponed.")


def write_query(nem, models, ev, lang, tag):
    """(query or None, tries). Rule B.2: non-empty, at most 300 characters; small model first, then mid."""
    tries = []
    for m in models:
        try:
            out, cid = nem.chat_json(m, SYSTEM, prompt(ev, lang), SCHEMA, tag=f"{tag} query")
        except Exception as e:                       # one model failing passes the job to the next
            tries.append({"model": m, "error": type(e).__name__})
            continue
        q = (out or {}).get("query") if isinstance(out, dict) else None
        q = q.strip() if isinstance(q, str) else ""
        tries.append({"model": m, "call": cid, "query": q[:MAX_QUERY + 50]})
        if q and len(q) <= MAX_QUERY:
            return q, tries
    return None, tries


def sentences(text):
    return [s.strip() for s in re.split(r"[.!?।\n]+", text or "") if s.strip()]


def kind_words(kind):
    return K.KINDS.get(kind, {}).get("words", []) + K.FORMS.get(kind, [])


def challenge(result, ev):
    """The first sentence of a result's title and snippet with a reversal word and a word of the event's kind."""
    for s in sentences(f"{result.get('title', '')}\n{result.get('content', '')}"):
        if any(K.has_word(s, w) for w in REVERSAL_WORDS) and any(K.has_word(s, w) for w in kind_words(ev["kind"])):
            return s
    return None


def check_event(tav, nem, models, ev, radar, tag="skeptic"):
    """One event: the model's query, one time-locked search, code's flag. Raises BudgetExceeded before sending."""
    lang = lang_of(ev, radar)
    q, tries = write_query(nem, models, ev, lang, tag)
    row = {"event": key(ev), "lang": lang, "query": q, "model_tries": tries, "challenged": []}
    if not q:
        row["status"] = "skeptic not run (no valid query)"
        return row
    start, end = R.window(RD.MONTH)
    resp, sid = tav.search(q, topic="news", search_depth="basic", max_results=10, start_date=start, end_date=end,
                           tag=f"{tag} search")
    own = {s["url"] for s in ev["sources"]}
    kept = dropped = 0
    for r in resp.get("results", []):
        d, _ = best_date(r)
        if not d or not start <= d <= end or r.get("url") in own:
            dropped += 1
            continue
        kept += 1
        quote = challenge(r, ev)
        if quote:
            row["challenged"].append({"url": r["url"], "quote": quote, "date": d})
    row.update(status="challenged" if row["challenged"] else "not challenged", search_call=sid,
               credits=(resp.get("usage") or {}).get("credits") or 0, results=len(resp.get("results", [])),
               kept=kept, dropped=dropped, window=[start, end], **{f"search_{k}": v for k, v in provenance(resp).items()})
    return row


def load_state(path=OUT):
    return json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else {"month": RD.MONTH,
                                                                                         "events": {}}


def todo(radar, state):
    return [e for e in radar.get("events", []) if key(e) not in state["events"]]


def run(tav, nem, models, radar=None, state=None, now=None):
    now = now or datetime.now(timezone.utc)
    if now >= RD.FREEZE_UTC:
        raise SystemExit("the radar is frozen (29 Oct 23:59 IST): no more skeptic searches")
    radar = radar or json.loads(RD.RADAR.read_text(encoding="utf-8"))
    state = state or load_state()
    stopped, errors = None, []
    for ev in todo(radar, state):
        try:
            row = check_event(tav, nem, models, ev, radar)
        except BudgetExceeded as e:
            stopped = str(e)
            break
        except Exception as e:                  # a failed call is not charged: the event is tried again next run
            errors.append({"event": key(ev), "error": f"{type(e).__name__}: {str(e)[:200]}"})
            continue
        state["events"][key(ev)] = {**row, "utc": now.isoformat()}
    state.setdefault("runs", []).append({"utc": now.isoformat(), "complete": stopped is None and not errors,
                                         **({"stopped": stopped} if stopped else {}),
                                         **({"errors": errors} if errors else {})})
    return state


def flags(state):
    """{event key: [{'url', 'quote'}]} for the radar page; an event not searched yet is absent."""
    return {k: v["challenged"] for k, v in (state or {}).get("events", {}).items()}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    radar = json.loads(RD.RADAR.read_text(encoding="utf-8"))
    state = load_state()
    left = cap_of(BUDGET, load_budget()) - spent(BUDGET)
    print(f"{len(todo(radar, state))} events to search: about {len(todo(radar, state))} credits; {left} left")
    if "--dry" in argv:
        return
    from shadow_cpi.budget import Budgeted
    from shadow_cpi.nemotron import Nemotron
    from shadow_cpi.recorder import Recorder
    from shadow_cpi.settings import models
    from shadow_cpi.tavily import Tavily
    tav = Budgeted(Tavily(recorder=Recorder(use_cache=False)), [BUDGET], fresh=True)
    state = run(tav, Nemotron(recorder=Recorder()), [models()["small"], models()["mid"]], radar, state)
    OUT.write_text(json.dumps(state, ensure_ascii=False, indent=1))
    ch = sum(bool(v["challenged"]) for v in state["events"].values())
    print(f"skeptic: {len(state['events'])} events searched, {ch} challenged; "
          f"{'complete' if state['runs'][-1]['complete'] else 'INCOMPLETE (cap)'}")


if __name__ == "__main__":
    main()
