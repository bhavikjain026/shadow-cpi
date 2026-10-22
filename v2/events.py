"""Announced price changes for one month under Amendment C: the 13 pre-registered searches (English, Hindi and five
regional languages), search proposes -> Nano reads -> Extract verifies (Super re-reads, Amendment B). Each verified
claim gets its kind from the words in its cited line (v2.kinds), its CPI item, its role and its places.
Saves v2/evidence/events_<month>.json and adds every checked claim to the evidence ledger."""
import json

from v2 import kinds as K
from v2 import ledger as LG
from v2 import pipeline as PL
from v2 import rules as R


def run_month(month, tav, nem, nano, super_model, tag="v2:events"):
    cards = PL.propose(tav, nem, nano, K.QUERIES, month, tag, set(), domains=K.DOMAINS, max_results=10)
    PL.fetch_and_verify(tav, nem, nano, cards, month, K.ALL_WORDS, None, None, "", tag, super_model=super_model)
    for c in cards:
        for cl in c["claims"]:
            if "status" not in cl:
                continue
            kind = K.kind_of(cl["line"])
            cfg = K.KINDS.get(kind, {})
            cl.update({"kind": kind, "cpi": cfg.get("cpi", ""), "role": cfg.get("role", ""),
                       "states": sorted(K.states_of(cl.get("region"), cl["line"], cl.get("context"), c["title"]))})
            LG.append({"id": f"{month}:{kind}:{c['page_sha256'][:12]}:{R.text_hash(cl['line'])[:8]}",
                       "month": month, "cutoff": R.cutoff(month), "cpi_item": cfg.get("cpi") or f"none ({kind})",
                       "cpi_name": kind or "", "item": kind or "", "kind": kind or "", "place": cl.get("region") or "",
                       "state": ", ".join(cl["states"]), "unit": cl.get("unit") or "",
                       "price_type": "retail price change", "price": cl.get("price"), "old_price": cl.get("old_price"),
                       "new_price": cl.get("new_price"), "change": cl.get("change"), "published_date": c["published"],
                       "effective_date": cl.get("effective_date"), "found_date": c["found"], "line": cl["line"],
                       "url": c["url"], "page_sha256": c["page_sha256"], "page_file": c["page_file"],
                       "status": cl["status"], "reason": cl["reason"], "use": cfg.get("role", ""),
                       "search_call": c["search_call"], "extract_call": c["extract_call"],
                       "model": cl.get("read_by") or nano})
    out = {"month": month, "cutoff": R.cutoff(month), "window": list(R.window(month)), "queries": K.QUERIES,
           "cards": cards}
    (LG.ROOT / f"events_{month}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float))
    return cards
