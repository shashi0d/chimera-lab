"""Real Meta Model API adapters (Muse Spark vision/planning, Muse Image generation).

UNVERIFIED AGAINST THE LIVE API (see TASKSHEET P7-02). Request building and
response parsing are small pure functions at the top of this file so they can
be corrected in minutes once real responses are visible. Everything else
(HTTP, error mapping) is generic.
"""

from __future__ import annotations

import base64
import json
from typing import Any

import httpx

from app.adapters.base import GeneratedImage
from app.errors import ChimeraError
from app.models.schemas import AnimalReading, ErrorCode, FusionPlan

# ------------------------------------------------------------- request builders

IMAGE_GENERATIONS_PATH = "/images/generations"  # TO VERIFY (P7-02)
CHAT_COMPLETIONS_PATH = "/chat/completions"

READING_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["is_animal", "contains_human", "common_name", "scientific_name", "confidence",
                 "visible_parts", "body_plan", "notes"],
    "properties": {
        "is_animal": {"type": "boolean"},
        "contains_human": {"type": "boolean"},
        "common_name": {"type": ["string", "null"]},
        "scientific_name": {"type": ["string", "null"]},
        "confidence": {"type": "number"},
        "visible_parts": {"type": "array", "items": {"type": "string"}},
        "body_plan": {"type": ["string", "null"],
                      "enum": ["quadruped", "biped", "avian", "aquatic", "serpentine", "cephalopod", "insectoid", None]},
        "notes": {"type": "string"},
    },
}

PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["body_plan", "part_donors", "rationale", "name_suggestion"],
    "properties": {
        "body_plan": {"type": "string"},
        "part_donors": {
            "type": "object",
            "additionalProperties": False,
            "required": ["head", "body", "limbs", "covering", "tail"],
            "properties": {k: {"type": "string", "enum": ["A", "B"]} for k in ["head", "body", "limbs", "covering", "tail"]},
        },
        "rationale": {"type": "string"},
        "name_suggestion": {"type": ["string", "null"]},
    },
}

DESCRIBE_INSTRUCTIONS = (
    "You are a field biologist. Identify the single main animal in the photo. "
    "If there is no animal, set is_animal=false. If any human or human body part is visible, "
    "set contains_human=true and do not describe the person. List only anatomy that is actually visible."
)

PLAN_INSTRUCTIONS = (
    "You design anatomically plausible creature fusions from two real animals, A and B. "
    "Choose which parent donates each part so the result can plausibly stand, move and feed. "
    "Respect the provided rule warnings and real-hybrid facts. Keep the rationale to two sentences."
)


def _data_url(image: bytes) -> str:
    mime = "image/png" if image[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(image).decode()}"


def build_describe_request(model: str, image: bytes) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": DESCRIBE_INSTRUCTIONS},
            {"role": "user", "content": [
                {"type": "text", "text": "Describe the animal in this photo."},
                {"type": "image_url", "image_url": {"url": _data_url(image)}},
            ]},
        ],
        "response_format": {"type": "json_schema", "json_schema": {"name": "animal_reading", "strict": True, "schema": READING_SCHEMA}},
        "temperature": 0,
    }


def build_plan_request(model: str, context: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": PLAN_INSTRUCTIONS},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
        ],
        "response_format": {"type": "json_schema", "json_schema": {"name": "fusion_plan", "strict": True, "schema": PLAN_SCHEMA}},
        "temperature": 0.4,
    }


def build_generate_request(model: str, prompt: str, refs: list[bytes], aspect: str | None) -> dict[str, Any]:
    # Muse Image takes 1-10 reference images; no seed, no mask.
    body: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "reference_images": [_data_url(r) for r in refs[:10]],
        "n": 1,
        "response_format": "b64_json",
    }
    if aspect:
        body["aspect_ratio"] = aspect
    return body


# ------------------------------------------------------------- response parsers


def _message_json(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        choice = payload["choices"][0]
        if choice.get("finish_reason") == "content_filter":
            raise ChimeraError(ErrorCode.MODEL_REFUSED, "The model declined to read this image.")
        content = choice["message"]["content"]
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content)
        return json.loads(content)
    except ChimeraError:
        raise
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise ChimeraError(ErrorCode.UPSTREAM_ERROR, "The model returned an unreadable answer.") from exc


