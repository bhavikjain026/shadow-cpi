"""Display-only needle jumps (docs/after_scoring_changes.md, 2026-10-27): a step whose evidence equals the item's own
trend jumps exactly 0, and adding the jumps changes no results file, seal, score lock or needle value. Offline."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import build_needle_jumps as BJ  # noqa: E402
from shadow_cpi import cpi_math as M  # noqa: E402
from v2 import needle as N  # noqa: E402

MONTH = "2026-09"
ELEC = "04.5.1.0.2.01"


@pytest.fixture(scope="module")
def inp():
    return N.P.load_inputs()


def test_zero_change_jumps_exactly_zero(inp):
    assert N.jumps(MONTH, [(ELEC, "add", 0.0)], inp) == [0.0]
    hist = {k: v for k, v in inp["series"][ELEC].items() if k < MONTH}
    own = M.trend_change(hist, MONTH)
    assert N.jumps(MONTH, [("01.1.7.4.1.01", "level", 0.4), (ELEC, "level", own)], inp)[1] == 0.0
    assert N.jumps(MONTH, [(ELEC, "add", 0.05)], inp)[0] > 0                     # a rise moves the needle up


def _hashes():
    files = [p for d in ("results", "sealed") for p in (ROOT / d).rglob("*") if p.is_file()]
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}


def _strip(o):
    if isinstance(o, dict):
        return {k: _strip(v) for k, v in o.items() if k not in ("jump_pp", "adds")}
    return [_strip(x) for x in o] if isinstance(o, list) else o


def test_jumps_are_display_only(tmp_path, inp):
    runs = [p for p in BJ.RUNS if p.exists()]
    if not runs:
        pytest.skip("no saved Live build runs")
    copies = [Path(shutil.copy(p, tmp_path / p.name)) for p in runs]
    before = _hashes()
    BJ.main(copies)
    assert _hashes() == before                       # no results file, seal or score lock (results/*_lock.json)
    for p, c in zip(runs, copies):
        old, new = json.loads(p.read_text(encoding="utf-8")), json.loads(c.read_text(encoding="utf-8"))
        assert _strip(new) == _strip(old)             # every existing field, needle values included, unchanged
        if "adds" in new:
            a = new["adds"]
            assert (a["start"], a["end"]) == (new["needle"]["start"], new["needle"]["end"])
            assert a["start"] + sum(b["pp"] for b in a["bars"]) == pytest.approx(a["end"], abs=1e-12)
