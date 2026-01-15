from fastapi import APIRouter, HTTPException, Header, Security
from fastapi.security import HTTPBearer
from typing import Dict, Optional
from pydantic import BaseModel
from app.workers.integrity_async import process_once
from app.workers.outbox_publisher import process_once as outbox_publish_once
from app.api.common import StandardResponse

router = APIRouter(prefix="/v1/maintenance", tags=["Обслуживание"], dependencies=[Security(HTTPBearer())])

class ProcessedResponse(BaseModel):
    ok: bool
    processed: int

@router.post("/proposals/run_integrity_async", summary="Асинхронная проверка целостности заявок", description="Запускает проверку заявок на целостность в фоне.", response_model=StandardResponse)
async def run_integrity_async(limit: int = 20, x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    """
    Принимает:
      - limit: количество заявок для обработки за запуск

    Возвращает:
      - ok: True
      - processed: количество обработанных заявок
    """
    try:
        res = process_once(limit=limit)
        return {"items": [{"ok": True, "processed": res.get("processed", 0)}], "meta": {}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/events/publish_outbox", summary="Публикация событий из Outbox", description="Публикует накопленные события из Outbox.", response_model=StandardResponse)
async def publish_outbox(limit: int = 100, x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    """
    Принимает:
      - limit: максимальное количество событий для публикации

    Возвращает:
      - ok: True
      - processed: количество опубликованных событий
    """
    try:
        res = outbox_publish_once(limit=limit)
        return {"items": [{"ok": True, "processed": res.get("processed", 0)}], "meta": {}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
