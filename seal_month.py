#!/usr/bin/env python3
"""Prompt 5 - seal one month's experimental nowcast so nobody (including us) can change it later.

Run:  python seal_month.py 2026-10            # real seal: write, commit, tag seal-2026-10, push
      python seal_month.py 2026-10 --dry-run  # everything except commit, tag and push

What it writes (via shadow_cpi.seal):
  sealed/<month>.json    canonical JSON: the prediction + manifest path and hash, code commit, model IDs,
                         weights-file hash, evidence cutoff (UTC), target month, sealed-at time (UTC), git tag
  sealed/<month>.sha256  SHA-256 of that exact file text
A dry run writes the same two files to sealed/dry-run/ instead, so it never blocks the real seal.

It refuses to seal (and changes nothing) when:
  - the month is not YYYY-MM, or the prediction file is missing or lacks headline_yoy / range_low / range_high;
  - the prediction is for a different month, or its range does not contain the number;
  - the month is already sealed, or the tag seal-<month> already exists;
  - the official figure for that month is already in data/official_releases.csv;
  - the weights in data/cpi_tidy.csv look like the 2012 series (food ~45.86% instead of ~36.75%);
  - (real seal only) there are uncommitted changes to tracked files, since the recorded code commit
    must be the code that produced the prediction.
No API calls are made. Only git is run, and only in a real seal.
"""
import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from shadow_cpi import official as O
from shadow_cpi import seal as S

ROOT = Path(__file__).resolve().parent
WEIGHTS_FILE = "data/official/mospi_cpi2024_weights_Annex_5.3.xlsx"
REQUIRED = ("headline_yoy", "range_low", "range_high")


class Refuse(Exception):
    """A reason not to seal. Printed as FAIL; nothing is written."""


def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def git(root, *args, check=True):
    r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise Refuse(f"git {' '.join(args)} failed: {r.stderr.strip() or r.stdout.strip()}")
    return r.stdout.strip()


def rel(root, p):
    p = Path(p)
    try:
        return p.resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return str(p)


def find_prediction(root, month, given):
    if given:
        return Path(given)
    for name in (f"results/nowcast_{month}.json", "results/nowcast_latest.json"):
        if (Path(root) / name).exists():
            return Path(root) / name
    raise Refuse(f"no prediction file: expected results/nowcast_{month}.json (or pass --prediction)")


def load_prediction(path, month):
    if not Path(path).exists():
        raise Refuse(f"prediction file not found: {path}")
    pred = json.loads(Path(path).read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED if not isinstance(pred.get(k), (int, float))]
    if missing:
        raise Refuse(f"prediction lacks a number for: {', '.join(missing)}")
    if pred.get("target_month", month) != month:
        raise Refuse(f"prediction is for {pred['target_month']}, not {month}")
    if not pred["range_low"] <= pred["headline_yoy"] <= pred["range_high"]:
        raise Refuse("the range does not contain the nowcast number")
    return pred


def already_released(root, month):
    p = Path(root) / "data" / "official_releases.csv"
    if not p.exists():
        return False
    with p.open(encoding="utf-8", newline="") as f:
        return any(r.get("month") == month and (r.get("official_yoy") or "").strip() for r in csv.DictReader(f))


def check_weights(root):
    tidy = Path(root) / "data" / "cpi_tidy.csv"
    if not tidy.exists():
        raise Refuse("data/cpi_tidy.csv not found, so the weights cannot be checked")
    _, weights, _, _ = O.load_tidy(tidy)
    try:
        return O.guard_2024_weights(weights)
    except O.WrongSeries as e:
        raise Refuse(str(e))


def parse_utc(text):
    if not text:
        raise Refuse("no evidence cutoff: pass --cutoff or put evidence_cutoff_utc in the prediction")
    try:
        t = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise Refuse(f"cutoff time is not a date-time: {text}")
    if t.tzinfo is None:
        raise Refuse(f"cutoff time must include a time zone (use UTC, e.g. 2026-10-28T23:59:00Z): {text}")
    return t.astimezone(timezone.utc)


def build_payload(root, month, pred, pred_path, manifest, cutoff, commit, models_file="config/models.json"):
    """Everything sealed except target_month and sealed_at_utc, which shadow_cpi.seal.seal adds."""
    root = Path(root)
    weights = root / WEIGHTS_FILE
    if not weights.exists():
        raise Refuse(f"weights file not found: {WEIGHTS_FILE}")
    models = json.loads((root / models_file).read_text(encoding="utf-8"))
    cut = parse_utc(cutoff or pred.get("evidence_cutoff_utc") or "")
    if cut > datetime.now(timezone.utc):
        raise Refuse(f"evidence cutoff {cut.isoformat()} is in the future")
    man = Path(manifest) if manifest else root / "manifests" / f"{month}.json"
    payload = {**pred,
               "prediction_file": rel(root, pred_path),
               "prediction_file_sha256": sha256_file(pred_path),
               "manifest": rel(root, man),
               "manifest_sha256": sha256_file(man) if man.exists() else None,
               "code_commit": commit,
               "model_ids": models,
               "weights_file": WEIGHTS_FILE,
               "weights_file_sha256": sha256_file(weights),
               "evidence_cutoff_utc": cut.isoformat(),
               "git_tag": f"seal-{month}"}
    payload.pop("sealed_at_utc", None)
    return payload, man.exists()


