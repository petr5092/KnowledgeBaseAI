from src.db.pg import ensure_schema_version, set_tenant_schema_version
from src.core.migrations import check_and_gatekeep

def test_schema_gatekeeper_tenant():
    ensure_schema_version()
    set_tenant_schema_version("acme", 0)
    assert check_and_gatekeep("acme") is False
    set_tenant_schema_version("acme", 2)
    assert check_and_gatekeep("acme") is True
