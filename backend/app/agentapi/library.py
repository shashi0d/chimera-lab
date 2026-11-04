"""The user's library: workspaces (named canvases), saved chimeras with their animal cards, and deleting images.

Workspaces live in the `graphs` collection under `ws:<user id>:<workspace id>`. The first one, `main`, takes over
the old single canvas (`workspace:<user id>`) the first time the list is read. Every image (lab version) carries the
workspace it was made in (`workspaceId`; images from before workspaces belong to `main`).

Deleting an image removes its record and its files (the image and its card's angle views); a Fusion's first image
also takes its run and creature records with it. Deleting a workspace deletes its images, except those another
workspace's canvas still shows.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.agentapi.lab import (
    GARDEN_PUBLIC,
    VERSION_KIND,
    _err,
    _user,
    get_version,
    lab,
    public_version,
    start_card,
)
from app.agentapi.routes import AgentApi, api
from app.auth import User, current_user
from app.models.schemas import ErrorCode
from app.util import new_id, now_iso

router = APIRouter(prefix="/evo/lab", tags=["library"])
garden_router = APIRouter(prefix="/evo", tags=["garden"])
GARDEN_MAX = 120
log = logging.getLogger(__name__)

MAIN = "main"
MAX_NAME = 80
WS_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
PROFILE_FIELDS = ("name", "length", "weight", "habitat", "explorers_notes")


def _ws_key(user: User, ws_id: str) -> str:
    return f"ws:{user.id}:{ws_id}"


def _ws_view(doc: dict[str, Any], images: int | None = None) -> dict[str, Any]:
    out = {k: doc.get(k) for k in ("id", "name", "createdAt", "updatedAt", "revision")}
    if images is not None:
        out["imageCount"] = images
    return out


def _clean_name(raw: Any, fallback: str) -> str:
    name = " ".join(str(raw or "").split())[:MAX_NAME]
    return name or fallback


async def _versions(a: AgentApi, user: User) -> list[dict[str, Any]]:
    return [d for d in await a.services.db.list("assets", "owner", user.id) if d.get("kind") == VERSION_KIND]


def _in_workspace(doc: dict[str, Any], ws_id: str) -> bool:
    return (doc.get("workspaceId") or MAIN) == ws_id


async def _workspaces(a: AgentApi, user: User) -> list[dict[str, Any]]:
    """The user's workspaces; the old single canvas becomes `main` the first time."""
    db = a.services.db
    docs = [d for d in await db.list("graphs", "owner", user.id) if d.get("kind") == "workspace"]
    if not docs:
        legacy = await db.get("graphs", f"workspace:{user.id}")
        now = now_iso()
        main = {"kind": "workspace", "id": MAIN, "owner": user.id, "name": "My workspace",
                "graph": (legacy or {}).get("graph"), "revision": int((legacy or {}).get("revision", 0)),
                "createdAt": (legacy or {}).get("updatedAt") or now, "updatedAt": (legacy or {}).get("updatedAt") or now}
        await db.put("graphs", _ws_key(user, MAIN), main)
        docs = [main]
    docs.sort(key=lambda d: d.get("updatedAt") or "", reverse=True)
    return docs


async def _workspace(a: AgentApi, user: User, ws_id: str) -> dict[str, Any]:
    if not WS_ID.match(ws_id):
        raise _err(ErrorCode.NOT_FOUND, "This workspace doesn't exist.", 404)
    doc = await a.services.db.get("graphs", _ws_key(user, ws_id))
    if not doc or doc.get("owner") != user.id or doc.get("kind") != "workspace":
        if ws_id == MAIN:  # the first read migrates the old canvas
            await _workspaces(a, user)
            doc = await a.services.db.get("graphs", _ws_key(user, ws_id))
        if not doc:
            raise _err(ErrorCode.NOT_FOUND, "This workspace doesn't exist.", 404)
    return doc


