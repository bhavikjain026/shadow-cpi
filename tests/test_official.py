"""Offline tests for Prompt 1 (official data, baselines, poll parsing). No network, no credits."""
import pytest

from shadow_cpi import cpi_math as M
from shadow_cpi import official as O
from shadow_cpi import polls as P
from shadow_cpi.recorder import Recorder, read_log


# ---------- weights guard ----------
def test_guard_refuses_2012_weights():
    with pytest.raises(O.WrongSeries):
        O.guard_2024_weights({"01": 45.86, "CPI": 100.0})
    with pytest.raises(O.WrongSeries):
        O.guard_2024_weights({"01": 40.0, "CPI": 100.0})      # neither series: also refused
    assert O.guard_2024_weights({"01": 36.75, "CPI": 100.0}) == pytest.approx(36.75)


@pytest.mark.skipif(not O.WEIGHTS_XLSX.exists(), reason="official weights file not present")
def test_real_weights_file_is_2024_series():
    w, names = O.load_weights()
    assert O.guard_2024_weights(w, names) == pytest.approx(36.753, abs=0.001)
    assert w[O.HEADLINE] == pytest.approx(100.0, abs=1e-6)
    assert len(O.codes_at("item", w)) == 358 and len(O.codes_at("group", w)) == 43
    assert sum(w[c] for c in O.codes_at("group", w)) == pytest.approx(100.0, abs=1e-6)
    assert names["01.1.7.4.1.01"] == "Onion"


def test_codes_and_levels():
    assert O.level_of("CPI") == "general" and O.level_of("01") == "division"
    assert O.level_of("01.1") == "group" and O.level_of("01.1.7.4") == "sub_class"
    assert O.level_of("01.1.7.4.1.01") == "item"
    assert O.parent_code("01.1.7.4.1.01", "group") == "01.1"
    assert O.parent_code("01.1.7.4.1.01", "sub_class") == "01.1.7.4"


# ---------- fetching (fake MoSPI API) ----------
def _api_page(month, rows, page, pages):
    y, m = month.split("-")
    return {"statusCode": True, "meta_data": {"page": page, "totalPages": pages},
            "data": [{"year": y, "month": O.MONTH_NAMES[int(m) - 1], "state": "All India", "sector": "Combined",
                      "division": d, "group": g, "class": None, "sub_class": None, "item": None, "code": c,
                      "index": idx, "inflation": inf, "imputation": None} for c, d, g, idx, inf in rows]}


def test_fetch_month_pages_and_is_logged(tmp_path):
    pages = {1: [(None, "CPI (General)", None, "104.00", "4.0")], 2: [("01", "Food and beverages", None, "106.00", "")]}
    seen = []

    def fake(url):
        seen.append(url)
        page = int(url.split("page=")[1].split("&")[0])
        return _api_page("2026-03", pages[page], page, 2)

    rec = Recorder(tmp_path / "c", tmp_path / "l.jsonl")
    rows = O.fetch_month("2026-03", rec, fetch=fake, raw_dir=tmp_path / "raw")
    assert len(rows) == 2 and len(seen) == 2
    O.fetch_month("2026-03", rec, fetch=fake, raw_dir=tmp_path / "raw")
    assert len(seen) == 2                                  # second time served from cache
    log = read_log(tmp_path / "l.jsonl")
    assert {e["service"] for e in log} == {"direct"} and all(e["tag"] == "official-mospi-api" for e in log)
    tidy = O.tidy_rows("2026-03", rows, {"CPI": 100.0, "01": 36.75}, {})
    assert [(r["code"], r["level"], r["index"]) for r in tidy] == [("CPI", "general", 104.0), ("01", "division", 106.0)]
    assert tidy[0]["name"] == "CPI (General)" and tidy[0]["published_yoy"] == 4.0


def test_tidy_rows_rejects_wrong_month():
    rows = _api_page("2026-04", [(None, "CPI (General)", None, "104.00", "4.0")], 1, 1)["data"]
    with pytest.raises(RuntimeError):
        O.tidy_rows("2026-03", rows, {}, {})


