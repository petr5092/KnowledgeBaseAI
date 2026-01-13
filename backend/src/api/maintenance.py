from fastapi import APIRouter, HTTPException, Header, Security
from fastapi.security import HTTPBearer
from typing import Dict, Optional
from pydantic import BaseModel
from src.services.jobs.rebuild import start_rebuild_async, get_job_status
from src.services.graph.utils import recompute_relationship_weights
from src.workers.integrity_async import process_once
from src.workers.outbox_publisher import process_once as outbox_publish_once
from src.api.common import StandardResponse

router = APIRouter(prefix="/v1/maintenance", tags=["Обслуживание"], dependencies=[Security(HTTPBearer())])

class JobQueuedResponse(BaseModel):
    job_id: str
    queued: bool
    ws: Optional[str] = None
    auto_publish: Optional[bool] = None

class PublishResponse(BaseModel):
    ok: bool
    published_at: Optional[int] = None
    job_id: Optional[str] = None
    status: Optional[str] = None

class ProcessedResponse(BaseModel):
    ok: bool
    processed: int

@router.post("/kb/rebuild_async", summary="Асинхронная пересборка KB", description="Запускает задачу пересборки базы знаний (ARQ/Redis), возвращает job_id и WebSocket для прогресса.", response_model=StandardResponse)
async def kb_rebuild_async(x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    """
    Принимает:
      - нет входных параметров

    Возвращает:
      - job_id: идентификатор задачи
      - queued: признак постановки в очередь
      - ws: путь WebSocket для отслеживания прогресса
    """
    job_id = str(int(__import__('time').time() * 1000))
    try:
        from arq.connections import RedisSettings, ArqRedis
        redis = await ArqRedis.create(RedisSettings(host='redis', port=6379))
        await redis.enqueue_job('kb_rebuild_job', job_id)
        await redis.close()
        return {"items": [{"job_id": job_id, "queued": True, "ws": f"/ws/progress?job_id={job_id}"}], "meta": {}}
    except Exception:
        r = start_rebuild_async()
        return {"items": [r], "meta": {}}

@router.post("/kb/pipeline_async", summary="Асинхронный конвейер KB", description="Запускает конвейер пересборки, опционально публикует результаты после валидации.", response_model=StandardResponse)
async def kb_pipeline_async(auto_publish: bool = False, x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    """
    Принимает:
      - auto_publish: публиковать ли автоматически после успешной валидации

    Возвращает:
      - job_id: идентификатор задачи
      - queued: признак постановки в очередь
      - ws: путь WebSocket
      - auto_publish: отражение входного параметра
    """
    job_id = str(int(__import__('time').time() * 1000))
    try:
        from arq.connections import RedisSettings, ArqRedis
        redis = await ArqRedis.create(RedisSettings(host='redis', port=6379))
        await redis.enqueue_job('kb_rebuild_job', job_id, auto_publish)
        await redis.close()
        return {"items": [{"job_id": job_id, "queued": True, "ws": f"/ws/progress?job_id={job_id}", "auto_publish": auto_publish}], "meta": {}}
    except Exception:
        r = start_rebuild_async()
        return {"items": [r], "meta": {}}

@router.get("/kb/rebuild_status", summary="Статус пересборки", description="Возвращает статус задачи пересборки по job_id.", response_model=StandardResponse)
async def kb_rebuild_status(job_id: str) -> Dict:
    """
    Принимает:
      - job_id: идентификатор задачи

    Возвращает:
      - объект статуса пересборки
    """
    try:
        from redis.asyncio import Redis
        r = Redis(host="redis", port=6379)
        raw = await r.get(f"kb:rebuild:{job_id}")
        await r.close()
        if raw:
            try:
                import json
                if isinstance(raw, (bytes, bytearray)):
                    raw = raw.decode("utf-8")
                return {"items": [json.loads(raw)], "meta": {}}
            except Exception:
                return {"items": [{"ok": False, "status": "error", "error": "invalid redis payload"}], "meta": {}}
    except Exception:
        pass
    return {"items": [get_job_status(job_id)], "meta": {}}

@router.get("/kb/rebuild_state", summary="Текущее состояние пересборки", description="Возвращает текущее состояние пересборки (из Redis) или из резервного источника.", response_model=StandardResponse)
async def kb_rebuild_state(job_id: str) -> Dict:
    """
    Принимает:
      - job_id: идентификатор задачи

    Возвращает:
      - объект текущего состояния
    """
    try:
        from redis.asyncio import Redis
        r = Redis(host="redis", port=6379)
        raw = await r.get(f"kb:rebuild:{job_id}")
        await r.close()
        if raw:
            import json
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode("utf-8")
            return {"items": [json.loads(raw)], "meta": {}}
    except Exception:
        pass
    return {"items": [get_job_status(job_id)], "meta": {}}

@router.get("/kb/validate_state", summary="Состояние валидации", description="Возвращает состояние результата валидации по job_id.", response_model=StandardResponse)
async def kb_validate_state(job_id: str) -> Dict:
    """
    Принимает:
      - job_id: идентификатор задачи

    Возвращает:
      - объект результата валидации
    """
    try:
        from redis.asyncio import Redis
        r = Redis(host="redis", port=6379)
        raw = await r.get(f"kb:validate:{job_id}")
        await r.close()
        if raw:
            import json
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode("utf-8")
            return {"items": [json.loads(raw)], "meta": {}}
    except Exception:
        pass
    return {"items": [{"status": "unknown"}], "meta": {}}

@router.post("/kb/validate_async", summary="Асинхронная валидация", description="Ставит задачу валидации графа в очередь.", response_model=StandardResponse)
async def kb_validate_async(job_id: str, subject_uid: str | None = None, x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    """
    Принимает:
      - job_id: идентификатор задачи
      - subject_uid: опционально, конкретный предмет для валидации

    Возвращает:
      - job_id: идентификатор задачи
      - queued: признак постановки в очередь
      - ws: путь WebSocket
    """
    try:
        from arq.connections import RedisSettings, ArqRedis
        redis = await ArqRedis.create(RedisSettings(host='redis', port=6379))
        await redis.enqueue_job('kb_validate_job', job_id, subject_uid)
        await redis.close()
        return {"items": [{"job_id": job_id, "queued": True, "ws": f"/ws/progress?job_id={job_id}"}], "meta": {}}
    except Exception:
        return {"items": [{"job_id": job_id, "queued": False}], "meta": {}}

@router.post("/kb/publish", summary="Публикация валидированного графа", description="Публикует результат пересборки, если валидация прошла успешно.", response_model=StandardResponse)
async def kb_publish(job_id: str, x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    """
    Принимает:
      - job_id: идентификатор задачи валидации

    Возвращает:
      - ok: признак успеха
      - published_at: отметка времени публикации
      - job_id: идентификатор задачи
    """
    try:
        from redis.asyncio import Redis
        r = Redis(host="redis", port=6379)
        raw = await r.get(f"kb:validate:{job_id}")
        if not raw:
            await r.close()
            raise HTTPException(status_code=409, detail="validation result not found")
        import json
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode("utf-8")
        v = json.loads(raw)
        res = (v.get("result") or {})
        if not res.get("ok"):
            await r.close()
            raise HTTPException(status_code=409, detail={"error": "validation_failed", "errors": res.get("errors", []), "warnings": res.get("warnings", [])})
        meta = {"job_id": job_id, "published_at": int(__import__('time').time())}
        await r.set("kb:published:current", json.dumps(meta, ensure_ascii=False))
        await r.close()
        return {"items": [{"ok": True, **meta}], "meta": {}}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/kb/published", summary="Текущая опубликованная версия", description="Возвращает метаданные последней опубликованной версии графа.", response_model=StandardResponse)
async def kb_published() -> Dict:
    """
    Принимает:
      - нет входных параметров

    Возвращает:
      - status: 'none' если не публиковалось
      - иначе объект метаданных публикации
    """
    try:
        from redis.asyncio import Redis
        r = Redis(host="redis", port=6379)
        raw = await r.get("kb:published:current")
        await r.close()
        if not raw:
            return {"items": [], "meta": {"status": "none"}}
        import json
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode("utf-8")
        return {"items": [json.loads(raw)], "meta": {}}
    except Exception:
        return {"items": [{"status": "unknown"}], "meta": {}}

@router.post("/recompute_links", summary="Пересчет весов связей", description="Пересчитывает статические веса отношений в графе.", response_model=StandardResponse)
async def recompute_links(x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    """
    Принимает:
      - нет входных параметров

    Возвращает:
      - ok: True
      - stats: объект статистики пересчета
    """
    stats = recompute_relationship_weights()
    return {"items": [{"ok": True, "stats": stats}], "meta": {}}

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
