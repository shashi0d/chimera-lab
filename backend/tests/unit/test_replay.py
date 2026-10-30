"""L1-09: mocks replay the recorded live response shapes through the real parsers."""

import json

from app.adapters.meta import client as meta
from app.adapters.mock.recorded import RECORDED, chat_payload, responses_payload
from app.models.schemas import ErrorCode
from tests.conftest import FIXTURES


def test_recordings_exist_and_hold_no_credentials():
    files = sorted(RECORDED.glob("*.json"))
    kinds = {f.name.rsplit("-", 1)[0] for f in files}
    assert {"describe", "plan", "generate", "text_to_image"} <= kinds
    for f in files:
        text = f.read_text()
        assert "Bearer " not in text and "Authorization" not in text and "api_key" not in text.lower()
        data = json.loads(text)
        assert set(data) == {"purpose", "request", "response"}


def test_recorded_generate_shape_interleaves_reasoning_message_and_image():
    resp = json.loads((RECORDED / "generate-01.json").read_text())["response"]
    assert [i["type"] for i in resp["output"]] == ["reasoning", "message", "image_generation_call"]
    assert resp["id"].startswith("resp_") and resp["usage"]["total_tokens"] > 0
    req = json.loads((RECORDED / "generate-01.json").read_text())["request"]
    parts = req["input"][0]["content"]
    assert parts[0]["type"] == "input_text" and [p["type"] for p in parts[1:]] == ["input_image", "input_image"]


def test_chat_replay_parses_like_live():
    payload = chat_payload("describe", {"is_animal": True, "contains_human": False, "common_name": "Lion",
                                        "scientific_name": "Panthera leo", "confidence": 0.9, "visible_parts": [],
                                        "body_plan": "quadruped", "notes": ""})
    assert payload["object"] == "chat.completion" and payload["model"] == "muse-spark-1.3"
    assert meta.parse_describe_response(payload).scientific_name == "Panthera leo"


def test_responses_replay_round_trip_and_refusal():
    webp = next((FIXTURES / "live").glob("lion.*")).read_bytes()
    out = meta.parse_generate_response(responses_payload(webp), "muse-image-1.0")
    assert out.data == webp and out.content_type == "image/webp" and out.response_id.startswith("resp-mock-")
    try:
        meta.parse_generate_response(responses_payload(None, "Sorry, I can't create that image."), "m")
    except meta.ChimeraError as e:
        assert e.code == ErrorCode.MODEL_REFUSED
    else:
        raise AssertionError("refusal not detected")
