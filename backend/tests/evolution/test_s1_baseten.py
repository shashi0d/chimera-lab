"""S1 part 1: the Baseten (Muse Spark Open) adapter behind the existing EvoSpark interface.

No network: the attempt wrapper is replaced by a stub, so these tests check the wiring (endpoint, model,
budget kind, retries, redaction), not the provider."""

from __future__ import annotations

import json

import pytest

from app.adapters.baseten.client import KIND, BasetenEvoSpark
from app.adapters.meta import client as meta_client
from app.adapters.usage import budget_used, guard
from app.config import Settings
from app.errors import ChimeraError
from app.evolution.adapters import EvoSpark
from app.models.schemas import ErrorCode

KEY_ENV = "BASETEN_API_KEY_MODEL_MUSE_SPARK_OPEN_26"


def _settings(**kw) -> Settings:
    return Settings(_env_file=None, retry_base_seconds=0.0, **{KEY_ENV: "bt-test-key-123", **kw})


class StubHttp:
    def __init__(self, payloads):
        self.payloads, self.calls = list(payloads), []

    async def call(self, kind, purpose, model, body, responses=False, raw=False):
        self.calls.append({"kind": kind, "purpose": purpose, "model": model, "body": body})
        p = self.payloads.pop(0)
        if isinstance(p, Exception):
            raise p
        return p


def _chat(content: dict) -> dict:
    return {"id": "x", "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(content)}}]}


def test_settings_read_the_baseten_key_by_its_env_name(monkeypatch):
    monkeypatch.setenv(KEY_ENV, "bt-from-env")
    s = Settings(_env_file=None)
    assert s.baseten_api_key == "bt-from-env"
    assert s.baseten_base_url == "https://inference.baseten.co/v1"
    assert s.baseten_spark_model == "meta-models/muse-spark-open-1026"


def test_adapter_targets_baseten_with_the_exact_model():
    a = BasetenEvoSpark(_settings())
    assert a.model_id == "meta-models/muse-spark-open-1026" and a.kind == KIND == "spark_baseten"
    assert str(a.http.client.base_url).rstrip("/") == "https://inference.baseten.co/v1"
    assert a.http.client.max_retries == 0  # call_with_retry is the only retry layer
    assert a.timeout == 300.0 and a.http.client.timeout == 300.0  # S1: plans need minutes, not 60 s
    missing = [m for m in ("write_plan", "vary", "polish", "critic", "checklist", "identify", "learn_traits",
                           "judge_functions") if not callable(getattr(a, m, None))]
    assert not missing and set(EvoSpark.__annotations__) <= set(dir(a))


def test_adapter_refuses_without_a_key(monkeypatch):
    monkeypatch.delenv(KEY_ENV, raising=False)
    with pytest.raises(RuntimeError, match=KEY_ENV):
        BasetenEvoSpark(Settings(_env_file=None))


@pytest.mark.parametrize("method,args,content,purpose", [
    ("polish", ("a prompt",), {"prompt": "a prompt"}, "evo_polish"),
    ("identify", ("axolotl",), {"kind": "species", "scientific_name": "Ambystoma mexicanum",
                               "common_name": "axolotl", "breed": "", "alternatives": [], "note": ""}, "evo_identify"),
])
async def test_spark_interface_calls_count_as_spark_baseten(method, args, content, purpose):
    a = BasetenEvoSpark(_settings())
    a.http = StubHttp([_chat(content)])
    await getattr(a, method)(*args)
    call = a.http.calls[0]
    assert call["kind"] == "spark_baseten" and call["purpose"] == purpose
    assert call["model"] == call["body"]["model"] == "meta-models/muse-spark-open-1026"


async def test_retryable_errors_retry_through_the_shared_policy():
    a = BasetenEvoSpark(_settings())
    a.http = StubHttp([ChimeraError(ErrorCode.UPSTREAM_ERROR), _chat({"prompt": "ok"})])
    assert await a.polish("p") == "ok" and len(a.http.calls) == 2


async def test_raw_chat_forces_the_configured_model():
    a = BasetenEvoSpark(_settings())
    a.http = StubHttp([{"choices": []}])
    await a.chat("probe_tools", {"model": "some-other-model", "messages": []}, retry=False)
    assert a.http.calls[0]["body"]["model"] == "meta-models/muse-spark-open-1026"


def test_budget_kind_has_its_own_cap(tmp_path, monkeypatch):
    monkeypatch.setenv("CHIMERA_LIVE_BUDGET_FILE", str(tmp_path / "b.json"))
    monkeypatch.setenv("CHIMERA_LIVE_MAX_SPARK_BASETEN", "2")
    monkeypatch.setenv("CHIMERA_LIVE_MAX_SPARK", "0")
    guard("spark_baseten")
    guard("spark_baseten")
    with pytest.raises(ChimeraError) as e:
        guard("spark_baseten")
    assert e.value.code == ErrorCode.BUDGET_EXCEEDED
    assert budget_used() == {"image": 0, "spark": 0, "sam": 0, "spark_baseten": 2}


def test_default_baseten_cap_is_300(tmp_path, monkeypatch):
    from app.adapters.usage import _limits

    monkeypatch.delenv("CHIMERA_LIVE_MAX_SPARK_BASETEN", raising=False)
    assert _limits()["spark_baseten"] == 300


def test_recordings_refuse_the_baseten_key(tmp_path, monkeypatch):
    monkeypatch.setenv("CHIMERA_RECORD_DIR", str(tmp_path))
    monkeypatch.setenv(KEY_ENV, "bt-secret-value-xyz")
    with pytest.raises(RuntimeError, match="credentials"):
        meta_client.save_recording("probe", {"note": "bt-secret-value-xyz"}, {})
    meta_client.save_recording("probe", {"note": "clean"}, {})
    assert (tmp_path / "probe-01.json").exists()


def test_baseten_is_built_only_by_the_live_router():
    # S1 kept it unused; S2 routes per call type, built in one place (live.build_live).
    from pathlib import Path

    app = Path(__file__).resolve().parents[2] / "app"
    users = sorted(p.name for p in app.rglob("*.py") if "BasetenEvoSpark" in p.read_text(encoding="utf-8"))
    assert users == ["client.py", "live.py"]
