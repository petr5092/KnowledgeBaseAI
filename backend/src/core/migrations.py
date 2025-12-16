from src.db.pg import ensure_schema_version, get_schema_version, get_tenant_schema_version

CODE_SCHEMA_VERSION = 1

def check_and_gatekeep(tenant_id: str | None = None) -> bool:
    ensure_schema_version()
    if tenant_id:
        dbv = get_tenant_schema_version(tenant_id)
        return CODE_SCHEMA_VERSION <= dbv
    dbv_global = get_schema_version()
    dbv_system = get_tenant_schema_version("system")
    return CODE_SCHEMA_VERSION <= max(dbv_global, dbv_system)
