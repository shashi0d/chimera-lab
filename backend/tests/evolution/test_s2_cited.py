"""S2 part 4: web-cited traits (Meta Spark 1.3, Responses API, web_search), validated against class_parts.json.

A citation counts only when its URL is a page the model opened (or a url_citation) in the same response. Fields
without one stay "model-estimated". The live probe response is replayed through the real parser."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.errors import ChimeraError
from app.evolution import live
from app.models.schemas import ErrorCode

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "recorded" / "s2"


def _probe() -> dict:
    return json.loads((FIX / "websearch_probe_response.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ request and parser


def test_cite_request_uses_web_search_and_a_strict_cited_schema():
    body = live.build_cite_request("muse-spark-1.3", {"common_name": "axolotl", "scientific_name": "Ambystoma mexicanum"})
    assert body["tools"] == [{"type": "web_search"}] and body["text"]["format"]["strict"] is True
    schema = body["text"]["format"]["schema"]
    for f in live.CITE_FIELDS:
        assert set(schema["properties"][f]["properties"]) == {"value", "source_url", "evidence"}
    assert "never invent a URL" in body["instructions"]


def test_live_probe_response_parses_and_verifies_against_opened_pages():
    out = live.parse_cite_response(_probe())
    mass = out["citations"]["body_mass_kg"]
    assert mass["verified"] and "nationalgeographic.com" in mass["url"]
    assert out["traits"]["body_mass_kg"] == {"min": 0.06, "max": 0.227}
    assert out["traits"]["habitat"] == []  # "Lake Xochimilco" is not an engine habitat: cleaned out
    assert not out["citations"]["diet"]["verified"]  # not in the probe's schema: no citation
    assert len(out["opened"]) == 2 and len(out["searches"]) == 2


def test_a_url_the_model_never_opened_is_not_a_citation():
    p = _probe()
    msg = next(i for i in p["output"] if i.get("type") == "message" and i.get("phase") != "commentary")
    data = json.loads(msg["content"][0]["text"])
    data["body_mass_kg"]["source_url"] = "https://invented.example.com/axolotl"
    msg["content"][0]["text"] = json.dumps(data)
    msg["content"][0]["annotations"] = []
    assert not live.parse_cite_response(p)["citations"]["body_mass_kg"]["verified"]


def test_an_unfinished_or_unreadable_answer_raises():
    p = copy.deepcopy(_probe())
    p["status"] = "incomplete"
    with pytest.raises(ChimeraError):
        live.parse_cite_response(p)
    p = _probe()
    next(i for i in p["output"] if i.get("type") == "message" and i.get("phase") != "commentary")["content"][0]["text"] = "{"
    with pytest.raises(ChimeraError):
        live.parse_cite_response(p)


def test_clean_traits_removes_duplicates():
    out = live.clean_traits({"body_plan": ["quadruped", "biped", "quadruped"], "movement": ["walk", "walk"]})
    assert out["body_plan"] == ["quadruped", "biped"] and out["movement"] == ["walk"]


# ------------------------------------------------------------------ resolver: new animals


async def test_a_new_animal_stores_web_cited_fields_with_urls(engine):
    res = await engine.resolve("woolly mammoth")
    entry = engine.resolver.store.lookup("woolly mammoth")[0]
    assert entry["provenance"]["diet"] == "web-cited" and entry["citations"]["diet"]["url"].startswith("https://")
    assert entry["provenance"]["visible_features"] == "model-estimated" and "visible_features" not in entry["citations"]
    assert entry["traits_note"] == "12 of 13 fields web-cited (source tier and quote checked)"  # S3a
    assert res.animal.public()["citations"]["diet"] == entry["citations"]["diet"]["url"]


async def test_cited_traits_failure_falls_back_to_model_estimated(engine, monkeypatch):
    async def down(ident):
        raise ChimeraError(ErrorCode.UPSTREAM_TIMEOUT)

    monkeypatch.setattr(engine.spark, "cite_traits", down)
    await engine.resolve("woolly mammoth")
    entry = engine.resolver.store.lookup("woolly mammoth")[0]
    assert set(entry["provenance"][f] for f in ("diet", "habitat", "body_mass_kg")) == {"model-estimated"}
    assert "cited traits failed (UPSTREAM_TIMEOUT" in entry["traits_note"] and entry["citations"] == {}


async def test_a_budget_stop_is_not_swallowed(engine, monkeypatch):
    async def capped(ident):
        raise ChimeraError(ErrorCode.BUDGET_EXCEEDED, "cap", retryable=False)

    monkeypatch.setattr(engine.spark, "cite_traits", capped)
    with pytest.raises(ChimeraError):
        await engine.resolve("woolly mammoth")


# ------------------------------------------------------------------ re-resolve: matched, corrected, uncited


async def test_re_resolve_reports_matched_and_uncited(engine):
    await engine.resolve("woolly mammoth")
    rep = await engine.resolver.cite("woolly mammoth")
    status = {r["field"]: r["status"] for r in rep["fields"]}
    assert status["visible_features"] == "uncited" and status["diet"] == "matched"
    assert rep["source"] == "learned" and "learned_animals.json" in rep["stored"]


async def test_re_resolve_corrects_a_learned_value_and_logs_the_old_one(engine, monkeypatch):
    await engine.resolve("woolly mammoth")
    real = engine.spark.cite_traits

    async def differs(ident):
        out = await real(ident)
        out["traits"]["diet"] = "omnivore"
        return out

    monkeypatch.setattr(engine.spark, "cite_traits", differs)
    rep = await engine.resolver.cite("woolly mammoth")
    row = next(r for r in rep["fields"] if r["field"] == "diet")
    assert row["status"] == "corrected" and row["stored"] == "herbivore" and row["cited"] == "omnivore"
    entry = engine.resolver.store.lookup("woolly mammoth")[0]
    assert entry["traits"]["diet"] == "omnivore" and entry["provenance"]["diet"] == "web-cited"
    log = next(c for c in entry["corrections"] if c["field"] == "diet")
    assert log["was"] == "herbivore" and log["by"] == "web-cited" and log["url"]
    assert engine.tax.resolve("woolly mammoth").diet == "omnivore"


async def test_cited_values_are_still_checked_against_the_class(engine, monkeypatch):
    real = engine.spark.cite_traits

    async def winged(ident):
        out = await real(ident)
        out["traits"]["body_plan"] = ["multi_legged", "winged"]
        return out

    monkeypatch.setattr(engine.spark, "cite_traits", winged)
    await engine.resolve("rhinoceros beetle")
    rep = await engine.resolver.cite("rhinoceros beetle")
    row = next(r for r in rep["fields"] if r["field"] == "body_plan")
    assert row["cited"] == ["multi_legged"] and "Insecta body plans" in row["class_parts"]


async def test_a_database_animal_is_compared_not_overwritten(engine):
    rep = await engine.resolver.cite("axolotl")
    assert rep["source"] == "database" and "comparison only" in rep["stored"]
    row = next(r for r in rep["fields"] if r["field"] == "covering")
    assert row["stored"] == "skin" and row["status"] in ("matched", "corrected")
    assert engine.resolver.store.lookup("axolotl")[0] is None  # nothing written for a database animal
