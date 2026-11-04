"""Creatures saved by agent runs, the gallery, and the S5 showcase seed.

Creatures live in the `creatures` table as {"kind": "evo_agent", "creatureId", "createdAt", "source", "owner",
"view": Creature, "trace": [...], "publications": [...]}. The `showcase` flag is not stored: it is read from
EVO_SHOWCASE at request time, so the list can change without re-seeding.

The gallery is the showcase plus what users chose to publish from the Lab (kind "lab_publication": a final version
with its whole path, app/agentapi/lab.py). A user's run creature stays private to them unless a version of it is
published.

The showcase creatures are seeded on first use from the S5 benchmark outputs (EVO_SHOWCASE_DIR/<case>/agent/): the
agent's doc, plan, trace, critic answers and images, converted to gallery JPEGs in public storage. A case whose folder
is missing is skipped with a warning.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.adapters.base import DbAdapter
from app.agentapi.creature import build_creature, gallery_item, parent_view
from app.agentapi.files import PublicFiles
from app.auth import User
from app.config import Settings

log = logging.getLogger(__name__)
KIND = "evo_agent"
PUBLICATION = "lab_publication"
SEED_VERSION = 1
SHOWCASE_EPOCH = datetime(2026, 11, 1, 20, 0, 0, tzinfo=UTC)


def showcase_id(case: str) -> str:
    return case if case.startswith("crt_") else f"crt_s5_{case}"


def _J(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def scientific_name(animal_id: str | None) -> str | None:
    if not animal_id:
        return None
    from app.evolution.data import DATA, taxonomy

    a = taxonomy().animals.get(animal_id)
    if a is not None and a.scientific_name:
        return a.scientific_name
    try:
        learned = _J(DATA / "learned_animals.json").get("animals", {})
    except (OSError, ValueError):
        return None
    return (learned.get(animal_id) or {}).get("scientific_name")


class Creatures:
    def __init__(self, db: DbAdapter, files: PublicFiles, settings: Settings) -> None:
        self.db, self.files, self.settings = db, files, settings
        self._seeded = False
        self._seed_lock = asyncio.Lock()

    # ------------------------------------------------------------ store

    async def save(self, view: dict[str, Any], source: str, **extra: Any) -> None:
        doc = {"kind": KIND, "creatureId": view["creatureId"], "createdAt": view["createdAt"], "source": source,
               "view": view, **extra}
        await self.db.put("creatures", view["creatureId"], doc)

    def _present(self, view: dict[str, Any]) -> dict[str, Any]:
        show = {showcase_id(c) for c in self.settings.showcase_list}
        return {**view, "showcase": view["creatureId"] in show}

    def _is_showcase(self, creature_id: str) -> bool:
        return creature_id in {showcase_id(c) for c in self.settings.showcase_list}

    async def get(self, creature_id: str, user: User | None = None) -> dict[str, Any] | None:
        """A creature card: public when it is in the showcase or published, else only for its owner."""
        await self.ensure_showcase()
        doc = await self.db.get("creatures", creature_id)
        if not doc or doc.get("kind") != KIND:
            return None
        public = self._is_showcase(creature_id) or bool(doc.get("publications"))
        if not public and (user is None or doc.get("owner") != user.id):
            return None
        return self._present(doc["view"])

    async def publication(self, publication_id: str) -> dict[str, Any] | None:
        doc = await self.db.get("creatures", publication_id)
        if not doc or doc.get("kind") != PUBLICATION or doc.get("unpublished"):
            return None
        return publication_view(doc)

    async def gallery(self, limit: int, cursor: str | None) -> dict[str, Any]:
        """The showcase first (in EVO_SHOWCASE order), then published creations, newest first."""
        await self.ensure_showcase()
        docs = await self.db.list("creatures", "kind", KIND)
        order = [showcase_id(c) for c in self.settings.showcase_list]
        by_id = {d["creatureId"]: d for d in docs}
        first = [gallery_item(self._present(by_id[i]["view"])) | {"kind": "showcase"} for i in order if i in by_id]
        pubs = [d for d in await self.db.list("creatures", "kind", PUBLICATION) if not d.get("unpublished")]
        pubs.sort(key=lambda d: d["createdAt"], reverse=True)
        items = first + [publication_item(d) for d in pubs]
        start = _decode_cursor(cursor)
        page = items[start:start + limit]
        nxt = start + limit
        return {"items": page, "nextCursor": _encode_cursor(nxt) if nxt < len(items) else None}

    # ------------------------------------------------------------ showcase seed

    async def ensure_showcase(self) -> None:
        if self._seeded:
            return
        async with self._seed_lock:
            if self._seeded:
                return
            root = self.settings.repo_path(self.settings.evo_showcase_dir)
            for i, case in enumerate(self.settings.showcase_list):
                if case.startswith("crt_"):
                    continue  # a live creature by id: nothing to seed
                cid = showcase_id(case)
                have = await self.db.get("creatures", cid)
                if have and have.get("seedVersion") == SEED_VERSION:
                    continue
                folder = root / case / "agent"
                if not (folder / "doc.json").exists():
                    log.warning("showcase %s: no S5 output at %s; skipped", case, folder)
                    continue
                try:
                    view, trace = await self._seed_case(case, folder, cid, SHOWCASE_EPOCH + timedelta(hours=i))
                except Exception:  # noqa: BLE001 - a broken folder must not take the gallery down
                    log.exception("showcase %s: could not be seeded", case)
                    continue
                await self.save(view, "showcase", trace=trace, seedVersion=SEED_VERSION, case=case)
            self._seeded = True

    async def _seed_case(self, case: str, d: Path, cid: str, created: datetime) -> tuple[dict[str, Any], Any]:
        doc, meta, plan = _J(d / "doc.json"), _J(d / "meta.json"), _J(d / "plan.json")
        crit, trace = _J(d / "critic.json"), _J(d / "trace.json")
        parents = plan.get("parents") or {}
        names = {"sire": meta.get("sire"), "dam": meta.get("dam")}
        try:
            from app.evolution.benchmark import cases

            c = next((c for c in cases() if c["id"] == case), None)
            if c:
                names = {"sire": c["sire"], "dam": c["dam"]}
        except (OSError, ValueError):
            pass
        sire = parent_view(names["sire"], scientific_name(parents.get("sire")))
        dam = parent_view(names["dam"], scientific_name(parents.get("dam")))
        images = []
        for iid, info in crit.items():
            src = d / f"{iid}.webp"
            if not src.exists():
                src = next(d.glob(f"{iid}.*"))
            url = await self.files.put_jpeg(f"showcase/{case}/{iid}.jpg", src.read_bytes())
            images.append({"imageId": iid, "url": url, "kind": info.get("kind", "render"),
                           "verdict": info.get("verdict")})
        overlay = None
        if (d / "anatomy_map.png").exists():
            overlay = await self.files.put_jpeg(f"showcase/{case}/anatomy.jpg", (d / "anatomy_map.png").read_bytes())
        asked = any(s.get("tool") == "ask_user" and ((s.get("result") or {}).get("answer")) for s in trace)
        view = build_creature(
            creature_id=cid, created_at=created.strftime("%Y-%m-%dT%H:%M:%SZ"), sire=sire, dam=dam,
            mode=meta.get("mode") or plan.get("design_mode"), card=doc["card"], plan=plan,
            route_mode=(doc.get("route") or {}).get("mode"), image_id=doc["image_id"], trace=trace, images=images,
            overlay_url=overlay, run_id=None, host_by="user" if asked else None,
            stats={"renders": meta.get("renders"), "edits": meta.get("edits"), "toolCalls": meta.get("tool_calls"),
                   "seconds": meta.get("wall_seconds")})
        return view, trace


def publication_item(doc: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "creation", "creatureId": doc["creatureId"], "title": doc.get("title"), "sire": doc.get("sire"),
            "dam": doc.get("dam"), "mode": doc.get("mode"), "imageUrl": doc.get("imageUrl"), "showcase": False,
            "createdAt": doc.get("createdAt"), "steps": len(doc.get("steps") or [])}


def publication_view(doc: dict[str, Any]) -> dict[str, Any]:
    """A published creation with its path: the parents, the Fusion run's creature, then every edit to the final."""
    return {"publicationId": doc["creatureId"], "title": doc.get("title"), "createdAt": doc.get("createdAt"),
            "sire": doc.get("sire"), "dam": doc.get("dam"), "mode": doc.get("mode"), "imageUrl": doc.get("imageUrl"),
            "sourceCreatureId": doc.get("sourceCreatureId"), "steps": doc.get("steps") or []}


def _encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(f"o:{offset}".encode()).decode().rstrip("=")


def _decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        return max(0, int(raw.split(":", 1)[1]))
    except (ValueError, IndexError):
        return 0
