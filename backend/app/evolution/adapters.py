"""Model adapters for the evolution engine.

Muse Image goes through the existing ImageGenAdapter (services.image_gen) and parent
identification through the existing VisionAdapter.describe_animal. The two new
roles have their own protocols: EvoSpark (first plan, crossover and mutation,
prompt polish, readability critic) and Segmenter (SAM 3.1).

This module holds the mocks. The live implementations (E2) are in `live.py`; in real
mode without META_API_KEY the engine refuses before any call.

Every call goes through `Meter`, which counts Meta calls by kind (spark, image, sam).
"""

from __future__ import annotations

import copy
import hashlib
import io
import json
import random
import re
from collections.abc import Awaitable
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar

from PIL import Image, ImageDraw

from app.adapters.mock.recorded import chat_payload

T = TypeVar("T")


class EvoSpark(Protocol):
    model_id: str

    async def write_plan(self, prompt: str, skeleton: dict[str, Any]) -> dict[str, Any]: ...

    async def vary(self, prompt: str, elites: list[dict[str, Any]], n: int, seed: int) -> list[dict[str, Any]]: ...

    async def polish(self, prompt: str) -> str: ...

    async def critic(self, image: bytes) -> dict[str, Any]: ...

    async def checklist(self, image: bytes, items: list[str], choices: list[str]) -> dict[str, Any]: ...


class Segmenter(Protocol):
    model_id: str

    async def segment(self, image: bytes, label: str) -> bytes: ...


# ------------------------------------------------------------------ call meter


@dataclass
class Meter:
    counts: dict[str, int] = field(default_factory=lambda: {"spark": 0, "image": 0, "sam": 0})
    events: list[dict[str, str]] = field(default_factory=list)

    async def call(self, kind: str, purpose: str, aw: Awaitable[T]) -> T:
        self.counts[kind] += 1
        self.events.append({"kind": kind, "purpose": purpose})
        return await aw

    def snapshot(self) -> dict[str, int]:
        return dict(self.counts)

    def since(self, before: dict[str, int]) -> dict[str, int]:
        return {k: self.counts[k] - before.get(k, 0) for k in self.counts}


# ------------------------------------------------------------------ mock registry


def ahash(image: bytes, size: int = 16) -> int:
    with Image.open(io.BytesIO(image)) as im:
        g = im.convert("L").resize((size, size))
        px = list(g.get_flattened_data() if hasattr(g, "get_flattened_data") else g.getdata())
    mean = sum(px) / len(px)
    bits = 0
    for p in px:
        bits = (bits << 1) | (1 if p >= mean else 0)
    return bits


class MockRegistry:
    """What the mock renderer painted, so the mock critic and mock SAM can 'see' it.

    Keyed by an average hash, so a thumbnail of the same image still matches."""

    def __init__(self) -> None:
        self._items: list[tuple[int, str]] = []

    def note(self, image: bytes, prompt: str) -> None:
        self._items.append((ahash(image), prompt))

    def lookup(self, image: bytes) -> str | None:
        h = ahash(image)
        best = min(self._items, key=lambda it: bin(it[0] ^ h).count("1"), default=None)
        if best is None or bin(best[0] ^ h).count("1") > 24:
            return None
        return best[1]


def swatch(name: str, size: int = 512) -> bytes:
    """A plain color reference for a parent given by name (mock render only)."""
    digest = hashlib.sha256(name.encode()).digest()
    color = (64 + digest[0] % 160, 64 + digest[1] % 160, 64 + digest[2] % 160)
    im = Image.new("RGB", (size, size), color)
    d = ImageDraw.Draw(im)
    d.ellipse([size * 0.2, size * 0.25, size * 0.8, size * 0.75], fill=tuple(255 - c for c in color))
    out = io.BytesIO()
    im.save(out, "PNG")
    return out.getvalue()


# ------------------------------------------------------------------ mocks

PAIR_RE = re.compile(r"A single creature that combines an? ([a-z' -]+?) and an? ([a-z' -]+?)\.")
HYBRID_RE = re.compile(r"^An? ([a-z' -]+?) \(.*?\), a real hybrid animal\.")
HOST_RE = re.compile(r"Host frame: the ([a-z' -]+?) sets")
STRONG_DONOR = ("full strength", "in place of the tail", "wings in place", "separate pair of")


