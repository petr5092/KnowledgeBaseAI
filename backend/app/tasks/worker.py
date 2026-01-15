from arq import create_pool, cron
from arq.connections import RedisSettings
import asyncio
import json

async def vector_consume_job(ctx):
    try:
        from app.workers.vector_sync import consume_graph_committed
        processed = 0
        while True:
            res = consume_graph_committed()
            if not res or res.get("processed", 0) == 0:
                break
            processed += res.get("processed", 0)
        return {"processed": processed}
    except Exception:
        return {"processed": 0}

async def outbox_publish_job(ctx):
    try:
        from app.workers.outbox_publisher import process_once
        return process_once()
    except Exception:
        return {"processed": 0}

class WorkerSettings:
    redis_settings = RedisSettings(host='redis', port=6379)
    functions = [vector_consume_job, outbox_publish_job]
    cron_jobs = [
        cron(vector_consume_job, second={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}),
        cron(outbox_publish_job, second={2, 7, 12, 17, 22, 27, 32, 37, 42, 47, 52, 57}),
    ]
