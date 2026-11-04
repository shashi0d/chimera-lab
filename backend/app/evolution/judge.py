"""Section 4.8: judge a rendered plan.

1. Readability critic (Muse Spark, image only, no plan shown): both parents named and
   one creature (RC-R6-11).
2. Silhouette check: SAM 3.1 mask compared with the planned frame by a simple shape
   comparison, which guards against texture bias in model critics (RC-R6-10).
3. Thumbnail check: the critic again on a small copy (RC-R6-06).
E2d/E4: both critics are a feature checklist (yes 1, unclear 0.5, no 0; score = mean): the pair's
hand-written R2 checklist on the real-hybrid route, otherwise generated from the plan. The same call gives
the creature count and the animals seen; the open critic is logged, not scored (S2: no forced choice).
quality = 0.4 critic + 0.3 silhouette + 0.1 thumbnail + 0.2 (1 - normalized soft penalty)
"""

from __future__ import annotations

import io
import re
from collections import deque
from typing import Any

from PIL import Image

from app.errors import ChimeraError
from app.evolution.adapters import EvoSpark, Meter, Segmenter
from app.evolution.checks import soft_penalties
from app.evolution.data import Animal, Taxonomy
from app.evolution.genome import Genome
from app.evolution.route import Route, hybrid_names, is_real_hybrid
from app.models.schemas import ErrorCode

WEIGHTS = {"critic": 0.4, "silhouette": 0.3, "thumbnail": 0.1, "rules": 0.2}
ASPECT = {"quadruped": (1.2, 2.6), "winged": (0.5, 1.5), "biped": (0.4, 1.2), "finned": (1.5, 4.0),
          "serpentine": (1.5, 6.0), "arthropod": (0.8, 2.5), "soft_bodied": (0.6, 2.0), "other": (0.5, 3.0)}
THUMB_PX = 192
SAM_PROMPT = "animal"
# Group words a critic may use for a parent ("bird" for an eagle): (taxonomy field, value).
GROUP_WORDS = {"bird": ("tax_class", "Aves"), "raptor": ("tax_class", "Aves"), "cat": ("family", "Felidae"),
               "big cat": ("family", "Felidae"), "feline": ("family", "Felidae"), "equine": ("family", "Equidae"),
               "equid": ("family", "Equidae"), "bear": ("family", "Ursidae"), "camelid": ("family", "Camelidae"),
               "salamander": ("tax_class", "Amphibia")}  # S3b: an axolotl is a salamander


def third_animals(result: dict[str, Any], sire: Animal, dam: Animal, tax: Taxonomy, r: Route | None = None) -> list[str]:
    """Names the critic gave that are neither parent, a group word for a parent, nor the known pair's name (E2b)."""
    own = hybrid_names(r.pair) if r else []
    out = []
    for said in [str(x) for x in result.get("animals") or []]:
        low = said.lower().strip()
        if _named(sire, [said]) or _named(dam, [said]) or _says_hybrid(own, [said]):
            continue
        group = GROUP_WORDS.get(low.removesuffix("s"))
        if group and any(getattr(p, group[0]) == group[1] for p in (sire, dam)):
            continue
        out.append(said)
    return out


def _named(animal: Animal, said: list[str]) -> bool:
    words = {w for w in animal.common_name.lower().replace("-", " ").split() if len(w) > 2}
    head = animal.common_name.lower().split()[-1]
    return any(head in s.lower() or words & set(s.lower().split()) for s in said)


def _says_hybrid(names: list[str], said: list[str]) -> bool:
    return any(re.search(rf"\b{re.escape(n)}s?\b", s.lower()) for n in names for s in said)


def critic_score(result: dict[str, Any], sire: Animal, dam: Animal, hybrid: list[str] | None = None) -> float:
    """hybrid (E2c, real-hybrid route only): the hybrid's own names. Naming it ("mule") counts as naming both parents."""
    said = [str(x) for x in result.get("animals") or []]
    one = int(result.get("creatures") or 0) == 1
    hits = 2 if hybrid and _says_hybrid(hybrid, said) else _named(sire, said) + _named(dam, said)
    if not one:
        return 0.0
    return {2: 1.0, 1: 0.5, 0: 0.0}[hits]


