"""Open-world parent resolver (E4, ENGINE_CONTRACT.md).

Order: chimera_data.json, then the learned cache (data/learned_animals.json), then the
open-world path:

a) Muse Spark turns the name or photo into {scientific_name, common_name, kind, alternatives}.
b) GBIF species match (strict, kingdom Animalia). Only an EXACT match at species rank or below
   is accepted; anything else returns needs_choice with the alternatives. Never guess.
c) Taxonomy (class, order, family, genus, gbif_key) comes only from GBIF (source "gbif"), or from
   the chimera_data.json tier2 table, which was itself built from GBIF matches.
d) Muse Spark fills body and life traits plus visible features, mouthparts and breathing organ,
   each marked "model-estimated". A breed takes its species' taxonomy and keeps its breed look.
e) The result is saved to the learned cache with provenance and a timestamp, reused next time,
   and never silently overwritten.

Refused with a clear reason: not an animal, a plant, a human, a mythic creature as a parent.
GBIF unreachable: taxonomy unknown, so the pair routes as a chimera with the speculative label;
such an entry is not saved, so a later run with GBIF up can learn it properly.
"""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

from app.evolution.data import Animal, Taxonomy, config, norm
from app.evolution.gbif import Gbif, GbifUnavailable, accepted, taxonomy_from

T = TypeVar("T")
MODEL = "model-estimated"
GBIF = "gbif"
TIER2 = "chimera_data.json tier2 (gbif)"
UNKNOWN = "unknown (GBIF unreachable)"
DB = "chimera_data.json"
REFUSE_KINDS = ("not_animal", "plant", "human", "mythic")
TRAIT_FIELDS = ("body_plan", "primary_locomotor_part", "covering", "movement", "habitat", "climate", "diet",
                "active_time", "body_mass_kg", "body_length_m", "visible_features", "mouthparts", "breathing")


@dataclass
class Resolution:
    query: str
    status: str  # resolved | needs_choice | refused
    animal: Animal | None = None
    source: str = ""  # database | learned | open_world
    kind: str = ""
    note: str = ""
    alternatives: list[dict[str, str]] = field(default_factory=list)
    taxonomy_source: str = ""
    traits_source: str = ""
    suggestion: str = ""
    gbif: dict[str, Any] | None = None

    def public(self) -> dict[str, Any]:
        return {"query": self.query, "status": self.status, "source": self.source, "kind": self.kind,
                "note": self.note, "alternatives": self.alternatives, "taxonomy_source": self.taxonomy_source,
                "traits_source": self.traits_source, "suggestion": self.suggestion, "gbif": self.gbif,
                "animal": self.animal.public() if self.animal else None}


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _mid(r: dict[str, Any] | None) -> float | None:
    if not r:
        return None
    lo, hi = float(r.get("min") or 0), float(r.get("max") or 0)
    vals = [v for v in (lo, hi) if v > 0]
    return round(sum(vals) / len(vals), 3) if vals else None


def _group(tax_class: str) -> str:
    for group, classes in config()["class_groups"].items():
        if tax_class in classes:
            return group
    return "other"


def animal_from_entry(e: dict[str, Any]) -> Animal:
    """A learned cache entry as an engine Animal. Unknown taxonomy leaves class and genus empty."""
    t = e.get("taxonomy") or {}
    tr = e.get("traits") or {}
    prov = e.get("provenance") or {}
    return Animal(
        id=e["id"], common_name=e["common_name"], scientific_name=e["scientific_name"],
        tax_class=t.get("class", ""), family=t.get("family", ""), body_plan="|".join(tr.get("body_plan") or []),
        covering=tr.get("covering", ""), mass_kg=_mid(tr.get("body_mass_kg")), habitats=tuple(tr.get("habitat") or ()),
        climate=tuple(tr.get("climate") or ()), active_time=tuple(tr.get("active_time") or ()),
        group=_group(t.get("class", "")), order=t.get("order", ""), genus_name=t.get("genus", ""),
        gbif_key=t.get("gbif_key", ""), diet=tr.get("diet", ""), movement=tuple(tr.get("movement") or ()),
        locomotor=tr.get("primary_locomotor_part", ""), length_m=_mid(tr.get("body_length_m")),
        features=tuple(tr.get("visible_features") or ()), mouthparts=tr.get("mouthparts", ""),
        breathing=tr.get("breathing", ""), kind=e.get("kind", "species"), source="learned",
        provenance=tuple(sorted(prov.items())),
        claims=tuple(f"documented cross with {c} (unverified claim)" for c in e.get("claims") or []),
    )


