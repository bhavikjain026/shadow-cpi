"""The v2 evidence ledger: one JSON line per checked claim, verified or rejected, with the reason.
v2/evidence/ledger.jsonl. Page texts are saved as v2/evidence/pages/<sha256>.txt at fetch time."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "evidence"
LEDGER = ROOT / "ledger.jsonl"
PAGES = ROOT / "pages"
FIELDS = ("id", "month", "cutoff", "cpi_item", "cpi_name", "item", "place", "state", "unit", "price_type", "price",
          "old_price", "new_price", "change", "published_date", "effective_date", "found_date", "line", "url",
          "page_sha256", "page_file", "status", "reason", "search_call", "extract_call", "model")
REQUIRED = ("month", "cpi_item", "url", "line", "status", "reason", "published_date", "found_date")


def save_page(text, sha, pages=PAGES):
    """Write the fetched page text once, named by its SHA-256. Returns the path relative to v2/evidence."""
    pages.mkdir(parents=True, exist_ok=True)
    p = pages / f"{sha}.txt"
    if not p.exists():
        p.write_text(text, encoding="utf-8")
    return f"pages/{sha}.txt"


def key(rec):
    return (rec["month"], rec["cpi_item"], rec["url"], rec["line"])


def read(path=LEDGER):
    p = Path(path)
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []


def append(rec, path=LEDGER):
    """Add a record unless the same claim (month, item, page, line) is already there. Returns True if added."""
    missing = [f for f in REQUIRED if rec.get(f) in (None, "")]
    if missing:
        raise ValueError(f"ledger record lacks {missing}")
    unknown = set(rec) - set(FIELDS)
    if unknown:
        raise ValueError(f"unknown ledger fields {sorted(unknown)}")
    if rec["status"] not in ("verified", "rejected"):
        raise ValueError("status must be verified or rejected")
    if any(key(r) == key(rec) for r in read(path)):
        return False
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("a", encoding="utf-8") as f:
        f.write(json.dumps({k: rec.get(k) for k in FIELDS}, ensure_ascii=False) + "\n")
    return True