def mask_stats(mask_png: bytes) -> dict[str, float]:
    with Image.open(io.BytesIO(mask_png)) as im:
        m = im.convert("L").resize((64, 64))
        data = m.get_flattened_data() if hasattr(m, "get_flattened_data") else m.getdata()
        px = [1 if p > 127 else 0 for p in data]
    n = 64
    on = sum(px)
    if not on:
        return {"fill": 0.0, "aspect": 0.0, "components": 0}
    xs = [i % n for i, p in enumerate(px) if p]
    ys = [i // n for i, p in enumerate(px) if p]
    w, h = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
    seen = [False] * len(px)
    comps = 0
    for i, p in enumerate(px):
        if not p or seen[i]:
            continue
        comps += 1
        q = deque([i])
        seen[i] = True
        while q:
            j = q.popleft()
            x, y = j % n, j // n
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                k = ny * n + nx
                if 0 <= nx < n and 0 <= ny < n and px[k] and not seen[k]:
                    seen[k] = True
                    q.append(k)
    return {"fill": round(on / len(px), 3), "aspect": round(w / h, 3), "components": comps}


def silhouette_score(stats: dict[str, float], frame: str, critic_one: bool = False) -> float:
    """critic_one (E2b): the critic saw one creature, so a mask in pieces (wing tips, a tail) is still one."""
    if stats["fill"] < 0.05:
        return 0.0
    lo, hi = ASPECT.get(frame, ASPECT["other"])
    a = stats["aspect"]
    score = 1.0 if lo <= a <= hi else max(0.0, 1.0 - min(abs(a - lo), abs(a - hi)))
    if stats["components"] > 1 and not critic_one:
        score *= 0.5  # reads as two creatures
    return round(score, 3)


def thumbnail(image: bytes) -> bytes:
    with Image.open(io.BytesIO(image)) as im:
        small = im.convert("RGB")
        small.thumbnail((THUMB_PX, THUMB_PX))
        out = io.BytesIO()
        small.save(out, "PNG")
    return out.getvalue()


CHECKLIST_VALUE = {"yes": 1.0, "unclear": 0.5, "no": 0.0}
CHECKLIST_MIN, CHECKLIST_MAX = 4, 8  # S2: 8 so structural items fit
CHECKLIST_PAD = ("feet resting on the ground", "the whole body visible, one creature")


def checklist_for(r: Route) -> list[str]:
    """A hand-written checklist from data/evo_known_pairs.json (real-hybrid route); it takes priority (E2d)."""
    return list((r.pair or {}).get("checklist") or []) if is_real_hybrid(r) else []


def _regions(regs: list[str] | None) -> str:
    regs = list(regs or [])
    return regs[0] if len(regs) == 1 else ", ".join(regs[:-1]) + " and " + regs[-1] if regs else "body"


def generated_checklist(g: Genome, tax: Taxonomy) -> list[str]:
    """S2: the checklist is the plan's own items (inspect.plan_items), structural ones first: frame, head, license
    compensations, absences, donor parts, "no whole donor animals", then surface and pattern; padded to 4 and capped
    at 8 so every structural item fits in the one critic call that inspect reuses."""
    from app.evolution.inspect import plan_items

    items = [i.text for i in plan_items(g, tax)]
    for pad in CHECKLIST_PAD:
        if len(items) >= CHECKLIST_MIN:
            break
        items.append(pad)
    return list(dict.fromkeys(items))[:CHECKLIST_MAX]


def checklist_score(result: dict[str, Any]) -> float:
    """Fraction of items answered yes; unclear counts 0.5."""
    answers = result.get("answers") or []
    if not answers:
        return 0.0
    return round(sum(CHECKLIST_VALUE.get(a.get("answer"), 0.5) for a in answers) / len(answers), 3)


async def judge(image: bytes, g: Genome, r: Route, tax: Taxonomy, spark: EvoSpark, seg: Segmenter,
                meter: Meter) -> dict[str, Any]:
    """E4: the checklist critic for every route (hand-written pair checklists first, else generated from the
    plan). The same call returns the creature count and the animals seen (third-animal check). The open critic
    runs once more on the full image as a logged second opinion; it is never scored."""
    sire, dam = tax.animals[g.parents.sire], tax.animals[g.parents.dam]
    frame_animal = tax.animals[g.host] if g.host else sire
    hand = checklist_for(r)
    checklist = hand or generated_checklist(g, tax)
    critic = await meter.call("spark", "critic", spark.checklist(image, checklist))
    mask = await meter.call("sam", "segment", seg.segment(image, SAM_PROMPT))  # E2b: never the host's name
    stats = mask_stats(mask)
    thumb = await meter.call("spark", "critic_thumbnail", spark.checklist(thumbnail(image), checklist))
    try:
        open_critic: dict[str, Any] = await meter.call("spark", "critic_open", spark.critic(image))
    except ChimeraError as e:  # a second opinion only: its failure never fails the judge
        if e.code == ErrorCode.BUDGET_EXCEEDED:
            raise
        open_critic = {"error": f"{e.code.value}: {e.message[:120]}"}
    items, soft = soft_penalties(g, r, tax)
    frame = "winged" if frame_animal.frame == "winged" else frame_animal.frame
    one = int(critic.get("creatures") or 0) == 1
    scores = {"critic": checklist_score(critic), "silhouette": silhouette_score(stats, frame, critic_one=one),
              "thumbnail": checklist_score(thumb), "soft_penalty": soft}
    scores["quality"] = round(WEIGHTS["critic"] * scores["critic"] + WEIGHTS["silhouette"] * scores["silhouette"]
                              + WEIGHTS["thumbnail"] * scores["thumbnail"] + WEIGHTS["rules"] * (1 - soft), 3)
    return {"scores": scores, "critic": critic, "critic_thumbnail": thumb, "mask": stats, "soft_cards": items,
            "third_animal": third_animals(critic, sire, dam, tax, r), "sam_prompt": SAM_PROMPT,
            "critic_mode": "checklist", "checklist": checklist,
            "checklist_source": "known pair (hand-written)" if hand else "generated from the plan",
            "open_critic": open_critic}  # logged second opinion, not scored
