from fastapi import APIRouter, Depends, HTTPException, Header, Security
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
import uuid
import json

from app.api.deps import require_admin
from app.services.graph.neo4j_repo import Neo4jRepo
from app.schemas.proposal import Proposal, Operation, ProposalStatus, OpType
from app.services.proposal_service import create_draft_proposal
from app.workers.commit import commit_proposal
from app.db.pg import get_conn, ensure_tables, get_graph_version, set_proposal_status

from app.core.canonical import ALLOWED_NODE_LABELS, ALLOWED_EDGE_TYPES

router = APIRouter(prefix="/v1/admin/graph", dependencies=[Depends(require_admin), Security(HTTPBearer())], tags=["Админка: граф"])



class NodeCreateInput(BaseModel):
    uid: str = Field(..., min_length=1, max_length=128)
    labels: List[str] = Field(..., min_length=1)
    props: Dict[str, Any] = Field(default_factory=dict)


class NodePatchInput(BaseModel):
    set: Dict[str, Any] = Field(default_factory=dict)
    unset: List[str] = Field(default_factory=list)


class EdgeCreateInput(BaseModel):
    edge_uid: Optional[str] = Field(default=None, min_length=1, max_length=128)
    from_uid: str = Field(..., min_length=1, max_length=128)
    to_uid: str = Field(..., min_length=1, max_length=128)
    type: str = Field(..., min_length=1, max_length=64)
    props: Dict[str, Any] = Field(default_factory=dict)


class EdgePatchInput(BaseModel):
    set: Dict[str, Any] = Field(default_factory=dict)
    unset: List[str] = Field(default_factory=list)


def _validate_labels(labels: List[str]) -> List[str]:
    clean = []
    for l in labels:
        if l not in ALLOWED_NODE_LABELS:
            raise HTTPException(status_code=400, detail=f"label not allowed: {l}")
        clean.append(l)
    return clean


def _validate_edge_type(t: str) -> str:
    if t not in ALLOWED_EDGE_TYPES:
        raise HTTPException(status_code=400, detail=f"edge type not allowed: {t}")
    return t


def _validate_props(props: Dict[str, Any]) -> Dict[str, Any]:
    if "uid" in props:
        raise HTTPException(status_code=400, detail="props.uid is not allowed")
    if len(props.keys()) > 50:
        raise HTTPException(status_code=400, detail="too many props")
    return props


async def _execute_admin_proposal(tenant_id: str, ops: List[Operation]) -> Dict:
    ensure_tables()
    base_ver = get_graph_version(tenant_id)
    
    # Bypass evidence validation for admin by providing dummy evidence if needed, 
    # but create_draft_proposal calls validate_operations which checks for evidence.
    # We should add dummy evidence.
    for op in ops:
        if not op.evidence:
            op.evidence = {"source": "admin_api", "user": "admin"}

    p = create_draft_proposal(tenant_id, base_ver, ops)
    
    conn = get_conn()
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO proposals (proposal_id, tenant_id, base_graph_version, proposal_checksum, status, operations_json) VALUES (%s,%s,%s,%s,%s,%s)",
            (
                p.proposal_id,
                p.tenant_id,
                p.base_graph_version,
                p.proposal_checksum,
                ProposalStatus.APPROVED.value, # Immediately APPROVED
                json.dumps(p.model_dump()["operations"]),
            ),
        )
    conn.close()
    
    # Commit immediately
    res = commit_proposal(p.proposal_id)
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res)
    
    return res


