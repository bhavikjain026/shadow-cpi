#!/usr/bin/env python3
"""Build the files the app reads that are not written by the pipeline itself (results/app/). 0 credits: reads the
local flight recorder, cache, manifests and audit files only.

    python tools/build_app_data.py

Writes:
  results/app/flight_recorder.jsonl   trimmed copy of logs/flight_recorder.jsonl (logs/ and cache/ are not committed)
  results/app/audit_summary.json      counts from audit/event_audit.{md,csv} and audit/missed_events.md (cross-checked)
  results/app/saved_run.json          the saved run the app opens on: the latest month's event layer
  results/app/tavily_trace_2026-03.json  every Tavily call for March 2026, the funnel, and the failures
"""
import csv
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from shadow_cpi import evidence as E  # noqa: E402
from shadow_cpi.recorder import read_log  # noqa: E402
from shadow_cpi.tavily import best_date  # noqa: E402

OUT = ROOT / "results" / "app"
KEEP = ("id", "time", "service", "endpoint", "cached", "latency_ms", "parent", "tag", "n_results", "n_failed",
        "credits")
# Tavily's documented defaults; a trace lists only the settings a call changed from these.
DEFAULTS = {"/search": {"topic": "general", "search_depth": "basic", "max_results": 5, "chunks_per_source": 3,
                        "include_answer": False, "include_raw_content": False, "include_images": False,
                        "include_domains": [], "exclude_domains": [], "include_usage": True},
            "/extract": {"extract_depth": "basic", "format": "markdown", "include_images": False,
                         "include_usage": True},
            "/map": {"max_depth": 1, "max_breadth": 20, "limit": 50, "allow_external": True, "include_usage": True},
            "/crawl": {"max_depth": 1, "max_breadth": 20, "limit": 50, "allow_external": True,
                       "extract_depth": "basic", "include_usage": True}}


def git_head():
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                          text=True).stdout.strip()


def cached(e):
    p = ROOT / "cache" / e["service"] / f"{e['cache_key']}.json"
    return json.loads(p.read_text()) if p.exists() else None


def flight_snapshot(log):
    rows = []
    for e in log:
        r = {k: e[k] for k in KEEP if k in e}
        p = dict(e.get("params") or {})
        if isinstance(p.get("urls"), list) and len(p["urls"]) > 2:
            p = {**p, "urls": p["urls"][:2], "n_urls": len(p["urls"])}
        r["params"] = {k: v for k, v in p.items() if k not in ("include_domains", "exclude_domains")}
        rows.append(r)
    (OUT / "flight_recorder.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")
    return len(rows)


