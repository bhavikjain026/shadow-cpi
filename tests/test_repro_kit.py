"""The 'Reproduce it yourself' kit: repro/ scripts, notebooks/reproduce_leak.ipynb, tools/run_repro.py.
Mock Tavily everywhere: no key, no network, 0 credits."""
import builtins
import contextlib
import getpass
import importlib.util
import io
import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "repro"))
sys.path.insert(0, str(ROOT / "tools"))
import _common as C  # noqa: E402
import run_repro as R  # noqa: E402

KEY = "tvly-NOT-A-REAL-KEY-0000"
SCRIPTS = R.SCRIPTS
BANNED = (r"\bfirst\b(?! commit\b)", r"beats economists", r"\bno leaks\b", r"every page through Tavily",
          r"scores itself", r"\bused by\b", r"\b3 of 10\b")
KEY_SHAPE = re.compile(r"tvly-(?:dev-|prod-)?[A-Za-z0-9]{20,}")
NEW_FILES = [*(ROOT / "repro").glob("*"), ROOT / "notebooks" / "reproduce_leak.ipynb", ROOT / "tools" / "run_repro.py",
             ROOT / "tests" / "test_repro_kit.py"]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "repro" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def fake_response(endpoint, body):
    if endpoint == "/usage":
        return {"account": {"plan_usage": 6}, "key": {"usage": 6}}
    if endpoint == "/search":
        return {"request_id": "rid-search", "usage": {"credits": 2 if body.get("auto_parameters") else 1},
                "auto_parameters": {"topic": "news", "time_range": "w"},
                "results": [{"url": "https://a.example/1", "published_date": "2026-10-20", "raw_content": "Updated: 9 Jul 2026"},
                            {"url": "https://a.example/2", "published_date": None}]}
    if endpoint == "/map":
        return {"request_id": "rid-map", "usage": {"credits": 1}, "results": []}
    return {"request_id": "rid-extract", "usage": {"credits": 1}, "failed_results": [],
            "results": [{"url": "u", "raw_content": "Gokul letterhead 2026"}]}


@pytest.fixture
def sent(monkeypatch):
    calls = []

    def fake(method, url, key, body):
        calls.append((method, url.replace(C.BASE, ""), key, body))
        return fake_response(url.replace(C.BASE, ""), body or {})
    monkeypatch.setattr(C, "transport", fake)
    monkeypatch.setenv("TAVILY_API_KEY", KEY)
    monkeypatch.delenv("REPRO_RECEIPT", raising=False)
    return calls


