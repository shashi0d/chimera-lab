"""Prompt mode (EVO_FUSION_MODE=prompt): the plain-prompt Fusion and its art styles.

The prompt is EVO_FUSION_PROMPT with {a} and {b} replaced by the parents' names, then the art style, then the
background rule (EVO_FUSION_BACKGROUND). Each parent may come with a reference image (an uploaded photo or an
earlier generated creature); those go to the image model directly, in slot order, and the prompt says which is which.
"""

from __future__ import annotations

from typing import Any

# The art styles a Fusion can render in (the frontend shows them in this order). Value: the prompt's wording.
STYLES: dict[str, str] = {
    "real": "a photorealistic wildlife photograph with natural detail and texture",
    "drawing": "a detailed hand-drawn pencil and ink illustration",
    "anime": "an anime-style illustration with clean line art and cel shading",
    "comic": "a comic book illustration with bold ink outlines and halftone shading",
    "cartoon": "a cute cartoon illustration with simple rounded shapes and flat colours",
}
DEFAULT_STYLE = "real"
SLOT_ORDER = ("sire", "dam")


def style_phrase(style: str | None) -> str:
    return STYLES.get(style or DEFAULT_STYLE, STYLES[DEFAULT_STYLE])


def background_rule(settings: Any) -> str:
    return str(settings.evo_fusion_background).strip()


def build_fusion_prompt(settings: Any, a: dict[str, Any], b: dict[str, Any], style: str | None,
                        ref_slots: list[str]) -> str:
    """`a`, `b`: the parent views (commonName, source). `ref_slots`: the slots that send a reference image, in the
    order the images are attached."""
    names = {"sire": a["commonName"], "dam": b["commonName"]}
    text = str(settings.evo_fusion_prompt).replace("{a}", names["sire"]).replace("{b}", names["dam"]).strip()
    parts = [text.rstrip(".") + "."]
    if ref_slots:
        said = []
        for i, slot in enumerate(ref_slots, 1):
            parent = a if slot == "sire" else b
            kind = "an earlier generated creature" if parent.get("source") == "version" else "a photo"
            said.append(f"reference image {i} is {kind} of {names[slot]}")
        parts.append("Use the attached reference images: " + "; ".join(said) + ". Keep each one's most "
                     "recognisable features, but make one single new creature, not a collage.")
    parts.append(f"Render it as {style_phrase(style)}.")
    rule = background_rule(settings)
    if rule:
        parts.append(rule)
    return " ".join(parts)
