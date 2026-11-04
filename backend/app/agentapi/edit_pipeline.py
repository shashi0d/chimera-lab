"""How the Lab's edits guide the image model (Revise, Paint, Draw). Used by lab.py's endpoints and by
scripts/edit_eval.py (the side-by-side bench).

Each edit runs in up to three steps:

1. Read the request (vision model, one call): ground the creator's words or marks in this image. "Make this wing
   feathered" on a magenta patch becomes "Replace the creature's left bat wing with a large feathered bird wing in
   white and gold, attached at the same shoulder". A drawing's strokes are read as the body parts they suggest
   ("two red curved strokes rising from the forehead: two curved horns"). Image models follow a precise, specific
   edit instruction much better than a vague one or a coloured marking alone. If this call fails, a written
   template is used instead, so the edit still runs.
2. Edit (image model, one call): a structured prompt (what to change, where, what to keep) with the guide image(s).
   A small painted area is edited as an enlarged close-up (crop-and-stitch, edit_regions.py) so it gets detail.
3. Put it back (no model): Paint and Draw keep the original everywhere except where the model really changed
   something near the brush or the strokes, feathered so no seam shows (edit_regions.change_mask/blend). If the
   model left the marks themselves in its image (magenta, drawn lines), it is asked once more.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from app.adapters.base import GeneratedImage
from app.agentapi import edit_regions as R

log = logging.getLogger(__name__)

PAINT_COLOUR = (255, 0, 200)
# How far beyond the brush/strokes the model's changes are accepted (share of the image's short side).
PAINT_REACH = 0.07
SKETCH_REACH = 0.10
# More than this share of the brush/strokes still shows the marks' colour: the model drew the marks; retry once.
LEFTOVER = 0.2


@dataclass
class EditResult:
    image: GeneratedImage
    prompt: str
    # True when the saved image is not exactly the provider's response (blended), so later edits can't chain on it.
    reference_only: bool
    record: dict[str, Any] = field(default_factory=dict)


# ------------------------------------------------------------------ context about the creature


def parent_animals(doc: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for p in (doc.get("generation") or {}).get("parents") or []:
        name = (p or {}).get("commonName") if isinstance(p, dict) else None
        if name and name not in names:
            names.append(str(name))
    return names


def creature_line(doc: dict[str, Any]) -> str:
    profile = doc.get("profile") or {}
    parents = parent_animals(doc)
    who = profile.get("name") or "a hybrid creature"
    made = f", a hybrid of {' and '.join(parents)}" if parents else ""
    summary = f" ({profile['summary'].rstrip('.')})" if profile.get("summary") else ""
    return f"{who}{made}{summary}"


STYLE_WORDS = {
    "real": "photorealistic wildlife photograph", "drawing": "hand-drawn pencil and ink sketch",
    "anime": "anime illustration with clean line art and cel shading", "comic": "comic book illustration",
    "cartoon": "cartoon illustration",
}


def style_line(doc: dict[str, Any]) -> str:
    return STYLE_WORDS.get(str(doc.get("style") or ""), "the same art style as the image")


KEEP = ("Keep everything else exactly the same: the creature's identity, pose, size, position and framing, its other "
        "body parts, colours and markings, the line art, shading and art style, and the plain white background. "
        "Keep the number of heads, legs, wings and tails unless the change asks otherwise. No text, no extra "
        "creatures, no scenery.")

ANATOMY = ("Make the new part real anatomy that belongs to this one living body: it attaches naturally, matches the "
           "creature's size, proportions, lighting and art style, and is built from the parent animals' parts where "
           "that fits. Never leave an empty gap or erase to background; where something is removed, the surrounding "
           "body continues there.")


# ------------------------------------------------------------------ step 1: read the request (vision model)


BRIEF_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["target", "change", "instruction", "keep"],
    "properties": {
        "target": {"type": "string", "description": "The body part(s) or area to change, named and located on the "
                                                     "creature (e.g. 'the creature's left bat wing')."},
        "change": {"type": "string", "description": "What it should look like afterwards, concretely: shape, "
                                                     "size, colour, texture, how it attaches."},
        "instruction": {"type": "string", "description": "One precise edit instruction for an image model: "
                                                          "'Replace/Change/Add <target> ... <change>'. No "
                                                          "references to colours of marks or highlights."},
        "keep": {"type": "array", "items": {"type": "string"},
                 "description": "5 to 8 specific visible features of this creature that must stay exactly as they "
                                "are (e.g. 'the orange coat with black stripes', 'the golden eyes')."},
    },
}

BRIEF_SYSTEM = (
    "You turn a creator's edit request for an image of a hybrid creature into a precise instruction for an image "
    "editing model. Look at the images. Name the exact body part(s) involved and where they are on the creature "
    "(left/right as seen in the image), and describe the result concretely (shape, size, colour, texture, how it "
    "attaches). Keep the creator's intent; don't add changes they didn't ask for. If the request is vague, choose "
    "the most natural reading for this creature. Answer with JSON only.")


def _brief_request(model: str, op: str, doc: dict[str, Any], images: list[bytes], ask: str) -> dict[str, Any]:
    from app.adapters.meta.client import _data_url, _json_schema

    context = {"creature": creature_line(doc), "art_style": style_line(doc), "tool": op, "request": ask}
    content: list[dict[str, Any]] = [{"type": "text", "text": json.dumps(context, ensure_ascii=False)}]
    content += [{"type": "image_url", "image_url": {"url": _data_url(i)}} for i in images]
    return {"model": model, "messages": [{"role": "system", "content": BRIEF_SYSTEM}, {"role": "user", "content": content}],
            "response_format": _json_schema("edit_brief", BRIEF_SCHEMA)}


async def read_request(vision: Any, op: str, doc: dict[str, Any], images: list[bytes], ask: str) -> dict[str, Any] | None:
    """The grounded edit (target, change, instruction), or None when the vision model can't answer (the caller
    falls back to a template)."""
    brief = getattr(vision, "edit_brief", None)
    if brief is None:
        return None
    try:
        data = await brief(_brief_request(getattr(vision, "model_id", ""), op, doc, images, ask))
    except Exception as exc:  # any failure: edit with the template prompt instead
        log.info("edit brief failed: %s", type(exc).__name__)
        return None
    out: dict[str, Any] = {k: " ".join(str(data.get(k) or "").split())[:600] for k in ("target", "change", "instruction")}
    keep = data.get("keep") if isinstance(data.get("keep"), list) else []
    out["keep"] = [" ".join(str(k).split())[:120] for k in keep if str(k).strip()][:8]
    return out if out["instruction"] else None


# ------------------------------------------------------------------ prompts (step 2)
# Order (as the image-model guides recommend): what changes first, then the specific things to keep, then the rest.


def keep_line(brief: dict[str, Any] | None) -> str:
    items = (brief or {}).get("keep") or []
    return f"Keep these exactly as they are: {'; '.join(items)}. " if items else ""


def revise_prompt(doc: dict[str, Any], instruction: str, brief: dict[str, Any] | None) -> str:
    what = brief["instruction"] if brief else instruction.rstrip(".")
    return (f"Edit this image of {creature_line(doc)}, a {style_line(doc)}. {what.rstrip('.')}. "
            f"Make the change clearly visible. {keep_line(brief)}{KEEP}")


def paint_prompt(doc: dict[str, Any], instruction: str, brief: dict[str, Any] | None, close_up: bool) -> str:
    what = brief["instruction"] if brief else f"In the highlighted area: {instruction.rstrip('.')}"
    where = ("Image 1 is a close-up of part of the creature with the area to change highlighted in translucent "
             "magenta; image 2 is the same close-up without the highlight; image 3 shows the whole creature for "
             "context. Return the close-up only, framed exactly like image 2."
             if close_up else
             "Image 1 shows the creature with the area to change highlighted in translucent magenta; image 2 is the "
             "same image without the highlight.")
    return (f"Edit an image of {creature_line(doc)}, a {style_line(doc)}. {where} {what.rstrip('.')}. "
            f"Change only the highlighted part; the new part may extend a little past the highlight where the "
            f"anatomy needs it. {ANATOMY} Draw no magenta and no outline. {keep_line(brief)}{KEEP}")


def sketch_prompt(doc: dict[str, Any], instruction: str, brief: dict[str, Any] | None) -> str:
    if brief:
        what = brief["instruction"]
    else:
        parents = parent_animals(doc)
        from_parents = f" (usually a part of a {' or '.join(parents)})" if parents else ""
        note = f" The creator says: {instruction.rstrip('.')}." if instruction else ""
        what = ("Turn each drawn mark into the real body part its shape suggests" + from_parents + ", at the drawn "
                "size, position and direction: a long stroke a tail, horn, tentacle or limb; dots eyes or spots; a "
                "jagged line spines or a crest; a filled patch a colour or pattern." + note)
    return (f"Edit an image of {creature_line(doc)}, a {style_line(doc)}. Image 1 shows the creature with coloured "
            f"marks its creator drew on it; image 2 is the same image without the marks. {what.rstrip('.')}. "
            f"Use the marks for position, size and shape only: the result is a finished {style_line(doc)}, with no "
            f"drawn lines left. {ANATOMY} {keep_line(brief)}{KEEP}")


# ------------------------------------------------------------------ the edits


async def _generate(svc: Any, settings: Any, prompt: str, refs: list[bytes], chain: str | None = None) -> GeneratedImage:
    from app.adapters.retrying import RetryingImageGen
    from app.errors import ChimeraError
    from app.models.schemas import ErrorCode

    image = await RetryingImageGen(svc.image_gen, settings).generate(prompt, refs, "1:1", chain)
    if not image.data:
        raise ChimeraError(ErrorCode.UPSTREAM_ERROR, "The image provider returned no image. Please try again.",
                           retryable=True).with_status(502)
    return image


def _note(trace: dict[str, bytes] | None, key: str, text: str) -> None:
    if trace is not None:
        trace[key] = b"TEXT" + text.encode()


async def revise(svc: Any, settings: Any, doc: dict[str, Any], original: bytes, instruction: str,
                 chain: str | None, trace: dict[str, bytes] | None = None) -> EditResult:
    """A whole-image edit from words. Chained on the provider's last response when there is one (the model keeps
    its own context), else the stored image as the reference."""
    brief = await read_request(svc.vision, "revise", doc, [original], instruction)
    prompt = revise_prompt(doc, instruction, brief)
    _note(trace, "brief", (brief or {}).get("instruction", "(template)"))
    image = await _generate(svc, settings, prompt, [] if chain else [original], chain)
    return EditResult(image, prompt, reference_only=False, record={"brief": brief})


RETRY_NOTE = (" The previous attempt still showed the marks; this time render the body part fully and leave no "
              "magenta, outline or drawn line anywhere.")
# The close-up came back as something else (the whole creature, another framing): edit the whole image instead.
MAX_CLOSE_UP_DRIFT = 0.35


async def paint(svc: Any, settings: Any, doc: dict[str, Any], original: bytes, mask: bytes, instruction: str,
                trace: dict[str, bytes] | None = None) -> EditResult:
    base = R.load_rgb(original)
    hint = R.alpha_of(mask, base.size)
    marked = R.highlight(base, hint, PAINT_COLOUR)
    box = R.crop_box(hint)
    brief = await read_request(svc.vision, "paint", doc, [R.png(marked)],
                               f"Change the area highlighted in magenta: {instruction}")
    _note(trace, "brief", (brief or {}).get("instruction", "(template)"))
    if trace is not None:
        trace["guide"] = R.png(marked)
    record: dict[str, Any] = {"brief": brief, "closeUp": False, "retried": False}

    async def attempt(extra: str = "") -> tuple[Any, GeneratedImage, str]:
        if box:
            prompt = paint_prompt(doc, instruction, brief, close_up=True) + extra
            raw = await _generate(svc, settings, prompt, [R.png(R.crop(marked, box)), R.png(R.crop(base, box)), original])
            got = R.load_rgb(raw.data)
            # Same framing as the close-up we sent? Compare outside the brush.
            framing = R.drift(R.crop(base, box), got.resize((1024, 1024)), R.crop(hint, box).point(lambda v: v), 0.06)
            if framing <= MAX_CLOSE_UP_DRIFT:
                record["closeUp"] = True
                return R.paste(base, got, box), raw, prompt
            record["closeUpRejected"] = round(framing, 3)
        prompt = paint_prompt(doc, instruction, brief, close_up=False) + extra
        raw = await _generate(svc, settings, prompt, [R.png(marked), original])
        return R.load_rgb(raw.data, base.size), raw, prompt

    candidate, raw, prompt = await attempt()
    if R.leftover_colour(candidate, hint, PAINT_COLOUR) > LEFTOVER:
        record["retried"] = True
        candidate, raw, prompt = await attempt(RETRY_NOTE)
    if trace is not None:
        trace["raw"] = raw.data
    return _put_back(base, candidate, hint, PAINT_REACH, raw, prompt, record, trace)


async def sketch(svc: Any, settings: Any, doc: dict[str, Any], original: bytes, drawing: bytes, instruction: str,
                 trace: dict[str, bytes] | None = None) -> EditResult:
    base = R.load_rgb(original)
    strokes = R.alpha_of(drawing, base.size)
    guide = R.overlay(base, drawing)
    ask = ("Read the coloured marks drawn on the creature as the body parts the creator wants there"
           + (f"; the creator also says: {instruction}" if instruction else "") + ".")
    brief = await read_request(svc.vision, "sketch", doc, [R.png(guide), original], ask)
    _note(trace, "brief", (brief or {}).get("instruction", "(template)"))
    record: dict[str, Any] = {"brief": brief, "retried": False}
    prompt = sketch_prompt(doc, instruction, brief)
    raw = await _generate(svc, settings, prompt, [R.png(guide), original])
    candidate = R.load_rgb(raw.data, base.size)
    if R.leftover_strokes(base, guide, candidate, strokes) > LEFTOVER:
        record["retried"] = True
        prompt += RETRY_NOTE
        raw = await _generate(svc, settings, prompt, [R.png(guide), original])
        candidate = R.load_rgb(raw.data, base.size)
    if trace is not None:
        trace["guide"] = R.png(guide)
        trace["raw"] = raw.data
    return _put_back(base, candidate, strokes, SKETCH_REACH, raw, prompt, record, trace)


def _put_back(base: Any, candidate: Any, hint: Any, reach: float, raw: GeneratedImage, prompt: str,
              record: dict[str, Any], trace: dict[str, bytes] | None) -> EditResult:
    # Always blended: Paint and Draw promise that the rest of the creature stays as it was. How much the model
    # changed elsewhere (drift) is kept for diagnosis only; in practice it is a few percent.
    area = R.change_mask(base, candidate, hint, reach)
    moved = R.drift(base, candidate, area, 0.02)
    record = {**record, "drift": round(moved, 3)}
    out = R.blend(base, candidate, area)
    if trace is not None:
        trace["area"] = R.png(area)
        _note(trace, "putback", f"drift {moved:.2f}: blended")
    return EditResult(GeneratedImage(R.png(out), "image/png", raw.model, raw.response_id), prompt,
                      reference_only=True, record=record)
