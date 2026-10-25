#!/usr/bin/env python3
"""Value of information per searchable item (display only: the radar and the score do not use it).

    python -m v2.voi        # results/voi.json (0 credits, no API call)

VOI(item), in percentage points of headline month-on-month CPI = CPI weight share x item uncertainty x chance of a
price change, all from the 2025 calibration year of the official 2024-series item indices (never the 2026 test months):
  - weight share: the item's official 2024-series weight / 100;
  - uncertainty: the standard deviation of the item's 2025 month-on-month % change;
  - chance of a change: the share of 2025 months whose month-on-month change was at least CHANGE_PCT in size.
A search is "worth up to" the summed VOI of the items its words name. The stop rule: searching further is not worth it
once the VOI of the items not yet covered is below STOP_PP.
"""
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from shadow_cpi import official as O  # noqa: E402
from shadow_cpi.verify import norm  # noqa: E402
from v2 import kinds as K  # noqa: E402

CALIBRATION_YEAR = "2025"
CHANGE_PCT = 1.0                 # a month counts as "a price change" when the item moved by at least 1% (either way)
STOP_PP = 0.01
OUT = ROOT / "results" / "voi.json"


def item_stats(series, weights, year=CALIBRATION_YEAR):
    """Per kind with an official item code: weight share, 2025 sd of m/m % change, chance of a change, VOI (pp)."""
    out = {}
    for kind, v in K.KINDS.items():
        code = v["cpi"]
        s = series.get(code) if code else None
        if not s or code not in weights:
            out[kind] = {"cpi_code": code or None, "voi_pp": None, "why_missing": "no official item index"}
            continue
        months = sorted(m for m in s if m.startswith(year))
        mom = [(s[b] / s[a] - 1) * 100 for a, b in zip(months, months[1:])]
        sd = statistics.stdev(mom) if len(mom) > 1 else 0.0
        p = sum(abs(x) >= CHANGE_PCT for x in mom) / len(mom) if mom else 0.0
        w = weights[code] / 100
        out[kind] = {"cpi_code": code, "weight_share": w, "sd_mom_pct": sd, "p_change": p, "months": len(mom),
                     "voi_pp": w * sd * p}
    return out


def _has(word, text):
    """Whole-word match for Latin-script words ('bus' does not match 'business'); substring for Indic scripts."""
    w = norm(word)
    return bool(re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", text)) if w.isascii() else w in text


def kinds_in(query):
    t = norm(query or "")
    return [k for k, v in K.KINDS.items() if any(_has(w, t) for w in v["words"])]


def search_worth(query, stats):
    """'Why this search: worth up to X pp' = summed VOI of the items the query names (None if it names none)."""
    vals = [stats[k]["voi_pp"] for k in kinds_in(query) if stats.get(k, {}).get("voi_pp") is not None]
    return sum(vals) if vals else None


def stop_rule(stats, stop=STOP_PP):
    """Items in VOI order. Before each search, the VOI still uncovered; searching stops once that is below `stop`
    (stop_after = how many items are worth a search; 0 if even the whole basket is below `stop`)."""
    items = sorted(((k, s["voi_pp"]) for k, s in stats.items() if s["voi_pp"] is not None), key=lambda x: -x[1])
    remaining = sum(v for _, v in items)
    total, rows, stop_at = remaining, [], None
    for i, (k, v) in enumerate(items):
        if stop_at is None and remaining < stop:
            stop_at = i
        rows.append({"kind": k, "voi_pp": v, "remaining_before_pp": remaining, "worth_searching": stop_at is None})
        remaining -= v
    return {"order": rows, "stop_after": len(items) if stop_at is None else stop_at, "stop_pp": stop, "total_pp": total}


def credits_by_item(ledger, calls):
    """Real credits per item from the credit ledger, joined by call id to the logged search query; a search that
    names several items splits its credits equally; extracts and unnamed searches go to 'not item-specific'."""
    q = {c["call_id"]: (c.get("sent") or {}).get("query") for c in calls if c.get("call_id")}
    out = {}
    for e in ledger:
        cr = e.get("credits") or 0
        if cr <= 0:
            continue
        ks = kinds_in(q.get(e.get("call_id"))) if e.get("endpoint") == "/search" else []
        for k in ks or ["not item-specific"]:
            out[k] = out.get(k, 0) + cr / max(1, len(ks))
    return out


def logged_calls():
    """Every call record with a query that the arms and the radar saved (they carry the ledger's call ids)."""
    calls = []
    for f in sorted((ROOT / "v2" / "ablation").glob("arm_*.json")):
        calls += json.loads(f.read_text(encoding="utf-8")).get("calls", [])
    radar = ROOT / "v2" / "radar" / "radar_2026-10.json"
    if radar.exists():
        calls += [c for r in json.loads(radar.read_text(encoding="utf-8"))["runs"] for c in r["calls"]]
    return calls


def build():
    from shadow_cpi.budget import read_ledger
    series, weights, _, _ = O.load_tidy()
    stats = item_stats(series, weights)
    out = {"calibration_year": CALIBRATION_YEAR, "change_pct": CHANGE_PCT, "items": stats, "stop": stop_rule(stats),
           "searches": [{"lang": lang, "query": q, "items": kinds_in(q), "worth_up_to_pp": search_worth(q, stats)}
                        for lang, q in K.QUERIES],
           "credits_by_item": credits_by_item(read_ledger(), logged_calls()),
           "label": "display only: the radar and the score do not use it"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    return out


if __name__ == "__main__":
    o = build()
    print(f"{OUT.relative_to(ROOT)}: stop after {o['stop']['stop_after']} items of {len(o['stop']['order'])}")
