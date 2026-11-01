"""The evolution engine: seed plan (4.1 to 4.5), render and judge (4.6 to 4.8),
evolve loop with a quality-diversity archive (4.9), edits, and storage.

Model calls: identify parents (only for image inputs), first plan, prompt polish,
render, critic, SAM, thumbnail critic; plus one crossover/mutation call per round.
All go through `Meter` so the number of Meta calls is known from the code path.
"""

from __future__ import annotations

import base64
import contextvars
import copy
import hashlib
import json
import random
from pathlib import Path
from typing import Any

from app.adapters.base import ImageGenAdapter
from app.errors import ChimeraError
from app.evolution.adapters import EvoSpark, Meter, MockEvoSpark, MockRegistry, MockSegmenter, Segmenter, swatch
from app.evolution.audit import apply_judgment, plan_text, run_audit, uncovered
from app.evolution.card import output_card
from app.evolution.checks import Violation, hard_violations
from app.evolution.critic import critics_for
from app.evolution.data import DATA, Animal, Taxonomy, cards, taxonomy
from app.evolution.fiction import settle
from app.evolution.gbif import FixtureGbif, GbifClient
from app.evolution.genome import DESIGN_MODES, TRAIT_TAGS, Genome, Trait, validate_plan
from app.evolution.growth import drift as growth_drift
from app.evolution.growth import has_covering, host_first
from app.evolution.growth import instruction as growth_instruction
from app.evolution.habitat import apply_habitat, choose_habitat, clear_habitat
from app.evolution.inspect import Item, edit_instruction, inspect, inspect_checklist, plan_items
from app.evolution.judge import judge
from app.evolution.parts import fix_parts
from app.evolution.physics import run_checks
from app.evolution.prompt import PROMPT_CARDS, accept_polish, compile_prompt
from app.evolution.resolve import LearnedStore, Resolution, Resolver
from app.evolution.route import Route, choose_host, is_real_hybrid, route, silhouette, silhouette_issues
from app.evolution.routing import summarize
from app.evolution.traits import build_traits, contribution, gate
from app.evolution.transfer import build as build_transfers
from app.evolution.transfer import fold_shapes, sync_regions
from app.models.schemas import ErrorCode
from app.services import Services

