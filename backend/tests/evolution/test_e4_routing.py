"""E4 step 2: routing for any pair, by taxonomy distance, with precedent only from data files."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.evolution.data import known_pairs, taxonomy
from app.evolution.resolve import animal_from_entry
from app.evolution.route import KIND, LABEL_CHIMERA, LABEL_CLOSE, LABEL_HYBRID, LABEL_MYTHIC, route, taxonomy_distance

EVO = Path(__file__).resolve().parents[2] / "app" / "evolution"


def _learned(aid: str, sci: str, cls: str, order: str, family: str, genus: str, claims: list[str] | None = None,
             known: bool = True):
    return animal_from_entry({
        "id": aid, "common_name": aid.replace("_", " "), "scientific_name": sci,
        "taxonomy": {"class": cls, "order": order, "family": family, "genus": genus} if known else {},
        "traits": {"body_plan": ["quadruped"], "covering": "fur", "body_mass_kg": {"min": 10, "max": 20}},
        "claims": claims or [], "provenance": {}})


A = ("alpha_cat", "Felis alpha", "Mammalia", "Carnivora", "Felidae", "Felis")
B = ("beta_cat", "Felis beta", "Mammalia", "Carnivora", "Felidae", "Felis")
C = ("gamma_cat", "Leptailurus gamma", "Mammalia", "Carnivora", "Felidae", "Leptailurus")


def test_unknown_same_genus_pair_is_a_hybrid_candidate(tax):
    r = route(_learned(*A), _learned(*B), tax)
    assert r.mode == "hybrid" and r.labels == [LABEL_CLOSE] and r.pair is None
    assert r.reason == "same genus (Felis): hybrid candidate" and r.distance == {"shared_rank": "genus", "steps": 1}


def test_unknown_same_family_pair_is_a_chimera(tax):
    r = route(_learned(*A), _learned(*C), tax)
    assert r.mode == "chimera" and r.labels == [LABEL_CHIMERA] and r.distance["shared_rank"] == "family"


def test_a_model_claim_of_a_cross_is_never_precedent(tax):
    claimed = _learned(*A[:5], "Felis", claims=["Leptailurus gamma"])
    assert claimed.claims == ("documented cross with Leptailurus gamma (unverified claim)",)
    r = route(claimed, _learned(*C), tax)
    assert r.mode == "chimera" and LABEL_HYBRID not in r.labels


def test_unknown_taxonomy_routes_as_a_speculative_chimera_even_with_a_shared_genus_word(tax):
    a = _learned("x_one", "Felis alpha", "", "", "", "", known=False)
    b = _learned("x_two", "Felis beta", "", "", "", "", known=False)
    r = route(a, b, tax)
    assert r.mode == "chimera" and LABEL_CHIMERA in r.labels and "taxonomy unknown" in r.reason
    assert r.distance == {"shared_rank": "unknown", "steps": None}


def test_documented_cross_comes_only_from_data(tax):
    r = route(tax.animals["lion"], tax.animals["tiger"], tax)
    assert r.mode == "hybrid" and r.pair and r.labels == [LABEL_HYBRID]
    documented = next(iter(tax.documented))
    assert all(isinstance(x, str) for x in documented)


@pytest.mark.parametrize("a,b,rank", [("lion", "tiger", "genus"), ("lion", "cheetah", "family"),
                                      ("lion", "eagle", "beyond class"), ("brown_bear", "polar_bear", "genus")])
def test_taxonomy_distance(tax, a, b, rank):
    assert taxonomy_distance(tax.resolve(a), tax.resolve(b))["shared_rank"] == rank


def test_mythic_kind_vocabulary(tax):
    r = route(tax.animals["lion"], tax.animals["golden_eagle"], tax, myth=True)
    assert r.labels[0] == LABEL_MYTHIC == "mythic composite" and r.public()["kind"] == "mythic composite"
    assert set(KIND.values()) == {"hybrid", "chimera", "mythic composite"}  # RC-R9-01


async def test_fuse_any_pair_of_learned_animals(engine):
    doc = await engine.fuse(sire_name="rhinoceros beetle", dam_name="pangolin")
    assert doc["route"]["mode"] == "chimera" and doc["route"]["distance"]["shared_rank"] == "beyond class"


def test_no_animal_or_pair_is_hard_coded_in_engine_logic():
    """Pair and animal knowledge lives in data files. String literals in engine code (docstrings excluded)
    never name a database animal or a known pair (E4 found and moved two: RC-R2-08 and RC-R2-11 checks)."""
    tax = taxonomy()
    names = {a.id for a in tax.animals.values()} | {a.common_name.lower() for a in tax.animals.values()}
    names |= {p["id"] for p in known_pairs()} | {p["name"].lower() for p in known_pairs()}
    hits = []
    for path in EVO.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = {id(n.body[0].value) for n in ast.walk(tree)
                      if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                      and n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
                if node.value.strip().lower() in names:
                    hits.append(f"{path.name}:{node.lineno} {node.value!r}")
    assert not hits, hits
