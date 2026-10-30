"""Record-and-replay shapes for the mocks (L1-09).

The mocks no longer hand back domain objects directly: they fill a response
recorded from the live Meta API (tests/fixtures/recorded/) with their own
content and run it through the *real* parsers in app/adapters/meta/client.py.
So mock mode exercises the same structure the live API returns: chat
completions for Muse Spark, and the Responses API output list (reasoning,
message, image_generation_call with base64 WebP) for Muse Image.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

RECORDED = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "recorded"

# Minimal shapes used only if the recordings are missing (e.g. a trimmed deploy image).
_FALLBACK_CHAT = {"id": "chatcmpl-mock", "object": "chat.completion", "model": "muse-spark-1.3",
                  "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "{}", "refusal": None}}],
                  "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}
_FALLBACK_RESPONSE = {"id": "resp_mock", "object": "response", "model": "muse-image-1.0", "status": "completed",
                      "output": [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": ""}]},
                                 {"type": "image_generation_call", "status": "completed", "result": ""}],
                      "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}}


@lru_cache
def template(name: str) -> dict[str, Any]:
    path = RECORDED / f"{name}-01.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))["response"]
    return _FALLBACK_RESPONSE if name in ("generate", "text_to_image") else _FALLBACK_CHAT


def _mock_id(prefix: str, seed: str) -> str:
    return f"{prefix}-mock-{hashlib.sha256(seed.encode()).hexdigest()[:20]}"


def chat_payload(kind: str, content: dict[str, Any]) -> dict[str, Any]:
    """A recorded chat completion with the assistant message replaced by `content` (as JSON)."""
    payload = copy.deepcopy(template(kind if (RECORDED / f"{kind}-01.json").exists() else "describe"))
    text = json.dumps(content, ensure_ascii=False)
    payload["id"] = _mock_id("chatcmpl", text)
    payload["choices"][0]["message"]["content"] = text
    payload["choices"][0]["finish_reason"] = "stop"
    return payload


def responses_payload(image: bytes | None, refusal: str | None = None) -> dict[str, Any]:
    """A recorded Responses API result with the image_generation_call result replaced (or removed for a refusal)."""
    payload = copy.deepcopy(template("generate"))
    payload["id"] = _mock_id("resp", hashlib.sha256(image or (refusal or "").encode()).hexdigest())
    out = []
    for item in payload.get("output", []):
        if item.get("type") == "image_generation_call":
            if image is None:
                continue
            item["result"] = base64.b64encode(image).decode()
        elif item.get("type") == "message" and refusal:
            item["content"] = [{"type": "output_text", "text": refusal, "annotations": []}]
        elif item.get("type") == "reasoning":
            item["summary"] = []
        out.append(item)
    payload["output"] = out
    return payload
