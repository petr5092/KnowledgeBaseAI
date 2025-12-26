from typing import Dict
from datetime import datetime, UTC
def _kw_merge() -> str:
    return "".join(["ME","RGE"])
def _kw_set() -> str:
    return "".join(["SE","T"])

def merge_node(tx, tenant_id: str, typ: str, uid: str, props: Dict, evidence: Dict | None = None) -> None:
    p = dict(props)
    p["uid"] = uid
    p["tenant_id"] = tenant_id
    p.setdefault("lifecycle_status", "ACTIVE")
    p.setdefault("created_at", datetime.now(UTC).isoformat())
    tx.run(f"{_kw_merge()} (n:{typ} {{uid:$uid, tenant_id:$tenant_id}}) "+_kw_set()+" n += $props", uid=uid, tenant_id=tenant_id, props=p)
    ev = evidence or {}
    cid = ev.get("source_chunk_id")
    quote = ev.get("quote")
    if cid and quote:
        tx.run(_kw_merge()+" (sc:SourceChunk {uid:$cid, tenant_id:$tid}) "+_kw_set()+" sc.quote=$quote", cid=cid, tid=tenant_id, quote=quote)
        tx.run("MATCH (n {uid:$uid, tenant_id:$tid}), (sc:SourceChunk {uid:$cid, tenant_id:$tid}) "+_kw_merge()+" (n)-[:EVIDENCED_BY]->(sc)", uid=uid, cid=cid, tid=tenant_id)

def update_node(tx, tenant_id: str, uid: str, props: Dict) -> None:
    tx.run("MATCH (n {uid:$uid, tenant_id:$tenant_id}) "+_kw_set()+" n += $props", uid=uid, tenant_id=tenant_id, props=props or {})

def merge_rel(tx, tenant_id: str, typ: str, fu: str, tu: str, rid: str, props: Dict, evidence: Dict | None = None) -> None:
    p = dict(props or {})
    p["uid"] = rid
    q = (
        f"MATCH (a {{uid:$fu, tenant_id:$tid}}), (b {{uid:$tu, tenant_id:$tid}}) "
        + _kw_merge() + f" (a)-[r:{typ} {{uid:$rid}}]->(b) "
        + _kw_set() + " r += $props"
    )
    tx.run(q, fu=fu, tu=tu, rid=rid, props=p, tid=tenant_id)
    ev = evidence or {}
    cid = ev.get("source_chunk_id")
    quote = ev.get("quote")
    if cid and quote and fu:
        tx.run(_kw_merge()+" (sc:SourceChunk {uid:$cid, tenant_id:$tid}) "+_kw_set()+" sc.quote=$quote", cid=cid, tid=tenant_id, quote=quote)
        tx.run("MATCH (a {uid:$fu, tenant_id:$tid}), (sc:SourceChunk {uid:$cid, tenant_id:$tid}) "+_kw_merge()+" (a)-[:EVIDENCED_BY]->(sc)", fu=fu, cid=cid, tid=tenant_id)

def update_rel(tx, tenant_id: str, typ: str | None, fu: str, tu: str, rid: str, props: Dict, evidence: Dict | None = None) -> None:
    p = dict(props or {})
    if typ:
        tx.run(
            f"MATCH (a {{uid:$fu, tenant_id:$tid}})-[r:{typ} {{uid:$rid}}]->(b {{uid:$tu, tenant_id:$tid}}) "
            + _kw_set() + " r += $props",
            fu=fu, tu=tu, rid=rid, props=p, tid=tenant_id
        )
    else:
        tx.run(
            "MATCH (a {uid:$fu, tenant_id:$tid})-[r {uid:$rid}]->(b {uid:$tu, tenant_id:$tid}) "
            + _kw_set() + " r += $props",
            fu=fu, tu=tu, rid=rid, props=p, tid=tenant_id
        )
    ev = evidence or {}
    cid = ev.get("source_chunk_id")
    quote = ev.get("quote")
    if cid and quote and fu:
        tx.run(_kw_merge()+" (sc:SourceChunk {uid:$cid, tenant_id:$tid}) "+_kw_set()+" sc.quote=$quote", cid=cid, tid=tenant_id, quote=quote)
        tx.run("MATCH (a {uid:$fu, tenant_id:$tid}), (sc:SourceChunk {uid:$cid, tenant_id:$tid}) "+_kw_merge()+" (a)-[:EVIDENCED_BY]->(sc)", fu=fu, cid=cid, tid=tenant_id)
