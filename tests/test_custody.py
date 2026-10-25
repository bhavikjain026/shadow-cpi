"""Chain of custody (tools/build_custody.py): every verified number has a chain; unlogged links say so. Offline."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import build_custody as BC  # noqa: E402


def test_every_row_has_a_full_chain_and_arms_a_b_say_not_logged():
    d = json.loads(BC.OUT.read_text())
    keys = {"quote", "url", "page_date", "search_request_id", "search_response_sha256", "extract_request_id",
            "extract_response_sha256", "page_sha256", "seal"}
    assert d["rows"] and all(keys <= set(r) and r["quote"] for r in d["rows"])
    ab = [r for r in d["rows"] if r["source"] in ("arm A", "arm B")]
    assert ab and all(r["search_request_id"] == BC.NOT_LOGGED for r in ab)
    radar = [r for r in d["rows"] if r["source"] == "radar"]
    assert radar and all(len(r["search_response_sha256"]) == 64 for r in radar)


def test_logged_ids_match_the_saved_cards():
    radar = json.loads((ROOT / "v2" / "radar" / "radar_2026-10.json").read_text())
    ids = {c["search_request_id"] for c in radar["cards"] if c.get("search_request_id")}
    d = json.loads(BC.OUT.read_text())
    assert {r["search_request_id"] for r in d["rows"] if r["source"] == "radar"} <= ids


def test_rebuild_matches_saved(tmp_path, monkeypatch):
    monkeypatch.setattr(BC, "OUT", tmp_path / "c.json")
    assert BC.build() == json.loads((ROOT / "results" / "custody.json").read_text())
