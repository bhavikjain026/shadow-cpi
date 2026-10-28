#!/usr/bin/env python3
"""Five leak-free research trajectories from TimeLock-34 cases, replayed from cached responses (0 Tavily credits,
0 Nemotron calls, no network). Each case's time-locked search (the "dates_filter" arm: Tavily's date filter on, the
window ending on the cutoff) is replayed through timelock.trajectories.generate. A case whose search or page extract
is not in the cache is skipped and named; nothing is fetched to fill the gap.

    python examples/trajectory_demo.py                          # cache/ in this checkout
    python examples/trajectory_demo.py --cache ../shadow-cpi/cache
    python examples/trajectory_demo.py --check                  # exit 1 if the written files would change

Also writes examples/trajectories/index.json (which cases had a cached search, which were written or skipped) and the
counts block in docs/trajectories.md, both read back from the written files, so no count in the doc is typed.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from timelock.trajectories import CacheMiss, CachedTavily, dumps, generate  # noqa: E402

DOC = ROOT / "docs" / "trajectories.md"
BEGIN, END = "<!-- counts:begin (examples/trajectory_demo.py writes this block) -->", "<!-- counts:end -->"

CASES = ROOT / "benchmarks" / "timelock34" / "cases.jsonl"
OUT = ROOT / "examples" / "trajectories"
WANT = ("E1", "M3", "T3", "R5", "C6")      # one per kind/month spread; others fill in if one lacks cached data
N = 5
ARM = "dates_filter"


def task_for(case):
    req = dict(case["requests"][ARM])
    req.pop("include_usage", None)
    return {"question": case["question"], "source": f"TimeLock-34 {case['id']} ({case['dataset']}), arm {ARM}",
            "searches": [req]}


def build(cache_dir):
    cases = [json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines() if line.strip()]
    order = sorted(cases, key=lambda c: (c["id"] not in WANT, WANT.index(c["id"]) if c["id"] in WANT else 0))
    cache = CachedTavily(cache_dir)
    searched = []
    for case in cases:
        try:
            cache.search(**task_for(case)["searches"][0])
            searched.append(case["id"])
        except CacheMiss:
            pass
    made, skipped = {}, []
    for case in order:
        if len(made) == N:
            break
        try:
            traj = generate(task_for(case), case["cutoff"], client=cache)
        except CacheMiss as e:
            skipped.append((case["id"], str(e)))
            continue
        if traj["searches"][0]["response_sha256"] != case["receipts"][ARM]["response_sha256"]:
            raise SystemExit(f"{case['id']}: replayed response does not match the case's receipt")
        made[case["id"]] = traj
    index = {"benchmark": "benchmarks/timelock34/cases.jsonl", "arm": ARM, "cases": len(cases),
             "search_cached": len(searched), "written": list(made), "skipped": [{"id": i, "why": w.rsplit(" in ", 1)[0]} for i, w in skipped]}
    return made, skipped, index


def counts_block(out=OUT):
    """The doc's counts paragraph, read from the written files."""
    index = json.loads((out / "index.json").read_text(encoding="utf-8"))
    ts = [json.loads((out / f"{cid}.json").read_text(encoding="utf-8")) for cid in index["written"]]
    c = {k: sum(t["counts"][k] for t in ts) for k in ("results", "kept", "kept_as_of_verified", "kept_not_checked",
                                                     "dropped", "leak", "date_flag")}
    skipped = ", ".join(s["id"] for s in index["skipped"]) or "none"
    return (f"{BEGIN}\n"
            f"Of the {index['cases']} TimeLock-34 cases, {index['search_cached']} have their time-locked search in the "
            f"cache. Written: {', '.join(index['written'])} ({len(ts)} trajectories); skipped for missing cached data: "
            f"{skipped}. Across the {len(ts)}: {c['results']} results, {c['kept']} kept, {c['dropped']} dropped "
            f"({c['leak']} leak, {c['date_flag']} date_flag). **Only {c['kept_as_of_verified']} of the {c['kept']} "
            f"kept results has a page copy as of the cutoff (as-of verified); the other {c['kept_not_checked']} are "
            f"snippet-level evidence, not checked as of the cutoff.**\n{END}")


def with_counts(doc_text, block):
    a, b = doc_text.index(BEGIN), doc_text.index(END) + len(END)
    return doc_text[:a] + block + doc_text[b:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=str(ROOT / "cache"))
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    made, skipped, index = build(a.cache)
    for cid, why in skipped:
        print(f"SKIPPED {cid}: {why}")
    OUT.mkdir(parents=True, exist_ok=True)
    stale = []
    for cid, traj in made.items():
        path, text = OUT / f"{cid}.json", dumps(traj)
        c = traj["counts"]
        print(f"{cid}: {c['results']} results, kept {c['kept']} (as-of verified {c['kept_as_of_verified']}, "
              f"not checked {c['kept_not_checked']}), dropped {c['dropped']} "
              f"(leak {c['leak']}, date_flag {c['date_flag']}); receipt {traj['receipt']['sha256'][:12]}")
        if a.check:
            stale += [] if path.exists() and path.read_text(encoding="utf-8") == text else [path.name]
        else:
            path.write_text(text, encoding="utf-8")
    index_text = json.dumps(index, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    if a.check:
        if not (OUT / "index.json").exists() or (OUT / "index.json").read_text(encoding="utf-8") != index_text:
            stale.append("index.json")
        doc = DOC.read_text(encoding="utf-8")
        if not stale and with_counts(doc, counts_block()) != doc:
            stale.append("docs/trajectories.md counts block")
    else:
        (OUT / "index.json").write_text(index_text, encoding="utf-8")
        DOC.write_text(with_counts(DOC.read_text(encoding="utf-8"), counts_block()), encoding="utf-8")
    if len(made) < N:
        print(f"only {len(made)} of {N} cases had cached data")
    if a.check and stale:
        print("would change: " + ", ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