# ---------- checks and baselines on a toy economy ----------
def toy():
    """Two groups, 2025-01 .. 2026-09. Headline = weighted mean of levels (as MoSPI publishes it)."""
    w = {"01.1": 40.0, "07.2": 60.0}
    s = {"01.1": {}, "07.2": {}, O.HEADLINE: {}}
    a, b = 100.0, 100.0
    for m in O.month_range():
        a *= 1.006 if m[5:] in ("06", "07", "08") else 1.002
        b *= 1.003
        s["01.1"][m], s["07.2"][m] = a, b
        s[O.HEADLINE][m] = M.aggregate({"01.1": a, "07.2": b}, w)
    pub = {O.HEADLINE: {m: M.yoy(s[O.HEADLINE][m], s[O.HEADLINE][M.add_months(m, -12)]) for m in O.TEST_MONTHS}}
    return s, {**w, O.HEADLINE: 100.0}, pub


def test_aggregation_and_yoy_checks_on_toy():
    s, w, pub = toy()
    assert all(abs(g) < 1e-9 for *_, g in O.aggregation_check(s, w, "group", O.month_range()))
    assert all(abs(d) < 1e-9 for *_, d in O.yoy_check(s, pub, O.TEST_MONTHS))


def test_b2_never_sees_the_target_month():
    s, w, pub = toy()
    before = O.b2(s, w, "2026-05")
    for code in s:
        for m in list(s[code]):
            if m >= "2026-05":
                s[code][m] *= 1.5                      # wildly change the target month and later
    assert O.b2(s, w, "2026-05") == before


def test_b1_uses_levels_or_last_official_print():
    s, w, pub = toy()
    v, src = O.b1(s, pub, "2026-03")
    assert v == pytest.approx(pub[O.HEADLINE]["2026-02"]) and src == "2024-series levels"
    v, src = O.b1(s, pub, "2026-01", older_prints={"2025-12": 1.33})
    assert v == 1.33 and src.startswith("2012-series")


def test_run_baselines_scores_poll_only_where_dated(tmp_path):
    s, w, pub = toy()
    poll_csv = tmp_path / "poll.csv"
    poll_csv.write_text("month,median_forecast,n_economists,source_url,published_at\n"
                        "2026-02,3.0,30,https://x/a,2026-03-09\n2026-03,none,none,none,none\n"
                        "2026-04,3.1,,https://x/b,\n", encoding="utf-8")
    poll = O.read_poll(poll_csv)
    assert poll == {"2026-02": 3.0}                    # 'none' and undated rows are left out
    rows = O.run_baselines(s, w, pub, O.TEST_MONTHS, poll, {"2025-12": 1.0})
    assert len(rows) == 9 and O.mean_abs([r["poll_miss"] for r in rows])[1] == 1


# ---------- poll parsing (code decides the number) ----------
def test_poll_line_reads_the_median():
    hit = P.poll_line("Annual retail inflation likely rose to 3.60% in March from 3.21% in February, according "
                      "to a Reuters poll of 42 economists.", "2026-03")
    assert hit["median_forecast"] == 3.6 and hit["n_economists"] == 42
    hit = P.poll_line("The median forecast of 2.4% represents a sharp increase from 1.33% in December, according "
                      "to a Reuters poll of 34 economists taken between", "2026-01",
                      url="https://www.reuters.com/world/india/india-january-consumer-inflation-likely-rose-24")
    assert hit["median_forecast"] == 2.4 and hit["tier"] == "A"


def test_poll_line_rejects_other_numbers():
    assert P.poll_line("In the June 2 to June 8 poll, 94% of economists, 66 of 70, forecast the policy rate would "
                       "rise to 1.0% by the end of June.", "2026-05") is None          # no inflation figure
    assert P.poll_line("Nearly 60% of economists, 35 of 61, in the September 18 to 28 Reuters poll expected a hike",
                       "2026-09") is None
    assert P.poll_line("Retail inflation likely rose to 3.6% in March, a Reuters poll of 42 economists showed.",
                       "2026-04") is None                                                 # wrong month


def test_poll_dates_and_estimate():
    assert P.release_date("2026-03").isoformat() == "2026-04-13"      # 12 April 2026 is a Sunday
    assert P.search_window("2026-09") == ("2026-09-25", "2026-10-11")
    assert P.estimate_credits(["2026-01"]) == 2 + 2 + 2
