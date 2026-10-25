"""Research exports (tools/export.py): schema columns, short quotes only, values copied from the sources. Offline."""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import export as EX  # noqa: E402


def read(name):
    with (ROOT / "exports" / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_columns_match_the_schema_doc():
    doc = (ROOT / "docs" / "exports_schema.md").read_text()
    for cols in (EX.NOWCAST_COLS, EX.EVIDENCE_COLS):
        assert all(c.split("_")[0] in doc for c in cols)
    assert list(read("nowcast.csv")[0]) == EX.NOWCAST_COLS and list(read("evidence.csv")[0]) == EX.EVIDENCE_COLS


def test_quotes_are_short_never_page_text():
    rows = read("evidence.csv")
    assert rows and all(len(r["quote_short"]) <= EX.QUOTE_MAX for r in rows)
    for line in (ROOT / "exports" / "radar.jsonl").read_text().splitlines():
        assert all(len(s["quote_short"]) <= EX.QUOTE_MAX for s in json.loads(line)["sources"])
    assert EX.short("x " * 300).endswith("…") and len(EX.short("x " * 300)) == EX.QUOTE_MAX


def test_exports_are_current_copies(tmp_path, monkeypatch):
    monkeypatch.setattr(EX, "OUT", tmp_path)
    EX.write()
    for n in ("nowcast.csv", "evidence.csv", "radar.jsonl"):
        assert (tmp_path / n).read_text() == (ROOT / "exports" / n).read_text()
