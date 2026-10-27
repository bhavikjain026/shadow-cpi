"""Forced model migration (v2/PREREGISTRATION.md Amendment G): the model ID is picked by the call date in IST, logged
with every call, and a request already cached for the original model is never sent to a replacement. Fakes only."""
import json
from datetime import datetime, timezone

import pytest

from shadow_cpi import model_map as MM
from shadow_cpi.nemotron import Nemotron
from shadow_cpi.recorder import Recorder, read_log
from shadow_cpi.settings import models

NANO, SUPER = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B", "nvidia/nemotron-3-super-120b-a12b"
LIGHTNING, SUPER_VL = "nvidia/Nemotron-3_5-Lightning", "nvidia/Nemotron-3.5-Super-VL"
LAST_OLD = datetime(2026, 11, 8, 18, 29, 59, tzinfo=timezone.utc)      # 8 Nov 23:59:59 IST
FIRST_NEW = datetime(2026, 11, 8, 18, 30, 0, tzinfo=timezone.utc)      # 9 Nov 00:00:00 IST


def test_config_roles_and_dated_map():
    cfg = models()
    assert (cfg["small"], cfg["mid"]) == (NANO, SUPER)          # role keys stay the original IDs
    MM.check(cfg)                                                # no gap or overlap
    assert cfg["dated"]["timezone"] == "Asia/Kolkata"


@pytest.mark.parametrize("when, nano, sup", [
    (datetime(2026, 10, 29, 6, 0, tzinfo=timezone.utc), NANO, SUPER),       # the October seal
    (LAST_OLD, NANO, SUPER),
    (FIRST_NEW, LIGHTNING, SUPER_VL),                                        # 9 Nov in IST, still 8 Nov in UTC
    (datetime(2026, 12, 10, 12, 0, tzinfo=timezone.utc), LIGHTNING, SUPER_VL),   # the November seal, judging
])
def test_resolve_by_ist_call_date(when, nano, sup):
    assert MM.resolve(NANO, when) == nano and MM.resolve(SUPER, when) == sup
    assert MM.in_use(when) == {"small": nano, "mid": sup}


def test_unmapped_ids_pass_through():
    assert MM.resolve("nvidia/Nemotron-3-Ultra-550b-a55b", FIRST_NEW) == "nvidia/Nemotron-3-Ultra-550b-a55b"
    assert MM.resolve("m", FIRST_NEW) == "m"
    assert MM.resolve(NANO, FIRST_NEW, cfg={"small": NANO}) == NANO          # no dated map: unchanged


def test_check_refuses_a_gap():
    cfg = {"dated": {"periods": [{"from": None, "until": "2026-11-07"}, {"from": "2026-11-09", "until": None}]}}
    with pytest.raises(ValueError):
        MM.check(cfg)


class Fake:
    def __init__(self):
        self.sent = []

    def __call__(self, method, url, key, body, timeout):
        self.sent.append(body)
        return {"choices": [{"message": {"content": json.dumps({"answer": body["model"]})}}]}


def nem(tmp_path, when):
    fake = Fake()
    rec = Recorder(cache_dir=tmp_path / "cache", log_file=tmp_path / "log.jsonl")
    return Nemotron(api_key="test", recorder=rec, transport=fake, clock=lambda: when), fake, rec


@pytest.mark.parametrize("when, sent, migrated", [(LAST_OLD, SUPER, False), (FIRST_NEW, SUPER_VL, True)])
def test_call_uses_and_logs_the_dated_model(tmp_path, when, sent, migrated):
    n, fake, rec = nem(tmp_path, when)
    out, _ = n.chat_json(SUPER, "sys", "user", {"type": "object"})
    assert fake.sent[0]["model"] == sent and out == {"answer": sent}
    assert fake.sent[0]["response_format"]["type"] == "json_schema"         # same schema request, only the ID moves
    log = read_log(rec.log_file)[-1]
    assert (log["params"]["model"], log["model_requested"], log["model_migrated"]) == (sent, SUPER, migrated)


def test_cached_original_answer_is_reused_after_the_switch(tmp_path):
    n, fake, rec = nem(tmp_path, LAST_OLD)
    n.chat_json(NANO, "sys", "same page", {"type": "object"})               # asked on 8 Nov: cached for Nano
    n.clock = lambda: FIRST_NEW
    out, _ = n.chat_json(NANO, "sys", "same page", {"type": "object"})     # re-checking it later: no new call
    assert len(fake.sent) == 1 and out == {"answer": NANO}
    log = read_log(rec.log_file)[-1]
    assert log["cached"] and log["params"]["model"] == NANO and not log["model_migrated"]
    n.chat_json(NANO, "sys", "a new page", {"type": "object"})              # a new request goes to the replacement
    assert fake.sent[-1]["model"] == LIGHTNING and read_log(rec.log_file)[-1]["model_migrated"]


def test_seal_payload_names_the_models_at_the_cutoff():
    cfg = models()
    assert MM.in_use(datetime(2026, 10, 28, 18, 29, tzinfo=timezone.utc), cfg) == {"small": NANO, "mid": SUPER}
    assert MM.in_use(datetime(2026, 11, 28, 18, 29, tzinfo=timezone.utc), cfg) == {"small": LIGHTNING,
                                                                                   "mid": SUPER_VL}


def test_schema_fallback_is_logged(tmp_path):
    from shadow_cpi.http import ApiError

    class Refuses(Fake):
        def __call__(self, method, url, key, body, timeout):
            if body["response_format"]["type"] == "json_schema":
                self.sent.append(body)
                raise ApiError(400, "schema mode not supported")
            return super().__call__(method, url, key, body, timeout)

    fake = Refuses()
    rec = Recorder(cache_dir=tmp_path / "cache", log_file=tmp_path / "log.jsonl")
    n = Nemotron(api_key="test", recorder=rec, transport=fake, clock=lambda: LAST_OLD)
    n.chat_json(SUPER, "sys", "user", {"type": "object"})
    assert [b["response_format"]["type"] for b in fake.sent] == ["json_schema", "json_object"]
    assert read_log(rec.log_file)[-1]["json_schema_fallback"] is True
