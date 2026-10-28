"""Aesthetic pass (display only): the theme uses only options this Streamlit supports, text colours pass 4.5:1, the
stylesheet avoids hashed class names, and the Leak demo cards show the results files' numbers as static text."""
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


def page_run():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


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
    assert "data-testid" in CSS and "<" not in CSS        # a "<" (even in a comment) makes st.html drop the sheet


def test_style_is_injected_once_and_takes_no_layout():
    styles = page_run().get("html")
    assert sum(s.proto.body.startswith("<style>") for s in styles) == 1


def test_reduced_motion_rule_and_viewer_toolbar():
    assert "prefers-reduced-motion: reduce" in CSS and "animation: none !important" in CSS
    assert THEME["client"]["toolbarMode"] == "viewer"
    assert THEME["theme"]["light"]["primaryColor"] == "#1d4ed8" and THEME["theme"]["dark"]["primaryColor"] == "#60a5fa"


# ---------- the opening cards ----------
def test_cards_numbers_come_from_the_results_files():
    at = page_run()
    d = DATA["totals"]["date"]
    rep = json.loads((ROOT / "results" / "replication.json").read_text())
    ra, pool = rep["metrics"]["price"]["arms"]["A"], rep["pooled"]["price"]["arms"]
    c = json.loads((ROOT / "results" / "date_field_test.json").read_text())["metrics"]["arms"]["C"]
    vals = [m.value for m in at.metric]
    # the pre-registered initial pass leads: pilot and replication shown separately, the pooled lock count, the cost
    assert vals == [f"{d['open']['first']}/{d['cases']} · {ra['leak_cases']}/{ra['cases']}",
                    f"{pool['C']['leak_cases']} of {pool['C']['cases']} detected", f"{c['valid_lost']} of {c['valid_total']}"]
    assert d["source"].startswith("results/field_report.json")
    deltas = [m.delta for m in at.metric]
    assert f"Pooled {pool['A']['leak_cases']} of {pool['A']['cases']} (pre-registered secondary)" in deltas[0]
    from app_pages.common import wilson95
    lo, hi = wilson95(pool["C"]["leak_cases"], pool["C"]["cases"])
    assert f"Wilson 95% interval {lo:.0%}–{hi:.0%}" in deltas[1]
    # the computed interval agrees with the one the results file stores
    assert round(hi, 6) == round(pool["C"]["wilson95"][1], 6)


def test_markup_has_no_animation_or_script_anywhere():
    files = [ROOT / "app.py", *sorted((ROOT / "app_pages").glob("*.py"))]
    hits = {f.name: len(re.findall(r"<script|components\.html|st\.iframe|components\.v1|anime", f.read_text()))
            for f in files}
    assert {k: v for k, v in hits.items() if v} == {}


def test_update_and_replication_lines_stay():
    d = DATA["totals"]["date"]
    caps = [c.value for c in page_run().caption]
    assert any(c.startswith(f"Update: {d['open']['retry']}/{d['cases']} with no time lock after retrying") for c in caps)
    assert any(c.startswith("Replication: ") and c.endswith("more cases detected leaking with the time lock.") for c in caps)


def test_provenance_and_how_we_know_on_the_four_pages():
    import hashlib
    at = page_run()
    fields = {"results/leak_demo.json": "built_utc", "results/field_report.json": "built",
              "results/score_lock.json": "scored_at_utc", "results/date_field_test.json": "built_utc"}
    for pg, rel in (("app_pages/leak_demo.py", "results/leak_demo.json"),
                    ("app_pages/field_report.py", "results/field_report.json"),
                    ("app_pages/home.py", None), ("app_pages/try_it.py", "results/date_field_test.json")):
        at.switch_page(pg)
        at.run()
        assert not at.exception
        body = " ".join(h.proto.body for h in at.get("html"))
        assert 'class="provenance"' in body, pg
        if rel:
            digest = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()[:12]
            verb = {"built_utc": "built", "built": "built", "scored_at_utc": "scored"}[fields[rel]]
            assert rel in body and digest in body and f"· {verb} <b>" in body, pg
            assert f"{fields[rel]} <b>" not in body or fields[rel] == verb, pg                  # never the raw field name
            assert "UTC" not in body.split("<style>")[0] or "IST" not in body.split("<style>")[0], pg
            assert str((ROOT / rel).stat().st_mtime)[:6] not in body and "modified" not in body, pg   # never a file time
            stored = json.loads((ROOT / rel).read_text())[fields[rel]]
            assert (stored[:10] in body) or fields[rel] == "built_utc", pg
        if pg in ("app_pages/leak_demo.py", "app_pages/field_report.py"):
            (ex,) = [e for e in at.expander if e.label == "How we know"]
            text = " ".join(m.value for m in ex.markdown)
            assert all(k in text for k in ("**Data.**", "**Analysis.**", "**Assumptions and limitations.**"))


