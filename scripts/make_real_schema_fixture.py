"""Builds backend/tests/fixtures/chimera_data.real_schema.json from data/chimera_data.json (D1-05).

Rows are copied verbatim from the real file, so field names, list separators,
range strings and parent formats ("Panthera tigris (father)") are exact.
Run: python scripts/make_real_schema_fixture.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.data.rule_map import RULE_CHECKS  # noqa: E402

ANIMALS = ["lion", "tiger", "horse", "donkey", "bald eagle", "common octopus",
           "scarlet macaw", "red fox", "green iguana", "bottlenose dolphin"]
HYBRIDS = ["liger", "tigon", "mule", "hinny", "liliger"]
MYTHS = ["griffin", "chimera", "hippogriff", "sphinx"]
UNMAPPED_SAMPLE = ["R-A2-04", "R-A3-01", "R-A3-02", "R-A7-01", "R-A7-02", "R-A8-05"]


def main() -> None:
    src = json.loads((ROOT / "data" / "chimera_data.json").read_text(encoding="utf-8"))
    animals = [r for name in ANIMALS for r in src["animals"] if r["common_name"] == name]
    assert len(animals) == len(ANIMALS), "an animal is missing from the real file"
    ids = {r["animal_id"] for r in animals}
    genera = {r["scientific_name"].split()[0] for r in animals}
    tier2 = [r for r in src["tier2_animals"] if r["genus"] in genera][:6] + src["tier2_animals"][:2]
    out = {
        "meta": {**src["meta"], "name": "Real-schema test fixture (rows copied verbatim from chimera_data.json)",
                 "built_by": "scripts/make_real_schema_fixture.py"},
        "animals": animals,
        "tier2_animals": tier2,
        "measurements": [m for m in src["measurements"] if m["animal_id"] in ids],
        "hybrids": [h for name in HYBRIDS for h in src["hybrids"] if h["hybrid_id"] == name],
        "mythology": [m for name in MYTHS for m in src["mythology"] if m["creature_name"] == name],
        "rules": [r for r in src["rules"] if r["rule_id"] in RULE_CHECKS or r["rule_id"] in UNMAPPED_SAMPLE],
        "failure_modes": src["failure_modes"][:3],
        "design_principles": src["design_principles"][:3],
        "definitions": src["definitions"],
    }
    path = ROOT / "backend" / "tests" / "fixtures" / "chimera_data.real_schema.json"
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print({k: len(v) for k, v in out.items() if isinstance(v, list)}, "->", path)


if __name__ == "__main__":
    main()
