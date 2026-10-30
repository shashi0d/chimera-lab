from app.data.loader import load_data
from app.models.schemas import AnimalReading
from app.pipeline.steps import rules_check
from app.pipeline.steps.compile import build_prompt
from app.pipeline.steps.match import match_reading
from tests.conftest import FIXTURES

DATA = load_data(FIXTURES / "chimera_data.sample.json")
# The checks the sample file's rules name (the sample predates the real-schema checks).
SAMPLE_CHECKS = {r["check"] for r in DATA.rules}


def side(common, sci, plan="quadruped"):
    r = AnimalReading(is_animal=True, common_name=common, scientific_name=sci, body_plan=plan)
    return (r, match_reading(DATA, r))


def test_match_prefers_scientific_then_name_then_genus():
    r = AnimalReading(is_animal=True, common_name="Something odd", scientific_name="Panthera leo")
    assert match_reading(DATA, r).matched_on == "scientific_name"
    r = AnimalReading(is_animal=True, common_name="Red fox", scientific_name=None)
    assert match_reading(DATA, r).animal_id == "red_fox"
    r = AnimalReading(is_animal=True, common_name="Clouded thing", scientific_name="Panthera nebulosa")
    m = match_reading(DATA, r)
    assert m.matched_on == "genus" and m.tier == 1
    assert match_reading(DATA, AnimalReading(is_animal=True, common_name="Quokka")) is None


def test_lion_tiger_same_genus_no_anatomy_warnings():
    a, b = side("Lion", "Panthera leo"), side("Tiger", "Panthera tigris")
    hits = {name for name in SAMPLE_CHECKS if rules_check.CHECKS[name].fn(rules_check.RuleInput(a, b))}
    assert hits == {"same_genus"}


def test_octopus_lion_triggers_anatomy_and_realm_rules():
    a, b = side("Common octopus", "Octopus vulgaris", "cephalopod"), side("Lion", "Panthera leo")
    hits = {name for name in SAMPLE_CHECKS if rules_check.CHECKS[name].fn(rules_check.RuleInput(a, b))}
    assert {"body_plan_mismatch", "limb_count_mismatch", "boneless_parent", "realm_conflict",
            "class_distance"} <= hits


def test_mass_ratio_uses_range_bounds():
    a, b = side("Scarlet macaw", "Ara macao", "avian"), side("Lion", "Panthera leo")
    assert rules_check.mass_ratio(a, b)  # 1.4 kg * 20 < 126 kg
    assert rules_check.flight_mass(a, b)
    a2 = side("Red fox", "Vulpes vulpes")
    assert not rules_check.mass_ratio(a2, side("Green iguana", "Iguana iguana"))


def test_unmatched_parent_never_crashes_rules():
    a = (AnimalReading(is_animal=True, common_name="Quokka", body_plan="quadruped"), None)
    b = side("Lion", "Panthera leo")
    for check in rules_check.CHECKS.values():
        check.fn(rules_check.RuleInput(a, b))


def test_prompt_names_each_reference_and_its_parts():
    prompt = build_prompt({"head": "A", "body": "B", "limbs": "B", "covering": "A", "tail": "A"},
                          {"A": "lion", "B": "scarlet macaw"}, "avian", ["Keep it light."])
    assert "Reference image 1 shows a lion. Use it only for the head, skin covering and tail." in prompt
    assert "Reference image 2 shows a scarlet macaw. Use it only for the torso and limbs." in prompt
    assert "avian body plan" in prompt and "Keep it light." in prompt and "no text" in prompt