def _version_ids_in(graph: Any) -> set[str]:
    """The lab versions a saved canvas shows (its image cards)."""
    ids: set[str] = set()
    for n in (graph or {}).get("nodes") or []:
        v = ((n or {}).get("data") or {}).get("version") if isinstance(n, dict) else None
        if isinstance(v, dict) and isinstance(v.get("id"), str):
            ids.add(v["id"])
    return ids


# ====================================================================== workspaces


@router.get("/workspaces")
async def list_workspaces(request: Request) -> JSONResponse:
    a = api(request)
    user, _ = await _user(request)
    docs = await _workspaces(a, user)
    versions = await _versions(a, user)
    out = []
    for d in docs:
        mine = sorted((v for v in versions if _in_workspace(v, d["id"])), key=lambda v: v.get("createdAt") or "",
                      reverse=True)
        out.append({**_ws_view(d, len(mine)), "thumbnails": [v.get("imageUrl") for v in mine[:4]]})
    return JSONResponse({"workspaces": out}, headers={"Cache-Control": "no-store"})


@router.post("/workspaces")
async def create_workspace(request: Request) -> JSONResponse:
    a = api(request)
    user, _ = await _user(request)
    try:
        body = await request.json()
    except ValueError:
        body = {}
    existing = await _workspaces(a, user)
    name = _clean_name((body or {}).get("name") if isinstance(body, dict) else None,
                       f"Workspace {len(existing) + 1}")
    now = now_iso()
    doc = {"kind": "workspace", "id": new_id("ws"), "owner": user.id, "name": name, "graph": None, "revision": 0,
           "createdAt": now, "updatedAt": now}
    await a.services.db.put("graphs", _ws_key(user, doc["id"]), doc)
    return JSONResponse(_ws_view(doc, 0), status_code=201)


@router.get("/workspaces/{ws_id}")
async def get_workspace(ws_id: str, request: Request) -> JSONResponse:
    a = api(request)
    user, _ = await _user(request)
    doc = await _workspace(a, user, ws_id)
    return JSONResponse({**_ws_view(doc), "graph": doc.get("graph")}, headers={"Cache-Control": "no-store"})


@router.put("/workspaces/{ws_id}")
async def put_workspace(ws_id: str, request: Request) -> JSONResponse:
    """Save the canvas and/or rename the workspace (last write wins)."""
    a = api(request)
    user, _ = await _user(request)
    raw = await request.body()
    if len(raw) > a.settings.lab_workspace_max_bytes:
        raise _err(ErrorCode.FILE_TOO_LARGE, "The workspace is too large to save.", 413)
    try:
        body = json.loads(raw)
    except ValueError as exc:
        raise _err(ErrorCode.VALIDATION_FAILED, "Send the workspace as JSON.", 422) from exc
    if not isinstance(body, dict):
        raise _err(ErrorCode.VALIDATION_FAILED, "Send the workspace as JSON.", 422)
    doc = await _workspace(a, user, ws_id)
    if "graph" in body:
        graph = body["graph"]
        if not isinstance(graph, dict) or not isinstance(graph.get("nodes"), list) or \
                not isinstance(graph.get("edges"), list):
            raise _err(ErrorCode.VALIDATION_FAILED, "The workspace needs nodes and edges.", 422)
        doc["graph"] = graph
        doc["revision"] = int(doc.get("revision", 0)) + 1
    if "name" in body:
        doc["name"] = _clean_name(body["name"], doc.get("name") or "Workspace")
    doc["updatedAt"] = now_iso()
    await a.services.db.put("graphs", _ws_key(user, ws_id), doc)
    return JSONResponse(_ws_view(doc), headers={"Cache-Control": "no-store"})


