"""Live Meta adapters for the evolution engine (E2).

* Muse Spark (chat completions, strict JSON schema): first plan, prompt polish,
  readability critic and thumbnail critic. Crossover/mutation (`vary`) is not
  enabled live: E2 runs no evolve rounds.
* Muse Image: the existing `MetaImageGen`, wrapped in the shared retry policy.
* SAM 3.1: the Responses API at the same Meta base URL, model ``sam-3.1``, one
  user message with a text prompt and the image as a data URL.

Everything reuses `app.adapters.meta.client`: the same `_MetaClient` (live budget
guard before every attempt, a usage record after it, key-free recordings), the
same error mapping, and `pipeline.retry.call_with_retry` as the only retry layer.
Request builders and parsers are pure functions so recordings replay in mock mode.
"""

from __future__ import annotations

import base64
import io
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from PIL import Image

from app.adapters.base import GeneratedImage, ImageGenAdapter
from app.adapters.meta.client import _data_url, _json_schema, _message_json, _MetaClient
from app.config import Settings
from app.errors import ChimeraError
from app.evolution.genome import REGIONS, TRAIT_TAGS
from app.models.schemas import ErrorCode
from app.pipeline.retry import call_with_retry

T = TypeVar("T")

SAM_MODEL = "sam-3.1"

# ------------------------------------------------------------------ schemas

_STR = {"type": "string"}
_STR_N = {"type": ["string", "null"]}
_NUM_N = {"type": ["number", "null"]}
_STRS = {"type": "array", "items": _STR}


def _obj(props: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "additionalProperties": False, "required": list(props), "properties": props}


_SLOT = _obj({"kind": {"type": "string", "enum": ["legs", "wings", "fins", "tentacles", "arms", "none"]},
              "donor": _STR_N})
_TRAIT = _obj({
    "op": {"type": "string", "enum": ["BLEND", "PICK", "OVERLAY", "PATCH"]},
    "donor": {"anyOf": [_STR, _STRS, {"type": "null"}]},
    "value": _NUM_N,
    "strength": _NUM_N,
    "region": {"anyOf": [{"type": "array", "items": {"type": "string", "enum": list(REGIONS)}}, {"type": "null"}]},
    "part": _STR_N,
    "note": _STR_N,
    "flags": _STRS,
})

# The plan fields the model may write. id, seed, lineage, checks and scores are set by code.
PLAN_SCHEMA: dict[str, Any] = _obj({
    "parents": _obj({"sire": _STR, "dam": _STR}),
    "mode": {"type": "string", "enum": ["hybrid", "chimera", "mythic"]},
    "known_pair": _STR_N,
    "host": _STR_N,
    "identity_balance": {"type": "number"},
    "habitat": _obj({"name": _STR, "source": {"type": "string", "enum": ["shared", "bridging", "user"]},
                     "adjustments": _STRS, "visible_trait": _STR_N}),
    "size": _obj({"mass_kg": _NUM_N, "flags": _STRS}),
    "silhouette": _STR,
    "limb_plan": _obj({"forelimbs": _SLOT, "hindlimbs": _SLOT, "extra_wings": {"anyOf": [_SLOT, {"type": "null"}]},
                       "appendages": _STRS,
                       "wing_use": {"type": "string", "enum": ["powered", "borderline", "gliding_or_display", "none"]},
                       "requested_wings": _STR_N}),
    "traits": _obj({t: _TRAIT for t in TRAIT_TAGS}),
    "labels": _STRS,
    "processes": _STRS,
    "card_trace": _STRS,
})
CODE_FIELDS = ("id", "seed", "lineage", "checks", "scores")

POLISH_SCHEMA = _obj({"prompt": _STR})
CRITIC_SCHEMA = _obj({"animals": _STRS, "creatures": {"type": "integer"}, "notes": _STR})

PLAN_INSTRUCTIONS = (
    "You write creature plans for a natural-history fusion engine. You get rule cards and a code-built plan as "
    "JSON. Return the plan in the same schema, improved where the rule cards allow: clearer trait notes, a better "
    "silhouette sentence, sensible strengths and regions. Never change parents, mode, known_pair, host or labels. "
    "Use animal ids exactly as given. Every trait donor must be one of the two parents."
)
POLISH_INSTRUCTIONS = (
    "You lightly edit a text-to-image prompt for readability. Keep the first sentence word for word. Do not add, "
    "remove or change any animal, body part, color, count, strength, habitat or view. Do not add brand or "
    "franchise names. Stay within 20 percent of the original length. Return the edited prompt only."
)
CRITIC_INSTRUCTIONS = (
    "You look at one picture with no other context. animals: the real animal species whose features you can "
    "clearly see in it, as everyday English common names, most prominent first, at most three. If it looks like "
    "one ordinary animal, list only that animal. creatures: how many separate creatures are in the picture. "
    "notes: one short sentence on what you see."
)

# ------------------------------------------------------------------ request builders (pure)


def build_plan_request(model: str, prompt: str) -> dict[str, Any]:
    return {"model": model, "messages": [{"role": "system", "content": PLAN_INSTRUCTIONS},
                                         {"role": "user", "content": prompt}],
            "response_format": _json_schema("evo_plan", PLAN_SCHEMA), "temperature": 0.4}


def build_polish_request(model: str, prompt: str) -> dict[str, Any]:
    return {"model": model, "messages": [{"role": "system", "content": POLISH_INSTRUCTIONS},
                                         {"role": "user", "content": prompt}],
            "response_format": _json_schema("polished_prompt", POLISH_SCHEMA), "temperature": 0.2}


