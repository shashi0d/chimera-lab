"""Real Meta Model API adapters (L1).

* Muse Spark (``muse-spark-1.3``): vision, planning and card writing via chat
  completions, images as ``image_url`` data URLs, structured output via
  ``response_format = {"type": "json_schema", ...}`` (no recursive $ref).
* Muse Image (``muse-image-1.0``): the Responses API (``client.responses.create``),
  reference images as ``input_image`` parts inside one user message; the image is
  the ``image_generation_call`` item's base64 ``result`` (WebP). A refinement turn
  passes ``previous_response_id`` plus only the new instruction.

Request builders and response parsers are small pure functions working on plain
dicts (``response.model_dump()``), so the recorded live responses in
``backend/tests/fixtures/recorded/`` exercise exactly the same parsing code in
mock mode (L1-09). The OpenAI SDK's own retries are disabled: the shared policy
in ``pipeline/retry.py`` is the only retry layer (L1-03), and every attempt is
counted by the spend guard and the live budget.
"""

from __future__ import annotations

import asyncio
import base64
import json
from typing import Any

import httpx

from app.adapters.base import GeneratedImage
from app.adapters.usage import CallKind, CallRecord, Timer, current_step, guard, record, tokens_of
from app.errors import ChimeraError
from app.models.schemas import AnimalReading, ErrorCode, FieldCard, FusionPlan

# ------------------------------------------------------------- formats


def image_mime(data: bytes) -> str:
    """Detect WebP, PNG and JPEG by magic bytes (Muse Image returns WebP)."""
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    raise ChimeraError(ErrorCode.UPSTREAM_ERROR, "The image model returned an unknown image format.")


def _data_url(image: bytes) -> str:
    return f"data:{image_mime(image)};base64,{base64.b64encode(image).decode()}"


# ------------------------------------------------------------- schemas and instructions

# The real data's body plans (chimera_data.json definitions), so readings match the data (R-A1-01).
BODY_PLANS = ["quadruped", "biped", "winged", "finned", "multi_legged", "serpentine", "radial"]

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
        "body_plan": {"type": ["string", "null"], "enum": [*BODY_PLANS, None]},
        "notes": {"type": "string"},
    },
}

PARTS = ["head", "body", "limbs", "covering", "tail"]

PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["creature_name", "body_plan", "part_donors", "rationale"],
    "properties": {
        "creature_name": {"type": "string"},
        "body_plan": {"type": "string"},
        "part_donors": {
            "type": "object",
            "additionalProperties": False,
            "required": PARTS,
            "properties": {k: {"type": "string", "enum": ["A", "B"]} for k in PARTS},
        },
        "rationale": {"type": "string"},
    },
}

CARD_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["common_name", "binomial", "habitat", "diet", "size", "behaviour"],
    "properties": {k: {"type": "string"} for k in ["common_name", "binomial", "habitat", "diet", "size", "behaviour"]},
}

DESCRIBE_INSTRUCTIONS = (
    "You are a field biologist. Identify the single main animal in the photo: its everyday English common name "
    "and its Latin binomial (genus species, the standard accepted name). If there is no animal, set is_animal=false. "
    "If any human or human body part is visible, set contains_human=true and do not describe the person. "
    "List only anatomy that is actually visible. body_plan is one of: " + ", ".join(BODY_PLANS) + "."
)

PLAN_INSTRUCTIONS = (
    "You design anatomically plausible creature fusions from two real animals, A and B. Choose which parent donates "
    "each part (head, body, limbs, covering, tail) so the result can plausibly stand, move and feed. Any part in "
    "donor_pins is fixed by the user: keep it exactly. body_plan must be exactly one value from allowed_body_plans. "
    "Respect the rule warnings and real-hybrid facts provided. Keep the rationale to two sentences. "
    "creature_name: an evocative common name of two or three words, as a field guide would print it. "
    "Do not glue the parents' names together (no portmanteaus like 'Liger' or 'Lioiger')."
)

CARD_INSTRUCTIONS = (
    "Write a natural-history field-guide entry for an INVENTED creature fused from two real animals. "
    "Invent a Latinate binomial. Base habitat and diet only on the parents' data provided. For size, quote "
    "the parents' recorded ranges exactly as given and do not compute averages or midpoints. Two sentences "
    "of behaviour at most. Never claim the creature exists."
)

# ------------------------------------------------------------- request builders (pure)


def _json_schema(name: str, schema: dict[str, Any]) -> dict[str, Any]:
    return {"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": schema}}


def build_describe_request(model: str, image: bytes) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": DESCRIBE_INSTRUCTIONS},
            {"role": "user", "content": [
                {"type": "text", "text": "Identify the animal in this photo."},
                {"type": "image_url", "image_url": {"url": _data_url(image)}},
            ]},
        ],
        "response_format": _json_schema("animal_reading", READING_SCHEMA),
        "temperature": 0,
    }