def run(month, dry_run=False, prediction=None, manifest=None, cutoff=None, root=ROOT, out=print):
    """Returns the SHA-256 written. Raises Refuse (nothing written) on any failed check."""
    root = Path(root)
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        raise Refuse(f"month must look like 2026-10, got {month!r}")
    tag = f"seal-{month}"
    seal_dir = root / "sealed" / ("dry-run" if dry_run else "")
    if (root / "sealed" / f"{month}.json").exists():
        raise Refuse(f"{month} is already sealed (sealed/{month}.json exists); a seal is never redone")
    if git(root, "tag", "--list", tag):
        raise Refuse(f"tag {tag} already exists")
    if already_released(root, month):
        raise Refuse(f"the official figure for {month} is already in data/official_releases.csv - too late to seal")
    food = check_weights(root)
    out(f"[PASS] 2024-series weights (food and beverages = {food:.2f}% of the basket)")

    pred_path = find_prediction(root, month, prediction)
    pred = load_prediction(pred_path, month)
    out(f"[PASS] prediction {rel(root, pred_path)}: {pred['headline_yoy']}% "
        f"(range {pred['range_low']}% to {pred['range_high']}%)")

    dirty = git(root, "status", "--porcelain", "--untracked-files=no")
    if dirty and not dry_run:
        raise Refuse("there are uncommitted changes to tracked files; commit them first so the recorded "
                     "code commit is the code that made this prediction:\n" + dirty)
    commit = git(root, "rev-parse", "HEAD")
    payload, has_manifest = build_payload(root, month, pred, pred_path, manifest, cutoff, commit)
    out(f"[{'PASS' if has_manifest else 'WARN'}] manifest {payload['manifest']}"
        + ("" if has_manifest else " not found - sealed with its path only"))
    if dirty:
        out("[WARN] uncommitted changes to tracked files (allowed in a dry run only)")

    digest = S.seal(month, payload, seal_dir=seal_dir)
    if not S.verify(month, seal_dir=seal_dir):
        raise Refuse("written seal does not verify")
    out(f"[PASS] wrote {rel(root, seal_dir / (month + '.json'))} and .sha256")
    out(f"       SHA-256 {digest}")
    out(f"       code commit {commit[:12]}, evidence cutoff {payload['evidence_cutoff_utc']}")

    if dry_run:
        out(f"[DRY RUN] stopped before commit, tag {tag} and push. Delete sealed/dry-run/ when done.")
        return digest

    files = [f"sealed/{month}.json", f"sealed/{month}.sha256"]
    git(root, "add", *files)
    git(root, "commit", "-m", f"Seal {month} experimental nowcast\n\nSHA-256 {digest}", "--", *files)
    git(root, "tag", "-a", tag, "-m", f"Sealed {month} experimental nowcast, SHA-256 {digest}")
    out(f"[PASS] committed and tagged {tag}")
    branch = git(root, "rev-parse", "--abbrev-ref", "HEAD")
    for args in (("push", "origin", branch), ("push", "origin", tag)):
        r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
        if r.returncode != 0:
            out(f"[FAIL] git {' '.join(args)} did not work: {r.stderr.strip()}")
            out(f"       The seal is committed and tagged locally. Retry with: git {' '.join(args)}")
            return digest
    out(f"[PASS] pushed {branch} and tag {tag}. The tag date on GitHub is the public proof (see verify.md).")
    return digest


def main(argv=None):
    ap = argparse.ArgumentParser(description="Seal one month's experimental nowcast.")
    ap.add_argument("month", help="target month, e.g. 2026-10")
    ap.add_argument("--dry-run", action="store_true", help="do everything except commit, tag and push")
    ap.add_argument("--prediction", help="prediction JSON (default results/nowcast_<month>.json)")
    ap.add_argument("--manifest", help="evidence manifest (default manifests/<month>.json)")
    ap.add_argument("--cutoff", help="evidence cutoff in UTC, e.g. 2026-10-28T23:59:00Z "
                                     "(default: evidence_cutoff_utc in the prediction)")
    a = ap.parse_args(argv)
    try:
        run(a.month, dry_run=a.dry_run, prediction=a.prediction, manifest=a.manifest, cutoff=a.cutoff)
    except Refuse as e:
        print(f"[FAIL] not sealed: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
