import psycopg2
from typing import Dict, List, Optional
from src.config.settings import settings

def get_conn():
    dsn = str(settings.pg_dsn) if settings.pg_dsn else ""
    if not dsn:
        return None
    return psycopg2.connect(dsn)

def create_curriculum(code: str, title: str, standard: str, language: str) -> Dict:
    conn = get_conn()
    if conn is None:
        return {"ok": False, "error": "postgres not configured"}
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO curricula(code, title, standard, language, status) VALUES (%s,%s,%s,%s,'draft') RETURNING id",
                (code, title, standard, language)
            )
            cid = cur.fetchone()[0]
    conn.close()
    return {"ok": True, "id": cid}

def add_curriculum_nodes(code: str, nodes: List[Dict]) -> Dict:
    conn = get_conn()
    if conn is None:
        return {"ok": False, "error": "postgres not configured"}
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM curricula WHERE code=%s", (code,))
            row = cur.fetchone()
            if not row:
                return {"ok": False, "error": "curriculum not found"}
            cid = row[0]
            for n in nodes:
                cur.execute(
                    "INSERT INTO curriculum_nodes(curriculum_id, kind, canonical_uid, order_index, is_required) VALUES (%s,%s,%s,%s,%s)",
                    (cid, n.get('kind'), n.get('canonical_uid'), int(n.get('order_index', 0)), bool(n.get('is_required', True)))
                )
    conn.close()
    return {"ok": True}

def get_graph_view(code: str) -> Dict:
    conn = get_conn()
    if conn is None:
        return {"ok": False, "error": "postgres not configured"}
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM curricula WHERE code=%s", (code,))
            row = cur.fetchone()
            if not row:
                return {"ok": False, "error": "curriculum not found"}
            cid = row[0]
            cur.execute("SELECT kind, canonical_uid, order_index FROM curriculum_nodes WHERE curriculum_id=%s ORDER BY order_index ASC", (cid,))
            nodes = [{"kind": r[0], "canonical_uid": r[1], "order_index": r[2]} for r in cur.fetchall()]
    conn.close()
    return {"ok": True, "nodes": nodes}