def build_plan_request(model: str, context: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": PLAN_INSTRUCTIONS},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
        ],
        "response_format": _json_schema("fusion_plan", PLAN_SCHEMA),
        "temperature": 0.4,
    }


def build_card_request(model: str, context: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": CARD_INSTRUCTIONS},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
        ],
        "response_format": _json_schema("field_card", CARD_SCHEMA),
        "temperature": 0.6,
    }


def build_generate_request(
    model: str, prompt: str, refs: list[bytes], aspect: str | None, previous_response_id: str | None = None
) -> dict[str, Any]:
    """Responses API body. References go as input_image parts inside one user message
    (a bare list of parts is rejected). With previous_response_id, send only the new instruction."""
    text = prompt if not aspect else f"{prompt}\nAspect ratio: {aspect}."
    content: list[dict[str, Any]] = [{"type": "input_text", "text": text}]
    if previous_response_id is None:
        content += [{"type": "input_image", "image_url": _data_url(r)} for r in refs[:10]]
    body: dict[str, Any] = {"model": model, "input": [{"role": "user", "content": content}]}
    if previous_response_id:
        body["previous_response_id"] = previous_response_id
    return body


# ------------------------------------------------------------- response parsers (pure)


def _message_json(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        choice = payload["choices"][0]
        if choice.get("finish_reason") == "content_filter":
            raise ChimeraError(ErrorCode.MODEL_REFUSED, "The model declined to read this image.")
        message = choice["message"]
        if message.get("refusal"):
            raise ChimeraError(ErrorCode.MODEL_REFUSED, "The model declined this request.")
        content = message["content"]
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
    data = _message_json(payload)
    if "creature_name" in data:  # L1-10: the plan names the creature
        data["name_suggestion"] = data.pop("creature_name")
    return FusionPlan.model_validate(data)


def parse_card_response(payload: dict[str, Any]) -> FieldCard:
    return FieldCard.model_validate(_message_json(payload))


def parse_generate_response(payload: dict[str, Any], model: str) -> GeneratedImage:
    """Take the image_generation_call item from the interleaved output list and decode its result."""
    output = payload.get("output") or []
    call = next((i for i in output if isinstance(i, dict) and i.get("type") == "image_generation_call"), None)
    if call is None or not call.get("result"):
        text = " ".join(
            c.get("text", "") for i in output if isinstance(i, dict) and i.get("type") == "message"
            for c in (i.get("content") or []) if isinstance(c, dict)
        ).lower()
        if any(w in text for w in ("can't", "cannot", "unable", "not able", "won't", "policy", "sorry")):
            raise ChimeraError(ErrorCode.MODEL_REFUSED, "The image model declined this request.")
        raise ChimeraError(ErrorCode.UPSTREAM_ERROR, "The image model returned no image.")
    try:
        data = base64.b64decode(call["result"])
    except (ValueError, TypeError) as exc:
        raise ChimeraError(ErrorCode.UPSTREAM_ERROR, "The image model returned undecodable image data.") from exc
    return GeneratedImage(data=data, content_type=image_mime(data), model=model,
                          response_id=payload.get("id"), usage=payload.get("usage") or {})


# ------------------------------------------------------------- error mapping (L1-03)


def map_http_error(status: int, body: dict[str, Any] | None, headers: httpx.Headers) -> ChimeraError:
    """429, 5xx (and timeouts) are retryable; 400/401/403/404 never are."""
    err = (body or {}).get("error") or {}
    code = str(err.get("code") or err.get("type") or "").lower() if isinstance(err, dict) else ""
    message = str(err.get("message") or "").lower() if isinstance(err, dict) else ""
    if status == 429:
        retry_after = headers.get("retry-after")
        ms = int(float(retry_after) * 1000) if retry_after and retry_after.replace(".", "").isdigit() else 4000
        return ChimeraError(ErrorCode.RATE_LIMITED, retry_after_ms=ms)
    if status in (408, 504):
        return ChimeraError(ErrorCode.UPSTREAM_TIMEOUT)
    if status >= 500:
        return ChimeraError(ErrorCode.UPSTREAM_ERROR)
    if status == 400 and any(w in code + " " + message for w in ("safety", "content_policy", "refus", "moderation")):
        return ChimeraError(ErrorCode.MODEL_REFUSED, "The image model declined this request.")
    if status in (401, 403):
        return ChimeraError(ErrorCode.UPSTREAM_ERROR, "Model API credentials were rejected.", retryable=False)
    return ChimeraError(ErrorCode.UPSTREAM_ERROR, "The model API rejected the request.", retryable=False)


def map_sdk_error(exc: Exception) -> ChimeraError:
    import openai

    if isinstance(exc, openai.APITimeoutError):
        return ChimeraError(ErrorCode.UPSTREAM_TIMEOUT)
    if isinstance(exc, openai.APIConnectionError):
        return ChimeraError(ErrorCode.UPSTREAM_ERROR)  # retryable
    if isinstance(exc, openai.APIStatusError):
        try:
            body = exc.response.json()
        except ValueError:
            body = None
        return map_http_error(exc.status_code, body, exc.response.headers)
    return ChimeraError(ErrorCode.UPSTREAM_ERROR)


# ------------------------------------------------------------- record and replay (L1-09)

ELIDED = "<elided>"


def _elide(obj: Any) -> Any:
    """Drop bulky base64 (data URLs, image results) but keep the structure and its size."""
    if isinstance(obj, dict):
        return {k: _elide(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_elide(v) for v in obj]
    if isinstance(obj, str) and (obj.startswith("data:image/") or len(obj) > 4000):
        return f"{ELIDED} ({len(obj)} chars)"
    return obj


def save_recording(purpose: str, request: dict[str, Any], payload: dict[str, Any]) -> None:
    """When CHIMERA_RECORD_DIR is set, save the live request/response pair as a JSON fixture.
    Refuses to write anything that contains the API key."""
    import os
    from pathlib import Path

    folder = os.environ.get("CHIMERA_RECORD_DIR")
    if not folder:
        return
    text = json.dumps({"purpose": purpose, "request": _elide(request), "response": _elide(payload)}, indent=1,
                      ensure_ascii=False, default=str)
    key = os.environ.get("META_API_KEY") or ""
    if (key and key in text) or "Bearer " in text or "Authorization" in text:
        raise RuntimeError("refusing to save a recording that contains credentials")
    path = Path(folder)
    path.mkdir(parents=True, exist_ok=True)
    n = len(list(path.glob(f"{purpose}-*.json"))) + 1
    (path / f"{purpose}-{n:02d}.json").write_text(text + "\n", encoding="utf-8")


# ------------------------------------------------------------- adapters


class _MetaClient:
    def __init__(self, base_url: str, api_key: str, timeout: float) -> None:
        import openai

        # The SDK does not read our key from the environment by itself: pass it explicitly.
        self.client = openai.AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=timeout, max_retries=0)

    async def call(self, kind: CallKind, purpose: str, model: str, body: dict[str, Any], responses: bool = False) -> dict[str, Any]:
        guard(kind)
        payload: dict[str, Any] | None = None
        outcome = "ok"
        with Timer() as t:
            try:
                if responses:
                    resp = await self.client.responses.create(**body)
                else:
                    resp = await self.client.chat.completions.create(**body)
                payload = resp.model_dump()
            except asyncio.CancelledError:
                # The per-attempt timeout (asyncio.wait_for) cancelled us: still account for the attempt.
                t.__exit__()
                record(CallRecord(step=current_step.get(), kind=kind, purpose=purpose, model=model,
                                  latency_ms=t.ms, outcome="TIMEOUT_CANCELLED"))
                raise
            except Exception as exc:  # noqa: BLE001 - mapped below, then recorded
                mapped = exc if isinstance(exc, ChimeraError) else map_sdk_error(exc)
                outcome = mapped.code.value
                error: ChimeraError | None = mapped
            else:
                error = None
        inp, out, total = tokens_of((payload or {}).get("usage"))
        record(CallRecord(step=current_step.get(), kind=kind, purpose=purpose, model=model, latency_ms=t.ms,
                          input_tokens=inp, output_tokens=out, total_tokens=total, outcome=outcome,
                          response_id=(payload or {}).get("id")))
        if payload is not None:
            save_recording(purpose, body, payload)
        if error is not None:
            raise error
        assert payload is not None
        return payload


class MetaVision:
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 30.0) -> None:
        self.http = _MetaClient(base_url, api_key, timeout)
        self.model_id = model

    async def describe_animal(self, image: bytes, slot: str) -> AnimalReading:
        payload = await self.http.call("spark", "describe", self.model_id, build_describe_request(self.model_id, image))
        return parse_describe_response(payload)

    async def plan_fusion(self, context: dict[str, Any]) -> FusionPlan:
        payload = await self.http.call("spark", "plan", self.model_id, build_plan_request(self.model_id, context))
        return parse_plan_response(payload)

    async def write_field_card(self, context: dict[str, Any]) -> FieldCard:
        payload = await self.http.call("spark", "card", self.model_id, build_card_request(self.model_id, context))
        return parse_card_response(payload)


class MetaImageGen:
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 120.0) -> None:
        self.http = _MetaClient(base_url, api_key, timeout)
        self.model_id = model

    async def generate(self, prompt: str, reference_images: list[bytes], aspect: str | None,
                       previous_response_id: str | None = None) -> GeneratedImage:
        body = build_generate_request(self.model_id, prompt, reference_images, aspect, previous_response_id)
        purpose = "text_to_image" if not reference_images else "generate"
        payload = await self.http.call("image", purpose, self.model_id, body, responses=True)
        return parse_generate_response(payload, self.model_id)
