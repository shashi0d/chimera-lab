"""Live Meta adapters for the evolution engine (E2).

* Muse Spark (chat completions, strict JSON schema): first plan, prompt polish,
  readability critic and thumbnail critic (on the real-hybrid route, a feature
  checklist, E2d; the forced choice was removed in S2). Crossover/mutation (`vary`) is not
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

import io
import json
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from PIL import Image

from app.adapters.base import GeneratedImage, ImageGenAdapter
from app.adapters.meta.client import _data_url, _json_schema, _message_json, _MetaClient
from app.adapters.usage import CallKind
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
})  # S2: labels, processes and card_trace are code-filled (S1: an unbounded card_trace ran Spark Open away)
CODE_FIELDS = ("id", "seed", "lineage", "checks", "scores", "design_mode", "audit", "licenses",  # E4: code-owned
               "render_details", "labels", "processes", "card_trace")  # S2: derived lists are code-filled

POLISH_SCHEMA = _obj({"prompt": _STR})
CRITIC_SCHEMA = _obj({"animals": _STRS, "creatures": {"type": "integer"}, "notes": _STR})
ANSWERS = ("yes", "no", "unclear")


def checklist_schema() -> dict[str, Any]:
    """E2d: one yes/no/unclear answer per checklist item. S2: the forced choice is gone (ROADMAP Q6: it said
    "a mix of both" every time and was never scored)."""
    answer = _obj({"item": _STR, "answer": {"type": "string", "enum": list(ANSWERS)}})
    # No minItems/maxItems: strict schemas may reject them. The parser pads a short list with "unclear".
    return _obj({"answers": {"type": "array", "items": answer}, "creatures": {"type": "integer"},
                 "animals": _STRS, "notes": _STR})

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
CHECKLIST_INSTRUCTIONS = (
    "You look at one picture of an animal and check it against a list of visible features. For each item, answer "
    "yes if the feature is clearly visible, no if the picture clearly shows otherwise, or unclear if you cannot "
    "tell. Copy each item's text exactly, in the given order. Judge only what is visible. creatures: how many separate "
    "creatures are in the picture. animals: the real animal species whose features you can clearly see, as "
    "everyday English common names, at most three. notes: one short sentence."
)

# ------------------------------------------------------------------ E4: open world and audit

KINDS = ("species", "breed", "extinct", "ambiguous", "not_animal", "plant", "human", "mythic")
BODY_PLANS = ("quadruped", "biped", "winged", "finned", "multi_legged", "serpentine", "radial")
LOCOMOTOR = ("four legs", "two legs", "multiple legs", "wings", "fins", "flippers", "bell")
COVERINGS = ("fur", "feathers", "scales", "skin", "exoskeleton", "shell")
MOVEMENTS = ("walk", "run", "swim", "fly", "climb", "burrow", "glide")
HABITATS = ("grassland", "forest", "mountain", "tundra", "wetland", "freshwater", "marine", "desert")
CLIMATES = ("temperate", "tropical", "polar", "arid")
DIETS = ("carnivore", "herbivore", "omnivore", "insectivore", "piscivore")
ACTIVE = ("diurnal", "nocturnal", "crepuscular", "unrecorded")
MOUTHPARTS = ("grinding teeth", "bladed teeth", "mixed teeth", "pointed teeth", "beak", "mandibles",
              "toothless tongue", "other")
BREATHING = ("lungs", "gills", "external gills and lungs", "skin and lungs", "tracheae", "book lungs", "other")
AUDIT_RESULTS = ("pass", "repaired", "labeled")


def _enum(values: tuple[str, ...]) -> dict[str, Any]:
    return {"type": "string", "enum": list(values)}


def _enums(values: tuple[str, ...]) -> dict[str, Any]:
    return {"type": "array", "items": _enum(values)}


_RANGE = _obj({"min": {"type": "number"}, "max": {"type": "number"}})
_NAME = _obj({"scientific_name": _STR, "common_name": _STR})
IDENTIFY_SCHEMA = _obj({"kind": _enum(KINDS), "scientific_name": _STR, "common_name": _STR, "breed": _STR,
                        "alternatives": {"type": "array", "items": _NAME}, "note": _STR})
TRAITS_SCHEMA = _obj({
    "body_plan": _enums(BODY_PLANS), "primary_locomotor_part": _enum(LOCOMOTOR), "covering": _enum(COVERINGS),
    "movement": _enums(MOVEMENTS), "habitat": _enums(HABITATS), "climate": _enums(CLIMATES), "diet": _enum(DIETS),
    "active_time": _enums(ACTIVE), "body_mass_kg": _RANGE, "body_length_m": _RANGE, "visible_features": _STRS,
    "mouthparts": _enum(MOUTHPARTS), "mouthparts_detail": _STR, "breathing": _enum(BREATHING),
    "breathing_detail": _STR, "claimed_crosses": _STRS,
})
AUDIT_SCHEMA = _obj({"functions": {"type": "array", "items": _obj({
    "function": _STR, "result": _enum(AUDIT_RESULTS), "detail": _STR, "repair": _STR})}})

IDENTIFY_INSTRUCTIONS = (
    "You identify an animal from a name (common, scientific, misspelled or regional) or a photo. Return the "
    "scientific name of the species exactly as a taxonomist writes it (genus species, or genus species subspecies "
    "for a domestic form). kind: species; breed (a domestic breed: give the species' scientific name and the breed "
    "name in breed); extinct (a species known only from fossils or records); ambiguous (the name covers several "
    "species: pick the most common or best-known species as scientific_name and list up to four others in "
    "alternatives); not_animal; plant; human (any person or human group); mythic (a creature of myth, legend or "
    "fiction). For a misspelling, answer for the intended animal. Never invent a species; if unsure, say "
    "ambiguous and list candidates. note: one short sentence."
)
TRAITS_INSTRUCTIONS = (
    "You describe a real animal for a natural-history engine. Use typical adult values. body_plan: the overall "
    "layout (winged means wings are the main limbs; a bird is biped and winged). visible_features: three to six "
    "short visible features someone would draw (for a breed, the breed's look). mouthparts: what the head eats "
    "with. breathing: the main breathing organ. claimed_crosses: scientific names of species this animal is "
    "documented to hybridize with, or an empty list; these are stored as unverified claims. Do not guess numbers "
    "wildly: give a plausible min and max."
)
AUDIT_INSTRUCTIONS = (
    "You audit whether a planned fictional creature could perform basic body functions. You get the plan in "
    "plain words and a list of functions that no rule card covers. For each listed function only, answer pass "
    "(it works as planned), repaired (it works with a small change; put the change in repair as a short visible "
    "description) or labeled (it does not work; say why in detail). Judge from anatomy, not from story. Never "
    "state high oxygen as the settled reason giant insects existed."
)


def build_identify_request(model: str, name: str | None, image: bytes | None) -> dict[str, Any]:
    if image is not None:
        content: Any = [{"type": "text", "text": "Identify the animal in this photo."},
                        {"type": "image_url", "image_url": {"url": _data_url(image)}}]
    else:
        content = f"Identify this animal name: {name}"
    return {"model": model, "messages": [{"role": "system", "content": IDENTIFY_INSTRUCTIONS},
                                         {"role": "user", "content": content}],
            "response_format": _json_schema("identify_animal", IDENTIFY_SCHEMA), "temperature": 0}


def build_traits_request(model: str, ident: dict[str, Any]) -> dict[str, Any]:
    who = f"{ident.get('common_name')} ({ident.get('scientific_name')})"
    if ident.get("breed"):
        who += f", breed: {ident['breed']}"
    return {"model": model, "messages": [{"role": "system", "content": TRAITS_INSTRUCTIONS},
                                         {"role": "user", "content": f"Describe: {who}"}],
            "response_format": _json_schema("animal_traits", TRAITS_SCHEMA), "temperature": 0}


def build_audit_request(model: str, plan_text: str, functions: list[str]) -> dict[str, Any]:
    text = f"Plan: {plan_text}\nFunctions to judge: {', '.join(functions)}"
    return {"model": model, "messages": [{"role": "system", "content": AUDIT_INSTRUCTIONS},
                                         {"role": "user", "content": text}],
            "response_format": _json_schema("function_audit", AUDIT_SCHEMA), "temperature": 0}


def parse_identify_response(payload: dict[str, Any]) -> dict[str, Any]:
    d = _message_json(payload)
    kind = str(d.get("kind") or "")
    return {"kind": kind if kind in KINDS else "ambiguous", "scientific_name": str(d.get("scientific_name") or "").strip(),
            "common_name": str(d.get("common_name") or "").strip(), "breed": str(d.get("breed") or "").strip(),
            "alternatives": [{"scientific_name": str(a.get("scientific_name") or ""),
                              "common_name": str(a.get("common_name") or "")}
                             for a in d.get("alternatives") or [] if isinstance(a, dict)][:4],
            "note": str(d.get("note") or "")}


def parse_traits_response(payload: dict[str, Any]) -> dict[str, Any]:
    return clean_traits(_message_json(payload))


def clean_traits(d: dict[str, Any]) -> dict[str, Any]:
    """Trait values cleaned to the engine's vocabularies (shared by the plain and the web-cited trait calls)."""
    keep = lambda v, allowed: list(dict.fromkeys(x for x in (v or []) if x in allowed))  # noqa: E731
    one = lambda v, allowed, default: v if v in allowed else default  # noqa: E731
    rng = lambda v: {"min": float((v or {}).get("min") or 0), "max": float((v or {}).get("max") or 0)}  # noqa: E731
    return {"body_plan": keep(d.get("body_plan"), BODY_PLANS) or ["quadruped"],
            "primary_locomotor_part": one(d.get("primary_locomotor_part"), LOCOMOTOR, "four legs"),
            "covering": one(d.get("covering"), COVERINGS, "skin"), "movement": keep(d.get("movement"), MOVEMENTS),
            "habitat": keep(d.get("habitat"), HABITATS), "climate": keep(d.get("climate"), CLIMATES),
            "diet": one(d.get("diet"), DIETS, "omnivore"), "active_time": keep(d.get("active_time"), ACTIVE),
            "body_mass_kg": rng(d.get("body_mass_kg")), "body_length_m": rng(d.get("body_length_m")),
            "visible_features": [str(x) for x in d.get("visible_features") or []][:6],
            "mouthparts": one(d.get("mouthparts"), MOUTHPARTS, "other"),
            "mouthparts_detail": str(d.get("mouthparts_detail") or ""),
            "breathing": one(d.get("breathing"), BREATHING, "other"),
            "breathing_detail": str(d.get("breathing_detail") or ""),
            "claimed_crosses": [str(x) for x in d.get("claimed_crosses") or []]}


