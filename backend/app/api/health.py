from fastapi import APIRouter, Depends

from app.api.deps import services
from app.config import APP_VERSION
from app.models.schemas import Health
from app.services import Services

router = APIRouter()


@router.get("/health", response_model=None)
async def health(svc: Services = Depends(services)) -> dict[str, object]:
    return Health(mode=svc.settings.chimera_mode, version=APP_VERSION, data_source=svc.data.source).dump()  # type: ignore[arg-type]
