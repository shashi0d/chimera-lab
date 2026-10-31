"""E2 live adapters, exercised in mock mode: no network call is made here.

Request builders and parsers are pure; the engine wiring is tested with a fake
_MetaClient.call so the guard/record path is the real one.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from app.adapters import usage
from app.adapters.base import GeneratedImage
from app.adapters.mock.recorded import chat_payload
from app.errors import ChimeraError
from app.evolution import live
from app.evolution.adapters import swatch
from app.evolution.engine import EvoEngine
from app.evolution.genome import Genome, validate_plan
from app.evolution.judge import mask_stats, silhouette_score
from app.models.schemas import ErrorCode
from app.services import build_services
from tests.conftest import make_settings
from tests.evolution.conftest import plan_for


def test_plan_schema_covers_every_model_field():
    model_fields = set(Genome.model_fields) - set(live.CODE_FIELDS)
    assert set(live.PLAN_SCHEMA["properties"]) == model_fields
    assert set(live.PLAN_SCHEMA["required"]) == model_fields
    assert "$ref" not in json.dumps(live.PLAN_SCHEMA)  # Muse Spark: no recursive $ref


def test_plan_round_trip_keeps_code_fields(engine):
    g, _ = plan_for(engine, "lion", "eagle")
    skeleton = g.model_dump()
    model_side = {k: v for k, v in skeleton.items() if k not in live.CODE_FIELDS}
    model_side["silhouette"] = "a lion frame with eagle wings"
    out = live.parse_plan_response(chat_payload("plan", model_side), {**skeleton, "seed": 7})
    plan = validate_plan({**out, "id": "pending"})
    assert plan.silhouette == "a lion frame with eagle wings" and plan.seed == 7 and plan.lineage == g.lineage


def test_request_builders():
    img = swatch("lion")
    body = live.build_critic_request("muse-spark-1.3", img)
    assert body["messages"][1]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert body["response_format"]["json_schema"]["strict"] is True
    sam = live.build_sam_request(img, "animal")
    assert sam["model"] == "sam-3.1"
    parts = sam["input"][0]["content"]
    assert parts[0] == {"type": "input_text", "text": "animal"}
    assert parts[1]["type"] == "input_image" and parts[1]["image_url"].startswith("data:image/png;base64,")
    assert live.build_polish_request("m", "x")["messages"][1]["content"] == "x"


def test_critic_and_polish_parsers():
    c = live.parse_critic_response(chat_payload("describe", {"animals": ["lion", "eagle"], "creatures": 1, "notes": "n"}))
    assert c == {"animals": ["lion", "eagle"], "creatures": 1, "notes": "n"}
    assert live.parse_polish_response(chat_payload("plan", {"prompt": "Silhouette: x."})) == "Silhouette: x."


def test_sam_budget_kind(tmp_path, monkeypatch):
    monkeypatch.setenv("CHIMERA_LIVE_BUDGET_FILE", str(tmp_path / "budget.json"))
    monkeypatch.setenv("CHIMERA_LIVE_MAX_SAM", "2")
    usage.guard("sam")
    usage.guard("sam")
    with pytest.raises(ChimeraError) as e:
        usage.guard("sam")
    assert e.value.code == ErrorCode.BUDGET_EXCEEDED
    assert usage.budget_used() == {"image": 0, "spark": 0, "sam": 2}


def test_real_mode_builds_live_adapters(tmp_path):
    eng = EvoEngine(build_services(make_settings(tmp_path, chimera_mode="real", meta_api_key="k-test")))
    assert isinstance(eng.spark, live.LiveEvoSpark)
    assert isinstance(eng.segmenter, live.MetaSegmenter) and eng.segmenter.model_id == "sam-3.1"
    assert isinstance(eng.renderer, live.RetryingImageGen)
    assert eng.live_error is None


async def test_live_vary_refuses(tmp_path):
    with pytest.raises(ChimeraError):
        await live.LiveEvoSpark(make_settings(tmp_path, meta_api_key="k")).vary("p", [], 1, 0)


async def test_retrying_image_gen_retries_a_timeout(tmp_path):
    calls: list[int] = []

    class Flaky:
        model_id = "flaky"

        async def generate(self, *a: Any, **k: Any) -> GeneratedImage:
            calls.append(1)
            if len(calls) == 1:
                raise ChimeraError(ErrorCode.UPSTREAM_TIMEOUT)
            return GeneratedImage(data=b"x", content_type="image/png", model="flaky")

    out = await live.RetryingImageGen(Flaky(), make_settings(tmp_path)).generate("p", [], "1:1")  # type: ignore[arg-type]
    assert out.data == b"x" and len(calls) == 2


async def test_failed_first_plan_call_falls_back_to_skeleton(engine):
    async def boom(prompt: str, skeleton: dict[str, Any]) -> dict[str, Any]:
        raise ChimeraError(ErrorCode.UPSTREAM_ERROR, "The model returned an unreadable answer.")

    engine.spark.write_plan = boom  # type: ignore[method-assign]
    doc = await engine.fuse(sire_name="lion", dam_name="tiger")
    assert doc["model_plan"].startswith("call failed, code skeleton used (UPSTREAM_ERROR")
    assert doc["genome"]["known_pair"] == "liger"


async def test_budget_error_on_first_plan_is_not_swallowed(engine):
    async def broke(prompt: str, skeleton: dict[str, Any]) -> dict[str, Any]:
        raise ChimeraError(ErrorCode.BUDGET_EXCEEDED, retryable=False)

    engine.spark.write_plan = broke  # type: ignore[method-assign]
    with pytest.raises(ChimeraError) as e:
        await engine.fuse(sire_name="lion", dam_name="tiger")
    assert e.value.code == ErrorCode.BUDGET_EXCEEDED


# ------------------------------------------------------------------ SAM 3.1 (recorded probe, E2 step 3)

SAM_RECORDING = Path(__file__).resolve().parents[1] / "fixtures" / "recorded" / "sam-01.json"


def _sam_payload() -> dict[str, Any]:
    return json.loads(SAM_RECORDING.read_text(encoding="utf-8"))["response"]


def test_sam_recording_decodes_to_one_full_frame_silhouette():
    mask = live.parse_sam_response(_sam_payload(), 1600, 1600)
    with Image.open(io.BytesIO(mask)) as im:
        assert im.size == (1600, 1600) and im.mode == "L"
        assert im.getbbox() == (116, 97, 1477, 1509)  # the box token, in source pixels
    stats = mask_stats(mask)
    assert stats["components"] == 1
    assert 0.15 < stats["fill"] < 0.3  # a standing donkey, legs apart
    assert 0.9 < stats["aspect"] < 1.05
    assert silhouette_score(stats, "quadruped") < 1.0  # square-ish box: below the quadruped aspect band


def test_sam_text_and_empty_and_incomplete_responses():
    payload = _sam_payload()
    assert live.sam_text(payload).startswith("<0f>0<|box;")
    empty = {**payload, "output": [{"type": "message", "content": [{"type": "output_text", "text": ""}]}]}
    with Image.open(io.BytesIO(live.parse_sam_response(empty, 64, 64))) as im:
        assert im.getbbox() is None
    with pytest.raises(ChimeraError):
        live.sam_text({**payload, "status": "incomplete"})


async def test_meta_segmenter_parses_the_recorded_call(tmp_path, monkeypatch):
    seg = live.MetaSegmenter(make_settings(tmp_path, meta_api_key="k"))
    sent: list[dict[str, Any]] = []

    async def fake_call(kind, purpose, model, body, responses=False, raw=False):
        sent.append({"kind": kind, "model": model, "responses": responses, "raw": raw, "body": body})
        return _sam_payload()

    monkeypatch.setattr(seg.http, "call", fake_call)
    image = Image.new("RGB", (1600, 1600), "white")
    buf = io.BytesIO()
    image.save(buf, "PNG")
    mask = await seg.segment(buf.getvalue(), "animal")
    assert mask_stats(mask)["components"] == 1
    assert sent[0]["kind"] == "sam" and sent[0]["model"] == "sam-3.1" and sent[0]["raw"] and sent[0]["responses"]