@router.get("/workspaces/{ws_id}/images")
async def workspace_images(ws_id: str, request: Request) -> JSONResponse:
    a = api(request)
    user, _ = await _user(request)
    await _workspace(a, user, ws_id)
    rows = [public_version(v) for v in await _versions(a, user) if _in_workspace(v, ws_id)]
    rows.sort(key=lambda d: d.get("createdAt") or "", reverse=True)
    return JSONResponse({"images": rows}, headers={"Cache-Control": "no-store"})


@router.delete("/workspaces/{ws_id}")
async def delete_workspace(ws_id: str, request: Request) -> JSONResponse:
    """Delete a workspace and every image made in it, except images another workspace's canvas still shows."""
    a = api(request)
    user, _ = await _user(request)
    await _workspace(a, user, ws_id)
    others = [d for d in await _workspaces(a, user) if d.get("id") != ws_id]
    kept_ids: set[str] = set()
    for d in others:
        kept_ids |= _version_ids_in(d.get("graph"))
    deleted = 0
    for v in await _versions(a, user):
        if _in_workspace(v, ws_id) and v["id"] not in kept_ids:
            await delete_version_doc(a, v)
            deleted += 1
    await a.services.db.delete("graphs", _ws_key(user, ws_id))
    if ws_id == MAIN:  # the old single canvas must not come back as `main`
        await a.services.db.delete("graphs", f"workspace:{user.id}")
    return JSONResponse({"deleted": True, "imagesDeleted": deleted})


# ====================================================================== deleting an image


async def delete_version_doc(a: AgentApi, doc: dict[str, Any]) -> None:
    """The image's record and files (image, card angles); a Fusion's first image also takes its run records."""
    files = a.files
    keys = {doc.get("imageKey")}
    for angle in ((doc.get("card") or {}).get("angles") or []):
        keys.add(files.key_of(angle.get("url")))
    for key in keys:
        if key:
            await files.delete(key)
    db = a.services.db
    await db.delete("assets", doc["id"])
    if doc.get("operation") == "fusion" and doc.get("runId"):
        if doc.get("creatureId"):
            await db.delete("creatures", str(doc["creatureId"]))
        await db.delete("agent_runs", str(doc["runId"]))


@router.delete("/versions/{version_id}")
async def delete_version(version_id: str, request: Request) -> JSONResponse:
    a = api(request)
    user, _ = await _user(request)
    doc = await get_version(a, version_id, user)
    task = lab(request).tasks.pop(f"card:{version_id}", None)
    if task:
        task.cancel()
    await delete_version_doc(a, doc)
    return JSONResponse({"deleted": True})


# ====================================================================== saved chimeras and their cards


@router.put("/versions/{version_id}/saved")
async def set_saved(version_id: str, request: Request) -> JSONResponse:
    """Save (or unsave) a creature at once; saving makes its animal card in the background if it has none."""
    a = api(request)
    user, _ = await _user(request)
    doc = await get_version(a, version_id, user)
    try:
        body = await request.json()
    except ValueError as exc:
        raise _err(ErrorCode.VALIDATION_FAILED, "Choose whether to save this creature.", 422) from exc
    if not isinstance(body, dict) or not isinstance(body.get("saved"), bool):
        raise _err(ErrorCode.VALIDATION_FAILED, "Choose whether to save this creature.", 422)
    doc["saved"] = body["saved"]
    doc["savedAt"] = now_iso() if body["saved"] else None
    await a.services.db.put("assets", version_id, doc)
    if body["saved"]:
        doc["card"] = await start_card(request, user, doc)
    return JSONResponse(public_version(doc), headers={"Cache-Control": "no-store"})


