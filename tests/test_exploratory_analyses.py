"""The three exploratory tools (filter drops, paired statistics, evidence asymmetry): rules on small fakes, and every
saved figure traced to its source file. Offline."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))
import build_evidence_asymmetry as EA  # noqa: E402
import build_filter_drops as FD  # noqa: E402
import build_paired_stats as PS  # noqa: E402


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


ROW = {"id": "X1", "month": "2026-04", "cutoff": "2026-04-29"}


def item(tav=None, best=None, page=None, captures=("2026-04-02",), url="https://example.org/story"):
    return {"url": url, "tavily_date": tav, "best_date": best or tav, "page_date": page, "captures": list(captures)}


def test_class_a_when_no_field_gives_a_date():
    assert FD.classify(ROW, item())[0] == "a"


def test_class_b_tavily_after_cutoff_with_older_archive_copy_and_no_edit_date():
    assert FD.classify(ROW, item(tav="2026-09-17", captures=("2025-07-08",)))[0] == "b"


def test_class_c_when_the_page_shows_a_later_edit():
    assert FD.classify(ROW, item(tav="2026-09-17", page="2026-09-17"))[0] == "c"


def test_class_d_splits_before_window_and_inside_window():
    before, why = FD.classify(ROW, item(tav="2026-03-28"))
    inside, why2 = FD.classify(ROW, item(tav="2026-04-10"))
    assert (before, inside) == ("d", "d") and "before the window start" in why and "inside" in why2


def test_filter_drops_match_the_committed_pilot_counts():
    res, m = FD.build(), load("results/date_field_test.json")["metrics"]["arms"]["C"]
    assert (res["dropped"], res["valid_total"]) == (m["valid_lost"], m["valid_total"])
    assert sum(res["counts"].values()) == res["dropped"] == len(res["items"])
    assert res["d_split"]["before_window_start"] + res["d_split"]["inside_window_not_returned"] == res["counts"]["d"]
    assert res["label"].startswith("exploratory, added after scoring")


def test_mcnemar_pairs_by_case_and_counts_discordant_cases():
    def row(i, a, c):
        return {"id": i, "arms": {"A": {"results": [{"label": a}]}, "C": {"results": [{"label": c}]}}}
    s = PS.paired([row("1", "L", "P"), row("2", "L", "P"), row("3", "P", "P"), row("4", "L", "L")])
    assert (s["only_no_dates"], s["only_time_lock"], s["both"]) == (2, 0, 1) and s["p_exact_two_sided"] == 0.5


def test_paired_stats_equal_the_committed_values_and_the_zero_bounds():
    res = PS.build()
    rep = load("results/replication.json")["metrics"]["price"]["a_vs_c_mcnemar"]
    assert res["studies"]["replication"]["p_exact_two_sided"] == rep["p_exact"]
    assert res["studies"]["pilot"]["cases"] + res["studies"]["replication"]["cases"] == res["studies"]["pooled"]["cases"]
    z = res["zero"]
    assert z["rule_of_three_upper"] == 3 / z["cases"] and z["exact_one_sided_95_upper"] < z["rule_of_three_upper"]


def test_sign_treats_zero_as_flat():
    assert [EA.sign(x) for x in (0.01, -0.01, 0)] == ["rise", "fall", "flat"]


def test_official_signs_use_the_previous_month_across_the_year_end(tmp_path):
    p = tmp_path / "t.csv"
    p.write_text("month,level,code,name,weight,index,published_yoy,imputed\n2025-12,item,c1,One,1,100,,N\n"
                 "2026-01,item,c1,One,1,99,,N\n2026-01,item,c2,Two,1,5,,Y\n", encoding="utf-8")
    off, names = EA.official_signs(p, ["2026-01"])
    assert off == {"2026-01": {"c1": "fall"}} and names["c1"] == "One"


def test_asymmetry_counts_trace_to_the_saved_evidence():
    res = EA.build()
    replay = load("results/replay_predictions.json")
    n = sum(v.get("change") is not None for m in EA.TEST_MONTHS for v in replay[m]["c"]["evidence"].values())
    e = res["events_replay"]
    assert e["item_months"] == n == e["rise"] + e["fall"] + e["flat"]
    assert sum(sum(x.values()) for x in e["by_layer"].values()) == n
    for scope in res["share_of_official"].values():
        for x in scope.values():
            assert 0 <= x["with_event"] <= x["of"]
