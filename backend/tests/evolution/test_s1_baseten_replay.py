"""S1 part 2: recorded Spark Open (Baseten) responses replay through the engine's own parsers.

Fixtures in tests/fixtures/recorded/baseten/ are copies of docs/evolution/live/s1/spark/raw/ (key-free,
base64 and long reasoning elided). They pin what the live probe saw, so a parser change that would break
Spark Open answers shows up in mock mode."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.evolution import live

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "recorded" / "baseten"


def _rec(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def test_fixtures_are_key_free_and_name_the_exact_model():
    files = sorted(FIX.glob("*.json"))
    assert files
    for f in files:
        text = f.read_text(encoding="utf-8")
        assert "Bearer " not in text and "Authorization" not in text
        assert json.loads(text)["request"]["model"] == "meta-models/muse-spark-open-1026"


def test_identify_answer_parses():
    got = live.parse_identify_response(_rec("probe_json_identify-01.json")["response"])
    assert got["kind"] == "species" and got["scientific_name"].lower() == "ambystoma mexicanum"


def test_audit_answer_parses_one_entry_per_function():
    got = live.parse_audit_response(_rec("probe_json_audit-01.json")["response"], ["feeding", "heat"])
    assert [g["function"] for g in got] == ["feeding", "heat"]
    assert all(g["result"] in live.AUDIT_RESULTS for g in got)


def test_image_critic_answer_parses():
    got = live.parse_critic_response(_rec("probe_image_critic-01.json")["response"])
    assert got["creatures"] >= 1 and got["animals"]


@pytest.mark.parametrize("name", ["probe_tools-01.json"])
def test_tool_call_turn_has_parseable_arguments(name):
    msg = _rec(name)["response"]["choices"][0]["message"]
    calls = msg.get("tool_calls") or []
    assert calls and all(c["function"]["name"] in ("resolve_animal", "run_audit", "render") for c in calls)
    for c in calls:
        json.loads(c["function"]["arguments"])