def audit_summary():
    md = (ROOT / "audit" / "event_audit.md").read_text()
    rows = list(csv.DictReader((ROOT / "audit" / "event_audit.csv").open()))
    verdicts = {v: sum(r["verdict"].strip().lower() == v for r in rows) for v in ("correct", "partly", "wrong",
                                                                                     "unclear")}
    m = re.search(r"\*\*(\d+) of (\d+) fully correct, (\d+) partly, (\d+) wrong, (\d+) unclear; (\d+) confirmed", md)
    stated = dict(zip(("correct", "checked", "partly", "wrong", "unclear", "second_source"), map(int, m.groups())))
    assert (stated["checked"], stated["correct"], stated["partly"], stated["wrong"], stated["unclear"]) == \
        (len(rows), verdicts["correct"], verdicts["partly"], verdicts["wrong"], verdicts["unclear"]), "audit mismatch"
    miss = (ROOT / "audit" / "missed_events.md").read_text()
    ref = [ln for ln in miss.splitlines() if re.match(r"\|\s*[MLFET]\d+\s*\|", ln)]
    found = [ln for ln in ref if "**FOUND**" in ln]
    via_series = [ln for ln in ref if "MISSED" in ln and "**yes" in ln.split("|")[-2]]
    t = re.search(r"\*\*Total\*\* \| \*\*(\d+)\*\* \| \*\*(\d+)\*\*", miss)
    w = re.search(r"\*\*(\d+) of (\d+)\*\*", miss)
    assert (len(ref), len(found)) == (int(t.group(1)), int(t.group(2))), "missed_events totals mismatch"
    assert (len(found) + len(via_series), len(ref)) == (int(w.group(1)), int(w.group(2))), "series total mismatch"
    events_now = sum(len(json.loads(p.read_text())["events"]) for p in sorted((ROOT / "manifests").glob("2026-0*.json")))
    fixes = re.findall(r"^\| ([a-d]) \| ", (ROOT / "docs" / "after_scoring_changes.md").read_text(), re.M)
    out = {"events_checked": len(rows), "verdicts": verdicts, "second_source": stated["second_source"],
           "reference_changes": len(ref), "found_directly": len(found),
           "found_incl_official_series": len(found) + len(via_series),
           "fixes": sorted(set(fixes)), "events_before_fixes": len(rows), "events_after_fixes": events_now,
           "sources": {"verdicts": "audit/event_audit.csv (cross-checked with audit/event_audit.md)",
                       "second_source": "audit/event_audit.md", "recall": "audit/missed_events.md",
                       "fixes": "docs/after_scoring_changes.md §4", "events_after_fixes": "manifests/2026-0*.json"}}
    (OUT / "audit_summary.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return out


def saved_run():
    month = sorted(p.stem for p in (ROOT / "manifests").glob("2026-0*.json"))[-1]
    man = json.loads((ROOT / "manifests" / f"{month}.json").read_text())
    layer = {r["month"]: r for r in csv.DictReader((ROOT / "results" / "replay_layers.csv").open())}[month]
    times = sorted(q["retrieved_at"] for q in man["queries"] if q.get("retrieved_at"))
    out = {"label": f"Saved run: event scan for {E.MONTHS_EN[int(month[5:]) - 1]} {month[:4]} (latest replay month)",
           "month": month, "searched_from_utc": times[0] if times else None,
           "searched_to_utc": times[-1] if times else None, "manifest_written_utc": man["created_utc"],
           "code_commit": man["code_commit"], "events": man["events"], "counts": man["counts"],
           "n_searches": len(man["queries"]), "credits": int(layer["credits"]),
           "source": f"manifests/{month}.json, results/replay_layers.csv (credits)"}
    (OUT / "saved_run.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return out


def non_default(endpoint, request):
    d = DEFAULTS.get(endpoint, {})
    skip = {"query", "urls", "url", "include_usage"}
    return {k: v for k, v in request.items() if k not in skip and d.get(k, object()) != v}


def trace(month="2026-03"):
    log = read_log()
    start, end = E.month_window(month)
    pre_start, _ = E.search_window(month, E.EVENT_PRE_DAYS)
    led = {json.loads(l)["call_id"]: json.loads(l)["credits"] for l in (ROOT / "results" / "credit_ledger.jsonl").open()}
    live = [e for e in log if not e["cached"]]
    by_parent = {}
    for e in live:
        by_parent.setdefault(e.get("parent"), []).append(e)
    roots = []
    for e in live:
        if e["service"] != "tavily":
            continue
        p = e.get("params", {})
        if e["endpoint"] == "/search" and p.get("start_date", "") >= pre_start and p.get("end_date", "9") <= end \
                and p.get("end_date", "") >= pre_start:
            roots.append(e)
        elif e["endpoint"] == "/extract" and e.get("parent") is None and any(
                re.search(r"(0[1-9]|[12]\d|3[01])-03-2026", u) for u in p.get("urls", [])):
            roots.append(e)                                    # IBJA daily reports dated in March
    roots = [e for e in roots if not (e.get("tag") or "").startswith("poll-")]     # poll baselines, not evidence
    ids, calls = {e["id"] for e in roots}, []
    todo = list(roots)
    while todo:                                                # follow children (extracts after a search)
        e = todo.pop(0)
        for ch in by_parent.get(e["id"], []):
            if ch["id"] not in ids:
                ids.add(ch["id"])
                todo.append(ch)
    tav = [e for e in live if e["id"] in ids and e["service"] == "tavily"]
    nem = [e for e in live if e["id"] in ids and e["service"] == "nebius"]
    urls_found = dated_in = 0
    for e in tav:
        c = cached(e)
        req = (c or {}).get("request", {})
        produced = []
        if e["endpoint"] == "/search" and c:
            res = c["response"].get("results", [])
            inside = sum(bool(d) and req.get("start_date", "") <= d <= req.get("end_date", "") for d, _ in map(best_date, res))
            urls_found += len(res)
            dated_in += inside
            produced.append(f"{len(res)} results, {inside} dated inside the window")
        if e["endpoint"] == "/extract":
            produced.append(f"{e.get('n_results', 0)} pages read, {e.get('n_failed', 0)} failed")
        kids = by_parent.get(e["id"], [])
        if kids:
            produced.append(f"{sum(k['service'] == 'tavily' for k in kids)} follow-up Tavily calls, "
                            f"{sum(k['service'] == 'nebius' for k in kids)} Nemotron reads")
        calls.append({"id": e["id"], "time": e["time"], "endpoint": e["endpoint"], "job": e.get("tag"),
                      "what": (req.get("query") or ", ".join((req.get("urls") or [])[:2]))[:160],
                      "settings": non_default(e["endpoint"], req), "credits": led.get(e["id"], e.get("credits")),
                      "latency_ms": e["latency_ms"], "produced": "; ".join(produced)})
    calls.sort(key=lambda c: c["time"])
    pages_read = sum(e.get("n_results", 0) for e in tav if e["endpoint"] == "/extract")
    gate = sum((e.get("tag") or "").endswith("gatekeeper") for e in nem)
    reads = sum((e.get("tag") or "").endswith(("events", "quotes")) for e in nem)
    man = json.loads((ROOT / "manifests" / f"{month}.json").read_text())
    p2 = json.loads(subprocess.run(["git", "show", f"f00bd45:manifests/{month}.json"], cwd=ROOT, capture_output=True,
                                   text=True).stdout)["counts"]
    pred = json.loads((ROOT / "results" / "replay_predictions.json").read_text())[month]["c"]["evidence"]
    used = {c: v for c, v in pred.items() if v["change"] is not None}
    funnel = [
        {"stage": "Addresses found by Tavily search", "n": urls_found, "source": "flight recorder + cache"},
        {"stage": "Dated inside the search window", "n": dated_in, "source": "page address / published date"},
        {"stage": "Pages read by Tavily Extract", "n": pages_read, "source": "flight recorder"},
        {"stage": "Pages checked by the gatekeeper model", "n": gate, "source": "flight recorder (Nemotron)"},
        {"stage": "Pages read for prices or events", "n": reads, "source": "flight recorder (Nemotron)"},
        {"stage": "Price quotes extracted / verified word-for-word", "n": f"{p2['quotes_extracted']} / "
                                                                          f"{p2['quotes_verified']}",
         "source": "manifests/2026-03.json at f00bd45 (Prompt 2 quote run)"},
        {"stage": "Price events extracted / verified", "n": f"{man['counts']['events_extracted']} / "
                                                            f"{man['counts']['events_verified']}",
         "source": "manifests/2026-03.json"},
        {"stage": "Numbers used in the (c) prediction", "n": len(used),
         "source": "results/replay_predictions.json", "detail": {c: v["source"] for c, v in used.items()}},
    ]
    failures = []
    for f in sorted((ROOT / "results" / "prompt_t").glob("*.json")):
        rep = json.loads(f.read_text())
        for s in rep.get("sites", []) if isinstance(rep, dict) else []:
            for t in s.get("tried", []):
                if t.get("error") or t.get("n_urls") == 0:
                    failures.append({"what": f"Map {t['url']}", "result": t.get("error") or "0 addresses, no error",
                                     "source": f"results/prompt_t/{f.name}"})
            if "map_urls" in s and not s["map_urls"] and not s.get("tried"):
                failures.append({"what": f"Map {s['url']}", "result": "0 addresses, no error",
                                 "source": f"results/prompt_t/{f.name}"})
    gokul = [e for e in log if (e.get("tag") or "").startswith("prompt-t:dairy-extract") and "gokul" in e["tag"]]
    for e in gokul:
        c = cached(e)
        for r in (c or {}).get("response", {}).get("results", []):
            if r["url"].endswith(".pdf") and len(re.sub(r"\s+", "", r.get("raw_content") or "")) < 700:
                failures.append({"what": f"Extract ({c['request'].get('extract_depth')}) {r['url']}",
                                 "result": "only the letterhead came back: the rate table is an image",
                                 "source": f"flight recorder id {e['id']}"})
    ibja_failed = [e for e in tav if e["endpoint"] == "/extract" and e.get("n_failed")]
    if ibja_failed:
        failures.append({"what": f"{len(ibja_failed)} IBJA report extracts in this month's trace",
                         "result": f"{sum(e['n_failed'] for e in ibja_failed)} report addresses failed "
                                   "(holidays: retried on the next day)", "source": "flight recorder"})
    out = {"month": month, "built_utc": datetime.now(timezone.utc).isoformat(), "n_calls": len(calls),
           "credits": sum(c["credits"] or 0 for c in calls), "calls": calls, "funnel": funnel,
           "failures": failures,
           "note": "Uncached calls only (the first time each request was sent). Settings = what differs from "
                   "Tavily's defaults."}
    (OUT / f"tavily_trace_{month}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    n = flight_snapshot(read_log())
    a = audit_summary()
    s = saved_run()
    t = trace()
    (OUT / "built.json").write_text(json.dumps({"built_utc": datetime.now(timezone.utc).isoformat(),
                                                "from_commit": git_head()}, indent=1))
    print(f"flight recorder rows {n}; audit {a['events_checked']} events, recall {a['found_directly']}/"
          f"{a['reference_changes']} ({a['found_incl_official_series']} incl. series); saved run {s['month']} "
          f"({len(s['events'])} events); March trace {t['n_calls']} Tavily calls, {t['credits']} credits, "
          f"{len(t['failures'])} failures")


if __name__ == "__main__":
    main()
