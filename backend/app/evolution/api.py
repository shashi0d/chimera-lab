"""Section 5: the evolution API, mounted under /evo so the current app keeps working."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.evolution.data import cards
from app.evolution.engine import EvoEngine, decode_image
from app.evolution.genome import validate_plan

router = APIRouter(prefix="/evo", tags=["evolution"])


class ParentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    image_b64: str | None = None

    @model_validator(mode="after")
    def _one(self) -> ParentIn:
        if bool(self.name) == bool(self.image_b64):
            raise ValueError("give exactly one of name or image_b64")
        return self


class FuseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sire: ParentIn
    dam: ParentIn
    myth: bool = False
    host: Literal["sire", "dam"] | None = None
    habitat: str | None = None
    seed: int = Field(default=0, ge=0)


class EvolveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    creature_id: str
    rounds: int = Field(default=3, ge=1, le=5)
    batch: int = Field(default=4, ge=1, le=8)


class EditIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    gene: str
    value: Any


def engine(request: Request) -> EvoEngine:
    eng = getattr(request.app.state, "evo", None)
    if eng is None:
        eng = EvoEngine(request.app.state.services)
        request.app.state.evo = eng
    return eng


def _validated(doc: dict[str, Any]) -> dict[str, Any]:
    validate_plan(doc["genome"])  # every plan an endpoint produces is validated by code
    return doc


@router.post("/fuse")
async def fuse(body: FuseIn, request: Request) -> dict[str, Any]:
    return _validated(await engine(request).fuse(
        sire_name=body.sire.name, dam_name=body.dam.name, sire_image=decode_image(body.sire.image_b64),
        dam_image=decode_image(body.dam.image_b64), myth=body.myth, host=body.host, habitat=body.habitat,
        seed=body.seed))


@router.post("/evolve")
async def evolve(body: EvolveIn, request: Request) -> dict[str, Any]:
    return await engine(request).evolve(body.creature_id, body.rounds, body.batch)


@router.post("/creature/{creature_id}/edit")
async def edit(creature_id: str, body: EditIn, request: Request) -> dict[str, Any]:
    return _validated(await engine(request).edit(creature_id, body.gene, body.value))


@router.get("/creature/{creature_id}")
async def get_creature(creature_id: str, request: Request) -> dict[str, Any]:
    return _validated(await engine(request).get(creature_id))


@router.get("/cards")
async def get_cards() -> dict[str, Any]:
    book = cards()
    return {"count": len(book.all()), "hard": book.hard_ids(),
            "cards": [{**c.__dict__, "applies_to": list(c.applies_to), "weight": None if c.hard else c.weight}
                      for c in book.all()]}
