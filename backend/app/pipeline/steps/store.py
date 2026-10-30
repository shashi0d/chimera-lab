from __future__ import annotations

import hashlib

from app.models.schemas import Asset, Creature, RunResult
from app.pipeline.context import RunContext
from app.util import new_id, now_iso


async def run(ctx: RunContext) -> str:
    services = ctx.services
    generated = ctx.state["generated"]
    width, height = ctx.state.get("generated_size", (0, 0))
    asset_id = new_id("ast")
    key = f"assets/{asset_id}"
    await services.storage.put(key, generated.data, generated.content_type)
    asset = Asset(
        asset_id=asset_id, width=width, height=height, sha256=hashlib.sha256(generated.data).hexdigest(),
        content_type=generated.content_type, url=await services.storage.get_url(key), created_at=now_iso(),
    )
    await services.db.put("assets", asset_id, {**asset.dump(), "storageKey": key, "kind": "generated",
                                               "sessionId": ctx.run.session_id})
    creature = Creature(
        creature_id=new_id("crt"), run_id=ctx.run.id, asset_id=asset_id,
        parent_asset_ids=[i.asset_id for i in ctx.inputs], spec=ctx.state["spec"], created_at=now_iso(),
    )
    await services.db.put("creatures", creature.creature_id, {**creature.dump(), "metaResponseId": generated.response_id})
    ctx.state["result"] = RunResult(
        asset_id=asset_id, creature_id=creature.creature_id, image_url=asset.url, spec=ctx.state["spec"],
        meta_response_id=generated.response_id,
    )
    return "Saved with lineage"
