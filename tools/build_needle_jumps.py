#!/usr/bin/env python3
"""Display only (docs/after_scoring_changes.md, 2026-10-27): add each step's jump to the saved Live build runs, offline
and with 0 calls. Reads the steps already in each run, recomputes its needle path to check it still matches the
saved values, then adds only 'jump_pp' (per step) and 'adds' (the 'What Tavily adds' bars). No existing field changes.

    python tools/build_needle_jumps.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from shadow_cpi import predict as P  # noqa: E402
from v2 import basket as B  # noqa: E402
from v2.needle import jumps, path  # noqa: E402

RUNS = [ROOT / "v2" / "evidence" / "run_2026-09_basket.json",
        ROOT / "v2" / "evidence" / "run_2026-04_milk_madhya-pradesh.json"]


def add(p, inp):
    run = json.loads(p.read_text(encoding="utf-8"))
    steps = run.get("timeline") or run.get("items") or []
    seq = [(s["cpi_code"], s["mode"], s.get("value", s.get("change"))) for s in steps]
    start, after = path(run["month"], seq, inp)
    saved = [run["needle"]["start"]] + [s["yoy_after"] for s in steps]
    if [start] + after != saved:
        raise SystemExit(f"{p.name}: the recomputed needle path differs from the saved one; not touching it")
    if "timeline" in run:
        B.add_jumps(run, run["month"], inp)
    else:
        for s, j in zip(steps, jumps(run["month"], seq, inp)):
            s["jump_pp"] = j
    p.write_text(json.dumps(run, ensure_ascii=False, indent=1, default=float))
    return run


def main(paths=RUNS):
    inp = P.load_inputs()
    for p in paths:
        if p.exists():
            run = add(Path(p), inp)
            steps = run.get("timeline") or run.get("items") or []
            print(f"{Path(p).name}: {len(steps)} step jumps added" + (
                "; bars " + ", ".join(f"{b['pp']:+.4f}" for b in run["adds"]["bars"]) if "adds" in run else ""))


if __name__ == "__main__":
    main([Path(a) for a in sys.argv[1:]] or RUNS)
