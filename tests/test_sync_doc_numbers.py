"""tools/sync_doc_numbers.py: fills the run-dependent counts with an "as of" label and touches nothing else.
Offline, no calls."""
import shutil
from datetime import date
from pathlib import Path

import pytest

from tools import sync_doc_numbers as S

ROOT = Path(__file__).resolve().parent.parent
ST = {"calls": 1234, "cached": 1, "credits": 900, "spent_before_ledger": 160, "plan_limit": 1000,
      "addon_credits": 3125, "inside": 3, "total": 4, "undated": 0, "median_latency_s": 3.96}


def copy_docs(tmp_path):
    for rel in ("README.md", "docs/devpost_draft.md"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, tmp_path / rel)


def test_fills_the_four_counts_with_an_as_of_label(tmp_path):
    copy_docs(tmp_path)
    before = {rel: (tmp_path / rel).read_text() for rel in ("README.md", "docs/devpost_draft.md")}
    assert S.sync(ST, date(2026, 10, 25), root=tmp_path) == ["README.md", "docs/devpost_draft.md"]
    readme = (tmp_path / "README.md").read_text()
    assert "(as of 25 Oct 2026): 1,234 Tavily calls sent, 900 credits used" in readme.replace("\n", " ")
    dev = (tmp_path / "docs/devpost_draft.md").read_text()
    assert "1,234 Tavily calls sent" in dev and "75% (3 of 4; as of 25 Oct 2026)" in dev
    assert "median latency: 4.0 s per Tavily call (as of 25 Oct 2026)" in dev
    for rel, old in before.items():                       # only the synced passages differ
        new = (tmp_path / rel).read_text()
        assert len(new.splitlines()) - len(old.splitlines()) in (-1, 0, 1)
        kept = [x for x in old.splitlines() if "Tavily" not in x and "requested window" not in x
                and "median latency" not in x and "credits used" not in x]
        assert all(x in new for x in kept)


def test_second_run_is_a_no_op(tmp_path):
    copy_docs(tmp_path)
    S.sync(ST, date(2026, 10, 25), root=tmp_path)
    assert S.sync(ST, date(2026, 10, 25), root=tmp_path) == []


def test_missing_passage_stops(tmp_path):
    copy_docs(tmp_path)
    p = tmp_path / "docs/devpost_draft.md"
    p.write_text(p.read_text().replace("  - median latency:", "  - latency:"))
    with pytest.raises(SystemExit, match="latency"):
        S.sync(ST, date(2026, 10, 25), root=tmp_path)
