"""S2 part 5: route each Spark call type to its provider (data/evo_config.json `routing`; ROADMAP 5b).

Spark Open on Baseten takes identify, the checklist critic (full image and thumbnail), polish and the logged
open critic, each with its own output-token cap. Meta Spark 1.3 keeps the legacy full plan, plain and web-cited
traits, the function audit and vary. A Baseten failure (an error, or an unreadable answer such as one cut off at
its cap) falls back to Meta once, and the fallback is logged. A budget stop is never turned into a fallback.

Every routed call is appended to `log` ({call, provider, model, fallback}); the engine puts the slice for each
creature on its document and card. Each HTTP attempt's usage record also names its provider (usage.CallRecord).
"""

from __future__ import annotations

from typing import Any

from app.errors import ChimeraError
from app.evolution.data import config
from app.models.schemas import ErrorCode

METHODS = ("write_plan", "vary", "polish", "critic", "checklist", "identify", "learn_traits", "judge_functions",
           "cite_traits", "describe", "ask")
PURPOSE = {"identify": "evo_identify", "checklist": "evo_checklist", "polish": "evo_polish", "critic": "evo_critic",
           "write_plan": "evo_plan", "learn_traits": "evo_learn_traits", "judge_functions": "evo_audit",
           "cite_traits": "evo_cite_traits", "vary": "evo_vary",
           "describe": "evo_describe", "ask": "evo_ask"}


def routes() -> dict[str, Any]:
    return config()["routing"]


def provider_for(method: str) -> str:
    spec = routes().get(method) or {}
    return spec.get("provider", routes().get("fallback", "meta"))


def caps() -> dict[str, int]:
    """Output-token caps per request purpose, for the Baseten adapter."""
    return {PURPOSE[m]: int(spec["max_tokens"]) for m, spec in routes().items()
            if isinstance(spec, dict) and spec.get("max_tokens") and m in PURPOSE}


class RoutedSpark:
    """EvoSpark that sends each call type to its configured provider, with a logged fallback to Meta."""

    def __init__(self, meta: Any, baseten: Any | None) -> None:
        self.meta, self.baseten = meta, baseten
        self.model_id = f"routed({getattr(meta, 'model_id', 'meta')}, {getattr(baseten, 'model_id', 'none')})"
        self.log: list[dict[str, Any]] = []
        if baseten is not None:
            baseten.max_tokens = caps()

    def _pick(self, method: str) -> tuple[str, Any]:
        if provider_for(method) == "baseten" and self.baseten is not None:
            return "baseten", self.baseten
        return "meta", self.meta

    async def _call(self, method: str, *args: Any, **kw: Any) -> Any:
        provider, adapter = self._pick(method)
        entry: dict[str, Any] = {"call": method, "provider": provider, "model": adapter.model_id, "fallback": None}
        if provider == "meta" and provider_for(method) == "baseten":
            entry["fallback"] = "no Baseten adapter (BASETEN key missing): routed to Meta"
        try:
            out = await getattr(adapter, method)(*args, **kw)
        except ChimeraError as e:
            if provider != "baseten" or e.code == ErrorCode.BUDGET_EXCEEDED:
                self.log.append({**entry, "error": f"{e.code.value}: {e.message[:160]}"})
                raise
            reason = f"{e.code.value}: {e.message[:160]}"
        except (ValueError, KeyError, TypeError) as e:
            if provider != "baseten":
                raise
            reason = f"unreadable answer: {str(e)[:160]}"
        else:
            self.log.append(entry)
            return out
        self.log.append({**entry, "error": reason})
        fb = {"call": method, "provider": "meta", "model": self.meta.model_id, "fallback": f"Baseten failed ({reason})"}
        out = await getattr(self.meta, method)(*args, **kw)
        self.log.append(fb)
        return out

    async def write_plan(self, prompt: str, skeleton: dict[str, Any]) -> dict[str, Any]:
        return await self._call("write_plan", prompt, skeleton)

    async def vary(self, prompt: str, elites: list[dict[str, Any]], n: int, seed: int) -> list[dict[str, Any]]:
        return await self._call("vary", prompt, elites, n, seed)

    async def polish(self, prompt: str) -> str:
        return await self._call("polish", prompt)

    async def critic(self, image: bytes) -> dict[str, Any]:
        return await self._call("critic", image)

    async def checklist(self, image: bytes, items: list[str]) -> dict[str, Any]:
        return await self._call("checklist", image, items)

    async def identify(self, name: str | None = None, image: bytes | None = None) -> dict[str, Any]:
        return await self._call("identify", name=name, image=image)

    async def learn_traits(self, ident: dict[str, Any]) -> dict[str, Any]:
        return await self._call("learn_traits", ident)

    async def judge_functions(self, plan_text: str, functions: list[str]) -> list[dict[str, str]]:
        return await self._call("judge_functions", plan_text, functions)

    async def cite_traits(self, ident: dict[str, Any]) -> dict[str, Any]:
        return await self._call("cite_traits", ident)

    async def describe(self, image: bytes) -> dict[str, Any]:
        return await self._call("describe", image)

    async def ask(self, image: bytes, questions: list[str], parts: list[str] | None = None) -> dict[str, Any]:
        return await self._call("ask", image, questions, parts)


def summarize(log: list[dict[str, Any]]) -> dict[str, Any]:
    """For the card: which provider served each call type, and any fallbacks."""
    by: dict[str, list[str]] = {}
    fallbacks = []
    for e in log:
        if e.get("error"):
            continue
        by.setdefault(e["call"], [])
        tag = f"{e['provider']}:{e['model']}"
        if tag not in by[e["call"]]:
            by[e["call"]].append(tag)
        if e.get("fallback"):
            fallbacks.append({"call": e["call"], "reason": e["fallback"]})
    return {"by_call": by, "fallbacks": fallbacks}
