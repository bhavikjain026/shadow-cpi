#!/usr/bin/env python3
"""Build v3's files (v3/PREREG.md). Cache only: no Tavily or Nemotron call is ever sent (0 credits).

    python -m v3.build retro                          # results/v3_retrospective.json (Jan-Sep, not a test)
    python -m v3.build 2026-10 --cutoff 2026-10-28    # results/v3_nowcast_2026-10.json, after v1's seal
    python -m v3.build 2026-10 --cutoff 2026-10-28 --v1-seal sealed/dry-run/2026-10.json --dry-run   # print only

A live month is built from the same inputs as v1 (build_nowcast.gather, cache only) and refused unless it matches
v1's seal: the same evidence cutoff, the same manifest and prediction-file SHA-256, no code change since v1's
recorded commit (only sealed/ and results/ may differ), and (c) recomputed here equal to v1's headline_yoy.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from shadow_cpi import official as O  # noqa: E402
from shadow_cpi import predict as P  # noqa: E402
from shadow_cpi.live_range import LIVE_MONTHS  # noqa: E402
from v3 import model as V  # noqa: E402

RETRO = ROOT / "results" / "v3_retrospective.json"
CODE_FREE = ("sealed/", "results/")          # paths that may change between v1's commit and the v3 build


class Refuse(Exception):
    """A reason not to build. Printed as FAIL; nothing is written."""


def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def git(root, *args):
    r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    if r.returncode != 0:
        raise Refuse(f"git {' '.join(args)} failed: {r.stderr.strip() or r.stdout.strip()}")
    return r.stdout.strip()


def build_retro(inp=None):
    inp = inp or P.load_inputs()
    cal = V.calibration(inp)
    return {"label": "retrospective, not a test", "range_label": V.LABEL, "prereg": "v3/PREREG.md",
            "months": O.TEST_MONTHS, "tier_weights": V.W, "alpha": V.ALPHA,
            "methods": {m: cal[m] for m in V.METHODS}, "v1_c": cal["v1_c"],
            "created_utc": datetime.now(timezone.utc).isoformat()}


def committed_retro(root=ROOT):
    """results/v3_retrospective.json, refused unless today's inputs still give the same half-widths."""
    p = Path(root) / "results" / "v3_retrospective.json"
    if not p.exists():
        raise Refuse("results/v3_retrospective.json not found: run python -m v3.build retro and commit it")
    saved, fresh = json.loads(p.read_text(encoding="utf-8")), build_retro()
    for m in V.METHODS:
        if saved["methods"][m]["half_width"] != fresh["methods"][m]["half_width"]:
            raise Refuse(f"{m} half-width now {fresh['methods'][m]['half_width']!r}, committed "
                         f"{saved['methods'][m]['half_width']!r}: the Jan-Sep inputs changed")
    return saved


def check_against_v1(month, cutoff_utc, v1c_yoy, v1_seal, root=ROOT):
    """Refuse unless v3 used exactly v1's sealed inputs. Returns the checks for the output file."""
    root = Path(root)
    seal_path = Path(v1_seal)
    if not seal_path.exists():
        raise Refuse(f"v1 seal not found: {seal_path} (v3 is built right after v1's seal)")
    sealed = json.loads(seal_path.read_text(encoding="utf-8"))
    if sealed.get("target_month") != month:
        raise Refuse(f"v1 seal is for {sealed.get('target_month')}, not {month}")
    if sealed.get("evidence_cutoff_utc") != cutoff_utc:
        raise Refuse(f"evidence cutoff {cutoff_utc} differs from v1's {sealed.get('evidence_cutoff_utc')}")
    for key, rel in (("manifest_sha256", sealed.get("manifest")), ("prediction_file_sha256",
                                                                     sealed.get("prediction_file"))):
        p = root / rel if rel else None
        now = sha256_file(p) if p and p.exists() else None
        if now != sealed.get(key):
            raise Refuse(f"{rel}: SHA-256 now {now}, v1 sealed {sealed.get(key)}")
    changed = [f for f in git(root, "diff", "--name-only", sealed["code_commit"], "HEAD").splitlines()
               + [l[3:] for l in git(root, "status", "--porcelain", "--untracked-files=no").splitlines()]
               if not f.startswith(CODE_FREE)]
    if changed:
        raise Refuse(f"code changed since v1's commit {sealed['code_commit'][:12]}: {', '.join(changed[:5])}")
    if v1c_yoy != sealed["headline_yoy"]:
        raise Refuse(f"(c) recomputed by v3 = {v1c_yoy!r}, v1 sealed {sealed['headline_yoy']!r}: inputs differ")
    return {"v1_seal": seal_path.resolve().relative_to(root.resolve()).as_posix()
            if seal_path.resolve().is_relative_to(root.resolve()) else str(seal_path),
            "v1_seal_sha256": sha256_file(seal_path), "manifest_sha256": sealed["manifest_sha256"],
            "prediction_file_sha256": sealed["prediction_file_sha256"], "v1_code_commit": sealed["code_commit"],
            "v1_headline_yoy": sealed["headline_yoy"], "v1_c_recomputed": v1c_yoy, "all_match": True}


