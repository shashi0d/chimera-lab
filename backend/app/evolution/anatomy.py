"""S5 part 2: the anatomy map (ROADMAP step 4).

For a finalized creature, every planned part is segmented by name with SAM, and each found mask is colored by the
parent it comes from: the host one color, each donor its own, a blended part (a real hybrid) a third. The result is
an overlay image and a JSON list of parts with parent, mask area and "found" or "not located".

Never guessed: a part whose mask covers less than PRESENT_FILL of the frame (or whose SAM call fails) is listed as
"not located", with no color and nothing drawn. A located mask shows where SAM found the part, not that the part is
right; the critics judge that.
"""

from __future__ import annotations

import io
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from app.errors import ChimeraError
from app.evolution.audit import donor_parts
from app.evolution.data import Taxonomy
from app.evolution.genome import Genome
from app.evolution.inspect import PRESENT_FILL
from app.evolution.parts import surface
from app.models.schemas import ErrorCode

COLORS = {"host": (38, 139, 210), "donor": (230, 110, 40), "donor2": (200, 60, 150), "blend": (130, 90, 200)}
ALPHA = 0.45


def _strip(name: str, prefix: str) -> str:
    n, p = name.strip(), prefix.lower().strip()
    return n[len(p):].strip() if n.lower().startswith(p + " ") else n


def covering_label(donor: Any) -> str:
    """A short visible noun for the donor covering ("hard, glossy chitin plates with fine seams" -> "glossy chitin
    plates")."""
    return surface(donor).split(" with ")[0].split(",")[-1].strip() or donor.covering or "covering"


def planned_parts(g: Genome, tax: Taxonomy) -> list[dict[str, Any]]:
    """Every planned part with the SAM label it is searched by and its source parent (animal id, or "blend")."""
    out: list[dict[str, Any]] = []

    def add(part: str, label: str, parent: str) -> None:
        if not any(p["part"] == part for p in out):
            out.append({"part": part, "sam_label": label, "parent": parent})

    if g.host is None or g.mode == "hybrid":  # a real hybrid: each part from its trait's parent, or a blend of both
        for part, label, tag in (("head", "head", "head"), ("ears", "ears", "ears"), ("mane", "mane", "mane"),
                                 ("body", "torso", "body"), ("legs", "legs", "limbs"), ("tail", "tail", "tail")):
            tr = g.traits.get(tag)
            if tr is not None:
                add(part, label, tr.donor if isinstance(tr.donor, str) else "blend")
        return out
    host, did = g.host, g.other(g.host)
    dname = tax.animals[did].common_name
    head = g.traits["head"]
    add("head", "head", head.donor if head.part and head.donor else host)
    add("body", "torso", host)
    lp = g.limb_plan
    if lp.forelimbs.kind == "wings" and lp.forelimbs.donor == did:
        add("wings (in place of the forelegs)", "wings", did)
        add("hind legs", "legs", host)
    else:
        add("legs", "legs", host)
    if lp.extra_wings and lp.extra_wings.donor:
        add("wings (extra pair)", "wings", lp.extra_wings.donor)
    for _where, p in donor_parts(g):
        if p.endswith("(tail)"):
            continue
        label = _strip(p, dname)
        add(p, label, did)
    tail = g.traits.get("tail")
    if tail is not None and tail.part and tail.donor == did:
        add(f"tail ({_strip(tail.part, dname)})", _strip(tail.part, dname), did)
    elif tail is not None:
        add("tail", "tail", host)
    cov = next((t for t in g.transfers if t.kind == "covering"), None)
    if cov is not None and cov.extent:
        form = " (color only)" if cov.form == "material_only" else ""
        add(f"{dname} covering{form}", covering_label(tax.animals[cov.donor]), cov.donor)
    for ip in g.identity_parts:  # an identity part already listed under its plan name is not searched twice
        if not any(ip.part.lower() in p["part"].lower() for p in out):
            add(ip.part, ip.part, ip.donor)
    return out


def _mask(png: bytes, size: tuple[int, int]) -> Image.Image:
    with Image.open(io.BytesIO(png)) as m:
        return m.convert("L").resize(size).point(lambda v: 255 if v > 127 else 0)


async def anatomy_map(image: bytes, g: Genome, tax: Taxonomy, seg: Any, meter: Any) -> tuple[bytes, dict[str, Any]]:
    """(overlay PNG, map JSON). One SAM call per planned part."""
    parts = planned_parts(g, tax)
    with Image.open(io.BytesIO(image)) as im:
        base = im.convert("RGB")
    size = base.size
    roles: dict[str, str] = {}
    if g.host is not None:
        roles[g.host] = "host"
        roles[g.other(g.host)] = "donor"
    found: list[tuple[dict[str, Any], Image.Image]] = []
    for p in parts:
        role = "blend" if p["parent"] == "blend" else roles.get(p["parent"], "donor2")
        p.update(parent_role=role, parent_name=("both parents" if role == "blend"
                                                else tax.animals[p["parent"]].common_name),
                 mask_area=0.0, found=False, status="not located", color=None)
        try:
            png = await meter.call("sam", f"anatomy:{p['sam_label']}", seg.segment(image, p["sam_label"]))
        except ChimeraError as e:
            if e.code == ErrorCode.BUDGET_EXCEEDED:
                raise
            p["error"] = f"{e.code.value}: {e.message[:120]}"
            continue
        m = _mask(png, size)
        px = m.resize((128, 128)).tobytes()
        area = sum(1 for v in px if v > 127) / len(px)
        p["mask_area"] = round(area, 4)
        if area >= PRESENT_FILL:
            c = COLORS[role]
            p.update(found=True, status="found", color="#{:02x}{:02x}{:02x}".format(*c))
            found.append((p, m))
    over = base.copy()
    for p, m in sorted(found, key=lambda x: -x[0]["mask_area"]):  # large parts first, small parts drawn on top
        c = COLORS[p["parent_role"]]
        layer = Image.new("RGB", size, c)
        over = Image.composite(Image.blend(over, layer, ALPHA), over, m)
    legend_h = 22 * (len(parts) + 1) + 8
    sheet = Image.new("RGB", (size[0], size[1] + legend_h), "white")
    sheet.paste(over, (0, 0))
    d = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    y = size[1] + 6
    d.text((8, y), "Anatomy map (SAM masks; color = source parent; 'not located' = SAM found no mask)", fill="black",
           font=font)
    for p in parts:
        y += 22
        if p["found"]:
            d.rectangle([8, y, 24, y + 14], fill=COLORS[p["parent_role"]])
        else:
            d.rectangle([8, y, 24, y + 14], outline=(150, 150, 150))
        where = f", {p['mask_area'] * 100:.1f}% of frame" if p["found"] else ""
        d.text((32, y), f"{p['part']} - {p['parent_name']} ({p['parent_role']}) - {p['status']}{where}",
               fill="black", font=font)
    out = io.BytesIO()
    sheet.save(out, "PNG")
    legend = {r: "#{:02x}{:02x}{:02x}".format(*COLORS[r]) for r in ("host", "donor", "blend")}
    return out.getvalue(), {"parts": parts, "colors": legend, "present_fill": PRESENT_FILL,
                            "found": sum(p["found"] for p in parts), "not_located": sum(not p["found"] for p in parts),
                            "image_size": list(size)}