class LearnedStore:
    """data/learned_animals.json: {"about", "animals": {id: entry}, "aliases": {name: {id, note, alternatives}}}."""

    ABOUT = ("E4 learned-animal cache. Taxonomy from GBIF (source 'gbif'); body and life traits from Muse Spark "
             "(model-estimated). Entries are reused and never silently overwritten.")

    def __init__(self, path: Path) -> None:
        self.path = path
        self.data: dict[str, Any] = {"about": self.ABOUT, "animals": {}, "aliases": {}}
        if path.exists():
            self.data = json.loads(path.read_text(encoding="utf-8"))
            self.data.setdefault("animals", {})
            self.data.setdefault("aliases", {})

    def entries(self) -> list[dict[str, Any]]:
        return list(self.data["animals"].values())

    def lookup(self, name: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        """(entry, alias record). A database animal reached through an alias returns (None, record)."""
        key = norm(name)
        rec = self.data["aliases"].get(key)
        if rec:
            return self.data["animals"].get(rec["id"]), rec
        for e in self.data["animals"].values():
            if key in (norm(e["id"]), norm(e["common_name"]), norm(e["scientific_name"])):
                return e, {"id": e["id"]}
        return None, {}

    def alias(self, name: str, animal_id: str, note: str = "", alternatives: list[dict[str, str]] | None = None) -> None:
        key = norm(name)
        if key and key not in self.data["aliases"]:
            self.data["aliases"][key] = {"id": animal_id, "note": note, "alternatives": alternatives or []}
            self._save()

    def add(self, entry: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        """(stored entry, True if new). An existing id is kept as it is: never silently overwritten."""
        have = self.data["animals"].get(entry["id"])
        if have is not None:
            return have, False
        self.data["animals"][entry["id"]] = entry
        self._save()
        return entry, True

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(self.path)


async def _direct(kind: str, purpose: str, aw: Awaitable[T]) -> T:
    return await aw


class Resolver:
    def __init__(self, tax: Taxonomy, spark: Any, gbif: Gbif, store: LearnedStore,
                 call: Callable[[str, str, Awaitable[Any]], Awaitable[Any]] = _direct) -> None:
        self.tax, self.spark, self.gbif, self.store, self.call = tax, spark, gbif, store, call
        for e in store.entries():  # learned animals are part of this engine's taxonomy from the start
            self.tax.add(animal_from_entry(e), [e["common_name"]])

    # ------------------------------------------------------------------ lookups that cost nothing

    def _database(self, name: str) -> Animal | None:
        a = self.tax.resolve(name)
        return a if a is not None and a.source == "database" else None

    def _learned(self, query: str) -> Resolution | None:
        entry, rec = self.store.lookup(query)
        if not rec:
            return None
        if entry is None:  # an alias to a database animal ("jagwar")
            a = self.tax.animals.get(rec["id"])
            return Resolution(query, "resolved", a, "database", a.kind, rec.get("note", ""), rec.get("alternatives", []),
                              DB, DB) if a else None
        a = self.tax.animals.get(entry["id"]) or animal_from_entry(entry)
        self.tax.add(a, [query])
        return Resolution(query, "resolved", a, "learned", entry.get("kind", "species"),
                          rec.get("note") or entry.get("note", ""), rec.get("alternatives") or entry.get("alternatives", []),
                          entry.get("taxonomy_source", GBIF), MODEL)

    def _mythic(self, query: str) -> Resolution | None:
        key = norm(query)
        for m in self.tax.mythology:
            if norm(m.get("creature_name", "")) == key:
                return self._refuse(query, "mythic", parts=m.get("component_animals", ""))
        return None

    def _refuse(self, query: str, kind: str, parts: str = "") -> Resolution:
        what = {"not_animal": f"{query!r} is not an animal.",
                "plant": f"{query!r} is a plant, not an animal.",
                "human": "Humans are not used as parents.",
                "mythic": f"{query!r} is a mythic creature, not an animal, so it cannot be a parent."}[kind]
        tip = ""
        if kind == "mythic":
            animals = [p.strip() for p in parts.split("|") if p.strip()]
            tip = ("Use mythic mode with real animals instead"
                   + (f", for example {' x '.join(animals[:2])}." if len(animals) >= 2 else "."))
        return Resolution(query, "refused", kind=kind, note=what, suggestion=tip)

    # ------------------------------------------------------------------ the full path

    async def resolve(self, name: str | None = None, image: bytes | None = None) -> Resolution:
        query = (name or "").strip() or "photo"
        if name:
            if a := self._database(name):
                return Resolution(query, "resolved", a, "database", a.kind, "", [], DB, DB)
            if hit := self._learned(name):
                return hit
            if refusal := self._mythic(name):
                return refusal
        ident = await self.call("spark", "identify", self.spark.identify(name=name or None, image=image))
        kind = ident.get("kind", "")
        if kind in REFUSE_KINDS:
            parts = ""
            if kind == "mythic":
                parts = next((m.get("component_animals", "") for m in self.tax.mythology
                              if norm(m.get("creature_name", "")) == norm(ident.get("common_name", ""))), "")
            return self._refuse(query if name else ident.get("common_name") or "the photo", kind, parts)
        sci = ident.get("scientific_name", "").strip()
        alts = ident.get("alternatives", [])
        if not sci:
            return Resolution(query, "needs_choice", kind=kind, alternatives=alts,
                              note=f"Could not identify {query!r} as one animal; choose one of the alternatives.")
        ambiguous_note = ""
        if kind == "ambiguous":
            ambiguous_note = (f"{query!r} names several species; chose the {ident.get('common_name')} ({sci}), "
                              "the most common reading. Alternatives are listed.")
        breed = ident.get("breed", "") if kind == "breed" else ""
        # The model's reading may land on a known animal (a misspelling, a regional name).
        known = None if breed else self.tax.by_scientific(sci)
        if known is not None:
            note = ambiguous_note or f"read {query!r} as the {known.common_name} ({known.scientific_name})."
            if name:
                self.store.alias(name, known.id, note, alts)
            source = "database" if known.source == "database" else "learned"
            return Resolution(query, "resolved", known, source, kind if kind != "species" else known.kind, note, alts,
                              DB if source == "database" else GBIF, DB if source == "database" else MODEL)
        if breed and (have := self.store.lookup(breed)[0]):
            a = self.tax.animals.get(have["id"]) or animal_from_entry(have)
            self.tax.add(a, [breed])
            if name:
                self.store.alias(name, a.id)
            return Resolution(query, "resolved", a, "learned", "breed", have.get("note", ""), [], GBIF, MODEL)

        # b) and c): taxonomy from GBIF only (the tier2 table is a stored GBIF match).
        taxo, tax_source, match = None, UNKNOWN, None
        row = self.tax.tier2.get(sci.lower())
        if row:
            taxo = {"class": row.get("class", ""), "order": row.get("order", ""), "family": row.get("family", ""),
                    "genus": row.get("genus", ""), "gbif_key": str(row.get("gbif_key") or ""),
                    "canonical_name": row["scientific_name"], "rank": "SPECIES", "status": "ACCEPTED"}
            tax_source = TIER2
        else:
            try:
                match = await self.gbif.match(sci)
            except GbifUnavailable:
                match = None
            if match is not None:
                if not accepted(match):
                    return Resolution(
                        query, "needs_choice", kind=kind, alternatives=alts, gbif=match,
                        note=(f"GBIF has no exact species match for {sci!r} (matchType {match.get('matchType')}"
                              f"{', rank ' + match['rank'] if match.get('rank') else ''}"
                              f"{', suggests ' + match['canonicalName'] if match.get('canonicalName') else ''}). "
                              "Choose one of the alternatives; the engine does not guess."))
                taxo, tax_source = taxonomy_from(match), GBIF
        canonical = (taxo or {}).get("canonical_name") or sci

        # d) traits from Muse Spark, model-estimated.
        traits = await self.call("spark", "learn_traits", self.spark.learn_traits({**ident, "scientific_name": canonical}))
        common = breed or ident.get("common_name") or canonical
        aid = slug(common)
        if aid in self.tax.animals and self.tax.animals[aid].scientific_name.lower() != canonical.lower():
            aid = slug(f"{common} {canonical}")
        note = ambiguous_note
        if breed:
            note = f"a breed of {canonical}: taxonomy from the species, look from the breed."
        elif kind == "extinct":
            note = f"extinct species ({canonical}); traits are model-estimated from the record."
        prov = {f: MODEL for f in TRAIT_FIELDS}
        prov.update({f: tax_source for f in ("class", "order", "family", "genus", "gbif_key")})
        prov["scientific_name"] = tax_source if taxo else MODEL
        prov["common_name"] = MODEL
        entry = {
            "id": aid, "common_name": common, "scientific_name": canonical, "kind": kind if kind != "ambiguous" else "species",
            "breed": breed, "note": note, "inputs": [query], "alternatives": alts,
            "taxonomy": {k: v for k, v in (taxo or {}).items() if k in ("class", "order", "family", "genus", "gbif_key")},
            "taxonomy_source": tax_source, "traits": {k: traits[k] for k in TRAIT_FIELDS if k in traits},
            "details": {"mouthparts": traits.get("mouthparts_detail", ""), "breathing": traits.get("breathing_detail", "")},
            "claims": traits.get("claimed_crosses", []), "provenance": prov,
            "learned_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        if taxo is not None:  # e) save; an offline entry is not saved (its taxonomy is unknown)
            entry, _new = self.store.add(entry)
            if name:
                self.store.alias(name, entry["id"], ambiguous_note, alts)
        a = animal_from_entry(entry)
        self.tax.add(a, [common, query] if name else [common])
        return Resolution(query, "resolved", a, "open_world", kind, entry.get("note", note), alts, tax_source, MODEL,
                          gbif=match)