def default_gather(month, cutoff):
    import build_nowcast as BN
    from shadow_cpi.budget import Budgeted
    from shadow_cpi.recorder import Recorder
    from shadow_cpi.tavily import Tavily
    tav = Budgeted(Tavily(recorder=Recorder()), ["live-month"], cache_only=True)
    inp, _, missing = BN.gather(month, cutoff, tav)
    return inp, missing


def build_live(month, cutoff, v1_seal, gather=default_gather, retro=None, root=ROOT):
    import build_nowcast as BN
    if month not in LIVE_MONTHS:
        raise Refuse(f"{month} is not a live month {LIVE_MONTHS}")
    cut = BN.cutoff_utc(cutoff)
    inp, missing = gather(month, cutoff)
    pred = V.predict(month, inp)
    checks = check_against_v1(month, cut, pred["v1_c"], v1_seal, root)
    retro = retro or committed_retro(root)  # the 9 Jan-Sep misses, as published
    out = {"target_month": month, "label": "experimental (v3)", "primary": "v3a", "prereg": "v3/PREREG.md",
           "range_label": V.LABEL, "evidence_cutoff_utc": cut, "tier_weights": V.W,
           "created_utc": datetime.now(timezone.utc).isoformat(), "inputs_match_v1": checks,
           "missing_inputs": missing}
    for m in V.METHODS:
        out[m] = {**V.with_range(pred[m]["yoy"], retro["methods"][m]["half_width"]),
                  "calibration_abs_misses": sorted(abs(r["miss"]) for r in retro["methods"][m]["months"].values())}
    out["v3a"]["events"] = pred["v3a"]["events"]
    out["v3b"]["members"] = pred["v3b"]["members"]
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build v3 (cache only, 0 credits).")
    ap.add_argument("month", help="'retro' or a live month, e.g. 2026-10")
    ap.add_argument("--cutoff", help="last evidence day, YYYY-MM-DD (23:59 IST), as v1's build")
    ap.add_argument("--v1-seal", help="v1's sealed file (default sealed/<month>.json)")
    ap.add_argument("--dry-run", action="store_true", help="print, write nothing")
    a = ap.parse_args(argv)
    try:
        if a.month == "retro":
            out, path = build_retro(), RETRO
        else:
            if not a.cutoff:
                raise Refuse("--cutoff is required for a live month")
            out = build_live(a.month, a.cutoff, a.v1_seal or ROOT / "sealed" / f"{a.month}.json")
            path = ROOT / "results" / f"v3_nowcast_{a.month}.json"
    except Refuse as e:
        print(f"[FAIL] v3 not built: {e}")
        return 1
    text = json.dumps(out, ensure_ascii=False, indent=1)
    if a.dry_run:
        print(text)
        return 0
    path.write_text(text + "\n", encoding="utf-8")
    print(f"[PASS] wrote {path.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
