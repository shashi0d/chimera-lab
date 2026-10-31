"""The evolution engine: seed plan (4.1 to 4.5), render and judge (4.6 to 4.8),
evolve loop with a quality-diversity archive (4.9), edits, and storage.

Model calls: identify parents (only for image inputs), first plan, prompt polish,
render, critic, SAM, thumbnail critic; plus one crossover/mutation call per round.
All go through `Meter` so the number of Meta calls is known from the code path.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import random
from pathlib import Path
from typing import Any

from app.errors import ChimeraError
from app.evolution.adapters import EvoSpark, Meter, MockEvoSpark, MockRegistry, MockSegmenter, Segmenter, swatch
from app.evolution.card import output_card
from app.evolution.checks import Violation, hard_violations
from app.evolution.data import Animal, Taxonomy, cards, taxonomy
from app.evolution.genome import TRAIT_TAGS, Genome, Trait, validate_plan
from app.evolution.habitat import apply_habitat, choose_habitat
from app.evolution.judge import judge
from app.evolution.physics import run_checks
from app.evolution.prompt import PROMPT_CARDS, accept_polish, compile_prompt
from app.evolution.route import Route, choose_host, route, silhouette
from app.evolution.traits import build_traits, contribution
from app.models.schemas import ErrorCode
from app.services import Services

ARCHIVE_BUCKETS = 5
EDITABLE = ("habitat", "host", "size.mass_kg") + tuple(f"traits.{t}" for t in TRAIT_TAGS)


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def cache_key(sire: str, dam: str, myth: bool, host: str | None, habitat: str | None, seed: int) -> str:
    """Ordered: A x B and B x A never share a key (RC-R2-01)."""
    return f"{sire}>{dam}|myth={int(myth)}|host={host or '-'}|habitat={habitat or '-'}|seed={seed}"


def plan_id(g: Genome) -> str:
    body = g.model_dump(exclude={"id", "scores", "checks"})
    return "crt_" + hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:12]


class EvoStore:
    """Creatures and the fuse cache as JSON files (the shared DbAdapter has a fixed collection list)."""

    def __init__(self, root: Path) -> None:
        self.root = root
        (root / "creatures").mkdir(parents=True, exist_ok=True)
        (root / "cache").mkdir(parents=True, exist_ok=True)

    def _p(self, kind: str, key: str) -> Path:
        safe = hashlib.sha256(key.encode()).hexdigest()[:32] if kind == "cache" else key
        return self.root / kind / f"{safe}.json"

    def put(self, kind: str, key: str, doc: dict[str, Any]) -> None:
        self._p(kind, key).write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    def get(self, kind: str, key: str) -> dict[str, Any] | None:
        p = self._p(kind, key)
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


class EvoEngine:
    def __init__(self, services: Services, spark: EvoSpark | None = None, segmenter: Segmenter | None = None,
                 registry: MockRegistry | None = None, store_root: Path | None = None) -> None:
        self.services = services
        self.mock = services.settings.chimera_mode == "mock"
        self.registry = registry or MockRegistry()
        self.spark: EvoSpark = spark or MockEvoSpark(self.registry)
        self.segmenter: Segmenter = segmenter or MockSegmenter(self.registry)
        self.meter = Meter()
        self.tax: Taxonomy = taxonomy()
        self.store = EvoStore(store_root or services.settings.resolved_local_dir() / "evo")

    # ------------------------------------------------------------------ guards and lookups

    def _guard(self) -> None:
        if not self.mock:
            raise ChimeraError(ErrorCode.UPSTREAM_ERROR, "The evolution engine has no live Spark or SAM adapter yet "
                               "(E1-offline). Run with CHIMERA_MODE=mock.", retryable=False)

    def _animal(self, name: str) -> Animal:
        a = self.tax.resolve(name)
        if a is None:
            raise ChimeraError(ErrorCode.VALIDATION_FAILED, f"Unknown animal: {name!r}.",
                               details={"hint": "use a common name or animal_id from chimera_data.json"})
        return a

    async def resolve_parent(self, name: str | None, image: bytes | None, slot: str) -> Animal:
        if name:
            return self._animal(name)
        if image is None:
            raise ChimeraError(ErrorCode.VALIDATION_FAILED, f"{slot}: give a name or an image.")
        reading = await self.meter.call("spark", "identify", self.services.vision.describe_animal(image, slot))
        for cand in (reading.common_name, reading.scientific_name):
            if cand and (a := self.tax.resolve(cand)):
                return a
        raise ChimeraError(ErrorCode.VALIDATION_FAILED, f"{slot}: identified as {reading.common_name!r}, "
                           "which is not in chimera_data.json.")

    def route_for(self, g: Genome) -> Route:
        return route(self.tax.animals[g.parents.sire], self.tax.animals[g.parents.dam], self.tax, myth=g.mode == "mythic")

    # ------------------------------------------------------------------ 4.1 to 4.5

    def seed_plan(self, sire: Animal, dam: Animal, myth: bool = False, host_pick: str | None = None,
                  habitat: str | None = None, seed: int = 0) -> tuple[Genome, Route]:
        """Code skeleton for 4.1 to 4.3 plus the habitat choice. No model call."""
        r = route(sire, dam, self.tax, myth)
        host, host_cards, _ = choose_host(r, host_pick)
        rng = random.Random(f"{sire.id}>{dam.id}|{seed}")
        built = build_traits(r, host, self.tax, rng)
        hab, hab_cards = choose_habitat(sire, dam, rng, habitat)
        processes = list(r.processes)
        g = Genome(
            id="pending", parents={"sire": sire.id, "dam": dam.id}, mode=r.mode,  # type: ignore[arg-type]
            known_pair=r.pair["id"] if r.pair else None, host=host, identity_balance=0.5, habitat=hab,
            size=built["size"], silhouette="pending", limb_plan=built["limb_plan"], traits=built["traits"],
            labels=list(r.labels), processes=processes,
            card_trace=_dedupe(r.cards + host_cards + built["cards"] + hab_cards), seed=seed,
        )
        g.silhouette = silhouette(g, self.tax, r.pair)
        return g, r

    def finish(self, g: Genome, r: Route) -> Genome:
        """4.4 habitat and 4.5 physical checks, then derived fields. Idempotent."""
        g = g.model_copy(deep=True)
        locked = bool(r.pair and r.pair.get("locked"))
        hab_cards = apply_habitat(g, self.tax, locked)
        phys_cards = run_checks(g, self.tax)
        g.silhouette = silhouette(g, self.tax, r.pair)
        g.identity_balance = contribution(g.traits, g.limb_plan, g.host or g.parents.sire)
        g.labels = _dedupe([*r.labels, *g.labels])
        g.card_trace = _dedupe(g.card_trace + hab_cards + phys_cards + PROMPT_CARDS)
        assert g.limb_plan.requested_wings is None, "limb budget left a wing request unresolved (RC-R3-01)"
        g.id = plan_id(g)
        return validate_plan(g.model_dump())

    def plan_prompt(self, g: Genome, task: str) -> str:
        book = cards()
        ids = _dedupe(g.card_trace + book.hard_ids())
        return (f"{task}\nKeep the JSON schema exactly. Never change parents, mode or locked override fields.\n"
                f"Rule cards (quoted from data/rule_cards.json):\n{book.quote(ids)}\n"
                f"Plan:\n{g.model_dump_json()}")

    def _check(self, g: Genome, r: Route) -> list[Violation]:
        return hard_violations(g, r, self.tax)

    # ------------------------------------------------------------------ 4.6 to 4.8

    async def realize(self, g: Genome, r: Route, refs: list[bytes]) -> dict[str, Any]:
        prompt = compile_prompt(g, self.tax)
        polished = await self.meter.call("spark", "polish", self.spark.polish(prompt))
        final = accept_polish(prompt, polished)
        if not refs and self.mock:
            refs = [swatch(g.parents.sire), swatch(g.parents.dam)]  # the mock renderer needs references
        img = await self.meter.call("image", "render", self.services.image_gen.generate(final, refs, "1:1"))
        if self.mock:
            self.registry.note(img.data, final)
        verdict = await judge(img.data, g, r, self.tax, self.spark, self.segmenter, self.meter)
        g = g.model_copy(update={"scores": verdict["scores"]})
        key = f"evo/{g.id}.webp"
        await self.services.storage.put(key, img.data, img.content_type)
        doc = {"genome": g.model_dump(), "prompt": final, "prompt_compiled": prompt, "image_key": key,
               "judge": verdict, "card": output_card(g, r, self.tax), "route": r.public(),
               "ref_keys": []}
        self.store.put("creatures", g.id, doc)
        return doc

    # ------------------------------------------------------------------ endpoints

    async def fuse(self, sire_name: str | None = None, dam_name: str | None = None, sire_image: bytes | None = None,
                   dam_image: bytes | None = None, myth: bool = False, host: str | None = None,
                   habitat: str | None = None, seed: int = 0) -> dict[str, Any]:
        self._guard()
        before = self.meter.snapshot()
        sire = await self.resolve_parent(sire_name, sire_image, "sire")
        dam = await self.resolve_parent(dam_name, dam_image, "dam")
        if sire.id == dam.id:
            raise ChimeraError(ErrorCode.DUPLICATE_INPUTS, "Sire and dam are the same animal.")
        key = cache_key(sire.id, dam.id, myth, host, habitat, seed)
        hit = self.store.get("cache", key)
        if hit and (doc := self.store.get("creatures", hit["creature_id"])):
            return {**doc, "cached": True, "cache_key": key, "meta_calls": self.meter.since(before)}

        skeleton, r = self.seed_plan(sire, dam, myth, host, habitat, seed)
        model_note = "accepted"
        try:
            raw = await self.meter.call("spark", "first_plan", self.spark.write_plan(
                self.plan_prompt(skeleton, "Write the first plan for this pair."), skeleton.model_dump()))
            plan = validate_plan({**raw, "id": "pending"})
            if v := self._check(plan, r):
                raise ValueError("; ".join(f"{x.card}: {x.detail}" for x in v))
        except (ValueError, TypeError) as e:
            plan, model_note = skeleton, f"rejected, code skeleton used ({str(e)[:200]})"
        g = self.finish(plan, r)
        if v := self._check(g, r):  # cannot happen for code plans; guards the model path
            raise ChimeraError(ErrorCode.VALIDATION_FAILED, "Plan breaks a hard rule card.",
                               details={"violations": [x.public() for x in v]})
        refs = [i for i in (sire_image, dam_image) if i]
        doc = await self.realize(g, r, refs)
        self.store.put("cache", key, {"creature_id": g.id})
        return {**doc, "cached": False, "cache_key": key, "model_plan": model_note,
                "meta_calls": self.meter.since(before)}

    async def get(self, creature_id: str) -> dict[str, Any]:
        doc = self.store.get("creatures", creature_id) if creature_id.startswith("crt_") else None
        if doc is None:
            raise ChimeraError(ErrorCode.NOT_FOUND, f"No creature {creature_id}.")
        return {**doc, "image_url": await self.services.storage.get_url(doc["image_key"])}

    async def _offspring(self, raw: dict[str, Any], r: Route) -> tuple[Genome | None, list[dict[str, str]]]:
        try:
            plan = validate_plan({**raw, "id": raw.get("id") or "pending", "scores": {}})
        except ValueError as e:
            return None, [{"card": "schema", "detail": str(e)[:300]}]
        if v := self._check(plan, r):
            return None, [x.public() for x in v]
        g = self.finish(plan, r)
        if v := self._check(g, r):
            return None, [x.public() for x in v]
        return g, []

    async def evolve(self, creature_id: str, rounds: int = 3, batch: int = 4) -> dict[str, Any]:
        self._guard()
        before = self.meter.snapshot()
        seed_doc = await self.get(creature_id)
        seed = validate_plan(seed_doc["genome"])
        r = self.route_for(seed)
        archive: dict[str, dict[str, Any]] = {}
        rejected: list[dict[str, Any]] = []

        def place(doc: dict[str, Any]) -> None:
            g = doc["genome"]
            bucket = min(ARCHIVE_BUCKETS - 1, int(g["identity_balance"] * ARCHIVE_BUCKETS))
            cell = f"{bucket}|{g['habitat']['name']}"  # RC-R8-04, RC-R8-05
            cur = archive.get(cell)
            if cur is None or doc["genome"]["scores"]["quality"] > cur["genome"]["scores"]["quality"]:
                archive[cell] = doc

        place(seed_doc)
        for rnd in range(rounds):
            elites = sorted(archive.values(), key=lambda d: -d["genome"]["scores"]["quality"])[:2]
            elite_plans = [validate_plan(e["genome"]) for e in elites]
            prompt = self.plan_prompt(elite_plans[0], f"Round {rnd + 1}: return {batch} offspring by crossover or "
                                      "mutation of these elites as plans in the same schema.")
            raws = await self.meter.call("spark", "vary", self.spark.vary(
                prompt, [p.model_dump() for p in elite_plans], batch, seed=seed.seed * 1000 + rnd))
            for raw in raws[:batch]:
                g, why = await self._offspring(copy.deepcopy(raw), r)
                if g is None:
                    rejected.append({"round": rnd + 1, "violations": why})
                    continue
                doc = await self.realize(g, r, [])
                place(doc)
        cells = [{"cell": k, "creature_id": d["genome"]["id"], "quality": d["genome"]["scores"]["quality"],
                  "identity_balance": d["genome"]["identity_balance"], "habitat": d["genome"]["habitat"]["name"],
                  "generation": d["genome"]["lineage"]["generation"]} for k, d in sorted(archive.items())]
        show = sorted(cells, key=lambda c: -c["quality"])[:4]
        return {"seed": creature_id, "rounds": rounds, "batch": batch, "cells": cells, "elites": show,
                "rejected": rejected, "meta_calls": self.meter.since(before)}

    async def edit(self, creature_id: str, gene: str, value: Any) -> dict[str, Any]:
        self._guard()
        before = self.meter.snapshot()
        if gene not in EDITABLE:
            raise ChimeraError(ErrorCode.VALIDATION_FAILED, f"Gene {gene!r} is not editable.",
                               details={"editable": list(EDITABLE)})
        doc = await self.get(creature_id)
        raw = copy.deepcopy(doc["genome"])
        if gene.startswith("traits."):
            raw["traits"][gene.split(".", 1)[1]] = value if isinstance(value, dict) else Trait(**value).model_dump()
        elif gene == "habitat":
            raw["habitat"] = {"name": str(value), "source": "user", "adjustments": [], "visible_trait": None}
        elif gene == "host":
            raw["host"] = value
        else:
            raw["size"]["mass_kg"] = float(value)
        raw.update(id="pending", scores={}, lineage={"parent_ids": [creature_id], "generation": raw["lineage"]["generation"]})
        r = self.route_for(validate_plan(doc["genome"]))
        g, why = await self._offspring(raw, r)
        if g is None:
            raise ChimeraError(ErrorCode.VALIDATION_FAILED, "The edit breaks the schema or a hard rule card.",
                               details={"violations": why})
        out = await self.realize(g, r, [])
        return {**out, "meta_calls": self.meter.since(before)}


def decode_image(b64: str | None) -> bytes | None:
    if not b64:
        return None
    try:
        return base64.b64decode(b64.split(",", 1)[-1], validate=True)
    except ValueError as e:
        raise ChimeraError(ErrorCode.IMAGE_CORRUPT, "image_b64 is not valid base64.") from e
