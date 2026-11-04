"""Wire-shaped fake answers, so the fakes go through the same parsers as live calls."""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any


def _id(prefix: str, seed: str) -> str:
    return f"{prefix}_mock_{hashlib.sha256(seed.encode()).hexdigest()[:16]}"


def chat_payload(content: dict[str, Any]) -> dict[str, Any]:
    """A chat completion whose assistant message is `content` as JSON (structured output)."""
    text = json.dumps(content, ensure_ascii=False)
    return {"id": _id("chatcmpl", text), "object": "chat.completion", "model": "muse-spark-1.3",
            "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": text}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}}


def responses_payload(image: bytes | None, refusal: str | None = None) -> dict[str, Any]:
    """A Responses API result as Muse Image returns it: reasoning, a message, then the image_generation_call."""
    seed = hashlib.sha256(image or (refusal or "").encode()).hexdigest()
    output: list[dict[str, Any]] = [
        {"type": "reasoning", "id": _id("rs", seed), "summary": []},
        {"type": "message", "id": _id("msg", seed), "role": "assistant",
         "content": [{"type": "output_text", "text": refusal or "", "annotations": []}]},
    ]
    if image is not None:
        output.append({"type": "image_generation_call", "id": _id("ig", seed), "status": "completed",
                       "result": base64.b64encode(image).decode()})
    return {"id": _id("resp", seed), "object": "response", "model": "muse-image-1.0", "output": output,
            "usage": {"input_tokens": 1000, "output_tokens": 500, "total_tokens": 1500}}
