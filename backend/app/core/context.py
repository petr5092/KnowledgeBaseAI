from contextvars import ContextVar
from typing import Optional
import jwt
from fastapi import Request
from app.config.settings import settings

tenant_id_var: ContextVar[Optional[str]] = ContextVar("tenant_id", default=None)

def set_tenant_id(tenant_id: Optional[str]) -> None:
    tenant_id_var.set(tenant_id)

def get_tenant_id() -> Optional[str]:
    return tenant_id_var.get()

def extract_tenant_id_from_request(request: Request) -> Optional[str]:
    h = request.headers.get("X-Tenant-ID")
    if h:
        return h.strip() or None
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
        try:
            payload = jwt.decode(token, settings.jwt_secret_key.get_secret_value(), algorithms=["HS256"])
            tid = payload.get("tenant_id") or payload.get("tid")
            if isinstance(tid, str) and tid.strip():
                return tid.strip()
        except Exception:
            return None
    return None