def build_critic_request(model: str, image: bytes) -> dict[str, Any]:
    return {"model": model, "messages": [
        {"role": "system", "content": CRITIC_INSTRUCTIONS},
        {"role": "user", "content": [{"type": "text", "text": "What animals do you see, and how many creatures?"},
                                     {"type": "image_url", "image_url": {"url": _data_url(image)}}]},
    ], "response_format": _json_schema("readability_critic", CRITIC_SCHEMA), "temperature": 0}


def build_sam_request(image: bytes, prompt: str, model: str = SAM_MODEL) -> dict[str, Any]:
    return {"model": model, "input": [{"role": "user", "content": [
        {"type": "input_text", "text": prompt},
        {"type": "input_image", "image_url": _data_url(image)},
    ]}]}


# ------------------------------------------------------------------ parsers (pure)


def parse_plan_response(payload: dict[str, Any], skeleton: dict[str, Any]) -> dict[str, Any]:
    data = _message_json(payload)
    return {**data, **{k: skeleton[k] for k in CODE_FIELDS if k in skeleton}}


def parse_polish_response(payload: dict[str, Any]) -> str:
    return str(_message_json(payload).get("prompt") or "")


def parse_critic_response(payload: dict[str, Any]) -> dict[str, Any]:
    data = _message_json(payload)
    return {"animals": [str(a) for a in data.get("animals") or []], "creatures": int(data.get("creatures") or 0),
            "notes": str(data.get("notes") or "")}


def parse_sam_response(payload: dict[str, Any]) -> bytes:
    """Return a binary mask PNG (white = object). Written against the E2 probe recording (sam-01.json)."""
    raise ChimeraError(ErrorCode.UPSTREAM_ERROR, "SAM 3.1 response parser not written yet (E2 step 3).",
                       retryable=False)


def _mask_png(im: Image.Image) -> bytes:
    out = io.BytesIO()
    im.convert("L").point(lambda p: 255 if p > 127 else 0).save(out, "PNG")
    return out.getvalue()


def _b64_image(s: str) -> Image.Image:
    return Image.open(io.BytesIO(base64.b64decode(s.split(",", 1)[-1])))


# ------------------------------------------------------------------ adapters


class _Retrying:
    def __init__(self, settings: Settings, timeout: float) -> None:
        self.settings = settings
        self.timeout = timeout

    async def retry(self, fn: Callable[[], Awaitable[T]]) -> T:
        return await call_with_retry(fn, timeout=self.timeout, base_delay=self.settings.retry_base_seconds,
                                     max_attempts=self.settings.retry_max_attempts)


class LiveEvoSpark(_Retrying):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings, settings.plan_timeout_seconds)
        self.model_id = settings.meta_vision_model
        self.http = _MetaClient(settings.meta_api_base_url, settings.meta_api_key or "", self.timeout)

    async def _chat(self, purpose: str, body: dict[str, Any]) -> dict[str, Any]:
        return await self.retry(lambda: self.http.call("spark", purpose, self.model_id, body))

    async def write_plan(self, prompt: str, skeleton: dict[str, Any]) -> dict[str, Any]:
        payload = await self._chat("evo_plan", build_plan_request(self.model_id, prompt))
        return parse_plan_response(payload, skeleton)

    async def polish(self, prompt: str) -> str:
        return parse_polish_response(await self._chat("evo_polish", build_polish_request(self.model_id, prompt)))

    async def critic(self, image: bytes) -> dict[str, Any]:
        return parse_critic_response(await self._chat("evo_critic", build_critic_request(self.model_id, image)))

    async def vary(self, prompt: str, elites: list[dict[str, Any]], n: int, seed: int) -> list[dict[str, Any]]:
        raise ChimeraError(ErrorCode.UPSTREAM_ERROR, "Evolve rounds are not enabled live (E2 runs fuse only).",
                           retryable=False)


class MetaSegmenter(_Retrying):
    def __init__(self, settings: Settings, model: str = SAM_MODEL) -> None:
        super().__init__(settings, settings.sam_timeout_seconds)
        self.model_id = model
        self.http = _MetaClient(settings.meta_api_base_url, settings.meta_api_key or "", self.timeout)

    async def segment_raw(self, image: bytes, label: str) -> dict[str, Any]:
        body = build_sam_request(image, label, self.model_id)
        return await self.retry(lambda: self.http.call("sam", "sam", self.model_id, body, responses=True, raw=True))

    async def segment(self, image: bytes, label: str) -> bytes:
        return parse_sam_response(await self.segment_raw(image, label))


class RetryingImageGen(_Retrying):
    """Muse Image through the shared retry policy (the pipeline does this in its generate step)."""

    def __init__(self, inner: ImageGenAdapter, settings: Settings) -> None:
        super().__init__(settings, settings.generate_timeout_seconds)
        self.inner = inner
        self.model_id = inner.model_id

    async def generate(self, prompt: str, reference_images: list[bytes], aspect: str | None,
                       previous_response_id: str | None = None) -> GeneratedImage:
        return await self.retry(lambda: self.inner.generate(prompt, reference_images, aspect, previous_response_id))


def build_live(settings: Settings, image_gen: ImageGenAdapter) -> tuple[LiveEvoSpark, MetaSegmenter, RetryingImageGen]:
    if not settings.meta_api_key:
        raise RuntimeError("CHIMERA_MODE=real needs META_API_KEY")
    return LiveEvoSpark(settings), MetaSegmenter(settings), RetryingImageGen(image_gen, settings)
