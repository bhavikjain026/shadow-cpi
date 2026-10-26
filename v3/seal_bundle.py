#!/usr/bin/env python3
"""Seal v3 beside v1 in one hash bundle (v3/PREREG.md section 6). v1's seal code, file, hash and tag are untouched.

Run right after `python seal_month.py <month>`, in the same session:
    python -m v3.seal_bundle 2026-10 --dry-run    # everything except commit, tag and push (writes sealed/dry-run/)
    python -m v3.seal_bundle 2026-10              # write, commit, tag seal-2026-10-bundle, push
    python -m v3.seal_bundle 2026-10 --verify     # check the bundle hashes (no git, no writes)

What it writes:
  sealed/<month>.v3.json          canonical JSON of results/v3_nowcast_<month>.json + its SHA-256 + sealed-at time
  sealed/<month>.bundle.sha256    `shasum -a 256 -c` format: <month>.json, <month>.sha256, <month>.v3.json
It refuses (and writes nothing) when v1's seal is missing or does not verify, v1's tag is missing (real seal), the v3
file was not built from v1's sealed inputs, the bundle already exists, the official figure is out, it is past 23:59
IST on the 29th of the month, or (real seal) tracked files are uncommitted. No API calls; only git, real seal only.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import seal_month as SM  # noqa: E402
from shadow_cpi import seal as S  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))


class Refuse(Exception):
    """A reason not to seal. Printed as FAIL; nothing is written."""


def names(month):
    return {"v1": f"{month}.json", "v1_hash": f"{month}.sha256", "v3": f"{month}.v3.json",
            "bundle": f"{month}.bundle.sha256"}


def deadline(month):
    y, m = map(int, month.split("-"))
    return datetime(y, m, 29, 23, 59, tzinfo=IST)


def bundle_text(seal_dir, month):
    n = names(month)
    return "".join(f"{hashlib.sha256((seal_dir / n[k]).read_bytes()).hexdigest()}  {n[k]}\n"
                   for k in ("v1", "v1_hash", "v3"))


def verify(month, seal_dir=ROOT / "sealed"):
    """True when every line of <month>.bundle.sha256 matches its file and v1's own hash still verifies."""
    seal_dir = Path(seal_dir)
    n = names(month)
    if not all((seal_dir / n[k]).exists() for k in n):
        return False
    return S.verify(month, seal_dir) and (seal_dir / n["bundle"]).read_text(encoding="utf-8") == bundle_text(seal_dir,
                                                                                                            month)


def git(root, *args):
    try:
        return SM.git(root, *args)
    except SM.Refuse as e:
        raise Refuse(str(e))


