#!/usr/bin/env python3
"""October page drift (v2/DRIFT_PREREG.md, part A). Descriptive only: no forecast, seal, tier or effect changes.

    python -m v2.drift          # one daily run (cap 'drift-2026-10'), after the radar in tools/radar_daily.sh
    python -m v2.drift --dry    # the URL set and the credit estimate, nothing sent (0 credits)

For each radar page with a saved copy and a cited line: Tavily Extract (basic) again, normalise, SHA-256, compare with
the saved copy. A change is logged with a diff of at most 300 characters (never the page), whether each cited line is
still there and whether its number changed. Output: v2/radar/drift_2026-10.json.
"""
import difflib
import hashlib
import json
import math
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from shadow_cpi.budget import BudgetExceeded, cap_of, load_budget, spent
from shadow_cpi.recorder import provenance
from v2 import leakcheck as LC
from v2 import radar as RD

ROOT = Path(__file__).resolve().parent.parent
BUDGET = "drift-2026-10"
OUT = RD.DIR / "drift_2026-10.json"
PAGES = ROOT / "v2" / "evidence"
IST = timezone(timedelta(hours=5, minutes=30))
BATCH = 5                                   # 5 URLs per extract call = 1 credit (basic)
DIFF_MAX = 300
SIMILAR = 0.6
DEVANAGARI = str.maketrans("०१२३४५६७८९", "0123456789")


# ---------- rules A.4-A.6 ----------
def normalise(text):
    """Drop page-furniture lines (v2.leakcheck.IGNORE), collapse whitespace in each line, drop empty lines."""
    lines = (re.sub(r"\s+", " ", ln).strip() for ln in (text or "").split("\n") if not LC.IGNORE.search(ln))
    return "\n".join(ln for ln in lines if ln)


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def short_diff(old, new, limit=DIFF_MAX):
    """Lines removed (-) and added (+), in order, cut to `limit` characters."""
    out = [f"{d[0]} {d[2:]}" for d in difflib.ndiff(old.split("\n"), new.split("\n")) if d[:1] in "-+"]
    s = "\n".join(out)
    return s if len(s) <= limit else s[:limit - 1] + "…"


def numbers(line):
    return set(re.findall(r"\d+(?:\.\d+)?", (line or "").translate(DEVANAGARI).replace(",", "")))


def quote_check(line, new_norm):
    """(quote still present, number changed: 'yes' | 'no' | 'unknown') for one cited line."""
    q = re.sub(r"\s+", " ", line or "").strip()
    if q and q in new_norm:
        return True, "no"
    best, ratio = None, 0.0
    for ln in new_norm.split("\n"):
        r = difflib.SequenceMatcher(None, q, ln).ratio()
        if r > ratio:
            best, ratio = ln, r
    if ratio < SIMILAR:
        return False, "unknown"
    return False, "yes" if numbers(best) != numbers(q) else "no"


def summarise_quotes(checks):
    present = all(p for p, _ in checks)
    nums = [n for _, n in checks]
    number = "yes" if "yes" in nums else "unknown" if "unknown" in nums else "no"
    return present, number


# ---------- rule A.1: which URLs ----------
def bundle(radar):
    """{url: {'page_file', 'found', 'lines'}} for cards with a saved page and at least one cited line."""
    out = {}
    for c in radar["cards"] + [cc for co in radar.get("corroboration", []) for cc in co["cards"]]:
        lines = [cl["line"] for cl in c.get("claims", []) if cl.get("line")]
        if not c.get("page_file") or not lines:
            continue
        u = out.setdefault(c["url"], {"page_file": c["page_file"], "found": c.get("found"), "lines": []})
        u["lines"] += [ln for ln in lines if ln not in u["lines"]]
    return out


def due(urls, now):
    """URLs to fetch now: not those whose saved copy was fetched on today's UTC date (rule A.1)."""
    today = now.astimezone(timezone.utc).date().isoformat()
    return [u for u, x in urls.items() if x["found"] != today]


def estimate(n):
    return math.ceil(n / BATCH)


# ---------- the run ----------
def load_state(path=OUT):
    return json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else {"month": RD.MONTH,
                                                                                         "runs": []}