@router.put("/versions/{version_id}/garden")
async def set_shared(version_id: str, request: Request) -> JSONResponse:
    """Share a creature to the Garden (or take it back). Sharing saves it and makes its animal card if it has none."""
    a = api(request)
    user, _ = await _user(request)
    doc = await get_version(a, version_id, user)
    try:
        body = await request.json()
    except ValueError as exc:
        raise _err(ErrorCode.VALIDATION_FAILED, "Choose whether to share this creature.", 422) from exc
    if not isinstance(body, dict) or not isinstance(body.get("shared"), bool):
        raise _err(ErrorCode.VALIDATION_FAILED, "Choose whether to share this creature.", 422)
    if body["shared"]:
        doc["garden"] = GARDEN_PUBLIC
        doc["sharedAt"] = now_iso()
        if not doc.get("saved"):
            doc["saved"], doc["savedAt"] = True, now_iso()
    else:
        doc.pop("garden", None)
        doc["sharedAt"] = None
    await a.services.db.put("assets", version_id, doc)
    if body["shared"]:
        doc["card"] = await start_card(request, user, doc)
    return JSONResponse(public_version(doc), headers={"Cache-Control": "no-store"})


@garden_router.get("/garden")
async def garden(request: Request) -> JSONResponse:
    """Every creature shared to the Garden, by anyone, newest first. No visitor id needed; nothing private is sent
    (no owner, no workspace). `mine` marks the asking visitor's own."""
    a = api(request)
    user = await current_user(request)
    rows = []
    for v in await a.services.db.list("assets", "garden", GARDEN_PUBLIC):
        if v.get("kind") != VERSION_KIND or (v.get("card") or {}).get("status") != "ready":
            continue
        view = public_version(v)
        view.pop("workspaceId", None)
        view["mine"] = bool(user and v.get("owner") == user.id)
        rows.append(view)
    rows.sort(key=lambda d: d.get("sharedAt") or "", reverse=True)
    return JSONResponse({"garden": rows[:GARDEN_MAX]}, headers={"Cache-Control": "no-cache"})


@router.get("/chimeras")
async def chimeras(request: Request) -> JSONResponse:
    """Every saved creature with its card, newest first."""
    from app.agentapi.lab import card_is_live

    a = api(request)
    user, _ = await _user(request)
    rows = []
    for v in await _versions(a, user):
        if not v.get("saved"):
            continue
        view = public_version(v)
        card = v.get("card")
        if card and card.get("status") == "running" and not card_is_live(request, card, v["id"]):
            view["card"] = {**card, "status": "failed", "error": "The card was interrupted. Try again."}
        rows.append(view)
    rows.sort(key=lambda d: d.get("savedAt") or "", reverse=True)
    return JSONResponse({"chimeras": rows}, headers={"Cache-Control": "no-store"})


@router.put("/versions/{version_id}/profile")
async def edit_profile(version_id: str, request: Request) -> JSONResponse:
    """Edit a card's text (name, length, weight, habitat, notes). A new name must still be a creature's name."""
    from app.agentapi.creature_ai import check_topic

    a = api(request)
    user, _ = await _user(request)
    doc = await get_version(a, version_id, user)
    try:
        body = await request.json()
    except ValueError as exc:
        raise _err(ErrorCode.VALIDATION_FAILED, "Send the card's fields.", 422) from exc
    if not isinstance(body, dict):
        raise _err(ErrorCode.VALIDATION_FAILED, "Send the card's fields.", 422)
    profile = dict(doc.get("profile") or {})
    changes = {k: " ".join(str(body[k]).split())[:1500 if k == "explorers_notes" else 120]
               for k in PROFILE_FIELDS if k in body and isinstance(body[k], str)}
    if "name" in changes and not changes["name"]:
        raise _err(ErrorCode.VALIDATION_FAILED, "Give the creature a name.", 422)
    if changes.get("name") and changes["name"] != profile.get("name"):
        await check_topic(a.services.vision, [changes["name"]], [], "name")
    profile.update(changes)
    doc["profile"] = profile
    if changes.get("name"):
        doc["title"] = changes["name"]
    if doc.get("card"):
        doc["card"] = {**doc["card"], "profile": profile}
    await a.services.db.put("assets", version_id, doc)
    return JSONResponse(public_version(doc), headers={"Cache-Control": "no-store"})
