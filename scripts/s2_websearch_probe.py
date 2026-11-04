"""S2 part 4 probe: one Meta Responses API call with tools=[{"type": "web_search"}] and a strict JSON schema, to
learn where citations arrive. Writes the raw response (key-free) to docs/evolution/live/s2/probe/."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "evolution" / "live" / "s2" / "probe"
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT)
os.environ.update({"CHIMERA_LIVE_BUDGET_FILE": str(ROOT / "docs" / "live" / "budget.json"),
                   "CHIMERA_LIVE_LOG": str(ROOT / "docs" / "LIVE_LOG.md"), "CHIMERA_RECORD_DIR": str(OUT / "raw"),
                   "CHIMERA_LIVE_MAX_IMAGES": "80", "CHIMERA_LIVE_MAX_SPARK": "250", "CHIMERA_LIVE_MAX_SAM": "80",
                   "CHIMERA_LIVE_MAX_SPARK_BASETEN": "600"})

from app.adapters.meta.client import _MetaClient  # noqa: E402
from app.adapters.usage import current_step  # noqa: E402
from app.config import Settings  # noqa: E402
from app.errors import ChimeraError  # noqa: E402

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["body_mass_kg", "habitat"],
          "properties": {
              "body_mass_kg": {"type": "object", "additionalProperties": False,
                               "required": ["min", "max", "source_url", "evidence"],
                               "properties": {"min": {"type": "number"}, "max": {"type": "number"},
                                              "source_url": {"type": "string"}, "evidence": {"type": "string"}}},
              "habitat": {"type": "object", "additionalProperties": False, "required": ["value", "source_url", "evidence"],
                          "properties": {"value": {"type": "array", "items": {"type": "string"}},
                                         "source_url": {"type": "string"}, "evidence": {"type": "string"}}}}}


async def main() -> None:
    st = Settings(chimera_mode="real")
    http = _MetaClient(st.meta_api_base_url, st.meta_api_key or "", 180)
    body = {"model": st.meta_vision_model, "tools": [{"type": "web_search"}],
            "input": [{"role": "user", "content": [{"type": "input_text", "text":
                      "Use web search. For the axolotl (Ambystoma mexicanum): the typical adult body mass range in kg "
                      "and its natural habitat. For each field give the URL of the page you used and a short quote."}]}],
            "text": {"format": {"type": "json_schema", "name": "cited_probe", "strict": True, "schema": SCHEMA}}}
    current_step.set("s2:websearch_probe")
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        payload = await http.call("spark", "s2_websearch_probe", st.meta_vision_model, body, responses=True, raw=True)
    except ChimeraError as e:
        (OUT / "error.json").write_text(json.dumps({"error": f"{e.code.value}: {e.message}", "details": e.details},
                                                   indent=1, default=str), encoding="utf-8")
        print("ERROR", e.code.value, e.message, json.dumps(e.details, default=str)[:800])
        return
    (OUT / "response.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    for item in payload.get("output") or []:
        print("ITEM", item.get("type"), json.dumps({k: v for k, v in item.items() if k != "content"})[:600])
        for c in item.get("content") or []:
            print("  CONTENT", c.get("type"), str(c.get("text"))[:600])
            print("  ANNOTATIONS", json.dumps(c.get("annotations"))[:1500])
    print("usage", payload.get("usage"))


asyncio.run(main())
