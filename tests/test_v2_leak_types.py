"""Leaks by source type (v2/DRIFT_PREREG.md, part C): the URL rule and the table. Offline, 0 credits."""
import pytest

from v2 import leak_types as LT


@pytest.mark.parametrize("url,t", [
    ("https://www.livemint.com/economy/rbi-policy-live-updates-repo-rate-11234567.html", "live blog"),
    ("https://www.ndtv.com/business/rbi-mpc-live-news", "live blog"),
    ("https://www.thehindu.com/business/live/", "live blog"),
    ("https://timesofindia.indiatimes.com/business/india-business/", "hub or tag page"),
    ("https://www.ndtv.com/", "hub or tag page"),
    ("https://indianexpress.com/about/milk-price/", "hub or tag page"),
    ("https://economictimes.indiatimes.com/topic/milk-price-hike", "hub or tag page"),
    ("https://www.business-standard.com/industry/news/indias-milk-production-increases-faster-126100500707_1.html",
     "article"),
    ("https://navbharattimes.indiatimes.com/state/mp/indore/articleshow/134590661.cms", "article"),
    ("https://www.thehindu.com/news/national/x/article70851063.ece", "article"),
    ("https://rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=6", "other"),
    ("https://icici.bank.in/content/dam/board-notice.pdf", "other"),
    ("https://icici.bank.in/content/dam/NSEBSE_14072026.pdf", "article"),   # 6+ digits: article, as the rule says
    ("https://www.delivery.com/olive-oil", "other"),          # 'live' inside a word is not a live blog
])
def test_rule(url, t):
    assert LT.source_type(url) == t


def test_table_counts_leaks_per_type_with_wilson():
    dt = {"rows": [{"arms": {"A": {"results": [{"url": "https://x.com/a/b-c-d-e", "label": "L"},
                                                {"url": "https://x.com/tag/milk", "label": "U"}]},
                             "B": {"results": [{"url": "https://x.com/a/b-c-d-e", "label": "P"}]}}}]}
    fi = {"rows": [{"arms": {"N": {"results": [{"url": "https://x.com/live/rbi", "label": "confirmed"},
                                               {"url": "https://x.com/live/rbi2", "label": "snippet"}]}}}]}
    t = LT.table(dt, fi)
    by = {r["type"]: r for r in t["rows"]}
    assert (t["results"], t["leaks"]) == (5, 2)
    assert t["leaks_by_arm"] == {"date test A": 1, "finance N": 1}
    assert by["article"]["pooled"]["leaks"] == 1 and by["article"]["pooled"]["results"] == 2
    assert by["live blog"]["finance"] == {**by["live blog"]["finance"], "leaks": 1, "results": 2, "rate": 0.5}
    assert by["other"]["pooled"]["rate"] is None and by["other"]["pooled"]["wilson95"] is None
    lo, hi = by["article"]["pooled"]["wilson95"]
    assert lo < 0.5 < hi
