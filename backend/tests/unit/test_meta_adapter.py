"""Recorded-shape fake responses for the real Meta adapters (unverified against live API)."""

import base64
import json

import httpx
import pytest
from app.adapters.meta import client as meta
from app.errors import ChimeraError
from app.models.schemas import ErrorCode
from tests.conftest import IMAGES


def chat(content, finish="stop"):
    return {"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": finish}]}


def test_describe_request_carries_image_and_schema():
    body = meta.build_describe_request("muse-spark-x", b"\xff\xd8\xff" + b"0" * 10)
    assert body["model"] == "muse-spark-x"
    parts = body["messages"][1]["content"]
    assert parts[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert body["response_format"]["json_schema"]["strict"] is True


def test_parse_describe_response():
    reading = {"is_animal": True, "contains_human": False, "common_name": "Lion", "scientific_name": "Panthera leo",
               "confidence": 0.94, "visible_parts": ["head", "mane"], "body_plan": "quadruped", "notes": ""}
    r = meta.parse_describe_response(chat(json.dumps(reading)))
    assert r.common_name == "Lion" and r.is_animal


def test_parse_handles_content_parts_and_garbage():
    r = meta.parse_plan_response(chat([{"type": "text", "text": json.dumps({
        "body_plan": "avian", "part_donors": {"head": "A", "body": "B", "limbs": "B", "covering": "A", "tail": "B"},
        "rationale": "x", "name_suggestion": None})}]))
    assert r.part_donors.tail == "B"
    with pytest.raises(ChimeraError) as e:
        meta.parse_describe_response(chat("not json"))
    assert e.value.code == ErrorCode.UPSTREAM_ERROR
    with pytest.raises(ChimeraError) as e:
        meta.parse_describe_response(chat("{}", finish="content_filter"))
    assert e.value.code == ErrorCode.MODEL_REFUSED


def test_generate_request_and_response():
    img = (IMAGES / "lion.jpg").read_bytes()
    body = meta.build_generate_request("muse-image-x", "p", [img] * 12, "1:1")
    assert len(body["reference_images"]) == 10 and body["aspect_ratio"] == "1:1"
    out = meta.parse_generate_response({"data": [{"b64_json": base64.b64encode(img).decode()}]}, "m")
    assert out.content_type == "image/jpeg" and out.data == img
    with pytest.raises(ChimeraError):
        meta.parse_generate_response({"data": []}, "m")


@pytest.mark.parametrize("status,body,headers,code", [
    (429, {}, {"retry-after": "3"}, ErrorCode.RATE_LIMITED),
    (504, {}, {}, ErrorCode.UPSTREAM_TIMEOUT),
    (400, {"error": {"code": "content_policy_violation"}}, {}, ErrorCode.MODEL_REFUSED),
    (500, None, {}, ErrorCode.UPSTREAM_ERROR),
    (401, {}, {}, ErrorCode.UPSTREAM_ERROR),
])
def test_http_error_mapping(status, body, headers, code):
    err = meta.map_http_error(status, body, httpx.Headers(headers))
    assert err.code == code
    if status == 429:
        assert err.retry_after_ms == 3000
    if status == 401:
        assert err.retryable is False