@pytest.mark.parametrize("name", SCRIPTS)
def test_each_script_sends_one_request_prints_request_id_and_never_the_key(name, sent, capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", [name])
    mod = load(name)
    mod.main()
    out = capsys.readouterr().out
    assert "request_id" in out and KEY not in out
    paid = [c for c in sent if c[1] != "/usage"]
    assert len(paid) == 1 and all(c[2] == KEY for c in sent)
    assert mod.MAX_CREDITS <= 2 and C.MAX_CREDITS == 2


def test_scripts_refuse_without_a_key_before_sending(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.setattr(C, "transport", lambda *a: pytest.fail("sent without a key"))
    with pytest.raises(SystemExit):
        load("extract_no_asof").main()


def test_over_cap_estimate_is_refused_before_any_call(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", KEY)
    monkeypatch.setattr(C, "transport", lambda *a: pytest.fail("sent over cap"))
    with pytest.raises(SystemExit):
        C.call("/search", {"query": "x"}, estimate=3)


def test_receipt_file_gets_request_id_credits_and_hash(sent, monkeypatch, tmp_path):
    monkeypatch.setenv("REPRO_RECEIPT", str(tmp_path / "r.jsonl"))
    load("scanned_pdf_extract").main()
    row = json.loads((tmp_path / "r.jsonl").read_text())
    assert row["request_id"] == "rid-extract" and row["credits"] == 1 and len(row["response_sha256"]) == 64
    assert KEY not in json.dumps(row)


def test_scripts_hard_code_no_expected_counts():
    for name in SCRIPTS:
        text = (ROOT / "repro" / f"{name}.py").read_text()
        assert not re.search(r"(expected|should be)\s*[=:]\s*\d", text, re.I)


def test_every_tavily_report_links_a_script_that_exists():
    doc = (ROOT / "docs" / "tavily_bug_reports.md").read_text()
    reports = json.loads((ROOT / "results" / "bug_reports.json").read_text())["reports"]
    assert len(reports) == len(SCRIPTS)
    for r in reports:
        assert (ROOT / r["repro"]).is_file() and f"](../{r['repro']})" in doc
    assert [Path(r["repro"]).stem for r in reports] == list(SCRIPTS)


# ---- notebook -------------------------------------------------------------------------------------------------

def notebook_cells():
    nb = json.loads((ROOT / "notebooks" / "reproduce_leak.ipynb").read_text(encoding="utf-8"))
    return nb["cells"]


class FakeClient:
    """Stands in for timelock.TavilyHTTP: serves F3-shaped responses, records every call, never touches the network."""
    instances = []
    after = 2                                   # how many results per search are dated after the cutoff

    def __init__(self, api_key=None):
        assert api_key == KEY
        self.calls = []
        FakeClient.instances.append(self)

    def search(self, query, **params):
        self.calls.append((query, params))
        results = [{"url": f"https://news.example/{i}", "published_date": "2026-05-20", "content": "x"} for i in range(2)]
        results += [{"url": f"https://news.example/late{i}", "published_date": "2026-06-0%d" % (i + 1), "content": "x"}
                    for i in range(self.after)]
        results.append({"url": "https://news.example/undated", "published_date": None, "content": "x"})
        return {"request_id": f"rid-{len(self.calls)}", "usage": {"credits": 1}, "results": results}


def run_notebook(monkeypatch, after=2):
    import timelock
    FakeClient.instances, FakeClient.after = [], after
    monkeypatch.setattr(timelock, "TavilyHTTP", FakeClient)
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": KEY)
    monkeypatch.chdir(ROOT)
    ns, buf = {"__name__": "__main__"}, io.StringIO()
    with contextlib.redirect_stdout(buf):
        for cell in notebook_cells():
            if cell["cell_type"] != "code":
                continue
            src = "".join(l for l in cell["source"] if not l.lstrip().startswith(("!", "%")))   # shell lines need Colab
            exec(compile(src, "notebook", "exec"), ns)
    return buf.getvalue(), ns


def test_notebook_runs_top_to_bottom_with_a_fake_client(monkeypatch):
    out, ns = run_notebook(monkeypatch)
    client, = FakeClient.instances
    assert len(client.calls) == 2                                   # one search with no dates, one time-locked
    plain, locked = client.calls[0][1], client.calls[1][1]
    assert "start_date" not in plain and "end_date" not in plain
    assert locked["end_date"] <= ns["CUTOFF"] and locked["filter_by_published_date"] is True
    assert ns["QUERY"] == "petrol diesel price hike India May 2026" and ns["CUTOFF"] == "2026-05-29"
    assert "https://news.example/late0" in out and "Tavily credits reported for this run: 2 (cap 4)" in out
    assert "request ids: rid-1 (no dates), rid-2 (time-locked)" in out
    assert "confirmed leaks need the Wayback check in the repo" in out and "Today's index may differ" in out
    assert KEY not in out


def test_notebook_summary_is_computed_not_typed(monkeypatch):
    out2, _ = run_notebook(monkeypatch, after=2)
    out0, _ = run_notebook(monkeypatch, after=0)
    assert "2 of 5 results are dated after the cutoff" in out2 and "0 of 3 results are dated after the cutoff" in out0
    summary = notebook_summary_lines(out2)
    assert len(summary) == 2


def notebook_summary_lines(out):
    return [l for l in out.splitlines() if re.match(r"(no dates|time-locked): \d+ of \d+ results are dated after", l)]


def test_notebook_estimate_is_within_four_credits_and_shows_no_key(monkeypatch):
    cells = notebook_cells()
    text = "".join("".join(c["source"]) for c in cells)
    assert "getpass(" in text and "print(key" not in text and "print(client" not in text
    assert "MAX_CREDITS, ESTIMATE = 4, 2" in text
    assert "pip install" in text and "github.com/bhavikjain026/shadow-cpi" in text
    for c in cells:
        assert c["cell_type"] != "code" or (c["outputs"] == [] and c["execution_count"] is None)   # no stored outputs


def test_readme_reuse_line_has_colab_badge():
    for p in ("README.md", "docs/templates/README.md"):
        line = next(l for l in (ROOT / p).read_text().splitlines() if "[![Open in Colab]" in l)
        assert "colab.research.google.com/github/bhavikjain026/shadow-cpi/blob/main/notebooks/reproduce_leak.ipynb" in line
    assert (ROOT / "pyproject.toml").is_file()


# ---- runner ----------------------------------------------------------------------------------------------------

def test_runner_dry_run_sends_nothing_and_lists_the_worst_case(capsys, monkeypatch):
    monkeypatch.setattr(R, "run_one", lambda *a: pytest.fail("ran a script in a dry run"))
    assert R.main(live=False) is None
    out = capsys.readouterr().out
    assert "cap 20" in out and "dry run" in out
    assert sum(R.worst_case(s) for s in SCRIPTS) <= 20 + 4          # 7 scripts, each declared at most 2 credits


def test_runner_stops_before_a_script_that_would_pass_the_cap():
    ledger = [{"credits": 19, "budgets": [R.BUDGET]}]
    with pytest.raises(R.BudgetExceeded):
        R.check(2, ledger=ledger)
    R.check(1, ledger=ledger)


def test_runner_ledger_rows_match_the_ledger_format():
    rows = R.ledger_rows([{"endpoint": "/search", "request_id": "r", "credits": 2, "response_sha256": "h" * 64}], "s", now="t")
    assert rows[0].keys() >= {"time", "call_id", "endpoint", "credits", "real_spent", "original_cost", "budgets",
                              "request_id", "response_sha256"} and rows[0]["budgets"] == ["repro-kit"]
    rows_in_ledger = [json.loads(l) for l in (ROOT / "results" / "credit_ledger.jsonl").read_text().splitlines()]
    real = next(e for e in reversed(rows_in_ledger) if R.BUDGET not in e["budgets"] and not e.get("cached")
                and e["endpoint"].startswith("/"))
    assert set(rows[0]) - {"response_time"} == set(real) - {"cached"}


# ---- hygiene ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("path", [p for p in NEW_FILES if p.is_file()], ids=lambda p: p.name)
def test_no_key_shaped_strings_and_no_banned_words(path):
    text = path.read_text(encoding="utf-8")
    assert not KEY_SHAPE.search(text), f"{path.name} holds something shaped like a Tavily key"
    if path.suffix in (".md", ".ipynb") or path.name == "README.md":
        assert [b for b in BANNED if re.search(b, text, re.I)] == []


def test_the_real_key_is_nowhere_in_the_new_files():
    env = ROOT.parent / "shadow-cpi" / ".env"
    if not env.exists():
        pytest.skip("no .env to compare against")
    key = next((l.split("=", 1)[1].strip() for l in env.read_text().splitlines() if l.startswith("SCPI_TAVILY_API_KEY=")), "")
    if len(key) < 12:
        pytest.skip("no key in .env")
    for p in NEW_FILES + [ROOT / "results" / "repro_run.json", ROOT / "results" / "credit_ledger.jsonl"]:
        if p.is_file():
            assert key not in p.read_text(encoding="utf-8"), p.name


def test_runner_keeps_free_usage_reads_out_of_the_ledger():
    rows = R.ledger_rows([{"endpoint": "/usage", "request_id": None, "credits": 0, "response_sha256": "h" * 64},
                          {"endpoint": "/search", "request_id": "r", "credits": 1, "response_sha256": "g" * 64}], "s")
    assert [r["endpoint"] for r in rows] == ["/search"]
