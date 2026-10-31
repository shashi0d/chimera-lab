"""Section 4.10: the output card each creature ships with."""

from __future__ import annotations

import re
from typing import Any

from app.evolution.data import Taxonomy, cards
from app.evolution.genome import Genome
from app.evolution.route import KIND, LABEL_HYBRID, Route

VIABILITY_CAVEAT = "This is a design, not a prediction: no claim is made that such a creature would be healthy or viable."
FOSSIL_CAVEAT = "Stories that trace myth creatures to specific fossils are contested, not established."
DOMESTICATION_NOTE = " (the domestication syndrome explanation is a debated hypothesis)"


def safe_text(text: str, distant: bool) -> str:
    """Wording guards: RC-R1-12 (domestication syndrome as hypothesis), RC-R7-03 (fossil
    origins contested), RC-R5-09 (never call a distant-pair chimera healthy or viable)."""
    if "domestication syndrome" in text.lower() and "hypothesis" not in text.lower():
        text += DOMESTICATION_NOTE
    if "fossil" in text.lower() and "contested" not in text.lower():
        text += " (contested)"
    if distant:
        text = re.sub(r"\b(is|would be|are)\s+(healthy|viable)\b", r"\1 not claimed to be \2", text, flags=re.IGNORECASE)
    if "oxygen" in text.lower() and not re.search(r"debated|not settled|probably not|contested", text, re.IGNORECASE):
        text += " (the oxygen explanation for giant insects is debated, not settled)"  # RC-R9-09
    return text


def can_it_live(g: Genome, distant: bool) -> list[dict[str, Any]]:
    """E4: the "Can it live?" panel: each audited function, its result and the cards (or model) behind it."""
    return [{"function": i.function, "result": i.result, "detail": safe_text(i.detail, distant),
             "cards": i.cards, "decided_by": "model-judged" if i.source == "model-judged" else "code (rule cards)"}
            for i in g.audit]


def provenance(g: Genome, tax: Taxonomy) -> dict[str, Any]:
    """E4: per-fact provenance for each parent, plus any model claims (never used as precedent)."""
    out: dict[str, Any] = {}
    for slot, pid in (("sire", g.parents.sire), ("dam", g.parents.dam)):
        a = tax.animals[pid]
        out[slot] = {"animal": a.common_name, "scientific_name": a.scientific_name, "kind": a.kind,
                     "source": a.source, "facts": dict(a.provenance), "unverified_claims": list(a.claims)}
    return out


def resemblances(g: Genome, tax: Taxonomy) -> list[dict[str, str]]:
    words = set()
    for pid in (g.parents.sire, g.parents.dam):
        a = tax.animals[pid]
        words.add(a.common_name.lower().split()[-1])
    out = []
    for m in tax.mythology:
        comps = {c.strip().lower() for c in (m.get("component_animals") or "").split("|") if c.strip()}
        if comps and comps == words and m.get("has_human_part", "no") == "no":
            out.append({"text": f"resembles {m['creature_name']} ({m.get('culture') or 'unknown culture'})",
                        "status": "unverified", "source": m.get("source_url", "")})
    return out[:5]


def output_card(g: Genome, r: Route, tax: Taxonomy) -> dict[str, Any]:
    book = cards()
    distant = g.mode != "hybrid"
    processes = list(g.processes)
    if g.habitat.adjustments:
        processes.append(f"coat and extremities shaped by a {g.habitat.name} habitat")
    caveats: list[str] = list((r.pair or {}).get("caveats", []))
    if distant:
        caveats.append(VIABILITY_CAVEAT)
    res = resemblances(g, tax)
    if res and g.mode == "mythic":
        caveats.append(FOSSIL_CAVEAT)
    primary = g.labels[0] if g.labels else ("" if distant else LABEL_HYBRID)
    sire, dam = tax.animals[g.parents.sire], tax.animals[g.parents.dam]
    return {
        "kind": KIND[g.mode],  # RC-R9-01: hybrid | chimera | mythic composite
        "design_mode": g.design_mode,
        "label": primary,
        "check_labels": g.labels[1:],
        "processes": [safe_text(p, distant) for p in processes],
        "resemblances": res,
        "why": [{"card": c, "rule": book[c].rule, "strength": book[c].strength, "status": book[c].status,
                 "source": book[c].source} for c in g.card_trace if c in book],
        "lineage": {"sire": sire.common_name, "dam": dam.common_name, "parent_ids": g.lineage.parent_ids,
                    "generation": g.lineage.generation},
        "caveats": [safe_text(c, distant) for c in caveats],
        "can_it_live": can_it_live(g, distant),
        "licenses": [{"rule": lic.rule, "card": lic.card, "compensation": lic.compensation, "reason": lic.reason}
                     for lic in g.licenses],
        "provenance": provenance(g, tax),
    }
