"""Seal a prediction: canonical JSON + SHA-256, so anyone can verify it was not changed later.
Commit and tag the files in git (seal-YYYY-MM) right after sealing; the tag date is the public proof."""
import hashlib
import json
from datetime import datetime, timezone

from .settings import ROOT

SEAL_DIR = ROOT / "sealed"


def canonical(payload):
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def fingerprint(payload):
    return hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest()


def seal(month, payload, seal_dir=SEAL_DIR):
    payload = {**payload, "target_month": month, "sealed_at_utc": datetime.now(timezone.utc).isoformat()}
    seal_dir.mkdir(parents=True, exist_ok=True)
    text = canonical(payload)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    (seal_dir / f"{month}.json").write_text(text, encoding="utf-8")
    (seal_dir / f"{month}.sha256").write_text(digest + "\n", encoding="utf-8")
    return digest


def verify(month, seal_dir=SEAL_DIR):
    text = (seal_dir / f"{month}.json").read_text(encoding="utf-8")
    expected = (seal_dir / f"{month}.sha256").read_text(encoding="utf-8").strip()
    return hashlib.sha256(text.encode("utf-8")).hexdigest() == expected
