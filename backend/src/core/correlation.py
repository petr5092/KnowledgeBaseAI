from contextvars import ContextVar
import uuid

correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)

def new_correlation_id() -> str:
    return "corr-" + uuid.uuid4().hex[:16]

def set_correlation_id(cid: str) -> None:
    correlation_id_var.set(cid)

def get_correlation_id() -> str | None:
    return correlation_id_var.get()