def run(tav, radar=None, state=None, now=None, pages=PAGES):
    """One daily run. Returns the state with the new run appended (or unchanged, with a reason, if not allowed)."""
    now = now or datetime.now(timezone.utc)
    state = state or load_state()
    radar = radar or json.loads(RD.RADAR.read_text(encoding="utf-8"))
    day = now.astimezone(IST).date().isoformat()
    if now >= RD.FREEZE_UTC:
        raise SystemExit("the radar is frozen (29 Oct 23:59 IST): no more drift runs")
    if any(r["ist_date"] == day for r in state["runs"]):
        raise SystemExit(f"drift already ran on {day} (IST): once a day")
    urls = bundle(radar)
    todo = due(urls, now)
    rows, failed, not_checked, credits, complete = [], [], [], 0, True
    for k in range(0, len(todo), BATCH):
        batch = todo[k:k + BATCH]
        try:
            resp, cid = tav.extract(batch, extract_depth="basic", tag="drift extract")
        except BudgetExceeded as e:
            not_checked += todo[k:]
            complete, why = False, str(e)
            break
        credits += (resp.get("usage") or {}).get("credits") or 0
        got = {p["url"]: p.get("raw_content") or "" for p in resp.get("results", [])}
        for u in batch:
            text = got.get(u, "")
            if not text:
                failed.append(u)
                continue
            old = normalise((Path(pages) / urls[u]["page_file"]).read_text(encoding="utf-8"))
            new = normalise(text)
            row = {"url": u, "changed": sha(old) != sha(new), "saved_sha256": sha(old), "new_sha256": sha(new),
                   "extract_call": cid, **{f"extract_{k}": v for k, v in provenance(resp).items()}}
            if row["changed"]:
                checks = [quote_check(ln, new) for ln in urls[u]["lines"]]
                row["quote_present"], row["number_changed"] = summarise_quotes(checks)
                row["quotes"] = [{"line": ln[:200], "present": p, "number_changed": n}
                                 for ln, (p, n) in zip(urls[u]["lines"], checks)]
                row["diff"] = short_diff(old, new)
            rows.append(row)
    state["runs"].append({
        "ist_date": day, "utc": now.isoformat(), "credits": credits, "complete": complete,
        "urls_in_set": len(urls), "skipped_fetched_today": len(urls) - len(todo), "checked": len(rows),
        "changed": sum(r["changed"] for r in rows), "failed": failed, "not_checked": not_checked,
        **({} if complete else {"stopped": why}), "pages": rows})
    return state


def latest(state):
    """The Field Report summary of the latest run: N of M changed and, per changed page, the two flags."""
    if not state or not state.get("runs"):
        return None
    r = state["runs"][-1]
    ch = [p for p in r["pages"] if p["changed"]]
    return {"ist_date": r["ist_date"], "checked": r["checked"], "changed": len(ch), "failed": len(r["failed"]),
            "not_checked": len(r["not_checked"]), "complete": r["complete"], "credits": r["credits"],
            "runs": len(state["runs"]), "credits_total": sum(x["credits"] for x in state["runs"]),
            "pages": [{"url": p["url"], "quote_present": p["quote_present"], "number_changed": p["number_changed"],
                       "diff": p["diff"]} for p in ch]}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    radar = json.loads(RD.RADAR.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    todo = due(bundle(radar), now)
    cfg = load_budget()
    left = cap_of(BUDGET, cfg) - spent(BUDGET)
    print(f"{len(bundle(radar))} URLs in the set, {len(todo)} to fetch: about {estimate(len(todo))} credits; "
          f"{left} left of the {cap_of(BUDGET, cfg)} cap")
    if "--dry" in argv:
        return
    from shadow_cpi.budget import Budgeted
    from shadow_cpi.recorder import Recorder
    from shadow_cpi.tavily import Tavily
    tav = Budgeted(Tavily(recorder=Recorder(use_cache=False)), [BUDGET], fresh=True)   # a fresh copy each day
    state = run(tav, radar, now=now)
    OUT.write_text(json.dumps(state, ensure_ascii=False, indent=1))
    r = state["runs"][-1]
    print(f"drift {r['ist_date']}: {r['changed']} of {r['checked']} pages changed, {len(r['failed'])} failed, "
          f"{len(r['not_checked'])} not checked; {r['credits']} credits; {'complete' if r['complete'] else 'INCOMPLETE'}")


if __name__ == "__main__":
    main()
