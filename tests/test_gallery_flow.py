"""The gallery's flow diagram must say where Nemotron runs (tools/build_gallery.py draws it; no browser needed here)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import build_gallery as bg  # noqa: E402


def test_quote_check_box_names_nemotron_and_nebius():
    box = dict(bg.flow_steps())[bg.QUOTE_CHECK_TITLE]
    assert "Nemotron" in box and "Nebius" in box
    assert "Nano screens the page" in box and "Super cites the exact line" in box
    page = bg.flow_html()
    assert bg.QUOTE_CHECK_CODE in page and bg.QUOTE_CHECK_LABEL in page


def test_flow_diagram_has_no_model_ids():
    assert "nvidia/" not in bg.flow_html()


def test_gallery_caption_matches_the_box():
    cap = " ".join((Path(bg.ROOT) / "docs/templates/gallery.md").read_text(encoding="utf-8").split())
    assert bg.QUOTE_CHECK_MODEL in cap
    assert bg.QUOTE_CHECK_CODE in cap
