from fastapi import APIRouter, HTTPException
from typing import Dict
from src.services.jobs.rebuild import start_rebuild_async, get_job_status
from src.services.graph.utils import recompute_relationship_weights
from src.workers.integrity_async import process_once
from src.workers.outbox_publisher import process_once as outbox_publish_once

router = APIRouter(prefix="/v1/maintenance")

@router.post("/kb/rebuild_async")
async def kb_rebuild_async() -> Dict:
    job_id = str(int(__import__('time').time() * 1000))
    try:
        from arq.connections import RedisSettings, ArqRedis
        redis = await ArqRedis.create(RedisSettings(host='redis', port=6379))
        await redis.enqueue_job('kb_rebuild_job', job_id)
        await redis.close()
        return {"job_id": job_id, "queued": True, "ws": f"/ws/progress?job_id={job_id}"}
    except Exception:
        return start_rebuild_async()

@router.post("/kb/pipeline_async")
async def kb_pipeline_async(auto_publish: bool = False) -> Dict:
    job_id = str(int(__import__('time').time() * 1000))
    try:
        from arq.connections import RedisSettings, ArqRedis
        redis = await ArqRedis.create(RedisSettings(host='redis', port=6379))
        await redis.enqueue_job('kb_rebuild_job', job_id, auto_publish)
        await redis.close()
        return {"job_id": job_id, "queued": True, "ws": f"/ws/progress?job_id={job_id}", "auto_publish": auto_publish}
    except Exception:
        return start_rebuild_async()

@router.get("/kb/rebuild_status")
async def kb_rebuild_status(job_id: str) -> Dict:
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
                return json.loads(raw)
            except Exception:
                return {"ok": False, "status": "error", "error": "invalid redis payload"}
    except Exception:
        pass
    return get_job_status(job_id)

@router.get("/kb/rebuild_state")
async def kb_rebuild_state(job_id: str) -> Dict:
    try:
        from redis.asyncio import Redis
        r = Redis(host="redis", port=6379)
        raw = await r.get(f"kb:rebuild:{job_id}")
        await r.close()
        if raw:
            import json
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode("utf-8")
            return json.loads(raw)
    except Exception:
        pass
    return get_job_status(job_id)

@router.get("/kb/validate_state")
async def kb_validate_state(job_id: str) -> Dict:
    try:
        from redis.asyncio import Redis
        r = Redis(host="redis", port=6379)
        raw = await r.get(f"kb:validate:{job_id}")
        await r.close()
        if raw:
            import json
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode("utf-8")
            return json.loads(raw)
    except Exception:
        pass
    return {"status": "unknown"}

@router.post("/kb/validate_async")
async def kb_validate_async(job_id: str, subject_uid: str | None = None) -> Dict:
    try:
        from arq.connections import RedisSettings, ArqRedis
        redis = await ArqRedis.create(RedisSettings(host='redis', port=6379))
        await redis.enqueue_job('kb_validate_job', job_id, subject_uid)
        await redis.close()
        return {"job_id": job_id, "queued": True, "ws": f"/ws/progress?job_id={job_id}"}
    except Exception:
        return {"job_id": job_id, "queued": False}

@router.post("/kb/publish")
async def kb_publish(job_id: str) -> Dict:
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
        return {"ok": True, **meta}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/kb/published")
async def kb_published() -> Dict:
    try:
        from redis.asyncio import Redis
        r = Redis(host="redis", port=6379)
        raw = await r.get("kb:published:current")
        await r.close()
        if not raw:
            return {"status": "none"}
        import json
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode("utf-8")
        return json.loads(raw)
    except Exception:
        return {"status": "unknown"}

@router.post("/recompute_links")
async def recompute_links() -> Dict:
    stats = recompute_relationship_weights()
    return {"ok": True, "stats": stats}

@router.post("/proposals/run_integrity_async")
async def run_integrity_async(limit: int = 20) -> Dict:
    try:
        res = process_once(limit=limit)
        return {"ok": True, "processed": res.get("processed", 0)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/events/publish_outbox")
async def publish_outbox(limit: int = 100) -> Dict:
    try:
        res = outbox_publish_once(limit=limit)
        return {"ok": True, "processed": res.get("processed", 0)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