def parse_audit_response(payload: dict[str, Any], functions: list[str]) -> list[dict[str, str]]:
    """One entry per asked function; a missing or unknown answer becomes 'labeled' (never a silent pass)."""
    got = {str(f.get("function", "")).lower(): f for f in _message_json(payload).get("functions") or []
           if isinstance(f, dict)}
    out = []
    for fn in functions:
        f = got.get(fn, {})
        result = f.get("result") if f.get("result") in AUDIT_RESULTS else "labeled"
        detail = str(f.get("detail") or ("no model judgment returned" if not f else ""))
        out.append({"function": fn, "result": result, "detail": detail, "repair": str(f.get("repair") or "")})
    return out


# ------------------------------------------------------------------ S2: web-cited traits (Meta Responses + web_search)

CITE_FIELDS = ("body_plan", "primary_locomotor_part", "covering", "movement", "habitat", "climate", "diet",
               "active_time", "body_mass_kg", "body_length_m", "visible_features", "mouthparts", "breathing")


def _cited(value: dict[str, Any]) -> dict[str, Any]:
    return _obj({"value": value, "source_url": _STR, "evidence": _STR})


CITED_SCHEMA = _obj({
    "body_plan": _cited(_enums(BODY_PLANS)), "primary_locomotor_part": _cited(_enum(LOCOMOTOR)),
    "covering": _cited(_enum(COVERINGS)), "movement": _cited(_enums(MOVEMENTS)), "habitat": _cited(_enums(HABITATS)),
    "climate": _cited(_enums(CLIMATES)), "diet": _cited(_enum(DIETS)), "active_time": _cited(_enums(ACTIVE)),
    "body_mass_kg": _cited(_RANGE), "body_length_m": _cited(_RANGE), "visible_features": _cited(_STRS),
    "mouthparts": _cited(_enum(MOUTHPARTS)), "breathing": _cited(_enum(BREATHING)),
    "mouthparts_detail": _STR, "breathing_detail": _STR, "claimed_crosses": _STRS,
})
CITE_INSTRUCTIONS = (
    "You describe a real animal for a natural-history engine, from sources. Use web search and open the pages you "
    "rely on: encyclopedias, museums, universities, zoos, government agencies or peer-reviewed papers. For each "
    "field give the value, source_url (the exact URL of a page you opened that supports the value) and evidence "
    "(a short quote from that page). If no source you opened supports a field, give your best estimate and leave "
    "source_url and evidence empty; never invent a URL. Use typical adult values. body_plan: the overall layout "
    "(winged means wings are the main limbs; insects are multi_legged). visible_features: three to six short "
    "visible features someone would draw. mouthparts: what the head eats with. breathing: the main breathing "
    "organ. claimed_crosses: scientific names of species it is documented to hybridize with, or an empty list."
)


