#!/usr/bin/env python3
"""v2 issue 1, the tracer bullet: one basket item end to end (milk, Madhya Pradesh, April 2026), under the
pre-registration and Amendment A (v2/PREREGISTRATION.md).

    python -m v2.tracer                 # may spend credits (hard cap 'v2-issue1' in config/budget.json)
    python -m v2.tracer --cache-only    # re-run from the cache, 0 credits

Search proposes -> Nano reads -> Extract verifies (v2.pipeline). Then Amendment A: milk is covered by the government
price spine, so the spine moves milk and verified milk events are context; a city event with no statewide
confirmation and no documented city share is context too. The run is saved for the Live build page.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from shadow_cpi import predict as P  # noqa: E402
from shadow_cpi.budget import Budgeted, spent  # noqa: E402
from shadow_cpi.evidence import spine_change  # noqa: E402
from shadow_cpi.nemotron import Nemotron  # noqa: E402
from shadow_cpi.recorder import Recorder  # noqa: E402
from shadow_cpi.settings import models  # noqa: E402
from shadow_cpi.tavily import Tavily  # noqa: E402
from v2 import ledger as LG  # noqa: E402
from v2 import pipeline as PL  # noqa: E402
from v2 import rules as R  # noqa: E402
from v2.needle import jumps, path  # noqa: E402

BUDGET = "v2-issue1"
QUERIES = {"milk": [("en", "milk price hike per litre Madhya Pradesh"),
                    ("hi", "मध्य प्रदेश दूध के दाम बढ़े प्रति लीटर")]}


def use_of(cl, cpi_code, spine_covers, kind, card):
    """Amendment A: 'moves CPI' or 'context: why' for a verified claim (rule 1, then rule 2)."""
    role, why = R.source_role(cpi_code, spine_covers=spine_covers)
    if role == "context":
        return f"context: {why}", None
    sc, weight, where, why = R.geography(kind, cl["line"], cl.get("region") or "", cl.get("seller") or "",
                                         card["title"] + " " + cl.get("context", ""), cpi_code)
    return ("context: " + why, None) if sc == "context" else (f"moves CPI ({sc}: {where})", weight)


def run(month="2026-04", item="milk", state="madhya pradesh", cache_only=False):
    cfg = R.ITEMS[item]
    rec = Recorder()
    tav = Budgeted(Tavily(recorder=rec), [BUDGET], cache_only=cache_only)
    nem, nano = Nemotron(recorder=rec), models()["small"]
    inp = P.load_inputs()
    cards = PL.propose(tav, nem, nano, QUERIES[item], month, f"v2:{item}", set())
    PL.fetch_and_verify(tav, nem, nano, cards, month, cfg["words"], cfg["units"], state, item, f"v2:{item}",
                        super_model=models()["mid"])
    ch, n_zones = spine_change(inp["spine"], item, month)
    factor = inp["factors"][item]["factor"]
    for c in cards:
        for cl in c["claims"]:
            if cl.get("status") == "verified":
                cl["use"], _ = use_of(cl, cfg["cpi_code"], ch is not None, item, c)
    PL.ledger_rows(cards, month, cfg["cpi_code"], cfg["cpi_name"], item, state, nano)
    steps = [(cfg["cpi_code"], "level", factor * ch)] if ch is not None else []
    start, after = path(month, steps, inp)
    out = {"month": month, "item": item, "cpi_item": cfg["cpi_code"], "cpi_name": cfg["cpi_name"], "state": state,
           "cutoff": R.cutoff(month), "window": list(R.window(month)), "queries": QUERIES[item], "model_read": nano,
           "built_utc": datetime.now(timezone.utc).isoformat(), "cards": cards,
           "items": [{"cpi_code": cfg["cpi_code"], "name": cfg["cpi_name"], "source": "government price spine (DoCA)",
                      "detail": f"{n_zones} zones, pass-through factor {factor:.3f}", "change": factor * ch,
                      "mode": "level", "yoy_after": after[0]}] if steps else [],
           "needle": {"start": start, "end": after[-1] if after else start},
           "credits_budget": BUDGET, "credits_spent": spent(BUDGET)}
    for it, j in zip(out["items"], jumps(month, steps, inp)):             # display only
        it["jump_pp"] = j
    LG.ROOT.mkdir(parents=True, exist_ok=True)
    p = LG.ROOT / f"run_{month}_{item}_{state.replace(' ', '-')}.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    return out, p


if __name__ == "__main__":
    o, p = run(cache_only="--cache-only" in sys.argv)
    v = [cl for c in o["cards"] for cl in c["claims"] if cl.get("status") == "verified"]
    print(f"{len(o['cards'])} cards; {len(v)} verified claims ({sum(cl['use'].startswith('moves') for cl in v)} move "
          f"CPI); needle {o['needle']}; credits ({BUDGET}) {o['credits_spent']}; wrote {p.relative_to(ROOT)}")
