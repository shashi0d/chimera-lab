"""Recorded-shape fake responses for the real Meta adapters (unverified against live API)."""

import base64
import json

import httpx
import pytest

from app.adapters.meta import client as meta
from app.errors import ChimeraError
from app.models.schemas import ErrorCode
from tests.conftest import FIXTURES, IMAGES

LIVE = FIXTURES / "live"
RECORDED = FIXTURES / "recorded"


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


def test_generate_request_uses_responses_input_parts():
    img = (IMAGES / "lion.jpg").read_bytes()
    body = meta.build_generate_request("muse-image-1.0", "p", [img] * 12, "1:1")
    assert set(body) == {"model", "input"}
    msg = body["input"][0]
    assert msg["role"] == "user"
    parts = msg["content"]
    assert parts[0]["type"] == "input_text" and "1:1" in parts[0]["text"]
    assert len(parts) == 11 and all(p["type"] == "input_image" for p in parts[1:])
    assert parts[1]["image_url"].startswith("data:image/jpeg;base64,")
    # refinement turn: previous_response_id plus only the new instruction
    edit = meta.build_generate_request("muse-image-1.0", "make the mane darker", [img], None, previous_response_id="resp_1")
    assert edit["previous_response_id"] == "resp_1" and len(edit["input"][0]["content"]) == 1


def test_generate_response_takes_the_image_generation_call():
    webp = (LIVE / "lion.webp").read_bytes()
    recorded = json.loads((RECORDED / "text_to_image-01.json").read_text())["response"]
    recorded["output"] = [dict(i) for i in recorded["output"]]
    call = next(i for i in recorded["output"] if i["type"] == "image_generation_call")
    call["result"] = base64.b64encode(webp).decode()
    out = meta.parse_generate_response(recorded, "muse-image-1.0")
    assert out.content_type == "image/webp" and out.data == webp
    assert out.response_id == recorded["id"] and out.usage["total_tokens"] > 0
    with pytest.raises(ChimeraError) as e:
        meta.parse_generate_response({"output": [{"type": "message", "content": [{"text": "Sorry, I can't make that."}]}]}, "m")
    assert e.value.code == ErrorCode.MODEL_REFUSED
    with pytest.raises(ChimeraError) as e:
        meta.parse_generate_response({"output": []}, "m")
    assert e.value.code == ErrorCode.UPSTREAM_ERROR


def test_magic_bytes():
    assert meta.image_mime(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "image/webp"
    assert meta.image_mime(b"\x89PNG\r\n\x1a\n....") == "image/png"
    assert meta.image_mime(b"\xff\xd8\xff\xe0") == "image/jpeg"
    with pytest.raises(ChimeraError):
        meta.image_mime(b"GIF89a")


@pytest.mark.parametrize("status,body,headers,code", [
    (429, {}, {"retry-after": "3"}, ErrorCode.RATE_LIMITED),
    (504, {}, {}, ErrorCode.UPSTREAM_TIMEOUT),
    (400, {"error": {"code": "content_policy_violation"}}, {}, ErrorCode.MODEL_REFUSED),
    (500, None, {}, ErrorCode.UPSTREAM_ERROR),
    (503, None, {}, ErrorCode.UPSTREAM_ERROR),
    (401, {}, {}, ErrorCode.UPSTREAM_ERROR),
    (404, {}, {}, ErrorCode.UPSTREAM_ERROR),
    (400, {"error": {"message": "bad schema"}}, {}, ErrorCode.UPSTREAM_ERROR),
])
def test_http_error_mapping(status, body, headers, code):
    err = meta.map_http_error(status, body, httpx.Headers(headers))
    assert err.code == code
    if status == 429:
        assert err.retry_after_ms == 3000
    # L1-03: 429/5xx/timeouts retry; 400/401/404 never do
    assert err.retryable is (status in (429, 500, 503, 504))
