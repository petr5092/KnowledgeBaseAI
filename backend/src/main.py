import asyncio
from fastapi import FastAPI
from src.core.logging import setup_logging, logger
from src.config.settings import settings
from src.api.graph import router as graph_router
from src.api.construct import router as construct_router
from src.api.analytics import router as analytics_router
from src.api.ws import router as ws_router
from src.api.curriculum import router as curriculum_router
from src.api.admin import router as admin_router
from src.api.admin_curriculum import router as admin_curriculum_router
from src.api.admin_generate import router as admin_generate_router
from src.api.levels import router as levels_router
from src.api.maintenance import router as maintenance_router
try:
    from src.api.graphql import router as graphql_router
except Exception:
    graphql_router = None
from src.api.validation import router as validation_router
from src.api.auth import router as auth_router
from src.services.auth.users_repo import ensure_bootstrap_admin
try:
    from prometheus_client import Counter, Histogram
except Exception:
    class Counter:
        def __init__(self, *args, **kwargs): ...
        def inc(self): ...
    class Histogram:
        def __init__(self, *args, **kwargs): ...
        class _Ctx:
            def __enter__(self): ...
            def __exit__(self, a, b, c): ...
        def time(self): return self._Ctx()

app = FastAPI(title="Headless Knowledge Graph Platform")

REQ_COUNTER = Counter("http_requests_total", "Total HTTP requests")
LATENCY = Histogram("http_request_latency_ms", "Request latency ms")

@app.on_event("startup")
async def on_startup():
    setup_logging()
    logger.info("startup", neo4j_uri=settings.neo4j_uri)
    ensure_bootstrap_admin()

@app.middleware("http")
async def metrics_middleware(request, call_next):
    REQ_COUNTER.inc()
    with LATENCY.time():
        resp = await call_next(request)
    return resp

@app.get("/health")
async def health():
    return {"openai": bool(settings.openai_api_key.get_secret_value()), "neo4j": bool(settings.neo4j_uri)}

app.include_router(graph_router)
app.include_router(construct_router)
app.include_router(analytics_router)
app.include_router(ws_router)
app.include_router(curriculum_router)
app.include_router(admin_router)
app.include_router(admin_curriculum_router)
app.include_router(admin_generate_router)
app.include_router(levels_router)
app.include_router(maintenance_router)
if graphql_router:
    app.include_router(graphql_router, prefix="/v1/graphql")
app.include_router(auth_router)
app.include_router(validation_router)
