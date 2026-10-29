"""Verify a daily audit log hash chain (and its OpenTimestamps proof, if any).

    python tools/verify_audit_log.py results/audit_log/2026-10-28.jsonl
Exit 0 on OK, 1 on a broken chain or head mismatch.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_log import GENESIS, entry_hash  # noqa: E402


def verify(log_path):
    """Return (ok, message). Detects edits, reordering, deletions (incl. tail)."""
    log = Path(log_path)
    prev = GENESIS
    n = 0
    for i, line in enumerate(log.read_text().splitlines(), 1):
        try:
            e = json.loads(line)
        except ValueError:
            return False, f"entry {i}: not valid JSON"
        if e.get("prev_hash") != prev:
            return False, f"entry {i}: prev_hash does not match previous entry (deletion or reorder)"
        if e.get("entry_hash") != entry_hash(e):
            return False, f"entry {i}: entry_hash mismatch (entry was edited)"
        prev, n = e["entry_hash"], i
    head = log.with_suffix(".head")
    if not head.exists():
        return False, "missing .head file"
    if head.read_text().strip() != prev:
        return False, f"head mismatch after entry {n} (entries removed from the end, or added)"
    return True, f"OK: {n} entries, head {prev}"


def check_ots(log_path):
    ots = Path(log_path).with_suffix(".head.ots")
    if not ots.exists():
        return "no .ots file"
    exe = shutil.which("ots") or str(Path(sys.executable).parent / "ots")
    if not Path(exe).exists():
        return ".ots present but `ots` client not installed; not checked"
    r = subprocess.run([exe, "verify", str(ots)], capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip().splitlines()
    return "ots verify: " + (out[-1] if out else f"exit {r.returncode}")


def main(argv=None):
    paths = (argv if argv is not None else sys.argv[1:])
    if not paths:
        print(__doc__)
        return 2
    rc = 0
    for p in paths:
        ok, msg = verify(p)
        print(f"{p}: {msg}")
        if ok:
            print(f"  {check_ots(p)}")
        rc |= 0 if ok else 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
