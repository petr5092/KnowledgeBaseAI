import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.core.logging import setup_logging, logger
from src.config.settings import settings
from src.core.context import extract_tenant_id_from_request, set_tenant_id
from src.core.correlation import new_correlation_id, set_correlation_id, get_correlation_id
from src.api.graph import router as graph_router
from src.api.assistant import router as assistant_router
from src.api.construct import router as construct_router
from src.api.analytics import router as analytics_router
from src.api.ws import router as ws_router
from src.api.curriculum import router as curriculum_router
from src.api.admin import router as admin_router
from src.api.admin_curriculum import router as admin_curriculum_router
from src.api.admin_generate import router as admin_generate_router
from src.api.admin_graph import router as admin_graph_router
from src.api.levels import router as levels_router
from src.api.maintenance import router as maintenance_router
from src.api.proposals import router as proposals_router
try:
    from src.api.graphql import router as graphql_router
except Exception:
    graphql_router = None
from src.api.validation import router as validation_router
from src.api.auth import router as auth_router
from src.services.auth.users_repo import ensure_bootstrap_admin
from src.core.migrations import check_and_gatekeep
try:
    from prometheus_client import Counter, Histogram
except Exception:
    class Counter:
        def __init__(self, *args, **kwargs): ...
        def labels(self, *args, **kwargs): return self
        def inc(self, *args, **kwargs): ...
    class Histogram:
        def __init__(self, *args, **kwargs): ...
        def labels(self, *args, **kwargs): return self
        class _Ctx:
            def __enter__(self): ...
            def __exit__(self, a, b, c): ...
        def time(self): return self._Ctx()

app = FastAPI(title="Headless Knowledge Graph Platform")

REQ_COUNTER = Counter("http_requests_total", "Total HTTP requests", ["method", "path", "status"])
LATENCY = Histogram("http_request_latency_ms", "Request latency ms", ["method", "path"])

@app.on_event("startup")
async def on_startup():
    setup_logging()
    logger.info("startup", neo4j_uri=settings.neo4j_uri)
    ok = check_and_gatekeep()
    if not ok:
        raise SystemExit("Schema version gate failed")
    ensure_bootstrap_admin()

@app.middleware("http")
async def tenant_middleware(request, call_next):
    tid = extract_tenant_id_from_request(request)
    set_tenant_id(tid)
    cid = request.headers.get("X-Correlation-ID") or new_correlation_id()
    set_correlation_id(cid)
    resp = await call_next(request)
    try:
        resp.headers["X-Correlation-ID"] = cid
    except Exception:
        ...
    return resp

@app.middleware("http")
async def metrics_middleware(request, call_next):
    method = request.method
    path = request.url.path
    with LATENCY.labels(method=method, path=path).time():
        resp = await call_next(request)
    try:
        REQ_COUNTER.labels(method=method, path=path, status=str(resp.status_code)).inc()
    except Exception:
        ...
    return resp

@app.get("/health")
async def health():
    return {"openai": bool(settings.openai_api_key.get_secret_value()), "neo4j": bool(settings.neo4j_uri)}

@app.get("/metrics")
async def metrics():
    from prometheus_client import generate_latest
    return generate_latest()

origins = [o.strip() for o in (settings.cors_allow_origins or "").split(",") if o.strip()]
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
app.include_router(graph_router)
app.include_router(assistant_router)
app.include_router(construct_router)
app.include_router(analytics_router)
app.include_router(ws_router)
app.include_router(curriculum_router)
app.include_router(admin_router)
app.include_router(admin_curriculum_router)
app.include_router(admin_generate_router)
app.include_router(admin_graph_router)
app.include_router(levels_router)
app.include_router(maintenance_router)
app.include_router(proposals_router)
if graphql_router:
    app.include_router(graphql_router, prefix="/v1/graphql")
app.include_router(auth_router)
app.include_router(validation_router)
