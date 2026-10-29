"""tools/content_check.py: the quote must exist in the excerpt, units without text are skipped, the Nebius cap holds."""
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("content_check", ROOT / "tools" / "content_check.py")
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)
from shadow_cpi.nemotron import Nemotron  # noqa: E402
from shadow_cpi.recorder import Recorder  # noqa: E402

EXCERPT = "Prices rose on May 15.\nThe  board then   announced a second hike on June 2."


def unit(n, arm="C", excerpt=EXCERPT, source="pilot"):
    return {"source": source, "case": f"X{n}", "arm": arm, "url": f"https://e.test/{arm}{n}", "cutoff": "2026-05-31",
            "question": "petrol price hike", "excerpt": excerpt}


def reply(answer, sentence=None):
    return {"id": "chatcmpl-test", "choices": [{"message": {"content": json.dumps({"answer": answer,
                                                                                     "sentence": sentence})}}]}


class Fake:
    def __init__(self, fn):
        self.fn, self.calls = fn, 0

    def __call__(self, method, url, key, body, timeout):
        self.calls += 1
        return self.fn(body)


def harness(tmp_path, fn, cap=C.CAP):
    t = C.Capped(cap=cap, inner=Fake(fn))
    nem = Nemotron(api_key="test-key", recorder=Recorder(cache_dir=tmp_path / "c", log_file=tmp_path / "log.jsonl"),
                   transport=t)
    return nem, t


# ---- the quote must be in the excerpt ------------------------------------------------------------------------

def test_quote_found_after_whitespace_collapse():
    assert C.quote_in_excerpt("The board then announced a second hike on June 2.", EXCERPT)


def test_quote_with_edge_ellipsis_is_found():
    assert C.quote_in_excerpt("...announced a second hike on June 2.", EXCERPT)


@pytest.mark.parametrize("q", ["The board cut prices in July.", "", "   ", None])
def test_quote_absent_or_empty(q):
    assert not C.quote_in_excerpt(q, EXCERPT)


def test_judge_flags_only_a_real_quote():
    assert C.judge({"answer": "yes", "sentence": "Prices rose on May 15."}, EXCERPT) == (True, "Prices rose on May 15.", None)
    assert C.judge({"answer": "yes", "sentence": "Invented sentence."}, EXCERPT) == (False, "Invented sentence.", "quote not in excerpt")
    assert C.judge({"answer": "yes", "sentence": None}, EXCERPT) == (False, None, "yes with no sentence")
    assert C.judge({"answer": "no", "sentence": "Prices rose on May 15."}, EXCERPT) == (False, None, None)


def test_a_made_up_quote_is_counted_as_no_end_to_end(tmp_path):
    nem, t = harness(tmp_path, lambda b: reply("yes", "Never on the page."))
    out = C.run(nem, t, [unit(1)], per_arm=5)
    row = out["rows"][0]
    assert row["flagged"] is False and row["dropped_reason"] == "quote not in excerpt"
    assert out["counts"]["C"]["flagged"] == 0 and out["counts"]["C"]["yes_dropped_quote_check"] == 1


def test_a_real_quote_is_flagged_with_receipt(tmp_path):
    nem, t = harness(tmp_path, lambda b: reply("yes", "Prices rose on May 15."))
    row = C.run(nem, t, [unit(1)], per_arm=5)["rows"][0]
    assert row["flagged"] and row["sentence"] == "Prices rose on May 15."
    assert row["model"] and row["receipt"]["nebius_response_id"] == "chatcmpl-test" and row["receipt"]["call_id"]


def test_prompt_hides_the_arm(tmp_path):
    seen = []
    nem, t = harness(tmp_path, lambda b: seen.append(json.dumps(b)) or reply("no"))
    C.run(nem, t, [unit(1, "A")], per_arm=5)
    assert seen and not re.search(r"arm|control|time-?lock", seen[0], re.I)


# ---- skipping ------------------------------------------------------------------------------------------------

def test_units_without_an_excerpt_are_skipped_and_counted(tmp_path):
    units = [unit(1), unit(2, excerpt=None), unit(3, excerpt=None, arm="A")]
    nem, t = harness(tmp_path, lambda b: reply("no"))
    out = C.run(nem, t, units, per_arm=5)
    assert t.attempts == 1 and len(out["rows"]) == 1
    assert out["counts"]["C"]["not_checked_no_excerpt"] == 1 and out["counts"]["A"]["not_checked_no_excerpt"] == 1


