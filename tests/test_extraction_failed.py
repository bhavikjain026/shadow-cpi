"""Amendment H (v2/PREREGISTRATION.md): a replacement-model reply with no parseable JSON skips that page, is counted and
logged, and the run completes; the original IDs keep raising. Fake transports only: no network, no credits."""
import json
from datetime import datetime, timezone

import pytest

from shadow_cpi import evidence as E
from shadow_cpi.nemotron import ExtractionFailed, Nemotron
from shadow_cpi.recorder import Recorder
from shadow_cpi.settings import models

MIGRATED = datetime(2026, 11, 8, 18, 30, tzinfo=timezone.utc)        # 9 Nov 00:00 IST
BEFORE = datetime(2026, 10, 31, 6, 0, tzinfo=timezone.utc)
SCHEMA = {"type": "object", "properties": {"events": {"type": "array"}}, "required": ["events"]}


def truncated(method, url, key, body, timeout):
    """A reply that hit the token limit: no closing brace, then whitespace (the real failure of 31 Oct)."""
    return {"choices": [{"message": {"content": "  " + "\n   " * 40}, "finish_reason": "length"}], "usage": {}}


def nem_at(clock, tmp_path, transport=truncated):
    return Nemotron(api_key="x", recorder=Recorder(cache_dir=tmp_path / "cache", log_file=tmp_path / "log.jsonl"),
                    transport=transport, clock=lambda: clock)


def test_a_truncated_replacement_reply_raises_extraction_failed_with_its_finish_reason(tmp_path):
    nem = nem_at(MIGRATED, tmp_path)
    with pytest.raises(ExtractionFailed) as e:
        nem.chat_json(models()["mid"], "system", "user", SCHEMA, tag="t")
    assert e.value.finish_reason == "length" and e.value.model == "nvidia/Nemotron-3.5-Super-VL" and e.value.call_id


def test_the_original_ids_still_raise_the_old_error(tmp_path):
    nem = nem_at(BEFORE, tmp_path)                                         # before 9 Nov: the original model is asked
    with pytest.raises(ValueError) as e:
        nem.chat_json(models()["mid"], "system", "user", SCHEMA, tag="t")
    assert not isinstance(e.value, ExtractionFailed) and "no JSON object" in str(e.value)


def test_a_valid_replacement_reply_is_unchanged(tmp_path):
    ok = lambda *a: {"choices": [{"message": {"content": json.dumps({"events": []})}, "finish_reason": "stop"}], "usage": {}}  # noqa: E731
    out, _ = nem_at(MIGRATED, tmp_path, ok).chat_json(models()["mid"], "s", "u", SCHEMA, tag="t")
    assert out == {"events": []}


class FakeTavily:
    def search(self, query, **kw):
        return {"results": [{"url": "https://a.example/bad", "title": "t", "published_date": "2026-11-03"},
                            {"url": "https://a.example/good", "title": "t", "published_date": "2026-11-04"}]}, "c1"

    def extract(self, urls, **kw):
        return {"results": [{"url": u, "raw_content": "Milk price hike by ₹2 per litre from 5 Nov"} for u in urls],
                "failed_results": []}, "e1"


class FakeNem:
    """price_events fails on one page (a replacement model's truncated reply) and works on the other."""
    def __init__(self):
        self.calls = []

    def price_events(self, model, text, tag=None, parent=None, **kw):
        self.calls.append(tag)
        if len(self.calls) == 1:
            raise ExtractionFailed("model returned no JSON object", call_id="c-bad", finish_reason="length",
                                   model="nvidia/Nemotron-3.5-Super-VL")
        return [], "c-ok"


def test_the_run_completes_skips_the_page_and_reports_the_count():
    nem = FakeNem()
    events = {"milk": {"queries": {"en": "milk price hike"}, "langs": ["en"], "cpi_code": "01.1.4.1.1.01"}}
    kept, stats, trace = E.collect_events(FakeTavily(), nem, "2026-11", events, langs=("en",), pre_days=0)
    assert len(nem.calls) == 2                                              # the second page was still read
    reason = "extraction_failed (replacement model reply had no parseable JSON)"
    assert stats["drops"][reason] == 1
    (f,) = [x for x in stats["failed_sources"] if x["url"] == "https://a.example/bad"]
    assert f["via"] == "Nemotron nvidia/Nemotron-3.5-Super-VL" and "finish_reason length" in f["reason"] and "c-bad" in f["reason"]
    assert kept == []


def test_the_quotes_path_also_skips_the_page_and_the_gatekeeper_failure_counts_too():
    class QNem(FakeNem):
        def price_quotes(self, model, text, item_hint="", tag=None, parent=None, **kw):
            self.calls.append(tag)
            raise ExtractionFailed("model returned no JSON object", call_id="q1", finish_reason="length",
                                   model="nvidia/Nemotron-3.5-Super-VL")
    items = {"onion": {"queries": {"en": "onion price"}, "base_unit": "kg"}}
    kept, stats, trace = E.collect_quotes(FakeTavily(), QNem(), "2026-11", items, langs=("en",))
    assert stats["drops"]["extraction_failed (replacement model reply had no parseable JSON)"] == 2   # both pages
    assert kept == [] and len(stats["failed_sources"]) == 2
    stats2 = {"drops": {}}
    E.extraction_failed(stats2, lambda r, n=1: stats2["drops"].__setitem__(r, stats2["drops"].get(r, 0) + n), "u",
                        ExtractionFailed("x", call_id="g", finish_reason="stop", model="m"))
    assert stats2["failed_sources"][0]["via"] == "Nemotron m"