class MockEvoSpark:
    model_id = "mock-muse-spark-evo"

    def __init__(self, registry: MockRegistry, invalid_every: int = 0) -> None:
        self.registry = registry
        self.invalid_every = invalid_every

    @staticmethod
    def _wire(kind: str, content: Any) -> Any:
        # Same wire shape as live Muse Spark: JSON text inside a recorded chat completion.
        payload = chat_payload(kind, {"result": content})
        return json.loads(payload["choices"][0]["message"]["content"])["result"]

    async def write_plan(self, prompt: str, skeleton: dict[str, Any]) -> dict[str, Any]:
        return self._wire("plan", copy.deepcopy(skeleton))

    async def polish(self, prompt: str) -> str:
        return self._wire("plan", prompt.replace("natural history illustration.", "natural history illustration, soft daylight."))

    async def critic(self, image: bytes) -> dict[str, Any]:
        prompt = self.registry.lookup(image)
        if prompt is None:
            return self._wire("describe", {"animals": [], "creatures": 1, "notes": "unrecognized image"})
        m = PAIR_RE.search(prompt)
        animals = [m.group(1), m.group(2)] if m else []
        with Image.open(io.BytesIO(image)) as im:
            small = max(im.size) < 400
        if small and animals and not any(s in prompt for s in STRONG_DONOR):
            host = HOST_RE.search(prompt)
            animals = [host.group(1)] if host else animals[:1]  # faint donor traits vanish at thumbnail size
        return self._wire("describe", {"animals": animals, "creatures": 1, "notes": "mock critic"})

    async def checklist(self, image: bytes, items: list[str], choices: list[str]) -> dict[str, Any]:
        """Mock: a real-hybrid render shows every item; at thumbnail size, fine detail (stripes, mane, tail
        hair) reads as unclear. An unrecognized image is unclear throughout."""
        prompt = self.registry.lookup(image)
        m = HYBRID_RE.search(prompt or "")
        with Image.open(io.BytesIO(image)) as im:
            small = max(im.size) < 400
        fine = ("stripe", "mane", "tail")
        answers = [{"item": it, "answer": "unclear" if not m or (small and any(f in it for f in fine)) else "yes"}
                   for it in items]
        choice = m.group(1) if m and m.group(1) in choices else "other"
        return self._wire("describe", {"answers": answers, "choice": choice, "notes": "mock checklist"})

    async def vary(self, prompt: str, elites: list[dict[str, Any]], n: int, seed: int) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        habitats = ["forest", "grassland", "mountain", "desert", "rocky coast", "tundra"]
        for i in range(n):
            rng = random.Random(f"{seed}-{i}")
            a = copy.deepcopy(elites[i % len(elites)])
            child = a
            kind = ["habitat", "regions", "strength", "crossover"][i % 4]
            if kind == "crossover" and len(elites) > 1:
                b = elites[(i + 1) % len(elites)]
                for tag in ("coat_pattern", "coat_color", "coat_texture"):
                    child["traits"][tag] = copy.deepcopy(b["traits"][tag])
                parents = [a["id"], b["id"]]
            else:
                parents = [a["id"]]
                if kind == "habitat" or kind == "crossover":
                    child["habitat"]["name"] = rng.choice([h for h in habitats if h != a["habitat"]["name"]])
                    child["habitat"]["source"] = "bridging"
                elif kind == "regions":
                    order = ["forequarters", "neck", "back", "flanks", "belly", "hindquarters"]
                    for tag in ("coat_pattern", "coat_color", "coat_texture"):
                        tr = child["traits"][tag]
                        if tr["op"] == "PATCH":
                            regs = tr["region"]
                            if len(regs) > 1 and rng.random() < 0.5:
                                regs.pop()
                            else:
                                extra = next((r for r in order if r not in regs), None)
                                if extra:
                                    regs.append(extra)
                        elif tr["op"] == "BLEND":
                            tr["value"] = round(min(1.0, max(0.0, tr["value"] + rng.choice([-0.1, 0.1]))), 2)
                else:
                    for tag in ("coat_pattern", "mane"):
                        tr = child["traits"][tag]
                        if tr.get("strength") is not None:
                            tr["strength"] = round(min(1.0, max(0.05, tr["strength"] + rng.choice([-0.1, 0.1]))), 2)
            if self.invalid_every and (i + 1) % self.invalid_every == 0:
                if child["mode"] == "hybrid":
                    child["mode"] = "chimera"
                else:
                    child["traits"]["coat_color"] = {"op": "BLEND", "donor": [child["parents"]["sire"], child["parents"]["dam"]],
                                                     "value": 0.5}
            child["lineage"] = {"parent_ids": parents, "generation": max(e["lineage"]["generation"] for e in elites) + 1}
            out.append(child)
        return self._wire("plan", out)


class MockSegmenter:
    model_id = "mock-sam-3.1"

    def __init__(self, registry: MockRegistry) -> None:
        self.registry = registry

    async def segment(self, image: bytes, label: str) -> bytes:
        prompt = self.registry.lookup(image) or ""
        wide = ("four-legged", "horizontal", "equine", "cat frame", "bear frame", "camelid")
        aspect = 1.7 if any(w in prompt for w in wide) else 0.9 if "upright" in prompt else 1.3
        size = 256
        w = size * 0.8 if aspect >= 1 else size * 0.8 * aspect
        h = w / aspect
        im = Image.new("L", (size, size), 0)
        ImageDraw.Draw(im).ellipse([(size - w) / 2, (size - h) / 2, (size + w) / 2, (size + h) / 2], fill=255)
        out = io.BytesIO()
        im.save(out, "PNG")
        return out.getvalue()
