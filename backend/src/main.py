import asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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

tags_metadata = [
    {
        "name": "Интеграция с LMS",
        "description": "Методы для внешних систем (StudyNinja) для работы с графом: дорожная карта, адаптивные вопросы, навигация.",
    },
    {
        "name": "ИИ ассистент",
        "description": "Диалоговый интерфейс и инструменты для объяснения связей и генерации контента.",
    },
    {
        "name": "Управление контентом",
        "description": "Система заявок (Proposals) для безопасных, атомарных и проверяемых изменений графа.",
    },
    {
        "name": "Аналитика",
        "description": "Метрики структуры графа и статистика использования ИИ.",
    },
    {
        "name": "Система",
        "description": "Проверка состояния и метрики Prometheus.",
    },
]

from src.api.common import ApiError

app = FastAPI(
    title="KnowledgeBaseAI Engine",
    description="""
# Платформа KnowledgeBaseAI

Ядро графовой модели знаний для экосистемы StudyNinja. Предоставляет **бестейт-сервис** работы с графом,
который используется для адаптивного обучения и аналитики качества контента.

## Ключевые принципы

* **Интеграция с LMS**: используйте эндпойнты `/v1/graph/*` для построения дорожной карты и выбора вопросов.
* **Proposals**: любые изменения графа проходят через конвейер Заявка → Ревью → Коммит (`/v1/proposals`).
* **Мультитенантность**: `X-Tenant-ID` обязателен для записей и админ-операций; для чтения может быть по умолчанию.
    """,
    version="1.0.0",
    openapi_tags=tags_metadata,
    contact={"name": "StudyNinja API", "url": "https://studyninja.ai", "email": "api@studyninja.ai"},
    license_info={"name": "Proprietary"},
)



REQ_COUNTER = Counter("http_requests_total", "Total HTTP requests", ["method", "path", "status"])
LATENCY = Histogram("http_request_latency_ms", "Request latency ms", ["method", "path"])

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("startup", neo4j_uri=settings.neo4j_uri)
    ok = check_and_gatekeep()
    if not ok:
        raise SystemExit("Schema version gate failed")
    ensure_bootstrap_admin()
    yield

@app.middleware("http")
async def tenant_middleware(request, call_next):
    tid = extract_tenant_id_from_request(request)
    set_tenant_id(tid)
    cid = request.headers.get("X-Correlation-ID") or new_correlation_id()
    set_correlation_id(cid)
    rid = request.headers.get("X-Request-ID") or ("req-" + __import__("uuid").uuid4().hex[:8])
    try:
        request.state.request_id = rid
    except Exception:
        ...
    resp = await call_next(request)
    try:
        resp.headers["X-Correlation-ID"] = cid
        resp.headers["X-Request-ID"] = rid
        if tid:
            resp.headers["X-Tenant-ID"] = tid
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

def _code_for_status(status: int) -> str:
    if status == 400: return "invalid_parameters"
    if status == 401: return "unauthorized"
    if status == 403: return "forbidden"
    if status == 404: return "not_found"
    if status == 405: return "method_not_allowed"
    if status == 409: return "conflict"
    if status == 422: return "validation_error"
    if status == 502: return "upstream_error"
    if status == 503: return "service_unavailable"
    return "internal_error"

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    ae = ApiError(
        code="internal_error",
        message="Internal server error",
        details={"error": exc.__class__.__name__},
        request_id=getattr(request.state, "request_id", None),
        correlation_id=get_correlation_id(),
    )
    return JSONResponse(status_code=500, content=ae.model_dump())

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    msg = exc.detail if isinstance(exc.detail, str) else "Request failed"
    ae = ApiError(
        code=_code_for_status(exc.status_code),
        message=msg,
        details=None,
        request_id=getattr(request.state, "request_id", None),
        correlation_id=get_correlation_id(),
    )
    return JSONResponse(status_code=exc.status_code, content=ae.model_dump())

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    ae = ApiError(
        code="validation_error",
        message="Validation failed",
        details={"errors": exc.errors()},
        request_id=getattr(request.state, "request_id", None),
        correlation_id=get_correlation_id(),
    )
    return JSONResponse(status_code=422, content=ae.model_dump())

@app.get("/health", tags=["Система"], summary="Проверка состояния", description="Возвращает статус доступности ключевых зависимостей.")
async def health():
    return {"openai": bool(settings.openai_api_key.get_secret_value()), "neo4j": bool(settings.neo4j_uri)}

@app.get("/metrics", tags=["Система"], summary="Метрики Prometheus", description="Экспорт метрик в формате, совместимом с Prometheus.")
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
