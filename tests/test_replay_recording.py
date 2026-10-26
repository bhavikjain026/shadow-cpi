"""The September replay recording (results/replay_sep.jsonl): ends on the committed needle, holds no page text."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import build_replay_recording as BR  # noqa: E402
from export import QUOTE_MAX  # noqa: E402

EVENTS = [json.loads(l) for l in (ROOT / "results" / "replay_sep.jsonl").read_text(encoding="utf-8").splitlines()]
RUN = json.loads(BR.RUN.read_text(encoding="utf-8"))


def test_final_needle_equals_the_committed_run():
    assert EVENTS[-1]["needle_after"] == RUN["needle"]["end"]
    assert round(EVENTS[-1]["needle_after"], 3) == 5.807


def test_recording_is_current_and_in_page_order(tmp_path):
    assert BR.build(out=tmp_path / "r.jsonl") == EVENTS          # rebuilt from committed files, byte for byte
    assert [e["seq"] for e in EVENTS] == list(range(len(EVENTS)))
    assert len([e for e in EVENTS if e["type"] == "page"]) == len(RUN["cards"])
    assert EVENTS[0]["needle_after"] == RUN["needle"]["start"]


def test_no_page_text():
    for e in EVENTS:
        assert not set(e) & {"raw_content", "content", "text", "page", "line"}
        assert len(e.get("quote_short") or "") <= QUOTE_MAX
