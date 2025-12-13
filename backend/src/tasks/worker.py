from arq import create_pool
from arq.connections import RedisSettings
import asyncio
import json

async def publish_progress(ctx, job_id: str, step: str, payload: dict):
    await ctx['redis'].publish(f"progress:{job_id}", json.dumps({"step": step, **payload}))

KB_STATE_TTL_SEC = 24 * 60 * 60

async def persist_kb_rebuild_state(ctx, job_id: str, state: dict):
    try:
        await ctx['redis'].set(f"kb:rebuild:{job_id}", json.dumps(state, ensure_ascii=False), ex=KB_STATE_TTL_SEC)
    except Exception:
        return

async def magic_fill_job(ctx, job_id: str, topic_uid: str, topic_title: str):
    await publish_progress(ctx, job_id, "started", {"topic_uid": topic_uid})
    await asyncio.sleep(0.5)
    await publish_progress(ctx, job_id, "concepts", {"count": 5})
    await asyncio.sleep(0.5)
    await publish_progress(ctx, job_id, "skills", {"count": 3})
    await asyncio.sleep(0.5)
    await publish_progress(ctx, job_id, "done", {})

async def kb_validate_job(ctx, job_id: str, subject_uid: str | None = None, auto_publish: bool = False):
    state = {"ok": True, "status": "running"}
    try:
        from src.services.graph.utils import build_graph_from_neo4j
        from src.services.validation import validate_canonical_graph_snapshot
        snapshot = build_graph_from_neo4j(subject_filter=subject_uid)
        res = validate_canonical_graph_snapshot({"nodes": snapshot.get("nodes", []), "edges": snapshot.get("edges", [])})
        state = {"ok": True, "status": "done", "subject_uid": subject_uid, "result": res, "auto_publish": auto_publish}
        await ctx['redis'].set(f"kb:validate:{job_id}", json.dumps(state, ensure_ascii=False), ex=KB_STATE_TTL_SEC)
        await publish_progress(ctx, job_id, "validate_done", {"ok": res.get("ok"), "errors": len(res.get("errors", [])), "warnings": len(res.get("warnings", []))})

        if auto_publish and res.get("ok"):
            meta = {"job_id": job_id, "published_at": int(__import__('time').time()), "auto": True}
            await ctx['redis'].set("kb:published:current", json.dumps(meta, ensure_ascii=False))
            await publish_progress(ctx, job_id, "published", meta)

        return state
    except Exception as e:
        state = {"ok": False, "status": "error", "error": str(e), "subject_uid": subject_uid, "auto_publish": auto_publish}
        try:
            await ctx['redis'].set(f"kb:validate:{job_id}", json.dumps(state, ensure_ascii=False), ex=KB_STATE_TTL_SEC)
        except Exception:
            pass
        await publish_progress(ctx, job_id, "validate_error", {"error": str(e)})
        return state

async def kb_rebuild_job(ctx, job_id: str, auto_publish: bool = False):
    state = {"ok": True, "status": "running", "stages": []}
    await persist_kb_rebuild_state(ctx, job_id, state)
    await publish_progress(ctx, job_id, "started", {})
    try:
        from src.services.graph.utils import sync_from_jsonl, compute_static_weights, add_prereqs_heuristic, analyze_knowledge
    except Exception as e:
        state = {"ok": False, "status": "error", "error": str(e), "stages": []}
        await persist_kb_rebuild_state(ctx, job_id, state)
        await publish_progress(ctx, job_id, "error", {"error": str(e)})
        return state

    try:
        state["stages"].append("import_jsonl")
        await persist_kb_rebuild_state(ctx, job_id, state)
        await publish_progress(ctx, job_id, "import_jsonl", {})
        sync_stats = sync_from_jsonl()
        state["sync_stats"] = sync_stats
        await persist_kb_rebuild_state(ctx, job_id, state)

        state["stages"].append("compute_static_weights")
        await persist_kb_rebuild_state(ctx, job_id, state)
        await publish_progress(ctx, job_id, "compute_static_weights", {})
        static_weights = compute_static_weights()
        state["static_weights"] = static_weights
        await persist_kb_rebuild_state(ctx, job_id, state)

        state["stages"].append("add_prereqs_heuristic")
        await persist_kb_rebuild_state(ctx, job_id, state)
        await publish_progress(ctx, job_id, "add_prereqs_heuristic", {})
        prereqs_added = add_prereqs_heuristic()
        state["prereqs_added"] = prereqs_added
        await persist_kb_rebuild_state(ctx, job_id, state)

        state["stages"].append("analysis")
        await persist_kb_rebuild_state(ctx, job_id, state)
        await publish_progress(ctx, job_id, "analysis", {})
        metrics = analyze_knowledge()
        state["metrics"] = metrics

        warnings = []
        if metrics.get('topics_without_targets'):
            warnings.append('topics_without_targets')
        if metrics.get('skills_without_methods'):
            warnings.append('skills_without_methods')
        if metrics.get('orphan_sections'):
            warnings.append('orphan_sections')
        state["warnings"] = warnings
        state["status"] = "done"
        await persist_kb_rebuild_state(ctx, job_id, state)

        try:
            from arq.connections import RedisSettings, ArqRedis
            redis = await ArqRedis.create(RedisSettings(host='redis', port=6379))
            await redis.enqueue_job('kb_validate_job', job_id, None, auto_publish)
            await redis.close()
            await publish_progress(ctx, job_id, "validate_queued", {})
        except Exception:
            pass

        await publish_progress(ctx, job_id, "done", {"warnings": warnings})
        return state
    except Exception as e:
        state = {"ok": False, "status": "error", "error": str(e), "stages": state.get("stages", [])}
        await persist_kb_rebuild_state(ctx, job_id, state)
        await publish_progress(ctx, job_id, "error", {"error": str(e)})
        return state

class WorkerSettings:
    redis_settings = RedisSettings(host='redis', port=6379)
    functions = [magic_fill_job, kb_rebuild_job, kb_validate_job]