def build_cite_request(model: str, ident: dict[str, Any]) -> dict[str, Any]:
    who = f"{ident.get('common_name')} ({ident.get('scientific_name')})"
    if ident.get("breed"):
        who += f", breed: {ident['breed']}"
    return {"model": model, "instructions": CITE_INSTRUCTIONS, "tools": [{"type": "web_search"}],
            "input": [{"role": "user", "content": [{"type": "input_text", "text": f"Describe, with sources: {who}"}]}],
            "text": {"format": {"type": "json_schema", "name": "cited_traits", "strict": True, "schema": CITED_SCHEMA}}}


def norm_url(url: str) -> str:
    u = (url or "").strip().lower().rstrip("/")
    for prefix in ("https://", "http://"):
        u = u.removeprefix(prefix)
    return u.removeprefix("www.")


def parse_cite_response(payload: dict[str, Any]) -> dict[str, Any]:
    """{traits, citations, opened, searches}. A field's citation is `verified` only when its URL is a page the
    model opened, or a url_citation annotation, in this same response; anything else is not a citation."""
    if payload.get("status") not in (None, "completed"):
        raise ChimeraError(ErrorCode.UPSTREAM_ERROR, f"cited traits: response status {payload.get('status')!r}")
    opened, searches, annotated, final = [], [], [], ""
    for item in payload.get("output") or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "web_search_call":
            act = item.get("action") or {}
            if act.get("url"):
                opened.append(act["url"])
            if act.get("query"):
                searches.append(act["query"])
            for src in act.get("sources") or []:
                if isinstance(src, dict) and src.get("url"):
                    annotated.append(src["url"])
        if item.get("type") == "message":
            for c in item.get("content") or []:
                if isinstance(c, dict) and c.get("type") == "output_text":
                    annotated += [a.get("url", "") for a in c.get("annotations") or [] if isinstance(a, dict)]
                    if item.get("phase") != "commentary":
                        final += c.get("text", "")
    try:
        data = json.loads(final)
    except json.JSONDecodeError as exc:
        raise ChimeraError(ErrorCode.UPSTREAM_ERROR, "cited traits: the model returned an unreadable answer.") from exc
    seen = {norm_url(u) for u in opened + annotated if u}
    values: dict[str, Any] = {}
    citations: dict[str, dict[str, Any]] = {}
    for f in CITE_FIELDS:
        cell = data.get(f) if isinstance(data.get(f), dict) else {}
        values[f] = cell.get("value") if "value" in cell else (  # a range may come flat: {min, max, source_url}
            {"min": cell.get("min"), "max": cell.get("max")} if "min" in cell else None)
        url = str(cell.get("source_url") or "").strip()
        citations[f] = {"url": url, "evidence": str(cell.get("evidence") or "").strip()[:300],
                        "verified": bool(url) and norm_url(url) in seen}
    for f in ("mouthparts_detail", "breathing_detail", "claimed_crosses"):
        values[f] = data.get(f)
    return {"traits": clean_traits(values), "citations": citations, "opened": opened, "searches": searches}


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


