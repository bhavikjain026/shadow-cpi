"""October page drift (v2/DRIFT_PREREG.md, part A): set, normalising, diff, quote and number checks, cap, freeze.
Offline with fakes."""
from datetime import datetime, timezone

import pytest

from shadow_cpi.budget import BudgetExceeded
from v2 import drift as D

NOW = datetime(2026, 10, 27, 4, 37, tzinfo=timezone.utc)          # 27 Oct, 10:07 IST
LINE = "Milk now costs 65 rupees a litre instead of 62 from 1 October"
SAVED = f"Header\n  {LINE}  \n© 2026 Some Paper. All rights reserved.\nFooter"


def card(url, lines=(LINE,), page=True, found="2026-10-25"):
    return {"url": url, "page_file": f"pages/{url[-1]}.txt" if page else None, "found": found,
            "claims": [{"line": ln} for ln in lines]}


def radar(*cards, corr=()):
    return {"cards": list(cards), "corroboration": [{"cards": list(corr)}]}


class FakeTav:
    def __init__(self, pages, cap=None):
        self.pages, self.cap, self.calls = pages, cap, []

    def extract(self, urls, **kw):
        if self.cap is not None and len(self.calls) >= self.cap:
            raise BudgetExceeded("cap")
        self.calls.append((list(urls), kw))
        return ({"results": [{"url": u, "raw_content": self.pages[u]} for u in urls if self.pages.get(u)],
                 "usage": {"credits": 1}, "request_id": "r"}, f"e{len(self.calls)}")


@pytest.fixture
def pages(tmp_path):
    (tmp_path / "pages").mkdir()
    for c in "abcdefg":
        (tmp_path / "pages" / f"{c}.txt").write_text(SAVED, encoding="utf-8")
    return tmp_path


def test_normalise_drops_furniture_and_whitespace_only_changes():
    assert D.normalise(SAVED) == f"Header\n{LINE}\nFooter"
    assert D.sha(D.normalise(SAVED)) == D.sha(D.normalise(SAVED.replace("Footer", "Footer\n\n   ") +
                                                          "\nCookie settings"))


def test_bundle_needs_a_saved_page_and_a_cited_line_and_counts_corroboration():
    r = radar(card("u/a"), card("u/b", lines=()), card("u/c", page=False), corr=[card("u/d"), card("u/a")])
    assert sorted(D.bundle(r)) == ["u/a", "u/d"]


def test_page_fetched_today_is_not_refetched():
    urls = D.bundle(radar(card("u/a", found="2026-10-27"), card("u/b", found=None)))
    assert D.due(urls, NOW) == ["u/b"]


def test_unchanged_page_and_changed_page(pages):
    new = f"Header\n{LINE.replace('65', '66')}\nFooter"
    tav = FakeTav({"u/a": SAVED.replace("Footer", "Footer  "), "u/b": new})
    st = D.run(tav, radar(card("u/a"), card("u/b")), {"runs": []}, NOW, pages)
    r = st["runs"][-1]
    assert (r["ist_date"], r["checked"], r["changed"], r["complete"]) == ("2026-10-27", 2, 1, True)
    a, b = r["pages"]
    assert not a["changed"] and "diff" not in a
    assert b["changed"] and b["quote_present"] is False and b["number_changed"] == "yes"
    assert "- " + LINE in b["diff"] and len(b["diff"]) <= 300
    assert tav.calls[0][1]["extract_depth"] == "basic"


def test_quote_still_there_when_only_other_text_changes():
    assert D.quote_check(LINE, f"New sidebar\n{LINE}") == (True, "no")
    assert D.quote_check(LINE, LINE.replace("instead of", "rather than")) == (False, "no")   # same numbers
    assert D.quote_check(LINE, "Totally different page text") == (False, "unknown")
    assert D.summarise_quotes([(True, "no"), (False, "unknown")]) == (False, "unknown")
    assert D.summarise_quotes([(False, "unknown"), (False, "yes")]) == (False, "yes")


def test_devanagari_digits_and_commas_read_as_numbers():
    assert D.numbers("दूध ६५ रुपये, 1,200 total") == {"65", "1200"}


