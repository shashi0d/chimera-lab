"""Mock mode: the contract fixtures (docs/api_fixtures/) that X-Mock-Scenario replays through the real job runner,
event store and SSE path."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

RUN_SCENARIOS = {"success": "run_success.json", "host_tie": "run_host_tie.json", "cap": "run_cap.json",
                 "error": "run_error.json", "queued": "run_queued.json"}
REFUSED = {"refused_human": 0, "refused_type": 1, "refused_size": 2, "refused_animal": 3}  # upload_refused cases
# Contract scenarios plus three extensions: refused_animal (NOT_AN_ANIMAL case), cap_daily (POST 429 and capped
# limits), agent (the real agent loop with the mock adapters and the policy brain, real identify of the photos).
SCENARIOS = (*RUN_SCENARIOS, "identify_choice", *REFUSED, "cap_daily", "agent")


@lru_cache(maxsize=32)
def _load(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load(root: Path, name: str) -> dict[str, Any]:
    return _load(str(root / name))
