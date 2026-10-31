"""E2 review fixes: the close-relative label wording, and the guanaco binomial (Lama guanicoe)."""

from __future__ import annotations

import pytest

from app.evolution.route import LABEL_CLOSE, LABEL_HYBRID, route
from tests.evolution.conftest import plan_for


def test_close_relative_label_says_speculative():
    assert LABEL_CLOSE == "speculative hybrid of close relatives, no documented cross"


def test_same_genus_pair_without_a_record_gets_the_close_label(engine, tax):
    g, r = plan_for(engine, "guanaco", "llama")
    assert r.mode == "hybrid" and r.pair is None
    assert r.reason == "same genus (Lama)"
    assert r.labels == [LABEL_CLOSE]
    assert LABEL_CLOSE in g.labels


def test_guanaco_and_llama_have_distinct_binomials(tax):
    assert tax.animals["guanaco"].scientific_name == "Lama guanicoe"
    assert tax.animals["llama"].scientific_name == "Lama glama"
    assert tax.resolve("Lama guanicoe").id == "guanaco"
    assert tax.resolve("Lama glama").id == "llama"


@pytest.mark.parametrize("dam", ["guanaco", "llama"])
def test_cama_override_resolves_for_both_dams(tax, dam):
    r = route(tax.animals["dromedary_camel"], tax.animals[dam], tax)
    assert r.mode == "hybrid" and r.pair is not None and r.pair["id"] == "cama"
    assert r.labels == [LABEL_HYBRID]
    assert r.pair["traits"]["feet"]["donor"] == dam  # role "dam" resolved to the animal id
