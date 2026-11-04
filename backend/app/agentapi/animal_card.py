"""The animal card: a profile of a generated creature, made on demand from its image and its stored generation record.

One vision call (Muse Spark on the Meta API, structured output). The model sees the image and how the image was made
(the Fusion prompt, the art style, the parents, every edit instruction from V1 to this image), so the card builds on
the decisions already taken instead of inventing a new creature. The model's own reasoning is kept on the card."""

from __future__ import annotations

import json
from typing import Any

from app.adapters.meta.client import _data_url, _json_schema, _message_json

_STR = {"type": "string"}
_LIST = {"type": "array", "items": _STR}

CARD_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["name", "scientific_style_name", "tagline", "inherited", "appearance", "size", "habitat", "diet",
                 "behaviour", "abilities", "weaknesses", "fun_fact", "reasoning"],
    "properties": {
        "name": _STR,
        "scientific_style_name": _STR,
        "tagline": _STR,
        "inherited": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["parent", "traits"],
            "properties": {"parent": _STR, "traits": _LIST}}},
        "appearance": _STR,
        "size": _STR,
        "habitat": _STR,
        "diet": _STR,
        "behaviour": _STR,
        "abilities": _LIST,
        "weaknesses": _LIST,
        "fun_fact": _STR,
        "reasoning": _STR,
    },
}

INSTRUCTIONS = (
    "You write the profile card of an invented hybrid creature for a creative app. You get the creature's image and "
    "the record of how it was made: the parents, the Fusion prompt, the art style and every later edit. Build on "
    "those decisions: describe the creature that is in the image, and attribute each visible trait to the parent it "
    "most plausibly came from. Never contradict the image. Keep it vivid but grounded: habitat, diet, size and "
    "behaviour should follow from the body you see and the parents' real biology. Write short sentences. "
    "`name`: a catchy common name. `scientific_style_name`: a playful Latin-style binomial. `tagline`: one line. "
    "`inherited`: one entry per parent with the traits it gave. `abilities` and `weaknesses`: 2 to 4 short items "
    "each. `reasoning`: two to four sentences on how you read the image and the record to decide this card.")


def card_context(chain: list[dict[str, Any]]) -> dict[str, Any]:
    """What the model is told about the image: the first version's Fusion record, then each edit in order."""
    first = chain[0]
    fusion = dict(first.get("generation") or {})
    if len(json.dumps(fusion, default=str)) > 6000:
        fusion.pop("agent_reasoning", None)
    edits = [{"operation": v.get("operation"), "instruction": v.get("instruction")} for v in chain[1:]]
    return {"title": first.get("title"), "style": first.get("style") or fusion.get("style"), "fusion": fusion,
            "edits": edits}


def build_card_request(model: str, image: bytes, context: dict[str, Any]) -> dict[str, Any]:
    return {"model": model, "messages": [
        {"role": "system", "content": INSTRUCTIONS},
        {"role": "user", "content": [
            {"type": "text", "text": "How this creature was made:\n" + json.dumps(context, ensure_ascii=False,
                                                                                   default=str)},
            {"type": "image_url", "image_url": {"url": _data_url(image)}}]},
    ], "response_format": _json_schema("animal_card", CARD_SCHEMA)}


def parse_card(payload: dict[str, Any]) -> dict[str, Any]:
    data = _message_json(payload)
    out: dict[str, Any] = {}
    for key, spec in CARD_SCHEMA["properties"].items():
        value = data.get(key)
        if spec.get("type") == "string":
            out[key] = str(value or "").strip()[:1200]
        elif key == "inherited":
            out[key] = [{"parent": str(r.get("parent") or "")[:120],
                         "traits": [str(t)[:200] for t in (r.get("traits") or [])][:8]}
                        for r in (value or []) if isinstance(r, dict)][:4]
        else:
            out[key] = [str(t).strip()[:200] for t in (value or []) if str(t).strip()][:6]
    return out


async def make_card(settings: Any, image: bytes, context: dict[str, Any]) -> dict[str, Any]:
    from app.evolution.live import LiveEvoSpark

    spark = LiveEvoSpark(settings)
    payload = await spark._chat("lab_card", build_card_request(spark.model_id, image, context))
    card = parse_card(payload)
    card["model"] = spark.model_id
    card["basedOn"] = context
    return card
