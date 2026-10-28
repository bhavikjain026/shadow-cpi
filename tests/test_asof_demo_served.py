"""tools/asof_demo_served.py: the page-selection rule and the marker, offline (0 credits)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import asof_demo_served as D  # noqa: E402


def write(tmp_path, cases):
    p = tmp_path / "cases.jsonl"
    p.write_text("\n".join(json.dumps(c) for c in cases))
    return p


def res(url, pub=None, pd=None, caps=()):
    return {"url": url, "published_date": pub, "page_date": pd, "wayback_captures": list(caps)}


def test_candidates_follow_case_order_and_rule_two(tmp_path):
    cut = "2026-07-08"
    cases = [{"id": "E2", "cutoff": cut, "results": [res("u/e2", "2026-07-01", None, ["2026-07-01", "2026-08-01"])]},
             {"id": "C10", "cutoff": cut, "results": [res("u/c10", None, "2026-07-02", ["2026-07-03", "2026-07-20"])]},
             {"id": "C2", "cutoff": cut, "results": [
                 res("u/late", "2026-07-09", None, ["2026-07-01", "2026-08-01"]),      # dated after: no
                 res("u/onlyafter", "2026-07-01", None, ["2026-07-10"]),               # no pre-cutoff capture: no
                 res("u/onlybefore", "2026-07-01", None, ["2026-07-01"]),              # no later capture: no
                 res("u/c2", "2026-07-01", None, ["2026-07-08", "2026-07-09"]),
                 res("u/e2", "2026-07-01", None, ["2026-07-01", "2026-08-01"])]}]       # seen again in E2: once
    assert [(c["id"], r["url"]) for c, r in D.candidates(write(tmp_path, cases))] == \
        [("C2", "u/c2"), ("C2", "u/e2"), ("C10", "u/c10")]


def test_digest_rule():
    caps = [("20260701000000", "A"), ("20260707000000", "B"), ("20260710000000", "B"), ("20260801000000", "C")]
    assert D.digest_changed(caps, "2026-07-08") == ("20260707000000", "20260801000000")
    assert D.digest_changed(caps[:3], "2026-07-08") is None              # later capture identical
    assert D.digest_changed(caps[2:], "2026-07-08") is None              # nothing on or before the cutoff
    assert D.digest_changed(None, "2026-07-08") is None


def test_pick_stops_at_the_first_passing_page_and_caps_lookups():
    class Fake:
        def __init__(self):
            self.asked = []

        def captures(self, url):
            self.asked.append(url)
            return {"b": [("20260701000000", "A"), ("20260801000000", "Z")]}.get(url, [("20260701000000", "A")])
    cands = [({"id": "C1", "cutoff": "2026-07-08"}, {"url": u}) for u in ("a", "b", "c")]
    fake = Fake()
    c, r, hit, tried = D.pick(fake, cands)
    assert r["url"] == "b" and fake.asked == ["a", "b"] and [t["passes"] for t in tried] == [False, True]
    fake = Fake()
    assert D.pick(fake, cands, max_lookups=1)[0] is None and fake.asked == ["a"]


def test_marker_counts_only_dates_after_the_cutoff():
    text = "Published 2026-07-01. Updated: July 9, 2026. Also 12 Aug 2026 and 2026-07-08."
    assert D.post_cutoff_dates(text, "2026-07-08") == ["2026-07-09", "2026-08-12"]
    assert D.post_cutoff_dates("", "2026-07-08") == []


def test_real_cases_have_a_candidate():
    assert D.candidates()