def build_checklist_request(model: str, image: bytes, items: list[str]) -> dict[str, Any]:
    listing = "\n".join(f"{i}. {item}" for i, item in enumerate(items, 1))
    text = f"Features to check:\n{listing}"
    return {"model": model, "messages": [
        {"role": "system", "content": CHECKLIST_INSTRUCTIONS},
        {"role": "user", "content": [{"type": "text", "text": text},
                                     {"type": "image_url", "image_url": {"url": _data_url(image)}}]},
    ], "response_format": _json_schema("feature_checklist", checklist_schema()), "temperature": 0}


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


def parse_checklist_response(payload: dict[str, Any], items: list[str]) -> dict[str, Any]:
    """Answers are matched to items by order (the model is told to keep it); anything missing or
    not one of yes/no/unclear becomes "unclear". A "choice" in an old recording is ignored (S2)."""
    data = _message_json(payload)
    got = [a for a in data.get("answers") or [] if isinstance(a, dict)]
    answers = []
    for i, item in enumerate(items):
        a = str(got[i].get("answer", "")).lower() if i < len(got) else ""
        answers.append({"item": item, "answer": a if a in ANSWERS else "unclear"})
    return {"answers": answers, "creatures": int(data.get("creatures") or 0), "animals": [str(a) for a in data.get("animals") or []],
            "notes": str(data.get("notes") or "")}


