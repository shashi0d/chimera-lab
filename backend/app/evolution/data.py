"""Static data for the evolution engine: rule cards, taxonomy, known pairs, tables.

Everything is read from files under data/ (ALGORITHM.md section 2 and 6). The
rule-card file is produced by scripts/build_rule_cards.py and is the single
source of truth: prompts quote cards from here, never from memory.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import REPO_ROOT

DATA = REPO_ROOT / "data"
CARDS_PATH = DATA / "rule_cards.json"
PAIRS_PATH = DATA / "evo_known_pairs.json"
CONFIG_PATH = DATA / "evo_config.json"
TAXONOMY_PATH = DATA / "chimera_data.json"


# ------------------------------------------------------------------ rule cards


@dataclass(frozen=True)
class Card:
    id: str
    doc: str
    rule: str
    applies_to: tuple[str, ...]
    strength: str
    status: str
    source: str

    @property
    def weight(self) -> float:
        """Soft-card penalty weight (section 2). Hard cards filter and carry no weight."""
        return 1.0 if self.status == "VERIFIED" else 0.5

    @property
    def hard(self) -> bool:
        return self.strength == "hard"


class CardBook:
    def __init__(self, cards: list[dict[str, Any]]) -> None:
        self._cards = {c["id"]: Card(**{**c, "applies_to": tuple(c["applies_to"])}) for c in cards}

    def __getitem__(self, card_id: str) -> Card:
        return self._cards[card_id]

    def __contains__(self, card_id: str) -> bool:
        return card_id in self._cards

    def all(self) -> list[Card]:
        return list(self._cards.values())

    def hard_ids(self) -> list[str]:
        return [c.id for c in self._cards.values() if c.hard]

    def quote(self, ids: list[str]) -> str:
        """Cards as prompt text, verbatim from the loader (section 2)."""
        return "\n".join(f"{i} ({self[i].strength}): {self[i].rule}" for i in ids if i in self)

    def for_tags(self, tags: list[str]) -> list[str]:
        want = set(tags) | {"all_traits", "pipeline"}
        return [c.id for c in self._cards.values() if want & set(c.applies_to)]


@lru_cache
def cards(path: Path = CARDS_PATH) -> CardBook:
    return CardBook(json.loads(path.read_text(encoding="utf-8")))


# ------------------------------------------------------------------ config tables


@lru_cache
def config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


PLAIN_COAT = "plain coat, no stripes or spots"


def coat_pattern(animal_id: str | None) -> str | None:
    """The parent's own visible coat pattern type (e.g. "stripes"), or None: no stripes or spots (E2b)."""
    return config().get("coat_patterns", {}).get(animal_id) if animal_id else None


def pattern_phrase(name: str, animal_id: str | None) -> str | None:
    """Always donor plus type, e.g. "tiger-type stripes"; never a bare "pattern" (E2b)."""
    kind = coat_pattern(animal_id)
    return f"{name.lower()}-type {kind}" if kind else None


@lru_cache
def known_pairs(path: Path = PAIRS_PATH) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))["pairs"]


# ------------------------------------------------------------------ taxonomy


def _mass_mid(raw: str) -> float | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        parts = [float(p) for p in raw.split("-") if p.strip()]
    except ValueError:
        return None
    return sum(parts) / len(parts) if parts else None


@dataclass(frozen=True)
class Animal:
    id: str
    common_name: str
    scientific_name: str
    tax_class: str
    family: str
    body_plan: str
    covering: str
    mass_kg: float | None
    habitats: tuple[str, ...]
    climate: tuple[str, ...]
    active_time: tuple[str, ...]
    group: str  # vertebrate | arthropod | soft_bodied | other

    @property
    def genus(self) -> str:
        return self.scientific_name.split()[0] if self.scientific_name else ""

    @property
    def winged(self) -> bool:
        return "winged" in self.body_plan.split("|")

    @property
    def frame(self) -> str:
        """Coarse frame used for silhouette and limb plans."""
        plans = self.body_plan.split("|")
        if self.group == "soft_bodied":
            return "soft_bodied"
        if self.group == "arthropod":
            return "arthropod"
        if "winged" in plans:
            return "winged"
        if "quadruped" in plans:
            return "quadruped"
        if "finned" in plans:
            return "finned"
        if "serpentine" in plans:
            return "serpentine"
        if "biped" in plans:
            return "biped"
        return "other"

    @property
    def structure_rank(self) -> int:
        """Body-schema structure (RC-R6-08, RC-R6-09): four-legged mammals and birds are
        structured frames; soft-bodied animals are low-structure donors."""
        return {"quadruped": 3, "winged": 3, "biped": 3, "finned": 2, "serpentine": 2,
                "arthropod": 1, "other": 1, "soft_bodied": 0}[self.frame]

    def public(self) -> dict[str, Any]:
        return {"id": self.id, "common_name": self.common_name, "scientific_name": self.scientific_name,
                "class": self.tax_class, "body_plan": self.body_plan, "group": self.group,
                "mass_kg": self.mass_kg}


@dataclass
class Taxonomy:
    animals: dict[str, Animal]
    aliases: dict[str, str]
    documented: set[tuple[str, str]] = field(default_factory=set)  # (sire binomial, dam binomial)
    mythology: list[dict[str, Any]] = field(default_factory=list)

    def resolve(self, name: str) -> Animal | None:
        key = name.strip().lower().replace("-", " ")
        for k in (key, key.replace(" ", "_")):
            if k in self.animals:
                return self.animals[k]
            if k in self.aliases:
                return self.animals.get(self.aliases[k])
        for a in self.animals.values():
            if a.common_name.lower() == key or a.scientific_name.lower() == key:
                return a
        return None

    def documented_hybrid(self, sire: Animal, dam: Animal) -> bool:
        s, d = sire.scientific_name, dam.scientific_name
        return (s, d) in self.documented or ("?" + s, "?" + d) in self.documented or ("?" + d, "?" + s) in self.documented


def _group(tax_class: str) -> str:
    for group, classes in config()["class_groups"].items():
        if tax_class in classes:
            return group
    return "other"


@lru_cache
def taxonomy(path: Path = TAXONOMY_PATH) -> Taxonomy:
    raw = json.loads(path.read_text(encoding="utf-8"))
    animals: dict[str, Animal] = {}
    for a in raw.get("animals", []):
        split = lambda v: tuple(x for x in (v or "").split("|") if x)  # noqa: E731
        animals[a["animal_id"]] = Animal(
            id=a["animal_id"], common_name=a["common_name"], scientific_name=a["scientific_name"],
            tax_class=a.get("class", ""), family=a.get("family", ""), body_plan=a.get("body_plan", ""), covering=a.get("covering", ""),
            mass_kg=_mass_mid(a.get("body_mass_kg", "")), habitats=split(a.get("habitat")),
            climate=split(a.get("climate")), active_time=split(a.get("active_time")), group=_group(a.get("class", "")),
        )
    documented: set[tuple[str, str]] = set()
    for h in raw.get("hybrids", []):
        p1, p2 = h.get("parent1", ""), h.get("parent2", "")
        if p1.startswith("hybrid:") or p2.startswith("hybrid:"):
            continue
        n1, n2 = p1.split(" (")[0].strip(), p2.split(" (")[0].strip()
        if "(unknown)" in p1 or "(unknown)" in p2:
            documented.add(("?" + n1, "?" + n2))  # order not recorded: counts both ways
        else:
            documented.add((n1, n2))
    return Taxonomy(animals=animals, aliases=config()["aliases"], documented=documented,
                    mythology=raw.get("mythology", []))