def parse_describe_response(payload: dict[str, Any]) -> AnimalReading:
    return AnimalReading.model_validate(_message_json(payload))


def parse_plan_response(payload: dict[str, Any]) -> FusionPlan:
    return FusionPlan.model_validate(_message_json(payload))


def parse_generate_response(payload: dict[str, Any], model: str) -> GeneratedImage:
    try:
        item = payload["data"][0]
    except (KeyError, IndexError, TypeError) as exc:
        raise ChimeraError(ErrorCode.UPSTREAM_ERROR, "The image model returned no image.") from exc
    if item.get("revised_prompt") is None and item.get("refusal"):
        raise ChimeraError(ErrorCode.MODEL_REFUSED, "The image model declined this request.")
    b64 = item.get("b64_json")
    if not b64:
        raise ChimeraError(ErrorCode.UPSTREAM_ERROR, "The image model returned no image data.")
    data = base64.b64decode(b64)
    mime = "image/png" if data[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"
    return GeneratedImage(data=data, content_type=mime, model=model)


def map_http_error(status: int, body: dict[str, Any] | None, headers: httpx.Headers) -> ChimeraError:
    err = (body or {}).get("error") or {}
    code = str(err.get("code") or err.get("type") or "").lower()
    if status == 429:
        retry_after = headers.get("retry-after")
        ms = int(float(retry_after) * 1000) if retry_after and retry_after.replace(".", "").isdigit() else 4000
        return ChimeraError(ErrorCode.RATE_LIMITED, retry_after_ms=ms)
    if status in (408, 504):
        return ChimeraError(ErrorCode.UPSTREAM_TIMEOUT)
    if status == 400 and ("safety" in code or "content_policy" in code or "refus" in code):
        return ChimeraError(ErrorCode.MODEL_REFUSED, "The image model declined this request.")
    if status in (401, 403):
        return ChimeraError(ErrorCode.UPSTREAM_ERROR, "Model API credentials were rejected.", retryable=False)
    return ChimeraError(ErrorCode.UPSTREAM_ERROR)


# ------------------------------------------------------------- adapters


class _MetaHttp:
    def __init__(self, base_url: str, api_key: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    async def post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    self.base_url + path, json=body, headers={"Authorization": f"Bearer {self.api_key}"}
                )
        except httpx.TimeoutException as exc:
            raise ChimeraError(ErrorCode.UPSTREAM_TIMEOUT) from exc
        except httpx.HTTPError as exc:
            raise ChimeraError(ErrorCode.UPSTREAM_ERROR) from exc
        try:
            payload = resp.json()
        except ValueError:
            payload = None
        if resp.status_code >= 400:
            raise map_http_error(resp.status_code, payload, resp.headers)
        if not isinstance(payload, dict):
            raise ChimeraError(ErrorCode.UPSTREAM_ERROR)
        return payload


class MetaVision:
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 30.0) -> None:
        self.http = _MetaHttp(base_url, api_key, timeout)
        self.model_id = model

    async def describe_animal(self, image: bytes, slot: str) -> AnimalReading:
        payload = await self.http.post(CHAT_COMPLETIONS_PATH, build_describe_request(self.model_id, image))
        return parse_describe_response(payload)

    async def plan_fusion(self, context: dict[str, Any]) -> FusionPlan:
        payload = await self.http.post(CHAT_COMPLETIONS_PATH, build_plan_request(self.model_id, context))
        return parse_plan_response(payload)


class MetaImageGen:
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 120.0) -> None:
        self.http = _MetaHttp(base_url, api_key, timeout)
        self.model_id = model

    async def generate(self, prompt: str, reference_images: list[bytes], aspect: str | None) -> GeneratedImage:
        payload = await self.http.post(
            IMAGE_GENERATIONS_PATH, build_generate_request(self.model_id, prompt, reference_images, aspect)
        )
        return parse_generate_response(payload, self.model_id)
