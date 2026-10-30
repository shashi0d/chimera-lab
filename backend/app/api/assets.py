from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Request, UploadFile
from fastapi.responses import Response

from app.api.deps import mock_fault, services, session_id
from app.assets_service import normalise
from app.errors import ChimeraError
from app.models.schemas import Asset, ErrorCode
from app.services import Services
from app.util import new_id, now_iso

router = APIRouter()


async def _read_limited(file: UploadFile, limit: int) -> bytes:
    chunks, total = [], 0
    while chunk := await file.read(1024 * 1024):
        total += len(chunk)
        if total > limit:
            raise ChimeraError(ErrorCode.FILE_TOO_LARGE, f"This file is over {limit // (1024 * 1024)} MB.",
                               details={"maxBytes": limit})
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/assets", status_code=201, response_model=None)
async def upload_asset(
    request: Request,
    file: UploadFile,
    svc: Services = Depends(services),
    sid: str = Depends(session_id),
    fault: str | None = Depends(mock_fault),
) -> dict[str, object]:
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > svc.settings.max_upload_bytes + 64 * 1024:
        raise ChimeraError(ErrorCode.FILE_TOO_LARGE, "This file is over 20 MB.")
    if fault == "slow":
        await asyncio.sleep(4 * svc.settings.mock_delay_scale)
    raw = await _read_limited(file, svc.settings.max_upload_bytes)
    norm = await asyncio.to_thread(normalise, raw, min_short_side=svc.settings.min_short_side)
    asset_id = new_id("ast")
    key = f"assets/{asset_id}"
    await svc.storage.put(key, norm.data, norm.content_type)
    asset = Asset(asset_id=asset_id, width=norm.width, height=norm.height, sha256=norm.sha256,
                  content_type=norm.content_type, url=await svc.storage.get_url(key), created_at=now_iso())
    await svc.db.put("assets", asset_id, {**asset.dump(), "storageKey": key, "kind": "upload", "sessionId": sid,
                                          "fileName": (file.filename or "")[:200]})
    return asset.dump()


async def _asset_doc(svc: Services, asset_id: str) -> dict[str, object]:
    doc = await svc.db.get("assets", asset_id)
    if doc is None:
        raise ChimeraError(ErrorCode.NOT_FOUND, "Image not found.")
    return doc


@router.get("/assets/{asset_id}", response_model=None)
async def get_asset(asset_id: str, svc: Services = Depends(services)) -> dict[str, object]:
    doc = await _asset_doc(svc, asset_id)
    doc["url"] = await svc.storage.get_url(str(doc["storageKey"]))
    return Asset.model_validate(doc).dump()


@router.get("/assets/{asset_id}/content")
async def asset_content(asset_id: str, svc: Services = Depends(services)) -> Response:
    doc = await _asset_doc(svc, asset_id)
    data = await svc.storage.get(str(doc["storageKey"]))
    return Response(data, media_type=str(doc["contentType"]),
                    headers={"Cache-Control": "public, max-age=31536000, immutable"})
