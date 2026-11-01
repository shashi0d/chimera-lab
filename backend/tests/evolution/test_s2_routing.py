"""S2 part 5: per-call-type routing (evo_config `routing`): Spark Open for identify, checklist, thumbnail,
polish and the open critic, each with an output cap; Meta Spark 1.3 for traits and the legacy full plan; a logged
fallback to Meta; the provider on every call record and on the card."""

from __future__ import annotations

from typing import Any

import pytest

from app.adapters import usage
from app.adapters.baseten.client import BasetenEvoSpark
from app.adapters.meta.client import _MetaClient
from app.config import Settings
from app.errors import ChimeraError
from app.evolution.routing import RoutedSpark, caps, provider_for, routes, summarize
from app.models.schemas import ErrorCode


class Stub:
    def __init__(self, name: str, fail: Exception | None = None) -> None:
        self.model_id, self.fail, self.calls = name, fail, []

    def __getattr__(self, method: str):
        async def call(*args: Any, **kw: Any) -> Any:
            self.calls.append(method)
            if self.fail:
                raise self.fail
            return {"from": self.model_id, "method": method}
        return call


@pytest.mark.parametrize("method", ["identify", "checklist", "polish", "critic"])
def test_vision_and_text_checks_go_to_spark_open_with_a_cap(method):
    assert provider_for(method) == "baseten" and routes()[method]["max_tokens"] >= 4000


@pytest.mark.parametrize("method", ["write_plan", "learn_traits", "cite_traits", "judge_functions", "vary"])
def test_plans_and_traits_stay_on_meta(method):
    assert provider_for(method) == "meta"


def test_caps_are_keyed_by_request_purpose():
    c = caps()
    assert set(c) == {"evo_identify", "evo_checklist", "evo_polish", "evo_critic", "evo_describe", "evo_ask"}


async def test_routed_calls_reach_their_provider_and_are_logged():
    meta, bt = Stub("muse-spark-1.3"), Stub("meta-models/muse-spark-open-1026")
    r = RoutedSpark(meta, bt)
    assert (await r.checklist(b"img", ["a"]))["from"] == bt.model_id
    assert (await r.cite_traits({"scientific_name": "x"}))["from"] == meta.model_id
    assert bt.calls == ["checklist"] and meta.calls == ["cite_traits"]
    assert [(e["call"], e["provider"], e["fallback"]) for e in r.log] == [("checklist", "baseten", None),
                                                                         ("cite_traits", "meta", None)]


@pytest.mark.parametrize("fail", [ChimeraError(ErrorCode.UPSTREAM_ERROR, "unreadable"), ValueError("bad json")])
async def test_a_baseten_failure_falls_back_to_meta_once_and_is_logged(fail):
    meta, bt = Stub("meta"), Stub("open", fail)
    r = RoutedSpark(meta, bt)
    out = await r.polish("p")
    assert out["from"] == "meta" and bt.calls == ["polish"] and meta.calls == ["polish"]
    assert r.log[0]["provider"] == "baseten" and r.log[0]["error"]
    assert r.log[1]["provider"] == "meta" and r.log[1]["fallback"].startswith("Baseten failed")
    assert summarize(r.log)["fallbacks"] == [{"call": "polish", "reason": r.log[1]["fallback"]}]


async def test_a_budget_stop_is_never_a_fallback():
    meta, bt = Stub("meta"), Stub("open", ChimeraError(ErrorCode.BUDGET_EXCEEDED, "cap", retryable=False))
    r = RoutedSpark(meta, bt)
    with pytest.raises(ChimeraError):
        await r.identify(name="axolotl")
    assert meta.calls == []


async def test_without_a_baseten_key_everything_goes_to_meta_with_a_note():
    meta = Stub("meta")
    r = RoutedSpark(meta, None)
    await r.critic(b"x")
    assert r.log[0]["provider"] == "meta" and "BASETEN key missing" in r.log[0]["fallback"]


async def test_baseten_requests_carry_their_purpose_cap(tmp_path):
    st = Settings(_env_file=None, retry_base_seconds=0.0, BASETEN_API_KEY_MODEL_MUSE_SPARK_OPEN_26="bt-x")
    bt = BasetenEvoSpark(st)
    RoutedSpark(Stub("meta"), bt)  # installs the caps
    sent: list[dict[str, Any]] = []

    async def fake(kind, purpose, model, body, responses=False, raw=False):
        sent.append(body)
        return {"choices": [{"finish_reason": "stop", "message": {"content": '{"prompt": "ok"}'}}]}

    bt.http.call = fake  # type: ignore[method-assign]
    assert await bt.polish("p") == "ok" and sent[0]["max_tokens"] == routes()["polish"]["max_tokens"]


def test_every_call_record_names_its_provider(tmp_path, monkeypatch):
    assert _MetaClient("https://inference.baseten.co/v1", "k", 5).provider == "baseten"
    assert _MetaClient("https://api.meta.ai/v1", "k", 5).provider == "meta"
    log = tmp_path / "LIVE_LOG.md"
    monkeypatch.setenv("CHIMERA_LIVE_LOG", str(log))
    usage.record(usage.CallRecord(step="s", kind="spark_baseten", purpose="evo_polish", model="m", latency_ms=1,
                                  provider="baseten"))
    assert "| baseten/m |" in log.read_text(encoding="utf-8")


async def test_the_card_names_the_providers(engine):
    doc = await engine.fuse(sire_name="lion", dam_name="eagle")
    prov = doc["card"]["providers"]
    assert prov == doc["providers"] and prov["render"].startswith("meta:") and prov["segment"].startswith("meta:")
    assert prov["by_call"]  # mock mode: one mock entry
