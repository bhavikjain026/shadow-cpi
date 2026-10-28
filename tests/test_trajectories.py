"""timelock.trajectories: leak-free kept evidence, as-of copies served, unchecked pages marked, a stable receipt,
loud replay gaps, replay only (offline, 0 credits)."""
import json
import sys
from pathlib import Path

import pytest

from timelock import Results, Wayback
from timelock.trajectories import (AsOfNotChecked, CacheMiss, CachedTavily, cached_extract_fn, generate,
                                   receipt_sha256, request_hash, verify_receipt)

ROOT = Path(__file__).resolve().parents[1]
CUT = "2026-10-06"
QUERY = "RBI repo rate decision October 2026"
PARAMS = {"topic": "news", "max_results": 5}
EDITED = "https://e.example/rbi-explainer"
RESULTS = [
    {"url": "https://a.example/rbi-preview", "title": "RBI preview", "content": "Economists expect a hold. More.",
     "published_date": "2026-10-03"},
    {"url": "https://b.example/2026/10/08/rbi-holds/", "title": "RBI holds rate", "content": "The RBI held rates.",
     "published_date": "2026-10-05"},                                              # address date after the cutoff
    {"url": "https://c.example/rbi", "title": "RBI explainer", "content": "What the MPC does."},   # undated
    {"url": "https://d.example/rbi-live", "title": "RBI live", "content": "Live updates.",
     "published_date": "2026-10-04"},                         # page says updated after cutoff, no archive copy
    {"url": EDITED, "title": "What the MPC will decide", "content": "The MPC held the repo rate at 5.25 per cent.",
     "published_date": "2026-10-02"},                         # edited after the cutoff; Wayback copy from before it
]
PAGES = {"https://a.example/rbi-preview": "Published: 3 October 2026. Economists expect a hold.",
         "https://d.example/rbi-live": "Updated: 7 October 2026. The MPC held the repo rate.",
         EDITED: "Updated: 8 October 2026. The MPC held the repo rate at 5.25 per cent on 7 October."}
ARCHIVED = "<p>Published: 2 October 2026.</p><p>The MPC meets on 7 October and is expected to hold the repo rate.</p>"
SEARCH_WINDOW = {"start_date": "2026-09-07", "end_date": CUT, "filter_by_published_date": True}


def save(cache, service, endpoint, body, response, when="2026-10-22T10:00:00+00:00"):
    d = cache / service
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{request_hash(service, endpoint, body)}.json").write_text(json.dumps(
        {"service": service, "endpoint": endpoint, "request": body, "response": response,
         "retrieved_at": when}), encoding="utf-8")


def save_get(cache, url, text):
    save(cache, "direct", "GET", {"url": url}, {"final_url": url, "text": text})


@pytest.fixture
def cache(tmp_path):
    save(tmp_path, "tavily", "/search", {"query": QUERY, **SEARCH_WINDOW, **PARAMS, "include_usage": True},
         {"request_id": "req-1", "results": RESULTS})
    for url, text in PAGES.items():
        save(tmp_path, "tavily", "/extract", {"urls": [url], "extract_depth": "basic", "include_usage": True},
             {"request_id": "ex-" + url[-3:], "results": [{"url": url, "raw_content": text}]})
    # the edited page's archive: a capture before the cutoff, and a different one after it
    save_get(tmp_path, Wayback().cdx_url(EDITED),
             json.dumps([["timestamp", "digest"], ["20261003120000", "AAA"], ["20261009090000", "BBB"]]))
    save_get(tmp_path, f"https://web.archive.org/web/20261003120000id_/{EDITED}", ARCHIVED)
    return tmp_path


TASK = {"question": "Did the RBI change the repo rate in October 2026?", "searches": [{"query": QUERY, **PARAMS}]}


def urls(items):
    return {e["url"] for e in items}


