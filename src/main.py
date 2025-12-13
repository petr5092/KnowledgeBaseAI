import asyncio
from fastapi import FastAPI
from src.core.logging import setup_logging, logger
from src.core.config import settings
from src.api.graph import router as graph_router
from src.api.construct import router as construct_router
from src.api.analytics import router as analytics_router
from prometheus_client import Counter, Histogram

app = FastAPI(title="Headless Knowledge Graph Platform")

REQ_COUNTER = Counter("http_requests_total", "Total HTTP requests")
LATENCY = Histogram("http_request_latency_ms", "Request latency ms")

@app.on_event("startup")
async def on_startup():
    setup_logging()
    logger.info("startup", neo4j_uri=settings.neo4j_uri, chroma_host=settings.chroma_host)

@app.middleware("http")
async def metrics_middleware(request, call_next):
    REQ_COUNTER.inc()
    with LATENCY.time():
        resp = await call_next(request)
    return resp

@app.get("/health")
async def health():
    return {"openai": bool(settings.openai_api_key), "neo4j": bool(settings.neo4j_uri), "chroma": bool(settings.chroma_host)}

app.include_router(graph_router)
app.include_router(construct_router)
app.include_router(analytics_router)
