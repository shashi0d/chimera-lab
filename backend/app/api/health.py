from fastapi import APIRouter, Depends

from app.api.deps import services
from app.config import APP_VERSION
from app.data.loader import ChimeraData
from app.models.schemas import DataHealth, Health
from app.pipeline.steps.rules_check import CHECKS
from app.services import Services

router = APIRouter()


def _data_health(data: ChimeraData) -> DataHealth:
    return DataHealth.model_validate(data.health(set(CHECKS)))


@router.get("/health", response_model=None)
async def health(svc: Services = Depends(services)) -> dict[str, object]:
    data = _data_health(svc.data)
    return Health(
        status="degraded" if data.problems else "ok",
        mode=svc.settings.chimera_mode,  # type: ignore[arg-type]
        version=APP_VERSION,
        data_source=svc.data.source,  # type: ignore[arg-type]
        data=data,
    ).dump()
