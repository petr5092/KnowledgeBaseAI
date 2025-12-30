from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, List, Set
from src.services.graph.neo4j_repo import get_driver
from src.services.roadmap_planner import plan_route

router = APIRouter(prefix="/v1/curriculum", tags=["Учебные планы"])

class PathfindInput(BaseModel):
    target_uid: str

class PathfindResponse(BaseModel):
    target: str
    path: List[str]

@router.post("/pathfind", summary="Построить порядок темы", description="Возвращает упорядоченный список тем из транзитивного замыкания PREREQ для указанной цели.", response_model=PathfindResponse)
async def pathfind(payload: PathfindInput) -> Dict:
    """
    Принимает:
      - target_uid: UID конечной темы

    Возвращает:
      - target: исходный UID
      - path: упорядоченный список UID тем для прохождения
    """
    drv = get_driver()
    with drv.session() as s:
        res = s.run(
            "MATCH (t:Topic {uid:$uid})-[:PREREQ*0..]->(p:Topic) RETURN collect(DISTINCT p.uid) AS uids",
            {"uid": payload.target_uid}
        ).single()
        closure: List[str] = res["uids"] if res else []
        edges = s.run(
            "MATCH (a:Topic)-[:PREREQ]->(b:Topic) WHERE a.uid IN $uids AND b.uid IN $uids "
            "RETURN a.uid AS a, b.uid AS b",
            {"uids": closure}
        )
        g: Dict[str, List[str]] = {u: [] for u in closure}
        indeg: Dict[str, int] = {u: 0 for u in closure}
        for r in edges:
            g[r["b"]].append(r["a"])
            indeg[r["a"]] += 1
    drv.close()
    q: List[str] = [u for u, d in indeg.items() if d == 0]
    ordered: List[str] = []
    seen: Set[str] = set()
    while q:
        u = q.pop(0)
        if u in seen:
            continue
        seen.add(u)
        ordered.append(u)
        for v in g.get(u, []):
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)
    return {"target": payload.target_uid, "path": ordered}

class RoadmapInput(BaseModel):
    subject_uid: str | None = None
    progress: Dict[str, float] = {}
    limit: int = 30
    penalty_factor: float = 0.15

class RoadmapItem(BaseModel):
    uid: str
    title: str | None = None
    mastered: float
    missing_prereqs: int
    priority: float

class RoadmapResponse(BaseModel):
    items: List[RoadmapItem]

@router.post("/roadmap", summary="Построить учебный маршрут", description="Возвращает отсортированный по приоритету список тем с учётом прогресса и недостающих PREREQ.", response_model=RoadmapResponse)
async def roadmap(payload: RoadmapInput) -> Dict:
    items = plan_route(payload.subject_uid, payload.progress or {}, payload.limit, payload.penalty_factor)
    return {"items": items}
