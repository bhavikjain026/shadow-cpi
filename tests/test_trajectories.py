"""timelock.trajectories: leak-free kept evidence, a stable receipt, loud replay gaps (offline, 0 credits)."""
import json
from pathlib import Path

import pytest

from timelock import Results
from timelock.trajectories import (CacheMiss, CachedTavily, generate, receipt_sha256, request_hash,
                                   verify_receipt)

ROOT = Path(__file__).resolve().parents[1]
CUT = "2026-10-06"
QUERY = "RBI repo rate decision October 2026"
PARAMS = {"topic": "news", "max_results": 4}
RESULTS = [
    {"url": "https://a.example/rbi-preview", "title": "RBI preview", "content": "Economists expect a hold. More.",
     "published_date": "2026-10-03"},
    {"url": "https://b.example/2026/10/08/rbi-holds/", "title": "RBI holds rate", "content": "The RBI held rates.",
     "published_date": "2026-10-05"},                                              # address date after the cutoff
    {"url": "https://c.example/rbi", "title": "RBI explainer", "content": "What the MPC does."},   # undated
    {"url": "https://d.example/rbi-live", "title": "RBI live", "content": "Live updates.",
     "published_date": "2026-10-04"},                                              # page says updated after cutoff
]
PAGES = {"https://a.example/rbi-preview": "Published: 3 October 2026. Economists expect a hold.",
         "https://d.example/rbi-live": "Updated: 7 October 2026. The MPC held the repo rate."}


def save(cache, service, endpoint, body, response):
    d = cache / service
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{request_hash(service, endpoint, body)}.json").write_text(json.dumps(
        {"service": service, "endpoint": endpoint, "request": body, "response": response,
         "retrieved_at": "2026-10-22T10:00:00+00:00"}), encoding="utf-8")


@pytest.fixture
def cache(tmp_path):
    body = {"query": QUERY, "start_date": "2026-09-07", "end_date": CUT, "filter_by_published_date": True,
            **PARAMS, "include_usage": True}
    save(tmp_path, "tavily", "/search", body, {"request_id": "req-1", "results": RESULTS})
    for url, text in PAGES.items():
        save(tmp_path, "tavily", "/extract", {"urls": [url], "extract_depth": "basic", "include_usage": True},
             {"request_id": "ex-" + url[-3:], "results": [{"url": url, "raw_content": text}]})
    return tmp_path


TASK = {"question": "Did the RBI change the repo rate in October 2026?", "searches": [{"query": QUERY, **PARAMS}]}


def test_no_result_after_cutoff_is_kept(cache):
    t = generate(TASK, CUT, client=CachedTavily(cache))
    kept = {e["url"] for e in t["evidence"]["kept"]}
    assert kept == {"https://a.example/rbi-preview"}
    why = {e["url"]: e["why"] for e in t["evidence"]["dropped"]}
    assert why["https://b.example/2026/10/08/rbi-holds/"].startswith("leak")
    assert why["https://c.example/rbi"].startswith("date_flag")
    assert why["https://d.example/rbi-live"].startswith("leak")         # caught by the page's own date
    for e in t["evidence"]["kept"]:
        assert all(d <= CUT for d in e["dates"])


def test_search_fn_labels_are_not_trusted():
    """A search_fn that labels everything safe cannot get a post-cutoff result into kept evidence."""
    def lying(query, cutoff, **params):
        return Results([{**r, "status": "safe"} for r in RESULTS], cutoff=cutoff, window=["2026-09-07", cutoff],
                       response={"request_id": "x", "results": RESULTS})
    t = generate(TASK, CUT, search_fn=lying, extract_fn=None)
    assert {e["url"] for e in t["evidence"]["kept"]} == {"https://a.example/rbi-preview",
                                                         "https://d.example/rbi-live"}
    assert all(d <= CUT for e in t["evidence"]["kept"] for d in e["dates"])
    assert t["results"][1]["search_label"] == "safe" and t["results"][1]["verdict"] == "leak"


def test_receipt_is_stable(cache):
    a = generate(TASK, CUT, client=CachedTavily(cache))
    b = generate(TASK, CUT, client=CachedTavily(cache))
    assert a["receipt"]["sha256"] == b["receipt"]["sha256"] == receipt_sha256(a)
    assert json.loads(json.dumps(a)) == a and verify_receipt(json.loads(json.dumps(a)))
    a["evidence"]["kept"][0]["quote"] = "edited"
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


def test_offline_by_default():
    with pytest.raises(ValueError, match="offline by default"):
        generate(TASK, CUT)


def test_require_as_of_drops_unverified_pages(cache):
    t = generate(TASK, CUT, client=CachedTavily(cache), require_as_of=True)
    assert t["evidence"]["kept"] == []                      # no Wayback copy cached for the one safe page
    assert "no page copy as of the cutoff" in t["evidence"]["dropped"][0]["why"]


def test_demo_trajectories_are_sealed_and_text_free():
    files = sorted((ROOT / "examples" / "trajectories").glob("*.json"))
    assert len(files) == 5
    for f in files:
        t = json.loads(f.read_text(encoding="utf-8"))
        assert verify_receipt(t), f.name
        assert "raw_content" not in f.read_text(encoding="utf-8")
        for e in t["evidence"]["kept"]:
            assert all(d <= t["cutoff"] for d in e["dates"]), (f.name, e["url"])
            assert len(e["quote"].split()) <= 25


def test_cache_key_matches_recorder():
    from shadow_cpi.recorder import request_hash as recorder_hash
    body = {"query": QUERY, "include_usage": True, "include_domains": ["x.in"]}
    assert request_hash("tavily", "/search", body) == recorder_hash("tavily", "/search", body)


def test_doc_counts_match_demo_files():
    ts = [json.loads(f.read_text(encoding="utf-8")) for f in (ROOT / "examples" / "trajectories").glob("*.json")]
    kept = sum(len(t["evidence"]["kept"]) for t in ts)
    verified = sum(e["as_of_verified"] for t in ts for e in t["evidence"]["kept"])
    doc = (ROOT / "docs" / "trajectories.md").read_text(encoding="utf-8")
    assert f"Only {verified} of the {kept} kept results" in " ".join(doc.split())
