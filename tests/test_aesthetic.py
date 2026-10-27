"""Aesthetic pass (display only): the theme uses only options this Streamlit supports, text colours pass 4.5:1, the
stylesheet avoids hashed class names, and the Leak demo hero shows the results file's numbers with one pinned,
non-looping animation that respects prefers-reduced-motion."""
import json
import re
import tomllib
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit import config as st_config  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
THEME = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text())
CSS = (ROOT / "app_pages" / "style.css").read_text()
DATA = json.loads((ROOT / "results" / "leak_demo.json").read_text())
FR = json.loads((ROOT / "results" / "field_report.json").read_text())


@pytest.fixture(autouse=True)
def no_keys(monkeypatch):
    monkeypatch.chdir(ROOT)
    for k in ("SCPI_TAVILY_API_KEY", "SCPI_NEBIUS_API_KEY", "RUN_LIVE_ENABLED"):
        monkeypatch.delenv(k, raising=False)


def flat(d, prefix=""):
    for k, v in d.items():
        if isinstance(v, dict):
            yield from flat(v, f"{prefix}{k}.")
        else:
            yield f"{prefix}{k}"


def contrast(a, b):
    def lum(h):
        c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    x, y = lum(a), lum(b)
    return (max(x, y) + 0.05) / (min(x, y) + 0.05)


def hero_html():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    frames = at.get("iframe")
    assert len(frames) == 1
    return at, frames[0].proto.srcdoc


# ---------- theme ----------
def test_every_theme_option_exists_in_the_installed_streamlit():
    st_config.get_config_options()
    known = set(st_config._config_options)
    assert [k for k in flat(THEME) if k not in known] == []
    assert "light" in THEME["theme"] and "dark" in THEME["theme"]


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_text_colours_reach_4_5_to_1(mode):
    t = THEME["theme"][mode]
    pairs = [("textColor", "backgroundColor"), ("textColor", "secondaryBackgroundColor"), ("linkColor", "backgroundColor"),
             ("linkColor", "redBackgroundColor"), ("codeTextColor", "codeBackgroundColor")]
    pairs += [(f"{c}TextColor", f"{c}BackgroundColor") for c in ("red", "green", "gray")]
    pairs += [(f"{c}TextColor", "backgroundColor") for c in ("red", "green")]
    low = {f"{a} on {b}": round(contrast(t[a], t[b]), 2) for a, b in pairs if contrast(t[a], t[b]) < 4.5}
    assert low == {}


def test_one_ui_font_and_one_mono():
    families = {re.split(r"[:,]", THEME["theme"][k])[0].strip("'\"") for k in ("font", "headingFont")}
    assert families == {"Inter"} and THEME["theme"]["codeFont"].startswith("'JetBrains Mono'")


# ---------- stylesheet ----------
def test_stylesheet_uses_test_ids_not_hashed_classes():
    assert not re.search(r"st-emotion-cache|\.css-[a-z0-9]+|\.e[a-z0-9]{6,}\b|\.st-[a-z]{2}\b", CSS)
    assert "data-testid" in CSS and "<script" not in CSS


def test_style_is_injected_once_and_takes_no_layout():
    at, _ = hero_html()
    styles = at.get("html")
    assert len(styles) == 1 and styles[0].proto.body.startswith("<style>")


# ---------- the hero ----------
def test_hero_numbers_come_from_the_results_files():
    _, html = hero_html()
    d = DATA["totals"]["date"]
    o, k, n = d["open"]["retry"], d["locked"]["retry"], d["cases"]
    assert f'<span id="leaked">{o}</span>/{n}' in html and f">{k}/{n}<" in html
    shown = re.findall(r"<span id=\"leaked\">(\d+)</span>/(\d+)|>(\d+)/(\d+)<", html)
    assert shown == [(str(o), str(n), "", ""), ("", "", str(k), str(n))]
    # the same counts the Field Report reads (results/field_report.json, date test, after the logged retry)
    assert d["source"].startswith("results/field_report.json")


def test_hero_has_one_pinned_animation_that_never_loops_and_respects_reduced_motion():
    _, html = hero_html()
    srcs = re.findall(r'<script src="([^"]+)" integrity="(sha512-[A-Za-z0-9+/=]+)" crossorigin="anonymous">', html)
    assert len(srcs) == 1 and re.fullmatch(r"https://cdnjs\.cloudflare\.com/ajax/libs/animejs/\d+\.\d+\.\d+/anime\.umd\.min\.js",
                                           srcs[0][0])
    assert "prefers-reduced-motion: reduce" in html and "loop" not in html and "alternate" not in html
    assert html.count("createTimeline(") == 1 and "setInterval" not in html


def test_no_script_anywhere_else_in_the_app():
    files = [ROOT / "app.py", *sorted((ROOT / "app_pages").glob("*.py"))]
    hits = {f.name: len(re.findall(r"<script|components\.html|st\.iframe|components\.v1", f.read_text()))
            for f in files}
    assert {k: v for k, v in hits.items() if v} == {"leak_demo.py": 3}   # two <script> tags + one st.iframe, in HERO
