import psycopg2
from typing import Any, Dict, Tuple
from src.config.settings import settings

def get_conn():
    dsn = str(settings.pg_dsn)
    if not dsn:
        raise RuntimeError("PG_DSN is not configured")
    return psycopg2.connect(dsn)

def ensure_tables():
    conn = get_conn()
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS proposals (
              proposal_id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              base_graph_version BIGINT NOT NULL,
              proposal_checksum TEXT NOT NULL,
              status TEXT NOT NULL,
              operations_json JSONB NOT NULL,
              created_at TIMESTAMP DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
              tx_id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              proposal_id TEXT NOT NULL,
              operations_applied JSONB NOT NULL,
              revert_operations JSONB NOT NULL,
              correlation_id TEXT DEFAULT '',
              created_at TIMESTAMP DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS tenant_graph_version (
              tenant_id TEXT PRIMARY KEY,
              graph_version BIGINT NOT NULL DEFAULT 0
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS graph_changes (
              tenant_id TEXT NOT NULL,
              graph_version BIGINT NOT NULL,
              target_id TEXT NOT NULL,
              PRIMARY KEY (tenant_id, graph_version, target_id)
            )
            """
        )
    conn.close()
    try:
        conn = get_conn()
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS correlation_id TEXT DEFAULT ''")
            cur.execute("ALTER TABLE proposals ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()")
        conn.close()
    except Exception:
        ...

def get_graph_version(tenant_id: str) -> int:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT graph_version FROM tenant_graph_version WHERE tenant_id=%s", (tenant_id,))
        row = cur.fetchone()
        conn.close()
        return int(row[0]) if row else 0

def set_graph_version(tenant_id: str, version: int) -> None:
    conn = get_conn()
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenant_graph_version (tenant_id, graph_version) VALUES (%s,%s) ON CONFLICT (tenant_id) DO UPDATE SET graph_version=EXCLUDED.graph_version",
            (tenant_id, version),
        )
    conn.close()

def add_graph_change(tenant_id: str, graph_version: int, target_id: str) -> None:
    conn = get_conn()
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO graph_changes (tenant_id, graph_version, target_id) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
            (tenant_id, graph_version, target_id),
        )
    conn.close()

def get_changed_targets_since(tenant_id: str, from_version: int) -> list[str]:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT target_id FROM graph_changes WHERE tenant_id=%s AND graph_version>%s",
            (tenant_id, from_version),
        )
        rows = cur.fetchall()
        conn.close()
        return [r[0] for r in rows]

def ensure_schema_version():
    conn = get_conn()
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_version (
              id INTEGER PRIMARY KEY,
              version INTEGER NOT NULL
            )
            """
        )
        cur.execute("INSERT INTO schema_version (id, version) VALUES (1, 1) ON CONFLICT (id) DO NOTHING")
    conn.close()

def get_schema_version() -> int:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT version FROM schema_version WHERE id=1")
        row = cur.fetchone()
    conn.close()
    return int(row[0]) if row else 0

def set_schema_version(version: int) -> None:
    conn = get_conn()
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("INSERT INTO schema_version (id, version) VALUES (1, %s) ON CONFLICT (id) DO UPDATE SET version=EXCLUDED.version", (version,))
    conn.close()

def get_proposal(proposal_id: str) -> dict | None:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT proposal_id, tenant_id, base_graph_version, proposal_checksum, status, operations_json FROM proposals WHERE proposal_id=%s", (proposal_id,))
        row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {"proposal_id": row[0], "tenant_id": row[1], "base_graph_version": int(row[2]), "proposal_checksum": row[3], "status": row[4], "operations": row[5]}

def set_proposal_status(proposal_id: str, status: str) -> None:
    conn = get_conn()
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("UPDATE proposals SET status=%s WHERE proposal_id=%s", (status, proposal_id))
    conn.close()

def list_proposals(tenant_id: str, status: str | None = None, limit: int = 20, offset: int = 0) -> list[dict]:
    conn = get_conn()
    with conn.cursor() as cur:
        if status:
            cur.execute(
                "SELECT proposal_id, tenant_id, base_graph_version, proposal_checksum, status, created_at FROM proposals WHERE tenant_id=%s AND status=%s ORDER BY created_at DESC LIMIT %s OFFSET %s",
                (tenant_id, status, limit, offset),
            )
        else:
            cur.execute(
                "SELECT proposal_id, tenant_id, base_graph_version, proposal_checksum, status, created_at FROM proposals WHERE tenant_id=%s ORDER BY created_at DESC LIMIT %s OFFSET %s",
                (tenant_id, limit, offset),
            )
        rows = cur.fetchall()
    conn.close()
    return [{"proposal_id": r[0], "tenant_id": r[1], "base_graph_version": int(r[2]), "proposal_checksum": r[3], "status": r[4], "created_at": r[5]} for r in rows]