@router.post("/nodes", summary="Создать узел", description="Создает узел с указанными метками и свойствами (без изменения uid).")
async def create_node(payload: NodeCreateInput, x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    labels = _validate_labels(payload.labels)
    props = _validate_props(payload.props)

    # Optional: Check existence (read-only)
    repo = Neo4jRepo()
    try:
        exists = repo.read("MATCH (n {uid:$uid}) WHERE ($tid IS NULL OR n.tenant_id=$tid) RETURN count(n) AS c", {"uid": payload.uid, "tid": x_tenant_id})
        if exists and int(exists[0].get("c") or 0) > 0:
            raise HTTPException(status_code=409, detail="node uid already exists")
    finally:
        repo.close()

    op = Operation(
        op_id=f"OP-{uuid.uuid4().hex[:8]}",
        op_type=OpType.CREATE_NODE,
        target_id=payload.uid,
        properties_delta={**props, "type": labels[0], "uid": payload.uid}, # Assuming first label is primary type
        requires_review=False
    )
    
    await _execute_admin_proposal(x_tenant_id, [op])
    return {"uid": payload.uid}


@router.get("/nodes/{uid}", summary="Получить узел", description="Возвращает метки и свойства узла по UID.")
async def get_node(uid: str, x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    repo = Neo4jRepo()
    try:
        rows = repo.read("MATCH (n {uid:$uid}) WHERE ($tid IS NULL OR n.tenant_id=$tid) RETURN labels(n) AS labels, properties(n) AS props", {"uid": uid, "tid": x_tenant_id})
        if not rows:
            raise HTTPException(status_code=404, detail="node not found")
        props = rows[0].get("props") or {}
        props.pop("uid", None)
        return {"uid": uid, "labels": rows[0].get("labels") or [], "props": props}
    finally:
        repo.close()


@router.patch("/nodes/{uid}", summary="Изменить узел", description="Устанавливает/удаляет свойства узла. UID менять нельзя.")
async def patch_node(uid: str, payload: NodePatchInput, x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    if "uid" in payload.set or "uid" in payload.unset:
        raise HTTPException(status_code=400, detail="uid cannot be modified")

    repo = Neo4jRepo()
    try:
        rows = repo.read("MATCH (n {uid:$uid}) WHERE ($tid IS NULL OR n.tenant_id=$tid) RETURN count(n) AS c", {"uid": uid, "tid": x_tenant_id})
        if not rows or int(rows[0].get("c") or 0) == 0:
            raise HTTPException(status_code=404, detail="node not found")
    finally:
        repo.close()

    # Construct props for update
    # Note: UPDATE_NODE in commit.py uses SET n += props. It doesn't handle unset/REMOVE.
    # We might need to handle unset by setting to null? Neo4j treats null as remove property?
    # Yes, SET n.prop = null removes the property.
    
    props = _validate_props(payload.set)
    for k in payload.unset:
        props[k] = None
        
    op = Operation(
        op_id=f"OP-{uuid.uuid4().hex[:8]}",
        op_type=OpType.UPDATE_NODE,
        target_id=uid,
        properties_delta=props,
        requires_review=False
    )
    
    await _execute_admin_proposal(x_tenant_id, [op])
    return {"ok": True}


@router.delete("/nodes/{uid}", summary="Удалить узел", description="Удаляет узел.")
async def delete_node(uid: str, detach: bool = False, x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    repo = Neo4jRepo()
    try:
        rows = repo.read("MATCH (n {uid:$uid}) WHERE ($tid IS NULL OR n.tenant_id=$tid) RETURN count(n) AS c", {"uid": uid, "tid": x_tenant_id})
        if not rows or int(rows[0].get("c") or 0) == 0:
            raise HTTPException(status_code=404, detail="node not found")
            
        if not detach:
            rels = repo.read("MATCH (n {uid:$uid})-[r]-() WHERE ($tid IS NULL OR n.tenant_id=$tid) RETURN count(r) AS c", {"uid": uid, "tid": x_tenant_id})
            if rels and int(rels[0].get("c") or 0) > 0:
                raise HTTPException(status_code=409, detail="node has relationships; use detach=true")
    finally:
        repo.close()

    op = Operation(
        op_id=f"OP-{uuid.uuid4().hex[:8]}",
        op_type=OpType.DELETE_NODE,
        target_id=uid,
        properties_delta={"detach": detach},
        requires_review=False
    )
    
    await _execute_admin_proposal(x_tenant_id, [op])
    return {"ok": True}


@router.post("/edges", summary="Создать связь", description="Создает отношение между узлами.")
async def create_edge(payload: EdgeCreateInput, x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    if payload.from_uid == payload.to_uid:
        raise HTTPException(status_code=400, detail="self-loop is not allowed")

    rel_type = _validate_edge_type(payload.type)
    props = _validate_props(payload.props)

    repo = Neo4jRepo()
    try:
        ok = repo.read(
            "MATCH (a {uid:$from}), (b {uid:$to}) WHERE ($tid IS NULL OR (a.tenant_id=$tid AND b.tenant_id=$tid)) RETURN count(a) AS ca, count(b) AS cb",
            {"from": payload.from_uid, "to": payload.to_uid, "tid": x_tenant_id},
        )
        if not ok or int(ok[0].get("ca") or 0) == 0 or int(ok[0].get("cb") or 0) == 0:
            raise HTTPException(status_code=404, detail="from/to node not found")
    finally:
        repo.close()

    edge_uid = payload.edge_uid or f"E-{uuid.uuid4().hex[:16]}"
    
    op = Operation(
        op_id=f"OP-{uuid.uuid4().hex[:8]}",
        op_type=OpType.CREATE_REL,
        target_id=edge_uid,
        properties_delta={**props, "type": rel_type, "uid": edge_uid, "from_uid": payload.from_uid, "to_uid": payload.to_uid},
        requires_review=False
    )
    
    await _execute_admin_proposal(x_tenant_id, [op])
    return {"edge_uid": edge_uid}


@router.get("/edges/{edge_uid}", summary="Получить связь", description="Возвращает from/to, тип и свойства связи по ее UID.")
async def get_edge(edge_uid: str, x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    repo = Neo4jRepo()
    try:
        rows = repo.read(
            "MATCH (a)-[r {uid:$uid}]->(b) WHERE ($tid IS NULL OR (a.tenant_id=$tid AND b.tenant_id=$tid)) RETURN a.uid AS from_uid, b.uid AS to_uid, type(r) AS type, properties(r) AS props",
            {"uid": edge_uid, "tid": x_tenant_id},
        )
        if not rows:
            raise HTTPException(status_code=404, detail="edge not found")
        props = rows[0].get("props") or {}
        props.pop("uid", None)
        return {
            "edge_uid": edge_uid,
            "from_uid": rows[0].get("from_uid"),
            "to_uid": rows[0].get("to_uid"),
            "type": rows[0].get("type"),
            "props": props,
        }
    finally:
        repo.close()


@router.get("/edges", summary="Список связей по паре узлов", description="Возвращает список связей между двумя узлами.")
async def list_edges(from_uid: str, to_uid: str, type: Optional[str] = None, x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    repo = Neo4jRepo()
    try:
        if type:
            rel_type = _validate_edge_type(type)
            query = (
                f"MATCH (a {{uid:$from}})-[r:{rel_type}]->(b {{uid:$to}}) "
                f"WHERE ($tid IS NULL OR (a.tenant_id=$tid AND b.tenant_id=$tid)) "
                f"RETURN r.uid AS edge_uid, properties(r) AS props"
            )
        else:
            query = (
                "MATCH (a {uid:$from})-[r]->(b {uid:$to}) "
                "WHERE ($tid IS NULL OR (a.tenant_id=$tid AND b.tenant_id=$tid)) "
                "RETURN r.uid AS edge_uid, type(r) AS type, properties(r) AS props"
            )

        rows = repo.read(query, {"from": from_uid, "to": to_uid, "tid": x_tenant_id})
        items = []
        for r in rows:
            props = r.get("props") or {}
            props.pop("uid", None)
            items.append({"edge_uid": r.get("edge_uid"), "type": r.get("type") or type, "props": props})
        return {"items": items}
    finally:
        repo.close()


@router.patch("/edges/{edge_uid}", summary="Изменить связь", description="Устанавливает/удаляет свойства отношения.")
async def patch_edge(edge_uid: str, payload: EdgePatchInput, x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    if "uid" in payload.set or "uid" in payload.unset:
        raise HTTPException(status_code=400, detail="uid cannot be modified")

    repo = Neo4jRepo()
    try:
        # Check existence and get current type/nodes if needed, but for patch we might not need them strictly if we trust UID
        # However, to filter by tenant, we need to check if the edge belongs to the tenant nodes
        rows = repo.read("MATCH (a)-[r {uid:$uid}]->(b) WHERE ($tid IS NULL OR (a.tenant_id=$tid AND b.tenant_id=$tid)) RETURN count(r) AS c", {"uid": edge_uid, "tid": x_tenant_id})
        if not rows or int(rows[0].get("c") or 0) == 0:
            raise HTTPException(status_code=404, detail="edge not found")
    finally:
        repo.close()

    props = _validate_props(payload.set)
    for k in payload.unset:
        props[k] = None

    op = Operation(
        op_id=f"OP-{uuid.uuid4().hex[:8]}",
        op_type=OpType.UPDATE_REL,
        target_id=edge_uid,
        properties_delta=props,
        requires_review=False
    )
    
    await _execute_admin_proposal(x_tenant_id, [op])
    return {"ok": True}


@router.delete("/edges/{edge_uid}", summary="Удалить связь", description="Удаляет отношение по UID.")
async def delete_edge(edge_uid: str, x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    repo = Neo4jRepo()
    try:
        rows = repo.read("MATCH (a)-[r {uid:$uid}]->(b) WHERE ($tid IS NULL OR (a.tenant_id=$tid AND b.tenant_id=$tid)) RETURN count(r) AS c", {"uid": edge_uid, "tid": x_tenant_id})
        if not rows or int(rows[0].get("c") or 0) == 0:
            raise HTTPException(status_code=404, detail="edge not found")
    finally:
        repo.close()

    op = Operation(
        op_id=f"OP-{uuid.uuid4().hex[:8]}",
        op_type=OpType.DELETE_REL,
        target_id=edge_uid,
        properties_delta={},
        requires_review=False
    )
    
    await _execute_admin_proposal(x_tenant_id, [op])
    return {"ok": True}
