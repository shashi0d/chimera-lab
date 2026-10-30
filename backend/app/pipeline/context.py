"""Per-run state shared by the pipeline steps, plus the spend guard."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.adapters.usage import CallRecord
from app.errors import ChimeraError
from app.models.schemas import ErrorCode, Graph, Run
from app.services import Services


@dataclass
class InputImage:
    slot: str  # "A" | "B"
    node_id: str
    asset_id: str
    data: bytes = b""
    sha256: str = ""


@dataclass
class RunContext:
    run: Run
    graph: Graph
    services: Services
    fault: str | None = None
    inputs: list[InputImage] = field(default_factory=list)
    state: dict[str, Any] = field(default_factory=dict)
    vision_calls: int = 0
    generations: int = 0
    calls: list[CallRecord] = field(default_factory=list)  # real model calls (L1-04)

    @property
    def run_tokens(self) -> int:
        return sum(c.total_tokens for c in self.calls)

    async def check_tokens(self) -> None:
        """L1-04: token caps per run and per day, checked before every paid attempt."""
        settings = self.services.settings
        if self.run_tokens >= settings.max_tokens_per_run:
            raise ChimeraError(ErrorCode.BUDGET_EXCEEDED, "This run reached its token limit.")
        day = datetime.now(UTC).strftime("%Y-%m-%d")
        if await self.services.db.incr(f"tokens:{day}", 0) >= settings.daily_token_cap:
            raise ChimeraError(ErrorCode.BUDGET_EXCEEDED, "Today's model token budget is used up.")

    # ----------------------------------------------------------- spend guard

    def can_use_vision(self) -> bool:
        return self.vision_calls < self.services.settings.max_vision_calls_per_run

    def can_generate(self) -> bool:
        return self.generations < self.services.settings.max_generations_per_run

    async def use_vision(self) -> None:
        if not self.can_use_vision():
            raise ChimeraError(ErrorCode.BUDGET_EXCEEDED, "This run reached its limit of vision calls.")
        await self.check_tokens()
        self.vision_calls += 1

    async def use_generation(self) -> None:
        settings = self.services.settings
        if self.fault == "budget":
            raise ChimeraError(ErrorCode.BUDGET_EXCEEDED, "Today's image generation budget is used up.")
        if not self.can_generate():
            raise ChimeraError(ErrorCode.BUDGET_EXCEEDED, "This run reached its limit of image generations.")
        await self.check_tokens()
        day = datetime.now(UTC).strftime("%Y-%m-%d")
        used = await self.services.db.incr(f"generations:{day}")
        if used > settings.daily_generation_cap:
            raise ChimeraError(ErrorCode.BUDGET_EXCEEDED, "Today's image generation budget is used up.")
        self.generations += 1
