"""E4 step 1: the open-world resolver, in mock mode (mock Spark knowledge plus recorded GBIF responses).

Order: database, learned cache, open world (Spark identifies, GBIF confirms with an EXACT species match,
Spark fills model-estimated traits). Refusals: not an animal, plant, human, mythic parent. GBIF down:
taxonomy unknown, routed as a chimera with the speculative label.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from app.errors import ChimeraError
from app.evolution.engine import EvoEngine
from app.evolution.gbif import FixtureGbif, GbifClient, GbifUnavailable, accepted
from app.evolution.resolve import MODEL, LearnedStore
from app.evolution.route import LABEL_CHIMERA, route
from app.services import build_services
from tests.conftest import IMAGES, make_settings


def _engine(tmp_path, **kw) -> EvoEngine:
    return EvoEngine(build_services(make_settings(tmp_path, **kw)))


def _learned(eng: EvoEngine) -> dict[str, Any]:
    return json.loads(eng.resolver.store.path.read_text(encoding="utf-8"))


# ------------------------------------------------------------------ database and learned cache


async def test_in_database_costs_nothing(engine):
    res = await engine.resolve("jaguar")
    assert res.status == "resolved" and res.source == "database" and res.animal.id == "jaguar"
    assert res.taxonomy_source == res.traits_source == "chimera_data.json"
    assert engine.meter.counts == {"spark": 0, "image": 0, "sam": 0} and engine.gbif.calls == []
    prov = res.animal.public()["provenance"]
    assert prov["family"] == "chimera_data.json" and "project default" in prov["breathing"]


async def test_exact_match_learns_and_the_cache_is_reused(tmp_path):
    eng = _engine(tmp_path)
    res = await eng.resolve("woolly mammoth")
    assert res.status == "resolved" and res.source == "open_world" and res.taxonomy_source == "gbif"
    a = res.animal
    assert (a.scientific_name, a.tax_class, a.order, a.family, a.genus) == (
        "Mammuthus primigenius", "Mammalia", "Proboscidea", "Elephantidae", "Mammuthus")
    assert a.gbif_key == "4825833" and a.mouthparts == "grinding teeth" and a.breathing == "lungs"
    prov = a.public()["provenance"]
    assert prov["family"] == "gbif" and prov["diet"] == MODEL and prov["breathing"] == MODEL
    assert eng.meter.counts["spark"] == 2 and eng.gbif.calls == ["Mammuthus primigenius"]
    entry = _learned(eng)["animals"]["woolly_mammoth"]
    assert entry["learned_at"] and entry["provenance"]["class"] == "gbif"

    eng2 = _engine(tmp_path)  # a new engine reads the cache: no Spark, no GBIF
    again = await eng2.resolve("woolly mammoth")
    assert again.source == "learned" and again.animal.scientific_name == "Mammuthus primigenius"
    assert eng2.meter.counts["spark"] == 0 and eng2.gbif.calls == []


async def test_tier2_species_uses_the_stored_gbif_row(tmp_path):
    eng = _engine(tmp_path)
    res = await eng.resolve("sunda pangolin")  # Manis javanica is in chimera_data.json tier2_animals
    assert res.taxonomy_source == "chimera_data.json tier2 (gbif)" and eng.gbif.calls == []
    assert res.animal.family == "Manidae" and res.animal.mouthparts == "toothless tongue"


async def test_learned_entries_are_never_silently_overwritten(tmp_path):
    store = LearnedStore(tmp_path / "learned.json")
    first, new1 = store.add({"id": "x", "common_name": "x", "scientific_name": "A b", "v": 1})
    second, new2 = store.add({"id": "x", "common_name": "x", "scientific_name": "A b", "v": 2})
    assert new1 and not new2 and second["v"] == 1
    assert json.loads((tmp_path / "learned.json").read_text())["animals"]["x"]["v"] == 1


async def test_misspelling_resolves_to_the_database_animal_and_is_remembered(tmp_path):
    eng = _engine(tmp_path)
    res = await eng.resolve("jagwar")
    assert res.status == "resolved" and res.animal.id == "jaguar" and res.source == "database"
    assert "read 'jagwar' as the jaguar" in res.note
    assert eng.meter.counts["spark"] == 1 and eng.gbif.calls == []  # known binomial: no GBIF, no trait call
    eng2 = _engine(tmp_path)
    assert (await eng2.resolve("jagwar")).animal.id == "jaguar" and eng2.meter.counts["spark"] == 0


async def test_breed_takes_species_taxonomy_and_keeps_its_look(engine):
    res = await engine.resolve("golden retriever")
    a = res.animal
    assert res.status == "resolved" and res.kind == "breed" and a.kind == "breed"
    assert a.scientific_name == "Canis lupus familiaris" and a.family == "Canidae" and a.genus == "Canis"
    assert "dense golden double coat" in a.features and "breed of Canis lupus familiaris" in res.note


async def test_extinct_species(engine):
    res = await engine.resolve("woolly mammoth")
    assert res.status == "resolved" and res.kind == "extinct" and res.animal.kind == "extinct"
    assert res.animal.family == "Elephantidae" and "extinct" in res.note


async def test_ambiguous_picks_the_most_common_and_returns_alternatives(tmp_path):
    eng = _engine(tmp_path)
    res = await eng.resolve("pangolin")
    assert res.status == "resolved" and res.kind == "ambiguous"
    assert res.animal.common_name == "Sunda pangolin" and "names several species" in res.note
    assert {x["scientific_name"] for x in res.alternatives} >= {"Phataginus tricuspis", "Manis pentadactyla"}
    again = await _engine(tmp_path).resolve("pangolin")  # the stated choice and alternatives survive the cache
    assert again.source == "learned" and again.alternatives and "names several species" in again.note


@pytest.mark.parametrize("name,kind,words", [
    ("rock", "not_animal", "is not an animal"),
    ("oak tree", "plant", "is a plant"),
    ("human", "human", "Humans are not used"),
    ("dragon", "mythic", "mythic creature"),
])
async def test_refusals(engine, name, kind, words):
    res = await engine.resolve(name)
    assert res.status == "refused" and res.kind == kind and words in res.note and res.animal is None


async def test_mythic_parent_from_data_is_refused_without_a_call_and_suggests_mythic_mode(engine):
    res = await engine.resolve("griffin")
    assert res.status == "refused" and res.kind == "mythic"
    assert "mythic mode" in res.suggestion and "eagle x lion" in res.suggestion
    assert engine.meter.counts["spark"] == 0


@pytest.mark.parametrize("name,why", [("manis javanicus", "FUZZY"), ("notarealus", "NONE")])
async def test_no_exact_match_needs_a_choice(tmp_path, name, why):
    eng = _engine(tmp_path)
    res = await eng.resolve(name)
    assert res.status == "needs_choice" and why in res.note and "does not guess" in res.note
    assert res.animal is None and not eng.resolver.store.path.exists()  # nothing learned


def test_genus_level_exact_is_not_a_species():
    rec = json.loads((FixtureGbif().root / "Pangolin.json").read_text())["response"]
    assert rec["matchType"] == "EXACT" and not accepted(rec)


async def test_gbif_down_falls_back_to_unknown_taxonomy_and_chimera(tmp_path):
    eng = _engine(tmp_path)
    eng.resolver.gbif = FixtureGbif(online=False)
    res = await eng.resolve("rhinoceros beetle")
    a = res.animal
    assert res.status == "resolved" and res.taxonomy_source.startswith("unknown")
    assert a.tax_class == "" and a.genus == "" and not a.taxonomy_known
    assert not eng.resolver.store.path.exists()  # not saved: learn it properly when GBIF is back
    r = route(a, eng.tax.animals["brown_bear"], eng.tax)
    assert r.mode == "chimera" and LABEL_CHIMERA in r.labels


async def test_tier2_taxonomy_needs_no_gbif_call(tmp_path, monkeypatch):
    eng = _engine(tmp_path)
    row = next(iter(eng.tax.tier2.values()))

    async def ident(name=None, image=None):
        return {"kind": "species", "scientific_name": row["scientific_name"], "common_name": "tier two animal",
                "breed": "", "alternatives": [], "note": ""}

    async def traits(ident):
        from app.evolution.adapters import open_world

        return open_world()["traits"]["Manis javanica"]

    monkeypatch.setattr(eng.resolver.spark, "identify", ident)
    monkeypatch.setattr(eng.resolver.spark, "learn_traits", traits)
    res = await eng.resolve("tier two animal")
    assert res.taxonomy_source == "chimera_data.json tier2 (gbif)" and eng.gbif.calls == []
    assert res.animal.family == row["family"] and res.animal.genus == row["genus"]


async def test_photo_is_identified_by_spark(engine):
    res = await engine.resolve(image=(IMAGES / "lion.jpg").read_bytes())
    assert res.status == "resolved" and res.animal is not None and engine.meter.counts["spark"] >= 1


async def test_model_claims_of_crosses_are_unverified(engine):
    res = await engine.resolve("golden retriever")
    assert res.animal.claims == ("documented cross with Canis lupus (unverified claim)",)


# ------------------------------------------------------------------ engine and API


async def test_fuse_refuses_with_the_resolution_in_details(engine):
    with pytest.raises(ChimeraError) as e:
        await engine.fuse(sire_name="griffin", dam_name="lion")
    assert e.value.details["resolution"]["status"] == "refused"


async def test_resolve_endpoint(client):
    r = await client.post("/evo/resolve", json={"name": "pangolin"})
    assert r.status_code == 200 and r.json()["status"] == "resolved" and r.json()["alternatives"]
    r = await client.post("/evo/resolve", json={"name": "notarealus"})
    assert r.status_code == 200 and r.json()["status"] == "needs_choice"


# ------------------------------------------------------------------ GBIF client


async def test_gbif_client_exact_and_retry_then_unavailable():
    hits: list[str] = []

    def ok(request: httpx.Request) -> httpx.Response:
        hits.append(str(request.url))
        return httpx.Response(200, json={"matchType": "EXACT", "rank": "SPECIES", "kingdom": "Animalia",
                                         "class": "Mammalia", "usageKey": 1})

    client = GbifClient(transport=httpx.MockTransport(ok), base_delay=0.0)
    m = await client.match("Manis javanica")
    assert accepted(m) and "strict=true" in hits[0] and "kingdom=Animalia" in hits[0]
    assert client.recorded[0]["response"]["usageKey"] == 1

    calls: list[int] = []

    def down(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503)

    with pytest.raises(GbifUnavailable):
        await GbifClient(transport=httpx.MockTransport(down), base_delay=0.0, attempts=2).match("Manis javanica")
    assert len(calls) == 2  # retried once, then the offline fallback takes over
