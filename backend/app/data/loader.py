"""Loader and query helpers for chimera_data.json.

The full file is placed by Shashi; the schema was inferred from TASKSHEET 5.4,
so field lookups go through `field()` which accepts a few spellings. Values
are kept as strings: `|` lists are split on read, ranges like "126-272" are
never turned into midpoints.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from dataclasses import field as dc_field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

SAMPLE_PATH = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "chimera_data.sample.json"

ALIASES: dict[str, tuple[str, ...]] = {
    "id": ("id", "animal_id", "slug", "key"),
    "common_name": ("common_name", "commonName", "name", "common"),
    "scientific_name": ("scientific_name", "scientificName", "binomial", "species"),
    "aliases": ("aliases", "other_names", "synonyms"),
    "genus": ("genus",),
    "class": ("class", "taxon_class", "taxonomic_class"),
    "body_plan": ("body_plan", "bodyPlan", "plan"),
    "parent_a": ("parent_a", "parentA", "sire", "parent_1"),
    "parent_b": ("parent_b", "parentB", "dam", "parent_2"),
    "animal_id": ("animal_id", "animalId", "id"),
}


def field(row: dict[str, Any], name: str, default: str = "") -> str:
    for key in ALIASES.get(name, (name,)):
        if key in row and row[key] not in (None, ""):
            return str(row[key])
    return default


def split_list(value: str | None) -> list[str]:
    return [v.strip() for v in (value or "").split("|") if v.strip()]


def parse_range(value: str | None) -> tuple[float, float] | None:
    """'126-272' -> (126.0, 272.0); '45' -> (45.0, 45.0). Never a midpoint."""
    if not value:
        return None
    nums = re.findall(r"\d+(?:\.\d+)?", str(value))
    if not nums:
        return None
    lo, hi = float(nums[0]), float(nums[-1])
    return (min(lo, hi), max(lo, hi))


def norm(s: str | None) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (s or "").lower()).strip()


@dataclass
class ChimeraData:
    raw: dict[str, Any]
    source: str  # "full" | "sample"
    _by_name: dict[str, tuple[dict[str, Any], int]] = dc_field(default_factory=dict)
    _by_sci: dict[str, tuple[dict[str, Any], int]] = dc_field(default_factory=dict)
    _by_genus: dict[str, tuple[dict[str, Any], int]] = dc_field(default_factory=dict)
    _by_id: dict[str, tuple[dict[str, Any], int]] = dc_field(default_factory=dict)

    def __post_init__(self) -> None:
        for tier, section in ((2, "tier2_animals"), (1, "animals")):  # tier 1 indexed last so it wins
            for row in self.raw.get(section, []) or []:
                entry = (row, tier)
                self._by_id[field(row, "id")] = entry
                for name in [field(row, "common_name"), *split_list(field(row, "aliases"))]:
                    if name:
                        self._by_name[norm(name)] = entry
                sci = field(row, "scientific_name")
                if sci:
                    self._by_sci[norm(sci)] = entry
                genus = field(row, "genus") or (sci.split()[0] if sci else "")
                if genus and (norm(genus) not in self._by_genus or tier == 1):
                    self._by_genus[norm(genus)] = entry

    # ------------------------------------------------------------- sections

    def section(self, name: str) -> list[dict[str, Any]]:
        value = self.raw.get(name) or []
        return value if isinstance(value, list) else []

    @property
    def rules(self) -> list[dict[str, Any]]:
        return self.section("rules")

    # ------------------------------------------------------------- queries

    def by_id(self, animal_id: str) -> tuple[dict[str, Any], int] | None:
        return self._by_id.get(animal_id)

    def find_by_name(self, name: str | None) -> tuple[dict[str, Any], int] | None:
        return self._by_name.get(norm(name)) if name else None

    def find_by_scientific(self, name: str | None) -> tuple[dict[str, Any], int] | None:
        return self._by_sci.get(norm(name)) if name else None

    def find_by_genus(self, genus: str | None) -> tuple[dict[str, Any], int] | None:
        return self._by_genus.get(norm(genus)) if genus else None

    def measurements_for(self, animal_id: str) -> dict[str, Any]:
        for row in self.section("measurements"):
            if field(row, "animal_id") == animal_id:
                return row
        return {}

    def find_hybrids(self, a_id: str, b_id: str) -> list[dict[str, Any]]:
        """Hybrids for the unordered pair. Exact (A,B) order sorts first."""
        exact, reverse = [], []
        for row in self.section("hybrids"):
            pa, pb = field(row, "parent_a"), field(row, "parent_b")
            if (pa, pb) == (a_id, b_id):
                exact.append(row)
            elif (pa, pb) == (b_id, a_id):
                reverse.append(row)
        return exact + reverse

    def applicable_rules(self, implemented: set[str]) -> list[dict[str, Any]]:
        return [r for r in self.rules if str(r.get("check", "")) in implemented]


def load_data(path: Path) -> ChimeraData:
    if path.exists():
        try:
            return ChimeraData(json.loads(path.read_text(encoding="utf-8")), "full")
        except (OSError, json.JSONDecodeError) as exc:
            log.error("Could not read %s (%s); falling back to the sample data", path, exc)
    else:
        log.warning("%s not found; using the sample data. Place the full file for real runs.", path)
    return ChimeraData(json.loads(SAMPLE_PATH.read_text(encoding="utf-8")), "sample")
