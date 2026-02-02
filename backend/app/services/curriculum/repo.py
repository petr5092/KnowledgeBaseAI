import psycopg2
from typing import Dict, List, Optional
from app.config.settings import settings

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
                    "INSERT INTO curriculum_nodes(curriculum_id, kind, canonical_uid, order_index, is_required, exam_task_number) VALUES (%s,%s,%s,%s,%s,%s)",
                    (cid, n.get('kind'), n.get('canonical_uid'), int(n.get('order_index', 0)), bool(n.get('is_required', True)), n.get('exam_task_number'))
                )
    conn.close()
    return {"ok": True}


def get_curriculum(code: str) -> Optional[Dict]:
    conn = get_conn()
    if conn is None:
        return None
    res = None
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, standard, language, status FROM curricula WHERE code=%s", (code,))
            row = cur.fetchone()
            if row:
                cid = row[0]
                res = {
                    "code": code,
                    "title": row[1],
                    "standard": row[2],
                    "language": row[3],
                    "status": row[4],
                    "items": []
                }
                # Fetch nodes
                cur.execute("SELECT kind, canonical_uid, order_index, is_required, exam_task_number FROM curriculum_nodes WHERE curriculum_id=%s ORDER BY order_index ASC", (cid,))
                nodes = cur.fetchall()
                for n in nodes:
                    res["items"].append({
                        "kind": n[0],
                        "canonical_uid": n[1],
                        "order_index": n[2],
                        "is_required": n[3],
                        "exam_task_number": n[4]
                    })
    conn.close()
    return res

def get_graph_view(code: str) -> Dict:
    # 1. Get curriculum definition
    curr = get_curriculum(code)
    if not curr:
        return {"ok": False, "error": "not_found"}
    
    # If filters are present, use them. Otherwise return all explicitly linked topics.
    filters = curr.get("filters", {})
    
    # 2. If simple filters are defined (e.g. list of topics)
    # For now, let's assume 'items' in curriculum are the source of truth for the Prism.
    # We return the explicit items. The Roadmap Planner will expand prereqs.
    
    return {
        "ok": True, 
        "nodes": curr.get("items", []),
        "meta": {"title": curr.get("title")}
    }

def list_curricula() -> List[Dict]:
    conn = get_conn()
    if conn is None:
        return []
    items = []
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, code, title, standard, language, status FROM curricula ORDER BY id DESC")
            rows = cur.fetchall()
            for r in rows:
                items.append({
                    "id": r[0],
                    "code": r[1],
                    "title": r[2],
                    "standard": r[3],
                    "language": r[4],
                    "status": r[5]
                })
    conn.close()
    return items
