from fastapi import APIRouter, Depends, HTTPException, Header, Security
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

from src.api.deps import require_admin
from src.services.graph.neo4j_repo import Neo4jRepo

router = APIRouter(prefix="/v1/admin/graph", dependencies=[Depends(require_admin), Security(HTTPBearer())], tags=["Админка: граф"])

ALLOWED_NODE_LABELS = {
    "Subject",
    "Section",
    "Topic",
    "Skill",
    "Method",
    "Goal",
    "Objective",
    "Example",
    "Error",
    "ContentUnit",
}

ALLOWED_EDGE_TYPES = {
    "CONTAINS",
    "PREREQ",
    "HAS_SKILL",
    "USES_SKILL",
    "LINKED",
    "TARGETS",
    "HAS_LEARNING_PATH",
    "HAS_PRACTICE_PATH",
    "HAS_MASTERY_PATH",
}


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


@router.post("/nodes", summary="Создать узел", description="Создает узел с указанными метками и свойствами (без изменения uid).")
async def create_node(payload: NodeCreateInput, x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    """
    Принимает:
      - uid: UID узла
      - labels: метки из разрешенного списка
      - props: свойства, кроме uid

    Возвращает:
      - uid: UID созданного узла
    """
    labels = _validate_labels(payload.labels)
    props = _validate_props(payload.props)

    repo = Neo4jRepo()
    try:
        exists = repo.read("MATCH (n {uid:$uid}) RETURN count(n) AS c", {"uid": payload.uid})
        if exists and int(exists[0].get("c") or 0) > 0:
            raise HTTPException(status_code=409, detail="node uid already exists")

        label_str = ":".join(labels)
        query = f"CREATE (n:{label_str} {{uid:$uid}}) SET n += $props RETURN n.uid AS uid"
        rows = repo.read(query, {"uid": payload.uid, "props": props})
        return {"uid": rows[0]["uid"] if rows else payload.uid}
    finally:
        repo.close()


@router.get("/nodes/{uid}", summary="Получить узел", description="Возвращает метки и свойства узла по UID.")
async def get_node(uid: str) -> Dict:
    """
    Принимает:
      - uid: UID узла

    Возвращает:
      - uid: UID
      - labels: список меток
      - props: свойства узла без uid
    """
    repo = Neo4jRepo()
    try:
        rows = repo.read("MATCH (n {uid:$uid}) RETURN labels(n) AS labels, properties(n) AS props", {"uid": uid})
        if not rows:
            raise HTTPException(status_code=404, detail="node not found")
        props = rows[0].get("props") or {}
        props.pop("uid", None)
        return {"uid": uid, "labels": rows[0].get("labels") or [], "props": props}
    finally:
        repo.close()


@router.patch("/nodes/{uid}", summary="Изменить узел", description="Устанавливает/удаляет свойства узла. UID менять нельзя.")
async def patch_node(uid: str, payload: NodePatchInput, x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    """
    Принимает:
      - uid: UID узла
      - set: свойства для установки
      - unset: список свойств для удаления

    Возвращает:
      - ok: True
    """
    if "uid" in payload.set or "uid" in payload.unset:
        raise HTTPException(status_code=400, detail="uid cannot be modified")

    repo = Neo4jRepo()
    try:
        rows = repo.read("MATCH (n {uid:$uid}) RETURN count(n) AS c", {"uid": uid})
        if not rows or int(rows[0].get("c") or 0) == 0:
            raise HTTPException(status_code=404, detail="node not found")

        set_props = _validate_props(payload.set)
        repo.write("MATCH (n {uid:$uid}) SET n += $set", {"uid": uid, "set": set_props})
        for k in payload.unset:
            if k == "uid":
                continue
            repo.write(f"MATCH (n {{uid:$uid}}) REMOVE n.{k}", {"uid": uid})
        return {"ok": True}
    finally:
        repo.close()


@router.delete("/nodes/{uid}", summary="Удалить узел", description="Удаляет узел. По умолчанию не удаляет связи; используйте detach=true для детач-удаления.")
async def delete_node(uid: str, detach: bool = False, x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    """
    Принимает:
      - uid: UID узла
      - detach: если True, удаляет вместе со связями

    Возвращает:
      - ok: True
    """
    repo = Neo4jRepo()
    try:
        rows = repo.read("MATCH (n {uid:$uid}) RETURN count(n) AS c", {"uid": uid})
        if not rows or int(rows[0].get("c") or 0) == 0:
            raise HTTPException(status_code=404, detail="node not found")

        if detach:
            repo.write("MATCH (n {uid:$uid}) DETACH DELETE n", {"uid": uid})
            return {"ok": True}

        rels = repo.read("MATCH (n {uid:$uid})-[r]-() RETURN count(r) AS c", {"uid": uid})
        if rels and int(rels[0].get("c") or 0) > 0:
            raise HTTPException(status_code=409, detail="node has relationships; use detach=true")

        repo.write("MATCH (n {uid:$uid}) DELETE n", {"uid": uid})
        return {"ok": True}
    finally:
        repo.close()


@router.post("/edges", summary="Создать связь", description="Создает отношение между узлами указанного типа с props. Запрещены самосвязи.")
async def create_edge(payload: EdgeCreateInput, x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    """
    Принимает:
      - edge_uid: UID связи (опционально)
      - from_uid: UID исходного узла
      - to_uid: UID целевого узла
      - type: тип отношения из разрешенного набора
      - props: свойства отношения (кроме uid)

    Возвращает:
      - edge_uid: UID созданной связи
    """
    if payload.from_uid == payload.to_uid:
        raise HTTPException(status_code=400, detail="self-loop is not allowed")

    rel_type = _validate_edge_type(payload.type)
    props = _validate_props(payload.props)

    repo = Neo4jRepo()
    try:
        ok = repo.read(
            "MATCH (a {uid:$from}), (b {uid:$to}) RETURN count(a) AS ca, count(b) AS cb",
            {"from": payload.from_uid, "to": payload.to_uid},
        )
        if not ok or int(ok[0].get("ca") or 0) == 0 or int(ok[0].get("cb") or 0) == 0:
            raise HTTPException(status_code=404, detail="from/to node not found")

        edge_uid = payload.edge_uid
        if not edge_uid:
            import uuid

            edge_uid = f"E-{uuid.uuid4().hex[:16]}"

        exists = repo.read("MATCH ()-[r {uid:$uid}]-() RETURN count(r) AS c", {"uid": edge_uid})
        if exists and int(exists[0].get("c") or 0) > 0:
            raise HTTPException(status_code=409, detail="edge uid already exists")

        query = (
            f"MATCH (a {{uid:$from}}), (b {{uid:$to}}) "
            f"CREATE (a)-[r:{rel_type} {{uid:$edge_uid}}]->(b) "
            f"SET r += $props "
            f"RETURN r.uid AS uid"
        )
        rows = repo.read(query, {"from": payload.from_uid, "to": payload.to_uid, "edge_uid": edge_uid, "props": props})
        return {"edge_uid": rows[0]["uid"] if rows else edge_uid}
    finally:
        repo.close()


@router.get("/edges/{edge_uid}", summary="Получить связь", description="Возвращает from/to, тип и свойства связи по ее UID.")
async def get_edge(edge_uid: str) -> Dict:
    """
    Принимает:
      - edge_uid: UID связи

    Возвращает:
      - edge_uid: UID
      - from_uid: исходный узел
      - to_uid: целевой узел
      - type: тип отношения
      - props: свойства, без uid
    """
    repo = Neo4jRepo()
    try:
        rows = repo.read(
            "MATCH (a)-[r {uid:$uid}]->(b) RETURN a.uid AS from_uid, b.uid AS to_uid, type(r) AS type, properties(r) AS props",
            {"uid": edge_uid},
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


@router.get("/edges", summary="Список связей по паре узлов", description="Возвращает список связей между двумя узлами. Можно фильтровать по типу.")
async def list_edges(from_uid: str, to_uid: str, type: Optional[str] = None) -> Dict:
    """
    Принимает:
      - from_uid: UID исходного узла
      - to_uid: UID целевого узла
      - type: опционально, тип отношения

    Возвращает:
      - items: список объектов {edge_uid, type, props}
    """
    repo = Neo4jRepo()
    try:
        if type:
            rel_type = _validate_edge_type(type)
            query = (
                f"MATCH (a {{uid:$from}})-[r:{rel_type}]->(b {{uid:$to}}) "
                f"RETURN r.uid AS edge_uid, properties(r) AS props"
            )
        else:
            query = (
                "MATCH (a {uid:$from})-[r]->(b {uid:$to}) "
                "RETURN r.uid AS edge_uid, type(r) AS type, properties(r) AS props"
            )

        rows = repo.read(query, {"from": from_uid, "to": to_uid})
        items = []
        for r in rows:
            props = r.get("props") or {}
            props.pop("uid", None)
            items.append({"edge_uid": r.get("edge_uid"), "type": r.get("type") or type, "props": props})
        return {"items": items}
    finally:
        repo.close()


@router.patch("/edges/{edge_uid}", summary="Изменить связь", description="Устанавливает/удаляет свойства отношения. UID менять нельзя.")
async def patch_edge(edge_uid: str, payload: EdgePatchInput, x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    """
    Принимает:
      - edge_uid: UID связи
      - set: свойства для установки
      - unset: список свойств для удаления

    Возвращает:
      - ok: True
    """
    if "uid" in payload.set or "uid" in payload.unset:
        raise HTTPException(status_code=400, detail="uid cannot be modified")

    repo = Neo4jRepo()
    try:
        rows = repo.read("MATCH ()-[r {uid:$uid}]->() RETURN count(r) AS c", {"uid": edge_uid})
        if not rows or int(rows[0].get("c") or 0) == 0:
            raise HTTPException(status_code=404, detail="edge not found")

        set_props = _validate_props(payload.set)
        repo.write("MATCH ()-[r {uid:$uid}]->() SET r += $set", {"uid": edge_uid, "set": set_props})
        for k in payload.unset:
            if k == "uid":
                continue
            repo.write(f"MATCH ()-[r {{uid:$uid}}]->() REMOVE r.{k}", {"uid": edge_uid})
        return {"ok": True}
    finally:
        repo.close()


@router.delete("/edges/{edge_uid}", summary="Удалить связь", description="Удаляет отношение по UID.")
async def delete_edge(edge_uid: str, x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    """
    Принимает:
      - edge_uid: UID связи

    Возвращает:
      - ok: True
    """
    repo = Neo4jRepo()
    try:
        rows = repo.read("MATCH ()-[r {uid:$uid}]->() RETURN count(r) AS c", {"uid": edge_uid})
        if not rows or int(rows[0].get("c") or 0) == 0:
            raise HTTPException(status_code=404, detail="edge not found")

        repo.write("MATCH ()-[r {uid:$uid}]->() DELETE r", {"uid": edge_uid})
        return {"ok": True}
    finally:
        repo.close()