def test_diff_is_capped_at_300_characters():
    old, new = "\n".join(f"old line {i} " * 5 for i in range(40)), "\n".join(f"new {i} " * 5 for i in range(40))
    d = D.short_diff(old, new)
    assert len(d) == 300 and d.endswith("…")


def test_fetch_failure_is_not_a_change(pages):
    st = D.run(FakeTav({"u/a": ""}), radar(card("u/a")), {"runs": []}, NOW, pages)
    r = st["runs"][-1]
    assert r["failed"] == ["u/a"] and r["changed"] == 0 and r["checked"] == 0


def test_cap_stops_cleanly_and_lists_unchecked(pages):
    cards = [card(f"u/{c}") for c in "abcdefg"]                # 7 URLs = 2 calls of 5
    tav = FakeTav({c["url"]: SAVED for c in cards}, cap=1)
    r = D.run(tav, radar(*cards), {"runs": []}, NOW, pages)["runs"][-1]
    assert not r["complete"] and r["checked"] == 5 and r["not_checked"] == ["u/f", "u/g"] and r["stopped"] == "cap"


def test_once_a_day_and_not_after_the_freeze(pages):
    st = D.run(FakeTav({"u/a": SAVED}), radar(card("u/a")), {"runs": []}, NOW, pages)
    with pytest.raises(SystemExit, match="once a day"):
        D.run(FakeTav({"u/a": SAVED}), radar(card("u/a")), st, NOW, pages)
    with pytest.raises(SystemExit, match="frozen"):
        D.run(FakeTav({}), radar(), {"runs": []}, datetime(2026, 10, 29, 18, 29, tzinfo=timezone.utc), pages)


def test_latest_summary_for_the_field_report(pages):
    st = D.run(FakeTav({"u/a": "Other\ntext"}), radar(card("u/a")), {"runs": []}, NOW, pages)
    s = D.latest(st)
    assert (s["changed"], s["checked"]) == (1, 1)
    assert s["pages"][0]["quote_present"] is False and s["pages"][0]["number_changed"] == "unknown"
    assert D.latest({"runs": []}) is None


def test_caps_in_config():
    from shadow_cpi.budget import cap_of, load_budget
    assert cap_of(D.BUDGET, load_budget()) == 60


def test_missing_saved_copy_is_listed_not_fetched_and_an_api_error_keeps_paid_results(pages):
    class Flaky(FakeTav):
        def extract(self, urls, **kw):
            if self.calls:
                raise ConnectionResetError("reset")
            return super().extract(urls, **kw)

    cards = [card(f"u/{c}") for c in "abcdefg"] + [card("u/z")]           # no pages/z.txt
    r = D.run(Flaky({c["url"]: SAVED for c in cards}), radar(*cards), {"runs": []}, NOW, pages)["runs"][-1]
    assert r["no_saved_copy"] == ["u/z"] and r["checked"] == 5 and r["not_checked"] == ["u/f", "u/g"]
    assert not r["complete"] and r["stopped"].startswith("ConnectionResetError")


def test_url_saved_twice_keeps_the_latest_copy_and_its_lines():
    old = {**card("u/a", lines=("old line",), found="2026-10-25"), "page_file": "pages/old.txt"}
    new = {**card("u/a", lines=("new line",), found="2026-10-26"), "page_file": "pages/new.txt"}
    b = D.bundle(radar(old, corr=[new]))["u/a"]
    assert (b["page_file"], b["lines"]) == ("pages/new.txt", ["new line"])


def test_cited_pieces_joined_with_ellipsis_are_each_searched_for():
    far = "Header\n" + "filler line\n" * 40 + "Milk up Rs 8 per litre\n" + "more filler\n" * 40 + "from 1 November"
    line = "Milk up Rs 8 per litre [...] from 1 November"
    assert D.quote_check(line, D.normalise(far)) == (True, "no")             # far apart, both present
    assert D.quote_check(line, D.normalise(far.replace("from 1 November", "from the start"))) == (False, "unknown")
    assert D.quote_check(line, D.normalise(far.replace("Rs 8", "Rs 6"))) == (False, "yes")   # one piece's number moved
    assert D.quote_check("A  [...]  B", "B\nA") == (True, "no")             # whitespace-normalised, order free
