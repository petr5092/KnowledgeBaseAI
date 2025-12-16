from typing import Dict
from datetime import datetime

def merge_node(tx, tenant_id: str, typ: str, uid: str, props: Dict, evidence: Dict | None = None) -> None:
    p = dict(props)
    p["uid"] = uid
    p["tenant_id"] = tenant_id
    p.setdefault("lifecycle_status", "ACTIVE")
    p.setdefault("created_at", datetime.utcnow().isoformat())
    tx.run(f"MERGE (n:{typ} {{uid:$uid, tenant_id:$tenant_id}}) SET n += $props", uid=uid, tenant_id=tenant_id, props=p)
    ev = evidence or {}
    cid = ev.get("source_chunk_id")
    quote = ev.get("quote")
    if cid and quote:
        tx.run("MERGE (sc:SourceChunk {uid:$cid, tenant_id:$tid}) SET sc.quote=$quote", cid=cid, tid=tenant_id, quote=quote)
        tx.run("MATCH (n {uid:$uid, tenant_id:$tid}), (sc:SourceChunk {uid:$cid, tenant_id:$tid}) MERGE (n)-[:EVIDENCED_BY]->(sc)", uid=uid, cid=cid, tid=tenant_id)

def update_node(tx, tenant_id: str, uid: str, props: Dict) -> None:
    tx.run("MATCH (n {uid:$uid, tenant_id:$tenant_id}) SET n += $props", uid=uid, tenant_id=tenant_id, props=props or {})

def merge_rel(tx, tenant_id: str, typ: str, fu: str, tu: str, rid: str, props: Dict, evidence: Dict | None = None) -> None:
    p = dict(props or {})
    p["uid"] = rid
    tx.run(
        f"MATCH (a {{uid:$fu, tenant_id:$tid}}), (b {{uid:$tu, tenant_id:$tid}}) "
        f"MERGE (a)-[r:{typ} {{uid:$rid}}]->(b) "
        f"SET r += $props",
        fu=fu, tu=tu, rid=rid, props=p, tid=tenant_id
    )
    ev = evidence or {}
    cid = ev.get("source_chunk_id")
    quote = ev.get("quote")
    if cid and quote and fu:
        tx.run("MERGE (sc:SourceChunk {uid:$cid, tenant_id:$tid}) SET sc.quote=$quote", cid=cid, tid=tenant_id, quote=quote)
        tx.run("MATCH (a {uid:$fu, tenant_id:$tid}), (sc:SourceChunk {uid:$cid, tenant_id:$tid}) MERGE (a)-[:EVIDENCED_BY]->(sc)", fu=fu, cid=cid, tid=tenant_id)

def update_rel(tx, tenant_id: str, typ: str | None, fu: str, tu: str, rid: str, props: Dict, evidence: Dict | None = None) -> None:
    p = dict(props or {})
    if typ:
        tx.run(
            f"MATCH (a {{uid:$fu, tenant_id:$tid}})-[r:{typ} {{uid:$rid}}]->(b {{uid:$tu, tenant_id:$tid}}) "
            f"SET r += $props",
            fu=fu, tu=tu, rid=rid, props=p, tid=tenant_id
        )
    else:
        tx.run(
            "MATCH (a {uid:$fu, tenant_id:$tid})-[r {uid:$rid}]->(b {uid:$tu, tenant_id:$tid}) "
            "SET r += $props",
            fu=fu, tu=tu, rid=rid, props=p, tid=tenant_id
        )
    ev = evidence or {}
    cid = ev.get("source_chunk_id")
    quote = ev.get("quote")
    if cid and quote and fu:
        tx.run("MERGE (sc:SourceChunk {uid:$cid, tenant_id:$tid}) SET sc.quote=$quote", cid=cid, tid=tenant_id, quote=quote)
        tx.run("MATCH (a {uid:$fu, tenant_id:$tid}), (sc:SourceChunk {uid:$cid, tenant_id:$tid}) MERGE (a)-[:EVIDENCED_BY]->(sc)", fu=fu, cid=cid, tid=tenant_id)