def test_card_markdown_blocks_do_not_overlap():
    # Streamlit pulls each markdown block up 1rem; with the card's p margin removed,
    # a two-line headline would run under the chip row unless that pull is reset too.
    assert re.search(r'\[class\*="st-key-card-"\] \[data-testid="stMarkdownContainer"\] \{ margin-bottom: 0; \}', CSS)


def test_provenance_without_a_stored_timestamp_shows_only_path_and_hash(monkeypatch):
    from app_pages import provenance as P
    assert P.generated("results/leak_demo.json", None) is None and P.generated("results/leak_demo.json", "nope") is None
    assert P.generated("results/leak_demo.json", "built_utc") == "2026-10-27 00:31 IST"     # 2026-10-26 19:01 UTC
    assert P.generated("results/field_report.json", "built") == "2026-10-28"


def test_every_altair_chart_goes_through_the_readable_wrapper():
    import glob
    for f in glob.glob(str(ROOT / "app_pages" / "*.py")):
        src = Path(f).read_text()
        assert not re.search(r"\bst\.altair_chart\(|\w+\.altair_chart\(", src.replace("into.altair_chart", "")), f


# ---------- chart tooltips: one plain line per mark, never raw fields or floats ----------
def chart_tooltips(pg):
    """Every Altair layer's tooltip encoding and the tooltip strings, from the charts on one page."""
    import pyarrow as pa
    at = page_run()
    at.switch_page(pg)
    at.run()
    assert not at.exception
    out = []
    for c in at.get("vega_lite_chart"):
        spec = json.loads(c.proto.spec)
        tables = [pa.ipc.open_stream(d.data.data).read_all().to_pandas() for d in c.proto.datasets]
        for layer in spec.get("layer", [spec]):
            tip = layer.get("encoding", {}).get("tooltip")
            texts = [str(v) for t in tables if tip and "field" in tip and tip["field"] in t for v in t[tip["field"]]]
            out.append((tip, texts))
    return out


@pytest.mark.parametrize("pg", ["app_pages/leak_demo.py", "app_pages/field_report.py", "app_pages/home.py",
                                "app_pages/try_it.py"])
def test_every_chart_layer_has_a_plain_tooltip(pg):
    for tip, texts in chart_tooltips(pg):
        # None would let the renderer list every raw field (e.g. "hi 0.0837987920769"): each layer sets its own
        assert tip is not None
        assert tip == {"value": None} or (set(tip) <= {"field", "type"} and tip["type"] == "nominal"), tip
        assert not [t for t in texts if re.search(r"\d\.\d{4,}", t)], texts


def test_leak_demo_tooltip_reads_like_the_cards():
    from app_pages.common import wilson95
    pool = json.loads((ROOT / "results" / "replication.json").read_text())["pooled"]["price"]["arms"]["C"]
    k, n = pool["leak_cases"], pool["cases"]
    lo, hi = wilson95(k, n)
    texts = {t for _, ts in chart_tooltips("app_pages/leak_demo.py") for t in ts}
    assert f"Pooled, time lock · {k} of {n} detected leaking · 95% CI {lo:.0%}–{hi:.0%}" in texts
    assert all(" detected leaking · 95% CI " in t for t in texts)
