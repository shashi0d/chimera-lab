"""Loader and query helpers for chimera_data.json.

Two schemas are supported:

* the **real** file (`data/chimera_data.json`): hybrids name parents as
  "Panthera tigris (father)", rules carry no check field (they are mapped in
  `rule_map.py`), measurements are long-form rows, mythology names component
  animals in everyday words ("eagle|lion");
* the original invented **sample** (`tests/fixtures/chimera_data.sample.json`),
  kept so earlier tests stay meaningful.

Values stay strings: `|` lists are split on read, ranges like "126-272" are
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

from app.data.rule_map import RULE_CHECKS

log = logging.getLogger(__name__)

SAMPLE_PATH = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "chimera_data.sample.json"

ALIASES: dict[str, tuple[str, ...]] = {
    "id": ("id", "animal_id", "slug", "key"),
    "common_name": ("common_name", "commonName", "name", "common", "hybrid_name"),
    "scientific_name": ("scientific_name", "scientificName", "binomial", "species"),
    "aliases": ("aliases", "other_names", "synonyms"),
    "genus": ("genus",),
    "class": ("class", "taxon_class", "taxonomic_class"),
    "body_plan": ("body_plan", "bodyPlan", "plan"),
    "parent_a": ("parent_a", "parentA", "sire", "parent1", "parent_1"),
    "parent_b": ("parent_b", "parentB", "dam", "parent2", "parent_2"),
    "animal_id": ("animal_id", "animalId", "id"),
    "hybrid_id": ("hybrid_id", "id"),
    "rule_id": ("rule_id", "id"),
    "rule_text": ("rule_text", "rule"),
}

ROLE_RE = re.compile(r"^\s*(?P<name>.+?)\s*\((?P<role>father|mother|unknown)\)\s*$", re.IGNORECASE)

# Broad animal words used by mythology rows, mapped to a taxon test on an animal row.
# Specific words ("eagle", "horse") match common names directly instead.
BROAD_TAXA: dict[str, dict[str, set[str]]] = {
    "bird": {"class": {"Aves"}},
    "fish": {"class": {"Actinopterygii", "Chondrichthyes", "Elasmobranchii"}},
    "snake": {"body_plan": {"serpentine"}},
    "serpent": {"body_plan": {"serpentine"}},
    "ape": {"family": {"Hominidae"}},
    "monkey": {"order": {"Primates"}},
    "bull": {"genus": {"Bos", "Bison", "Bubalus"}},
    "cow": {"genus": {"Bos", "Bison", "Bubalus"}},
    "ox": {"genus": {"Bos", "Bison", "Bubalus"}},
    "ram": {"genus": {"Ovis"}},
    "rooster": {"genus": {"Gallus"}},
    "peacock": {"genus": {"Pavo"}},
    "antelope": {"family": {"Bovidae", "Antilocapridae"}},
    "stag": {"family": {"Cervidae"}},
    "caribou": {"genus": {"Rangifer"}},
    "hare": {"family": {"Leporidae"}},
    "spider": {"order": {"Araneae"}},
    "weasel": {"family": {"Mustelidae"}},
    "moth": {"order": {"Lepidoptera"}},
    "insect": {"class": {"Insecta"}},
}
HUMAN_WORDS = {"human", "man", "woman"}


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


def genus_of(row: dict[str, Any]) -> str:
    """Real tier-1 rows have no genus field; derive it from the binomial."""
    sci = field(row, "scientific_name")
    return field(row, "genus") or (sci.split()[0] if sci else "")


def parse_parent(value: str) -> tuple[str, str | None]:
    """'Panthera tigris (father)' -> ('Panthera tigris', 'father'). Sample ids pass through."""
    m = ROLE_RE.match(value or "")
    if m:
        role = m.group("role").lower()
        return m.group("name").strip(), (None if role == "unknown" else role)
    return (value or "").strip(), None


@dataclass
class ResolvedParent:
    raw: str
    name: str
    role: str | None  # "father" | "mother" | None (unknown)
    animal_ids: list[str]  # every tier-1/tier-2 animal this parent may be
    via: str | None  # "id" | "scientific_name" | "genus" | "hybrid" | None (unresolved)
    reason: str = ""


@dataclass
class HybridMatch:
    row: dict[str, Any]
    a: ResolvedParent  # the hybrid parent matched to fusion input A
    b: ResolvedParent  # ... to input B


@dataclass
class MythMatch:
    row: dict[str, Any]
    matched: dict[str, str]  # slot -> component word it matched ("A": "eagle")
    how: dict[str, str]  # slot -> "name" | "taxon"


@dataclass
class ChimeraData:
    raw: dict[str, Any]
    source: str  # "full" | "sample"
    _by_name: dict[str, tuple[dict[str, Any], int]] = dc_field(default_factory=dict)
    _by_sci: dict[str, list[tuple[dict[str, Any], int]]] = dc_field(default_factory=dict)
    _by_genus: dict[str, list[tuple[dict[str, Any], int]]] = dc_field(default_factory=dict)
    _by_id: dict[str, tuple[dict[str, Any], int]] = dc_field(default_factory=dict)
    _measurements: dict[str, list[dict[str, Any]]] = dc_field(default_factory=dict)
    _hybrid_parents: list[tuple[dict[str, Any], ResolvedParent, ResolvedParent]] = dc_field(default_factory=list)

    def __post_init__(self) -> None:
        for tier, section in ((1, "animals"), (2, "tier2_animals")):  # tier 1 first: it wins on ties
            for row in self.section(section):
                entry = (row, tier)
                aid = field(row, "id")
                self._by_id.setdefault(aid, entry)
                for name in [field(row, "common_name"), *split_list(field(row, "aliases"))]:
                    if name:
                        self._by_name.setdefault(norm(name), entry)
                sci = field(row, "scientific_name")
                if sci:
                    self._by_sci.setdefault(norm(sci), []).append(entry)
                genus = genus_of(row)
                if genus:
                    self._by_genus.setdefault(norm(genus), []).append(entry)
        for row in self.section("measurements"):
            self._measurements.setdefault(field(row, "animal_id"), []).append(row)
        for row in self.section("hybrids"):
            self._hybrid_parents.append(
                (row, self.resolve_hybrid_parent(field(row, "parent_a")), self.resolve_hybrid_parent(field(row, "parent_b")))
            )

    # ------------------------------------------------------------- sections

    def section(self, name: str) -> list[dict[str, Any]]:
        value = self.raw.get(name) or []
        return value if isinstance(value, list) else []

    @property
    def rules(self) -> list[dict[str, Any]]:
        return self.section("rules")

    @property
    def body_plans(self) -> list[str]:
        """Allowed body plans: the values actually used by tier-1 animals (R-A1-01)."""
        seen: list[str] = []
        for row in self.section("animals"):
            for v in split_list(field(row, "body_plan")):
                if v not in seen:
                    seen.append(v)
        return seen

    # ------------------------------------------------------------- animal lookup

    def by_id(self, animal_id: str) -> tuple[dict[str, Any], int] | None:
        return self._by_id.get(animal_id)

    def find_by_name(self, name: str | None) -> tuple[dict[str, Any], int] | None:
        return self._by_name.get(norm(name)) if name else None

    def find_by_scientific(self, name: str | None) -> tuple[dict[str, Any], int] | None:
        hits = self._by_sci.get(norm(name)) if name else None
        return hits[0] if hits else None

    def find_by_genus(self, genus: str | None) -> tuple[dict[str, Any], int] | None:
        hits = self._by_genus.get(norm(genus)) if genus else None
        if not hits:
            return None
        return next((h for h in hits if h[1] == 1), hits[0])

    def measurements_for(self, animal_id: str) -> list[dict[str, Any]]:
        """Every measurement row for the animal (the real file has many per animal)."""
        return list(self._measurements.get(animal_id, []))

    # ------------------------------------------------------------- hybrids

    def resolve_hybrid_parent(self, value: str) -> ResolvedParent:
        name, role = parse_parent(value)
        if name.startswith("hybrid:"):
            return ResolvedParent(value, name, role, [], "hybrid", f"parent is itself a hybrid ({name})")
        if " " not in name and name in self._by_id:
            return ResolvedParent(value, name, role, [name], "id")  # sample schema: parents are animal ids
        hits = self._by_sci.get(norm(name))
        if hits:
            tier1 = [r for r, t in hits if t == 1]
            ids = [field(r, "id") for r in (tier1 or [r for r, _ in hits])]
            return ResolvedParent(value, name, role, ids, "scientific_name")
        genus = name.split()[0] if name else ""
        ghits = self._by_genus.get(norm(genus))
        if ghits:
            tier1 = [r for r, t in ghits if t == 1]
            ids = [field(r, "id") for r in (tier1 or [r for r, _ in ghits])]
            return ResolvedParent(value, name, role, ids, "genus", f"no exact species match; matched genus {genus}")
        return ResolvedParent(value, name, role, [], None, "no tier-1, tier-2 or genus match")

    def hybrid_resolution(self) -> list[tuple[dict[str, Any], ResolvedParent, ResolvedParent]]:
        return list(self._hybrid_parents)

    def find_hybrids(self, a_id: str, b_id: str) -> list[HybridMatch]:
        """Real hybrids for the unordered pair, keeping each row's cross direction.

        Exact species matches sort before genus-only matches; within those, a row whose
        parent1 is input A sorts first.
        """
        found: list[tuple[int, HybridMatch]] = []
        for row, p1, p2 in self._hybrid_parents:
            for first, second, order in ((p1, p2, 0), (p2, p1, 1)):
                if a_id in first.animal_ids and b_id in second.animal_ids:
                    genus_only = int("genus" in (first.via, second.via))
                    found.append((genus_only * 2 + order, HybridMatch(row, first, second)))
                    break
        found.sort(key=lambda x: x[0])
        return [m for _, m in found]

    # ------------------------------------------------------------- mythology

    @staticmethod
    def component_matches(word: str, row: dict[str, Any]) -> str | None:
        """'name' if the mythology word names this animal, 'taxon' if it is a broad word covering it."""
        w = norm(word)
        if not w or w in HUMAN_WORDS:
            return None
        common = norm(field(row, "common_name"))
        if common and (w == common or w in common.split()):
            return "name"
        taxa = BROAD_TAXA.get(w)
        if taxa:
            values = {
                "class": field(row, "class"),
                "order": field(row, "order"),
                "family": field(row, "family"),
                "genus": genus_of(row),
                "body_plan": field(row, "body_plan"),
            }
            if any(values.get(k) in allowed or any(v in allowed for v in split_list(values.get(k))) for k, allowed in taxa.items()):
                return "taxon"
        return None

    def find_mythology(self, a_row: dict[str, Any], b_row: dict[str, Any]) -> list[MythMatch]:
        """Mythology creatures whose components include both parents (by name, or genus/family for broad words)."""
        out: list[tuple[tuple[int, int], MythMatch]] = []
        for row in self.section("mythology"):
            words = [w for w in split_list(field(row, "component_animals")) if norm(w) not in HUMAN_WORDS]
            best: tuple[int, dict[str, str], dict[str, str]] | None = None
            for wa in words:
                ha = self.component_matches(wa, a_row)
                if not ha:
                    continue
                for wb in words:
                    if wb == wa:
                        continue
                    hb = self.component_matches(wb, b_row)
                    if hb:
                        score = (ha == "name") + (hb == "name")
                        if best is None or score > best[0]:
                            best = (score, {"A": wa, "B": wb}, {"A": ha, "B": hb})
            if best:
                comps = len(split_list(field(row, "component_animals")))
                out.append(((-best[0], comps), MythMatch(row, best[1], best[2])))
        out.sort(key=lambda x: x[0])
        return [m for _, m in out]

    # ------------------------------------------------------------- rules

    def rule_check(self, rule: dict[str, Any]) -> str | None:
        """The check a rule runs: the sample's own `check` field, else the explicit real-rule map."""
        explicit = rule.get("check")
        if explicit:
            return str(explicit)
        return RULE_CHECKS.get(field(rule, "rule_id"), (None, None))[0]

    def applicable_rules(self, implemented: set[str]) -> list[dict[str, Any]]:
        return [r for r in self.rules if self.rule_check(r) in implemented]

    # ------------------------------------------------------------- health

    def health(self, implemented: set[str]) -> dict[str, Any]:
        hybrids = self.hybrid_resolution()
        resolved = sum(1 for _, p1, p2 in hybrids if p1.animal_ids and p2.animal_ids)
        mapped = len(self.applicable_rules(implemented))
        problems = []
        if hybrids and resolved == 0:
            problems.append(f"0 of {len(hybrids)} hybrids resolve to animals: hybrid lookup will find nothing")
        if self.rules and mapped == 0:
            problems.append(f"0 of {len(self.rules)} rules map to a check: rules_check will run nothing")
        return {
            "animals": len(self.section("animals")),
            "tier2_animals": len(self.section("tier2_animals")),
            "measurements": len(self.section("measurements")),
            "hybrids": len(hybrids),
            "hybrids_resolved": resolved,
            "rules": len(self.rules),
            "rules_mapped": mapped,
            "mythology": len(self.section("mythology")),
            "problems": problems,
        }


def load_data(path: Path) -> ChimeraData:
    if path.exists():
        try:
            return ChimeraData(json.loads(path.read_text(encoding="utf-8")), "full")
        except (OSError, json.JSONDecodeError) as exc:
            log.error("Could not read %s (%s); falling back to the sample data", path, exc)
    else:
        log.warning("%s not found; using the sample data. Place the full file for real runs.", path)
    return ChimeraData(json.loads(SAMPLE_PATH.read_text(encoding="utf-8")), "sample")