def test_load_units_marks_empty_content_as_none(tmp_path):
    (tmp_path / "results").mkdir()
    rows = [{"id": "E1", "cutoff": "2026-01-01", "query": "q", "arms": {
        "C": {"results": [{"url": "u1", "content": "  "}, {"url": "u2", "content": "text"}]}, "A": {"from": "C"}}}]
    (tmp_path / "results" / "s.json").write_text(json.dumps({"rows": rows}))
    got = C.load_units(tmp_path, (("pilot", "results/s.json"),))
    assert [u["excerpt"] for u in got] == [None, "text"]


def test_error_after_one_retry_is_not_checked(tmp_path):
    def boom(body):
        raise OSError("down")
    nem, t = harness(tmp_path, boom)
    out = C.run(nem, t, [unit(1)], per_arm=5)
    assert out["rows"][0]["status"] == "not checked (error)" and t.attempts == 2
    assert out["counts"]["C"]["not_checked_error"] == 1


# ---- sampling and the budget cap -----------------------------------------------------------------------------

def test_sample_is_seeded_equal_per_arm_and_interleaved():
    units = [unit(i, arm) for i in range(30) for arm in ("A", "C")]
    a, left = C.sample(units, per_arm=10, seed=1)
    b, _ = C.sample(units, per_arm=10, seed=1)
    assert [u["url"] for u in a] == [u["url"] for u in b]
    assert [u["arm"] for u in a] == ["C", "A"] * 10 and left == {"C": 20, "A": 20}


def test_cap_stops_the_run_cleanly(tmp_path):
    units = [unit(i, arm, excerpt=f"text {i} {arm}") for i in range(6) for arm in ("A", "C")]
    nem, t = harness(tmp_path, lambda b: reply("no"), cap=5)
    out = C.run(nem, t, units, per_arm=6)
    assert t.attempts == 5 and out["incomplete"] and out["nebius_calls_used"] == 5
    c = out["counts"]
    assert c["C"]["checked"] + c["A"]["checked"] == 5
    assert c["C"]["not_checked_cap"] + c["A"]["not_checked_cap"] == 7


def test_capped_transport_refuses_attempt_after_cap():
    t = C.Capped(cap=2, inner=lambda *a: {"id": "x"})
    t("POST", "u", "k", {"model": "m"}, 1)
    t("POST", "u", "k", {"model": "m"}, 1)
    with pytest.raises(C.CapReached):
        t("POST", "u", "k", {"model": "m"}, 1)
    assert t.attempts == 2


def test_default_cap_is_120_and_sample_fits_with_slack():
    assert C.CAP == 120 and 2 * C.PER_ARM < C.CAP


def test_identical_requests_are_sent_once(tmp_path):
    nem, t = harness(tmp_path, lambda b: reply("no"))
    out = C.run(nem, t, [unit(1), {**unit(1), "arm": "A"}], per_arm=5)
    assert t.attempts == 1 and len(out["rows"]) == 2


# ---- hand labels and the Field Report section -----------------------------------------------------------------

def _load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def test_every_flagged_row_has_exactly_one_label_and_no_extra():
    res, lab = _load("results/content_check.json"), _load("results/content_check_labels.json")
    key = lambda x: (x["arm"], x["source"], x["case"], x["url"])  # noqa: E731
    flagged = sorted(key(r) for r in res["rows"] if r["flagged"])
    assert flagged == sorted(key(x) for x in lab["labels"])
    assert {x["label"] for x in lab["labels"]} <= {"true positive", "false positive"}
    assert lab["labeller"] == "team (cross-checked with two AI annotators)"


def test_field_report_section_counts_come_from_the_two_files():
    sys.path.insert(0, str(ROOT / "tools"))
    import build_field_report as FR
    cc = FR.content_check()
    res, lab = _load("results/content_check.json"), _load("results/content_check_labels.json")
    for arm, a in cc["arms"].items():
        flagged = [x for x in res["rows"] if x["arm"] == arm and x["flagged"]]
        true = [x for x in lab["labels"] if x["arm"] == arm and x["label"] == "true positive"]
        assert (a["flagged"], a["confirmed"]) == (len(flagged), len(true))
        assert a["false_positives"] == len(flagged) - len(true)
        assert a["sampled"] == len([x for x in res["rows"] if x["arm"] == arm])
        lo, hi = a["wilson95"]
        assert 0 <= lo <= a["confirmed"] / a["sampled"] <= hi <= 1
    assert cc["nebius_calls"] == res["nebius_calls_used"] <= C.CAP