def sam_text(payload: dict[str, Any]) -> str:
    """The output_text of SAM 3.1's message items (masks arrive as special-token text, not as an image)."""
    if payload.get("status") not in (None, "completed"):
        raise ChimeraError(ErrorCode.UPSTREAM_ERROR, f"SAM 3.1 response status {payload.get('status')!r}.")
    return "".join(c.get("text", "") for item in payload.get("output") or [] if isinstance(item, dict)
                   and item.get("type") == "message" for c in item.get("content") or []
                   if isinstance(c, dict) and c.get("type") == "output_text")


def parse_sam_response(payload: dict[str, Any], width: int, height: int) -> bytes:
    """Full-frame binary mask PNG (white = object), the union of every mask record.

    Format (recorded in tests/fixtures/recorded/sam-01.json): a box token and a mask token per object;
    the mask is box-local, base85, '~' lossless (arithmetic-coded). It is decoded with Meta's own
    `meta_sam_parser` (the SAM License forbids reverse engineering the format). No mask: an empty frame."""
    import meta_sam_parser as msp

    parser = msp.image_segmentation_format().create_parser()
    parser.push(sam_text(payload), emit=False)
    result = parser.finish(msp.CompletedOutcome()).result
    frame = Image.new("L", (width, height), 0)
    for rec in result.records:
        if not isinstance(rec, msp.SegmentationMaskRecord):
            continue
        try:
            raster = msp.decode_mask_to_raster(rec.mask)
        except msp.InvalidSegmentationMaskError as e:
            raise ChimeraError(ErrorCode.UPSTREAM_ERROR, "SAM 3.1 returned an undecodable mask.") from e
        local = Image.frombytes("L", (rec.mask.width, rec.mask.height), bytes(255 if v else 0 for v in raster))
        b = rec.bounds
        box = (round(b.left), round(b.top), round(b.right), round(b.bottom))
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        frame.paste(255, box[:2], local.resize((box[2] - box[0], box[3] - box[1]), Image.NEAREST))
    return _mask_png(frame)


def _mask_png(im: Image.Image) -> bytes:
    out = io.BytesIO()
    im.convert("L").point(lambda p: 255 if p > 127 else 0).save(out, "PNG")
    return out.getvalue()


# ------------------------------------------------------------------ adapters


class _Retrying:
    def __init__(self, settings: Settings, timeout: float) -> None:
        self.settings = settings
        self.timeout = timeout

    async def retry(self, fn: Callable[[], Awaitable[T]]) -> T:
        return await call_with_retry(fn, timeout=self.timeout, base_delay=self.settings.retry_base_seconds,
                                     max_attempts=self.settings.retry_max_attempts)


