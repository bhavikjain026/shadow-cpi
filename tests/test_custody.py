"""Chain of custody (tools/build_custody.py): every verified number has a chain; unlogged links say so. Offline;
builds fresh into a temporary file, so new radar data never breaks it."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import build_custody as BC  # noqa: E402


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    BC.OUT = tmp_path_factory.mktemp("c") / "custody.json"
    try:
        return BC.build()
    finally:
        BC.OUT = ROOT / "results" / "custody.json"


def test_every_row_has_a_full_chain_and_arms_a_b_say_not_logged(built):
    keys = {"quote", "url", "page_date", "search_request_id", "search_response_sha256", "extract_request_id",
            "extract_response_sha256", "page_sha256", "seal"}
    assert built["rows"] and all(keys <= set(r) and r["quote"] for r in built["rows"])
    ab = [r for r in built["rows"] if r["source"] in ("arm A", "arm B")]
    assert ab and all(r["search_request_id"] == BC.NOT_LOGGED for r in ab)


def test_logged_ids_match_the_saved_cards(built):
    radar = json.loads((ROOT / "v2" / "radar" / "radar_2026-10.json").read_text())
    ids = {c["search_request_id"] for c in radar["cards"] if c.get("search_request_id")}
    rows = [r for r in built["rows"] if r["source"] == "radar"]
    assert {r["search_request_id"] for r in rows} <= ids
    assert all(len(r["search_response_sha256"]) == 64 for r in rows)
