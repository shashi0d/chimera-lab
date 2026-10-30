from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import services, session_id
from app.errors import ChimeraError
from app.models.schemas import ErrorCode, Graph
from app.services import Services

router = APIRouter()
MAX_NODES = 500


@router.put("/graphs/{graph_id}", response_model=None)
async def save_graph(graph_id: str, graph: Graph, svc: Services = Depends(services),
                     sid: str = Depends(session_id)) -> dict[str, object]:
    if graph.graph_id != graph_id:
        raise ChimeraError(ErrorCode.VALIDATION_FAILED, "Graph id doesn't match the URL.")
    if len(graph.nodes) > MAX_NODES:
        raise ChimeraError(ErrorCode.VALIDATION_FAILED, f"A canvas can hold at most {MAX_NODES} nodes.")
    existing = await svc.db.get("graphs", graph_id)
    if existing and existing.get("sessionId") not in (None, sid):
        raise ChimeraError(ErrorCode.NOT_FOUND, "Graph not found.")
    await svc.db.put("graphs", graph_id, {"sessionId": sid, "graph": graph.dump()})
    return graph.dump()


@router.get("/graphs/{graph_id}", response_model=None)
async def load_graph(graph_id: str, svc: Services = Depends(services),
                     sid: str = Depends(session_id)) -> dict[str, object]:
    doc = await svc.db.get("graphs", graph_id)
    if doc is None or doc.get("sessionId") not in (None, sid):
        raise ChimeraError(ErrorCode.NOT_FOUND, "Graph not found.")
    return doc["graph"]  # type: ignore[no-any-return]
