"""Muse Spark Open on Baseten (S1): the existing evolution Spark interface over a second provider.

Baseten serves ``meta-models/muse-spark-open-1026`` through OpenAI-compatible chat completions at
``https://inference.baseten.co/v1``. Everything except the endpoint, the key and the budget kind is
shared with the Meta adapter: the request builders and parsers in ``app.evolution.live``, the
``_MetaClient`` attempt wrapper (live-budget guard before every attempt, a usage record after it,
key-free recordings), the error mapping and ``call_with_retry`` as the only retry layer.

Every attempt counts against the ``spark_baseten`` budget kind (``CHIMERA_LIVE_MAX_SPARK_BASETEN``,
default 300, a runaway guard only). No route uses this adapter yet (S1 is a probe; the routing
switch is a later step).
"""

from __future__ import annotations

from typing import Any

from app.adapters.meta.client import _MetaClient
from app.adapters.usage import CallKind
from app.config import Settings
from app.evolution.live import LiveEvoSpark, _Retrying

KIND: CallKind = "spark_baseten"


class BasetenEvoSpark(LiveEvoSpark):
    """EvoSpark (write_plan, polish, critic, checklist, identify, learn_traits, judge_functions) on Spark Open."""

    kind: CallKind = KIND

    def __init__(self, settings: Settings) -> None:
        if not settings.baseten_api_key:
            raise RuntimeError("Spark Open needs BASETEN_API_KEY_MODEL_MUSE_SPARK_OPEN_26")
        _Retrying.__init__(self, settings, settings.baseten_timeout_seconds)  # reasoning model: slower
        self.model_id = settings.baseten_spark_model
        self.http = _MetaClient(settings.baseten_base_url, settings.baseten_api_key, self.timeout)
        self.max_tokens: dict[str, int] = {}  # S2: output cap per request purpose (evo_config routing)

    async def _chat(self, purpose: str, body: dict[str, Any]) -> dict[str, Any]:
        """Every Spark Open call carries its purpose's output-token cap (reasoning tokens count toward it)."""
        if purpose in self.max_tokens and "max_tokens" not in body:
            body = {**body, "max_tokens": self.max_tokens[purpose]}
        return await super()._chat(purpose, body)

    async def chat(self, purpose: str, body: dict[str, Any], retry: bool = True) -> dict[str, Any]:
        """One raw chat-completions call (probes: tool calling, refusal checks). The body's model is forced
        to the configured model so a probe can never reach a different one."""
        body = {**body, "model": self.model_id}
        if retry:
            return await self._chat(purpose, body)
        return await self.http.call(self.kind, purpose, self.model_id, body)
