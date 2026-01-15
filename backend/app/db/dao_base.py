from typing import Any, Dict, Optional
from app.core.context import get_tenant_id

class TenantRequiredError(RuntimeError):
    pass

class DaoBase:
    def __init__(self, tenant_id: Optional[str] = None):
        self._tenant_id = tenant_id or get_tenant_id()
        if not self._tenant_id:
            raise TenantRequiredError("tenant_id is required for DAO operations")

    @property
    def tenant_id(self) -> str:
        assert self._tenant_id
        return self._tenant_id

    def inject_tenant(self, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        p = dict(params or {})
        p["tenant_id"] = self.tenant_id
        return p
