import json

from app.data.loader import load_data, parse_range, split_list
from tests.conftest import FIXTURES

SAMPLE = FIXTURES / "chimera_data.sample.json"


def test_sample_has_expected_shape():
    raw = json.loads(SAMPLE.read_text())
    for section in ["meta", "animals", "tier2_animals", "measurements", "hybrids", "mythology", "rules",
                    "failure_modes", "design_principles", "definitions"]:
        assert section in raw
    assert len(raw["animals"]) == 10 and len(raw["hybrids"]) == 3 and len(raw["rules"]) == 10


def test_lookup_by_name_scientific_genus_and_alias():
    data = load_data(SAMPLE)
    assert data.find_by_name("lion")[0]["id"] == "lion"
    assert data.find_by_name("African lion")[0]["id"] == "lion"
    assert data.find_by_scientific("panthera tigris")[0]["id"] == "tiger"
    row, tier = data.find_by_genus("Panthera")
    assert tier == 1
    assert data.find_by_scientific("Ambystoma mexicanum")[1] == 2


def test_hybrids_by_unordered_pair_exact_first():
    data = load_data(SAMPLE)
    assert [h.row["id"] for h in data.find_hybrids("lion", "tiger")] == ["liger", "tigon"]
    assert [h.row["id"] for h in data.find_hybrids("tiger", "lion")] == ["tigon", "liger"]
    assert data.find_hybrids("lion", "red_fox") == []


def test_ranges_and_lists_stay_strings_never_midpoints():
    assert parse_range("126-272") == (126.0, 272.0)
    assert parse_range("45") == (45.0, 45.0)
    assert parse_range("") is None
    assert split_list("a| b |c") == ["a", "b", "c"]
    data = load_data(SAMPLE)
    assert data.measurements_for("lion")[0]["body_mass_kg"] == "126-272"


def test_missing_file_falls_back_to_sample(tmp_path):
    data = load_data(tmp_path / "nope.json")
    assert data.source == "sample"
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert load_data(bad).source == "sample"