ARCHIVE_BUCKETS = 5
_LOG_MARK: contextvars.ContextVar[int | None] = contextvars.ContextVar("evo_log_mark", default=None)
EDITABLE = ("habitat", "host", "size.mass_kg") + tuple(f"traits.{t}" for t in TRAIT_TAGS)


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def cache_key(sire: str, dam: str, myth: bool, host: str | None, habitat: str | None, seed: int,
              mode: str = "speculative") -> str:
    """Ordered: A x B and B x A never share a key (RC-R2-01). The design mode is part of the key (E4)."""
    return f"{sire}>{dam}|myth={int(myth)}|mode={mode}|host={host or '-'}|habitat={habitat or '-'}|seed={seed}"


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
        self.renderer: ImageGenAdapter = services.image_gen
        self.live_error: str | None = None
        if not self.mock and (spark is None or segmenter is None):
            try:  # E2: live Spark, SAM 3.1 and a retrying Muse Image
                from app.evolution.live import build_live

                live_spark, live_seg, self.renderer = build_live(services.settings, services.image_gen)
                spark, segmenter = spark or live_spark, segmenter or live_seg
            except RuntimeError as e:
                self.live_error = str(e)
        self.spark: EvoSpark = spark or MockEvoSpark(self.registry, vision=getattr(services, "vision", None))
        self.segmenter: Segmenter = segmenter or MockSegmenter(self.registry)
        self.meter = Meter()
        self.tax: Taxonomy = taxonomy().copy()  # per engine: learned animals never leak between engines
        self.store = EvoStore(store_root or services.settings.resolved_local_dir() / "evo")
        st = services.settings
        learned = Path(st.evo_learned_path) if st.evo_learned_path else (
            st.resolved_local_dir() / "evo" / "learned_animals.json" if self.mock else DATA / "learned_animals.json")
        self.gbif = FixtureGbif() if self.mock else GbifClient(timeout=st.gbif_timeout_seconds)
        self.resolver = Resolver(self.tax, self.spark, self.gbif, LearnedStore(learned), self.meter.call,
                                 verifier=citation_verifier(self.mock))
        self.resolutions: dict[str, Resolution] = {}

    # ------------------------------------------------------------------ guards and lookups

    def _guard(self) -> None:
        if not self.mock and self.live_error:
            raise ChimeraError(ErrorCode.UPSTREAM_ERROR, f"Live evolution adapters unavailable: {self.live_error}.",
                               retryable=False)

    async def resolve(self, name: str | None = None, image: bytes | None = None) -> Resolution:
        """E4 open-world resolution: database, learned cache, then Muse Spark plus a GBIF exact match."""
        return await self.resolver.resolve(name=name, image=image)

    async def resolve_parent(self, name: str | None, image: bytes | None, slot: str) -> Animal:
        if not name and image is None:
            raise ChimeraError(ErrorCode.VALIDATION_FAILED, f"{slot}: give a name or an image.")
        res = await self.resolve(name, image)
        self.resolutions[slot] = res
        if res.status != "resolved" or res.animal is None:
            raise ChimeraError(ErrorCode.VALIDATION_FAILED, f"{slot}: {res.note}",
                               details={"resolution": res.public()})
        return res.animal

    async def plan_session(self, sire_name: str, dam_name: str, mode: str = "speculative", seed: int = 0) -> Any:
        """S2: a plan built by typed operations (ops.PlanSession), for the step-3 agent."""
        from app.evolution.ops import PlanSession

        sire = await self.resolve_parent(sire_name, None, "sire")
        dam = await self.resolve_parent(dam_name, None, "dam")
        return PlanSession(self, sire, dam, mode, seed)

    def route_for(self, g: Genome) -> Route:
        return route(self.tax.animals[g.parents.sire], self.tax.animals[g.parents.dam], self.tax, myth=g.mode == "mythic")

    # ------------------------------------------------------------------ 4.1 to 4.5

    def seed_plan(self, sire: Animal, dam: Animal, myth: bool = False, host_pick: str | None = None,
                  habitat: str | None = None, seed: int = 0, design_mode: str | None = None) -> tuple[Genome, Route]:
        """Code skeleton for 4.1 to 4.3 plus the habitat choice. No model call. design_mode (E4): realistic,
        speculative (default) or mythic; mythic routes a distant pair as a mythic composite."""
        design = design_mode or ("mythic" if myth else "speculative")
        myth = myth or design == "mythic"
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
            design_mode=design,  # type: ignore[arg-type]
        )
        g.checks += fix_parts(g, self.tax)  # S2 (E4c): donor parts must belong to the donor's class
        g.silhouette = silhouette(g, self.tax, r.pair)
        return g, r

    def finish(self, g: Genome, r: Route, license_requests: list[tuple[str, str]] | None = None,
               transfer_edits: list[dict[str, Any]] | None = None) -> Genome:
        """4.4 habitat and 4.5 physical checks, then derived fields. Idempotent. `license_requests` (S2): an
        agent's add_license calls, granted first within the budget."""
        g = g.model_copy(deep=True)
        g.render_details = []  # S2: rebuilt by the code steps below; model text never enters it
        locked = bool(r.pair and r.pair.get("locked"))
        g.checks += fix_parts(g, self.tax)  # S2 (E4c): a model plan's parts are checked against the class too
        gate_cards = gate(g.traits, r, g.host, self.tax)  # E2b: a model plan cannot undo GATE (e.g. a mane on feathers)
        real = is_real_hybrid(r)
        hab_cards = clear_habitat(g) if real else apply_habitat(g, self.tax, locked)  # E2c, D-056
        phys_cards = run_checks(g, self.tax)
        audit_cards, needs = run_audit(g, self.tax, r)  # 4.5b, after the physical checks (RC-R9-02)
        audit_cards += settle(g, needs, self.tax, license_requests)  # 4.5c fiction budget
        # S3b (RC-R10-15, 16): transfer records from the finished parts; the covering's extent becomes its regions
        fold_shapes(g, self.tax)
        g.transfers = build_transfers(g, self.tax, transfer_edits)
        sync_regions(g)
        g.silhouette = silhouette(g, self.tax, r.pair)  # last, from the final limb plan (S2: RC-R7-06)
        assert not silhouette_issues(g, self.tax), silhouette_issues(g, self.tax)
        g.identity_balance = contribution(g.traits, g.limb_plan, g.host or g.parents.sire)
        g.labels = _dedupe([*r.labels, *g.labels])
        tcards = (["RC-R10-15"] if g.transfers else []) + (
            ["RC-R10-16"] if any("RC-R10-16" in t.extent_reason for t in g.transfers) else [])
        g.card_trace = _dedupe(g.card_trace + gate_cards + hab_cards + phys_cards + audit_cards + tcards
                               + [c for c in PROMPT_CARDS if not (real and c == "RC-R4-11")])
        assert g.limb_plan.requested_wings is None, "limb budget left a wing request unresolved (RC-R3-01)"
        g.id = plan_id(g)
        return validate_plan(g.model_dump())

    def plan_prompt(self, g: Genome, task: str) -> str:
        book = cards()
        ids = _dedupe(g.card_trace + book.hard_ids())
        return (f"{task}\nKeep the JSON schema exactly. Never change parents, mode or locked override fields.\n"
                f"Rule cards (quoted from data/rule_cards.json):\n{book.quote(ids)}\n"
                f"Plan:\n{g.model_dump_json()}")

    def _check(self, g: Genome, r: Route, final: bool = True) -> list[Violation]:
        return hard_violations(g, r, self.tax, final)

    # ------------------------------------------------------------------ 4.6 to 4.8

    async def _render_and_judge(self, prompt: str, g: Genome, r: Route, refs: list[bytes]) -> tuple[Any, dict[str, Any]]:
        img = await self.meter.call("image", "render", self.renderer.generate(prompt, refs, "1:1"))
        if self.mock:
            self.registry.note(img.data, prompt)
        return img, await judge(img.data, g, r, self.tax, self.spark, self.segmenter, self.meter)

    async def _inspect(self, image: bytes, g: Genome, r: Route, verdict: dict[str, Any]) -> dict[str, Any]:
        """S3a: the plan-blind critic protocol with two independent critics (critic.critics_for), plus SAM presence
        for planned parts. The judge's checklist still scores the render; it no longer decides inspect."""
        return await inspect(image, g, self.tax, critics_for(self.spark), self.segmenter, self.meter, r)

    async def _inspect_checklist(self, image: bytes, g: Genome, r: Route, verdict: dict[str, Any]) -> dict[str, Any]:
        """S2 inspect (the calibration baseline): SAM presence plus the judge's own checklist answers."""
        if verdict.get("checklist_source", "").startswith("known pair"):
            items = [Item(t, "pad", False) for t in verdict["checklist"]]
        else:
            items = [i for i in plan_items(g, self.tax) if i.text in verdict["checklist"]]
        return await inspect_checklist(image, g, self.tax, items, verdict["critic"], verdict["third_animal"],
                                       self.segmenter, self.meter)

    async def _judge_functions(self, g: Genome) -> None:
        """4.5b: one Muse Spark call for every audit function no card covers, before the render."""
        fns = uncovered(g)
        if not fns:
            return
        try:
            judged = await self.meter.call("spark", "audit", self.spark.judge_functions(plan_text(g, self.tax), fns))
        except ChimeraError as e:
            if e.code == ErrorCode.BUDGET_EXCEEDED:
                raise
            apply_judgment(g, None, f"{e.code.value}: {e.message[:120]}")
            return
        apply_judgment(g, judged)

    def _spark_log(self) -> list[dict[str, Any]]:
        return getattr(self.spark, "log", None) or []

    def providers(self, start: int) -> dict[str, Any]:
        """S2: which provider served each Spark call since `start`, plus the image and SAM models."""
        if self.mock:
            spark = {"by_call": {"all": [f"mock:{self.spark.model_id}"]}, "fallbacks": []}
        else:
            spark = summarize(self._spark_log()[start:])
        return {**spark, "render": f"meta:{self.renderer.model_id}", "segment": f"meta:{self.segmenter.model_id}"}

    async def realize(self, g: Genome, r: Route, refs: list[bytes], growth: str | None = None) -> dict[str, Any]:
        mark = _LOG_MARK.get()
        start = mark if mark is not None else len(self._spark_log())
        if growth == "edit" and has_covering(g):  # S3b: coverings only; a plan without one renders normally
            return await self._realize_growth(g, r, refs, start)
        await self._judge_functions(g)
        prompt = compile_prompt(g, self.tax)
        polished = await self.meter.call("spark", "polish", self.spark.polish(prompt))
        final, polish_reason = accept_polish(prompt, polished, g, self.tax)
        if not refs and self.mock:
            refs = [swatch(g.parents.sire), swatch(g.parents.dam)]  # the mock renderer needs references
        img, verdict = await self._render_and_judge(final, g, r, refs)
        attempts = [{"prompt": "compiled" if final == prompt else "polished", "critic": verdict["critic"],
                     "third_animal": verdict["third_animal"], "scores": verdict["scores"]}]
        warnings: list[str] = []
        first_key: str | None = None
        insp = await self._inspect(img.data, g, r, verdict)
        inspection: dict[str, Any] = {"before": insp, "edit": None, "after": None, "kept": "first"}
        if insp["failures"]:  # S2: one Muse Image edit turn, worded from the failed plan items, then inspect again
            instruction = edit_instruction(insp["failures"])
            first_key = f"evo/{g.id}.try1.webp"
            await self.services.storage.put(first_key, img.data, img.content_type)
            try:
                img2 = await self.meter.call("image", "edit", self.renderer.generate(instruction, [], "1:1",
                                                                                     img.response_id))
            except ChimeraError as e:
                if e.code == ErrorCode.BUDGET_EXCEEDED:
                    raise
                warnings.append(f"structural miss ({_texts(insp)}); edit turn failed: {e.code.value}: {e.message[:120]}")
            else:
                if self.mock:
                    self.registry.note(img2.data, f"{final} {instruction}")
                v2 = await judge(img2.data, g, r, self.tax, self.spark, self.segmenter, self.meter)
                insp2 = await self._inspect(img2.data, g, r, v2)
                inspection.update(edit={"instruction": instruction, "previous_response_id": img.response_id,
                                        "response_id": img2.response_id}, after=insp2)
                attempts.append({"prompt": "edit", "instruction": instruction, "critic": v2["critic"],
                                 "third_animal": v2["third_animal"], "scores": v2["scores"]})
                if insp2["structural_failures"] <= insp["structural_failures"]:
                    img, verdict, inspection["kept"] = img2, v2, "edited"
                else:
                    warnings.append("the edit left more structural misses than the first render: first render kept")
                if insp2["failures"]:
                    warnings.append(f"structural miss after one edit turn: {_texts(insp2)}")
        g = g.model_copy(update={"scores": verdict["scores"]})
        key = f"evo/{g.id}.webp"
        await self.services.storage.put(key, img.data, img.content_type)
        doc = {"genome": g.model_dump(), "prompt": final, "prompt_compiled": prompt, "image_key": key,
               "judge": verdict, "card": output_card(g, r, self.tax), "route": r.public(),
               "polish": f"rejected: {polish_reason}" if polish_reason else "accepted",
               "render_attempts": attempts, "first_image_key": first_key, "warnings": warnings, "ref_keys": [],
               "inspect": inspection, "response_id": img.response_id}
        doc["providers"] = self.providers(start)
        doc["card"]["providers"] = doc["providers"]  # S2: the provider of every call type is on the card
        self.store.put("creatures", g.id, doc)
        return doc

    async def _realize_growth(self, g: Genome, r: Route, refs: list[bytes], start: int) -> dict[str, Any]:
        """S3b growth by edit: host with its discrete parts first, one edit growing the covering, a drift check;
        on drift, the first-pass render of the full plan (the default compile). No repair edit follows: a second
        edit on a grown creature is one more chance to drift."""
        await self._judge_functions(g)
        if not refs and self.mock:
            refs = [swatch(g.parents.sire), swatch(g.parents.dam)]
        first_prompt = compile_prompt(host_first(g), self.tax)
        img1 = await self.meter.call("image", "render", self.renderer.generate(first_prompt, refs, "1:1"))
        if self.mock:
            self.registry.note(img1.data, first_prompt)
        first_key = f"evo/{g.id}.host.webp"
        await self.services.storage.put(first_key, img1.data, img1.content_type)
        instr = growth_instruction(g, self.tax)
        full = compile_prompt(g, self.tax)
        warnings: list[str] = []
        img2 = await self.meter.call("image", "edit", self.renderer.generate(instr, [], "1:1", img1.response_id))
        if self.mock:
            self.registry.note(img2.data, full)
        d = await growth_drift(img1.data, img2.data, critics_for(self.spark), self.meter)
        growth = {"first_prompt": first_prompt, "instruction": instr, "first_image_key": first_key,
                  "previous_response_id": img1.response_id, "drift": d, "used": not d["drifted"]}
        prompt_used = f"{first_prompt}\n\n[edit turn]\n{instr}"
        if d["drifted"]:
            growth["edit_image_key"] = f"evo/{g.id}.grown.webp"
            await self.services.storage.put(growth["edit_image_key"], img2.data, img2.content_type)
            warnings.append(f"growth edit drifted the host ({', '.join(d['changed'])}): first-pass render of the "
                            "full plan used instead")
            img = await self.meter.call("image", "render", self.renderer.generate(full, refs, "1:1"))
            if self.mock:
                self.registry.note(img.data, full)
            prompt_used = full
        else:
            img = img2
        verdict = await judge(img.data, g, r, self.tax, self.spark, self.segmenter, self.meter)
        insp = await self._inspect(img.data, g, r, verdict)
        if insp["failures"]:
            warnings.append(f"structural miss (growth mode makes no repair edit): {_texts(insp)}")
        g = g.model_copy(update={"scores": verdict["scores"]})
        key = f"evo/{g.id}.webp"
        await self.services.storage.put(key, img.data, img.content_type)
        doc = {"genome": g.model_dump(), "prompt": prompt_used, "prompt_compiled": full, "image_key": key,
               "judge": verdict, "card": output_card(g, r, self.tax), "route": r.public(), "polish": "not used (growth)",
               "render_attempts": [{"prompt": "growth" if growth["used"] else "first-pass fallback",
                                    "critic": verdict["critic"], "third_animal": verdict["third_animal"],
                                    "scores": verdict["scores"]}],
               "first_image_key": first_key, "warnings": warnings, "ref_keys": [],
               "inspect": {"before": insp, "edit": None, "after": None, "kept": "growth" if growth["used"] else
                           "first-pass"}, "response_id": img.response_id, "growth": growth}
        doc["providers"] = self.providers(start)
        doc["card"]["providers"] = doc["providers"]
        self.store.put("creatures", g.id, doc)
        return doc

    # ------------------------------------------------------------------ endpoints

    async def fuse(self, sire_name: str | None = None, dam_name: str | None = None, sire_image: bytes | None = None,
                   dam_image: bytes | None = None, myth: bool = False, host: str | None = None,
                   habitat: str | None = None, seed: int = 0, mode: str | None = None,
                   compare_with: str = "speculative", growth: str | None = None) -> dict[str, Any]:
        """mode: realistic, speculative (default), mythic, or compare (realistic plus `compare_with`, as a pair).
        The old `myth` flag still means mythic."""
        if mode == "compare":
            return await self._compare(sire_name, dam_name, sire_image, dam_image, host, habitat, seed, compare_with)
        design = mode or ("mythic" if myth else "speculative")
        if design not in DESIGN_MODES:
            raise ChimeraError(ErrorCode.VALIDATION_FAILED, f"Unknown mode {mode!r}.",
                               details={"modes": [*DESIGN_MODES, "compare"]})
        myth = design == "mythic"
        self._guard()
        before = self.meter.snapshot()
        token = _LOG_MARK.set(len(self._spark_log()))  # S2: this fuse's calls start here (identify and plan too)
        try:
            return await self._fuse(sire_name, dam_name, sire_image, dam_image, myth, host, habitat, seed, design,
                                    before, growth)
        finally:
            _LOG_MARK.reset(token)

    async def _fuse(self, sire_name: str | None, dam_name: str | None, sire_image: bytes | None,
                    dam_image: bytes | None, myth: bool, host: str | None, habitat: str | None, seed: int,
                    design: str, before: dict[str, int], growth: str | None = None) -> dict[str, Any]:
        sire = await self.resolve_parent(sire_name, sire_image, "sire")
        dam = await self.resolve_parent(dam_name, dam_image, "dam")
        if sire.id == dam.id:
            raise ChimeraError(ErrorCode.DUPLICATE_INPUTS, "Sire and dam are the same animal.")
        key = cache_key(sire.id, dam.id, myth, host, habitat, seed, design) + ("-growth" if growth == "edit" else "")
        hit = self.store.get("cache", key)
        if hit and (doc := self.store.get("creatures", hit["creature_id"])):
            return {**doc, "cached": True, "cache_key": key, "meta_calls": self.meter.since(before)}

        skeleton, r = self.seed_plan(sire, dam, myth, host, habitat, seed, design)
        model_note = "accepted"
        try:
            raw = await self.meter.call("spark", "first_plan", self.spark.write_plan(
                self.plan_prompt(skeleton, "Write the first plan for this pair."), skeleton.model_dump()))
            plan = validate_plan({**raw, "id": "pending"})
            if v := self._check(plan, r, final=False):
                raise ValueError("; ".join(f"{x.card}: {x.detail}" for x in v))
        except (ValueError, TypeError) as e:
            plan, model_note = skeleton, f"rejected, code skeleton used ({str(e)[:200]})"
        except ChimeraError as e:  # the plan call is optional: the code skeleton is already a valid plan
            if e.code == ErrorCode.BUDGET_EXCEEDED:
                raise
            plan, model_note = skeleton, f"call failed, code skeleton used ({e.code.value}: {e.message[:200]})"
        g = self.finish(plan, r)
        if v := self._check(g, r):  # cannot happen for code plans; guards the model path
            raise ChimeraError(ErrorCode.VALIDATION_FAILED, "Plan breaks a hard rule card.",
                               details={"violations": [x.public() for x in v]})
        refs = [i for i in (sire_image, dam_image) if i]
        doc = await (self.realize(g, r, refs, growth) if growth else self.realize(g, r, refs))
        self.store.put("cache", key, {"creature_id": g.id})
        return {**doc, "cached": False, "cache_key": key, "model_plan": model_note,
                "meta_calls": self.meter.since(before)}

    async def _compare(self, sire_name: str | None, dam_name: str | None, sire_image: bytes | None,
                       dam_image: bytes | None, host: str | None, habitat: str | None, seed: int,
                       other: str) -> dict[str, Any]:
        """Compare mode (E4): the realistic version and the user's other mode, rendered as a pair."""
        if other not in ("speculative", "mythic"):
            raise ChimeraError(ErrorCode.VALIDATION_FAILED, "compare_with must be speculative or mythic.")
        before = self.meter.snapshot()
        docs = []
        for m in ("realistic", other):
            docs.append(await self.fuse(sire_name, dam_name, sire_image, dam_image, host=host, habitat=habitat,
                                        seed=seed, mode=m))
        return {"mode": "compare", "modes": ["realistic", other], "pair": docs, "meta_calls": self.meter.since(before)}

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
        if v := self._check(plan, r, final=False):
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


def citation_verifier(mock: bool) -> Any:
    """S3a: live pages are fetched in code; mock mode serves a fixture page that holds every mock quote."""
    from app.evolution.citecheck import CitationVerifier, http_fetch

    if not mock:
        return CitationVerifier(http_fetch)

    async def fixture_page(url: str) -> str:
        from app.evolution.live import CITE_FIELDS

        subject = url.rstrip("/").rsplit("/", 1)[-1].replace("_", " ")  # the mock URL ends with the binomial
        return (f"<html><body><h1>{subject}</h1>" + " ".join(f"<p>mock evidence for {f}.</p>" for f in CITE_FIELDS)
                + "</body></html>")

    return CitationVerifier(fixture_page, extra_tiers={"example.org": 1})


def _texts(insp: dict[str, Any]) -> str:
    return "; ".join(f["text"] for f in insp["failures"])


def decode_image(b64: str | None) -> bytes | None:
    if not b64:
        return None
    try:
        return base64.b64decode(b64.split(",", 1)[-1], validate=True)
    except ValueError as e:
        raise ChimeraError(ErrorCode.IMAGE_CORRUPT, "image_b64 is not valid base64.") from e