def test_no_result_after_cutoff_is_kept(cache):
    t = generate(TASK, CUT, client=CachedTavily(cache))
    ev = t["evidence"]
    assert urls(ev["kept_as_of_verified"]) == {EDITED}
    assert urls(ev["kept_not_checked"]) == {"https://a.example/rbi-preview"}
    why = {e["url"]: e["why"] for e in ev["dropped"]}
    assert why["https://b.example/2026/10/08/rbi-holds/"].startswith("leak")
    assert why["https://c.example/rbi"].startswith("date_flag")
    assert why["https://d.example/rbi-live"].startswith("leak")         # caught by the page's own date
    for e in ev["kept_as_of_verified"] + ev["kept_not_checked"]:
        assert all(d <= CUT for d in e["dates"])


def test_edited_page_is_served_from_its_archived_copy(cache):
    """Live page updated 8 Oct (after the cutoff), Wayback copy from 3 Oct: served as of the cutoff, not dropped."""
    t = generate(TASK, CUT, client=CachedTavily(cache))
    row = next(r for r in t["results"] if r["url"] == EDITED)
    assert row["extract"]["status"] == "wayback_asof" and row["as_of"] == "as-of verified (wayback_asof)"
    assert row["extract"]["live_page_date"] == "2026-10-08"            # recorded, but not the date that counts
    assert row["page_date"] == "2026-10-02" and row["verdict"] == "safe" and row["decision"] == "kept"
    assert row["extract"]["capture_time"] == "2026-10-03T12:00:00Z"
    assert row["quote_from"] == "as_of_copy" and "expected to hold" in row["quote"]
    assert "5.25" not in row["quote"]                                  # the later text never enters the quote


def test_missing_archive_lookup_is_marked_not_checked(cache):
    t = generate(TASK, CUT, client=CachedTavily(cache))
    row = next(r for r in t["results"] if r["url"] == "https://a.example/rbi-preview")
    assert row["as_of"] == "not checked (no cached archive lookup)"
    assert row["decision"] == "kept" and "snippet-level" in row["reason"]
    assert t["counts"]["kept_not_checked"] == 1 and t["counts"]["kept_as_of_verified"] == 1


def test_require_as_of_fails_loudly(cache):
    with pytest.raises(AsOfNotChecked, match="a.example"):
        generate(TASK, CUT, client=CachedTavily(cache), require_as_of=True)


def test_require_as_of_passes_when_every_kept_page_is_checked(cache):
    def two_results(query, cutoff, **params):
        res = CachedTavily(cache).search(query, **SEARCH_WINDOW, **params)
        return [r for r in res["results"] if r["url"] in (EDITED, "https://c.example/rbi")]
    t = generate(TASK, CUT, search_fn=two_results, extract_fn=cached_extract_fn(CachedTavily(cache)),
                 require_as_of=True)
    assert urls(t["evidence"]["kept_as_of_verified"]) == {EDITED} and t["evidence"]["kept_not_checked"] == []


def test_search_fn_labels_are_not_trusted():
    """A search_fn that labels everything safe cannot get a post-cutoff result into kept evidence."""
    def lying(query, cutoff, **params):
        return Results([{**r, "status": "safe"} for r in RESULTS], cutoff=cutoff, window=["2026-09-07", cutoff],
                       response={"request_id": "x", "results": RESULTS})
    t = generate(TASK, CUT, search_fn=lying, extract_fn=None)
    kept = t["evidence"]["kept_not_checked"]
    assert urls(kept) == {"https://a.example/rbi-preview", "https://d.example/rbi-live", EDITED}
    assert all(e["as_of"] == "not checked (page not read)" for e in kept)
    assert all(d <= CUT for e in kept for d in e["dates"])
    assert t["results"][1]["search_label"] == "safe" and t["results"][1]["verdict"] == "leak"


