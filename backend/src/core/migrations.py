from src.db.pg import ensure_schema_version, get_schema_version

CODE_SCHEMA_VERSION = 1

def check_and_gatekeep() -> bool:
    ensure_schema_version()
    dbv = get_schema_version()
    return CODE_SCHEMA_VERSION <= dbv