def run(month, dry_run=False, root=ROOT, now=None, out=print):
    root = Path(root)
    n = names(month)
    sealed = root / "sealed"
    v1_dir = sealed / ("dry-run" if dry_run else "")
    seal_dir = v1_dir
    now = now or datetime.now(timezone.utc)
    if now > deadline(month):
        raise Refuse(f"past the deadline {deadline(month).isoformat()} (v3 is sealed the same day as v1)")
    if (sealed / n["bundle"]).exists():
        raise Refuse(f"{month} bundle already sealed (sealed/{n['bundle']}); a seal is never redone")
    if SM.already_released(root, month):
        raise Refuse(f"the official figure for {month} is already in data/official_releases.csv - too late")
    if not (v1_dir / n["v1"]).exists():
        raise Refuse(f"v1 seal not found in {SM.rel(root, v1_dir)}/: run seal_month.py {month} first")
    if not S.verify(month, v1_dir):
        raise Refuse(f"v1 seal {n['v1']} does not match its .sha256")
    out(f"[PASS] v1 seal {SM.rel(root, v1_dir / n['v1'])} verifies")
    tag = f"seal-{month}-bundle"
    if not dry_run:
        if not git(root, "tag", "--list", f"seal-{month}"):
            raise Refuse(f"v1's tag seal-{month} not found: the v1 seal must be committed and tagged first")
        if git(root, "tag", "--list", tag):
            raise Refuse(f"tag {tag} already exists")
        dirty = git(root, "status", "--porcelain", "--untracked-files=no")
        if dirty:
            raise Refuse("there are uncommitted changes to tracked files; commit them first:\n" + dirty)

    v3_path = root / "results" / f"v3_nowcast_{month}.json"
    if not v3_path.exists():
        raise Refuse(f"{SM.rel(root, v3_path)} not found: run python -m v3.build {month} --cutoff ... first")
    v3 = json.loads(v3_path.read_text(encoding="utf-8"))
    v1 = json.loads((v1_dir / n["v1"]).read_text(encoding="utf-8"))
    chk = v3.get("inputs_match_v1") or {}
    if v3.get("target_month") != month:
        raise Refuse(f"v3 file is for {v3.get('target_month')}, not {month}")
    if not chk.get("all_match") or chk.get("v1_seal_sha256") != SM.sha256_file(v1_dir / n["v1"]):
        raise Refuse("the v3 file was not built against this v1 seal (rebuild with python -m v3.build)")
    if v3.get("evidence_cutoff_utc") != v1.get("evidence_cutoff_utc"):
        raise Refuse("v3 and v1 evidence cutoffs differ")
    out(f"[PASS] v3 built from v1's sealed inputs: v3a {v3['v3a']['yoy']}%, v3b {v3['v3b']['yoy']}%")

    payload = {**v3, "v3_file": SM.rel(root, v3_path), "v3_file_sha256": SM.sha256_file(v3_path),
               "bundle_git_tag": tag, "sealed_at_utc": now.isoformat()}
    seal_dir.mkdir(parents=True, exist_ok=True)
    (seal_dir / n["v3"]).write_text(S.canonical(payload), encoding="utf-8")
    (seal_dir / n["bundle"]).write_text(bundle_text(seal_dir, month), encoding="utf-8")
    if not verify(month, seal_dir):
        raise Refuse("written bundle does not verify")
    digest = hashlib.sha256((seal_dir / n["bundle"]).read_bytes()).hexdigest()
    out(f"[PASS] wrote {SM.rel(root, seal_dir / n['v3'])} and {n['bundle']} (bundle SHA-256 {digest})")
    if dry_run:
        out(f"[DRY RUN] stopped before commit, tag {tag} and push. Delete sealed/dry-run/ when done.")
        return digest

    files = [f"sealed/{n['v3']}", f"sealed/{n['bundle']}"]
    git(root, "add", *files)
    git(root, "commit", "-m", f"Seal {month} v3 (experimental) beside v1\n\nBundle SHA-256 {digest}", "--", *files)
    git(root, "tag", "-a", tag, "-m", f"Sealed {month} v1 + v3 bundle, bundle SHA-256 {digest}")
    out(f"[PASS] committed and tagged {tag}")
    branch = git(root, "rev-parse", "--abbrev-ref", "HEAD")
    for args in (("push", "origin", branch), ("push", "origin", tag)):
        r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
        if r.returncode != 0:
            out(f"[FAIL] git {' '.join(args)} did not work: {r.stderr.strip()}")
            out(f"       The bundle is committed and tagged locally. Retry with: git {' '.join(args)}")
            return digest
    out(f"[PASS] pushed {branch} and tag {tag}")
    return digest


def main(argv=None):
    ap = argparse.ArgumentParser(description="Seal v3 beside v1 in one hash bundle.")
    ap.add_argument("month")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true", help="check sealed/<month>.bundle.sha256 only")
    a = ap.parse_args(argv)
    if a.verify:
        ok = verify(a.month)
        print(f"[{'PASS' if ok else 'FAIL'}] bundle {a.month}: v1 hash and all three bundle lines "
              f"{'match' if ok else 'do not match (or files missing)'}")
        return 0 if ok else 1
    try:
        run(a.month, dry_run=a.dry_run)
    except Refuse as e:
        print(f"[FAIL] not sealed: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
