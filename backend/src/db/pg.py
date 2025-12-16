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
              operations_json JSONB NOT NULL
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