def test_receipt_is_stable(cache):
    a = generate(TASK, CUT, client=CachedTavily(cache))
    b = generate(TASK, CUT, client=CachedTavily(cache))
    assert a["receipt"]["sha256"] == b["receipt"]["sha256"] == receipt_sha256(a)
    assert json.loads(json.dumps(a)) == a and verify_receipt(json.loads(json.dumps(a)))
    a["evidence"]["kept_not_checked"][0]["quote"] = "edited"
    assert not verify_receipt(a)


def test_missing_search_cache_fails_loudly(cache):
    task = {"question": "q", "searches": [{"query": "a query nobody saved", **PARAMS}]}
    with pytest.raises(CacheMiss, match="a query nobody saved"):
        generate(task, CUT, client=CachedTavily(cache))


def test_missing_extract_cache_fails_loudly(cache):
    (cache / "tavily" / (request_hash("tavily", "/extract", {"urls": ["https://a.example/rbi-preview"],
                                                              "extract_depth": "basic", "include_usage": True})
                         + ".json")).unlink()
    with pytest.raises(CacheMiss, match="a.example"):
        generate(TASK, CUT, client=CachedTavily(cache))


def test_replay_only():
    with pytest.raises(ValueError, match="replay only"):
        generate(TASK, CUT)
    with pytest.raises(TypeError, match="replay only"):
        generate(TASK, CUT, client=object())
    with pytest.raises(TypeError):
        generate(TASK, CUT, live=True)                                   # no live switch in this version


def test_batch_extract_serves_the_earliest_saved_copy(tmp_path):
    url = "https://x.example/page"
    for when, text, other in (("2026-10-25T00:00:00+00:00", "late", "https://y.example/1"),
                              ("2026-10-20T00:00:00+00:00", "early", "https://y.example/2")):
        save(tmp_path, "tavily", "/extract", {"urls": [url, other], "extract_depth": "basic", "include_usage": True},
             {"request_id": text, "results": [{"url": url, "raw_content": text}]}, when=when)
    resp = CachedTavily(tmp_path).extract([url], extract_depth="basic")
    assert resp["results"][0]["raw_content"] == "early" and resp["batch_of"] == 2


def test_cache_key_matches_recorder():
    from shadow_cpi.recorder import request_hash as recorder_hash
    body = {"query": QUERY, "include_usage": True, "include_domains": ["x.in"]}
    assert request_hash("tavily", "/search", body) == recorder_hash("tavily", "/search", body)


def test_demo_trajectories_are_sealed_and_text_free():
    index = json.loads((ROOT / "examples" / "trajectories" / "index.json").read_text(encoding="utf-8"))
    assert len(index["written"]) == 5
    for cid in index["written"]:
        f = ROOT / "examples" / "trajectories" / f"{cid}.json"
        t = json.loads(f.read_text(encoding="utf-8"))
        assert verify_receipt(t), f.name
        assert "raw_content" not in f.read_text(encoding="utf-8")
        ev = t["evidence"]
        for e in ev["kept_as_of_verified"] + ev["kept_not_checked"]:
            assert all(d <= t["cutoff"] for d in e["dates"]), (f.name, e["url"])
            assert len(e["quote"].split()) <= 25
        assert all(e["as_of"].startswith("as-of verified") for e in ev["kept_as_of_verified"])
        assert all(e["as_of"].startswith("not checked") for e in ev["kept_not_checked"])


def test_doc_counts_are_generated_from_the_files():
    sys.path.insert(0, str(ROOT / "examples"))
    import trajectory_demo as demo
    doc = (ROOT / "docs" / "trajectories.md").read_text(encoding="utf-8")
    assert demo.with_counts(doc, demo.counts_block()) == doc


def test_doc_c6_example_matches_its_file():
    t = json.loads((ROOT / "examples" / "trajectories" / "C6.json").read_text(encoding="utf-8"))
    assert t["cutoff"] == "2026-10-07" and t["task"]["question"] == "TCS Q2 FY27 quarterly results"
    leak = [r for r in t["results"] if r["verdict"] == "leak"]
    assert [(r["published_date"], r["page_date"]) for r in leak] == [("2026-10-07", "2026-10-08")]