class LiveEvoSpark(_Retrying):
    kind: CallKind = "spark"  # the live-budget kind; the Baseten subclass counts as "spark_baseten"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings, settings.plan_timeout_seconds)
        self.model_id = settings.meta_vision_model
        self.http = _MetaClient(settings.meta_api_base_url, settings.meta_api_key or "", self.timeout)

    async def _chat(self, purpose: str, body: dict[str, Any]) -> dict[str, Any]:
        return await self.retry(lambda: self.http.call(self.kind, purpose, self.model_id, body))

    async def write_plan(self, prompt: str, skeleton: dict[str, Any]) -> dict[str, Any]:
        payload = await self._chat("evo_plan", build_plan_request(self.model_id, prompt))
        return parse_plan_response(payload, skeleton)

    async def polish(self, prompt: str) -> str:
        return parse_polish_response(await self._chat("evo_polish", build_polish_request(self.model_id, prompt)))

    async def critic(self, image: bytes) -> dict[str, Any]:
        return parse_critic_response(await self._chat("evo_critic", build_critic_request(self.model_id, image)))

    async def checklist(self, image: bytes, items: list[str]) -> dict[str, Any]:
        body = build_checklist_request(self.model_id, image, items)
        return parse_checklist_response(await self._chat("evo_checklist", body), items)

    async def identify(self, name: str | None = None, image: bytes | None = None) -> dict[str, Any]:
        return parse_identify_response(await self._chat("evo_identify", build_identify_request(self.model_id, name, image)))

    async def learn_traits(self, ident: dict[str, Any]) -> dict[str, Any]:
        return parse_traits_response(await self._chat("evo_learn_traits", build_traits_request(self.model_id, ident)))

    async def judge_functions(self, plan_text: str, functions: list[str]) -> list[dict[str, str]]:
        body = build_audit_request(self.model_id, plan_text, functions)
        return parse_audit_response(await self._chat("evo_audit", body), functions)

    async def cite_traits(self, ident: dict[str, Any]) -> dict[str, Any]:
        """S2: traits with web search and a citation per field (Meta Responses API; raw body, since the SDK has no
        type for every web_search_call action). Its own, longer timeout: the model searches and opens pages."""
        body = build_cite_request(self.model_id, ident)
        timeout = self.settings.cite_timeout_seconds
        http = _MetaClient(self.settings.meta_api_base_url, self.settings.meta_api_key or "", timeout)
        payload = await call_with_retry(
            lambda: http.call(self.kind, "evo_cite_traits", self.model_id, body, responses=True, raw=True),
            timeout=timeout, base_delay=self.settings.retry_base_seconds, max_attempts=self.settings.retry_max_attempts)
        return parse_cite_response(payload)

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
        payload = await self.segment_raw(image, label)
        with Image.open(io.BytesIO(image)) as im:
            size = im.size
        return parse_sam_response(payload, *size)


class RetryingImageGen(_Retrying):
    """Muse Image through the shared retry policy (the pipeline does this in its generate step)."""

    def __init__(self, inner: ImageGenAdapter, settings: Settings) -> None:
        super().__init__(settings, settings.generate_timeout_seconds)
        self.inner = inner
        self.model_id = inner.model_id

    async def generate(self, prompt: str, reference_images: list[bytes], aspect: str | None,
                       previous_response_id: str | None = None) -> GeneratedImage:
        return await self.retry(lambda: self.inner.generate(prompt, reference_images, aspect, previous_response_id))


def build_live(settings: Settings, image_gen: ImageGenAdapter) -> tuple[Any, MetaSegmenter, RetryingImageGen]:
    """S2: Spark calls are routed per call type (evo_config `routing`): Spark Open on Baseten where configured,
    Meta Spark 1.3 for the rest and as the fallback. Without a Baseten key everything goes to Meta (logged)."""
    if not settings.meta_api_key:
        raise RuntimeError("CHIMERA_MODE=real needs META_API_KEY")
    from app.evolution.routing import RoutedSpark

    baseten = None
    if settings.baseten_api_key:
        from app.adapters.baseten.client import BasetenEvoSpark

        baseten = BasetenEvoSpark(settings)
    return RoutedSpark(LiveEvoSpark(settings), baseten), MetaSegmenter(settings), RetryingImageGen(image_gen, settings)
