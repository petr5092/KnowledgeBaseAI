from fastapi import APIRouter, HTTPException, Depends, Header, Security
from fastapi.security import HTTPBearer
from typing import Dict, Optional
from pydantic import BaseModel, Field
from src.schemas.proposal import Proposal, Operation, ProposalStatus
from src.db.pg import get_conn, ensure_tables
from src.services.proposal_service import create_draft_proposal
from src.core.context import get_tenant_id
from src.workers.commit import commit_proposal
from src.db.pg import get_proposal, set_proposal_status, list_proposals
from src.services.diff import build_diff
from src.services.impact import impact_subgraph_for_proposal

router = APIRouter(prefix="/v1/proposals", tags=["Управление контентом"], dependencies=[Security(HTTPBearer())])

def require_tenant() -> str:
    tid = get_tenant_id()
    if not tid:
        raise HTTPException(status_code=400, detail="tenant_id missing")
    return tid

class CreateProposalResponse(BaseModel):
    proposal_id: str
    proposal_checksum: str
    status: str

class CommitResponse(BaseModel):
    ok: bool
    status: str
    graph_version: Optional[int] = None
    violations: Optional[Dict] = None
    error: Optional[str] = None

@router.post(
    "",
    summary="Создать черновик заявки",
    description="Создает новую заявку на изменение графа. Проверяет структуру и фиксирует checksum, но не применяет изменения.",
    response_model=CreateProposalResponse,
)
async def create_proposal(payload: Dict, tenant_id: str = Depends(require_tenant), x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    """
    Принимает:
      - base_graph_version: версия графа-основания для ребейза
      - operations: список операций [{op_id, op_type, target_id/temp_id, properties_delta, match_criteria, evidence, semantic_impact, requires_review}]

    Возвращает:
      - proposal_id: идентификатор заявки
      - proposal_checksum: детерминированная контрольная сумма содержимого
      - status: текущий статус (DRAFT)
    """
    try:
        ops = [Operation.model_validate(o) for o in (payload.get("operations") or [])]
        base_graph_version = int(payload.get("base_graph_version") or 0)
        ensure_tables()
        p = create_draft_proposal(tenant_id, base_graph_version, ops)
        conn = get_conn()
        conn.autocommit = True
        import json
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO proposals (proposal_id, tenant_id, base_graph_version, proposal_checksum, status, operations_json) VALUES (%s,%s,%s,%s,%s,%s)",
                (
                    p.proposal_id,
                    p.tenant_id,
                    p.base_graph_version,
                    p.proposal_checksum,
                    ProposalStatus.DRAFT.value,
                    json.dumps(p.model_dump()["operations"]),
                ),
            )
        conn.close()
        return {"proposal_id": p.proposal_id, "proposal_checksum": p.proposal_checksum, "status": ProposalStatus.DRAFT.value}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="failed to create proposal")

@router.post(
    "/{proposal_id}/commit",
    summary="Commit Proposal",
    description="Applies the proposal to the Neo4j graph. This operation is atomic and updates the graph version.",
    response_model=CommitResponse,
)
async def commit(proposal_id: str, tenant_id: str = Depends(require_tenant), x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    """
    Принимает:
      - proposal_id: идентификатор заявки

    Возвращает:
      - ok: признак успешного применения
      - status: DONE | FAILED | CONFLICT | ASYNC_CHECK_REQUIRED
      - graph_version: новая версия графа (если успешно)
      - violations: детали нарушений целостности (если есть)
      - error: текст ошибки (если есть)
    """
    res = commit_proposal(proposal_id)
    if not res.get("ok"):
        status = res.get("status") or "FAILED"
        code = 409 if status == "CONFLICT" else 400
        raise HTTPException(status_code=code, detail=res)
    return res

@router.get(
    "/{proposal_id}",
    summary="Получить детали заявки",
    description="Возвращает данные по конкретной заявке: операции, статус и метаданные."
)
async def get(proposal_id: str, tenant_id: str = Depends(require_tenant)) -> Dict:
    """
    Принимает:
      - proposal_id: идентификатор заявки

    Возвращает:
      - объект заявки из БД: {tenant_id, base_graph_version, status, operations_json}
    """
    p = get_proposal(proposal_id)
    if not p or p["tenant_id"] != tenant_id:
        raise HTTPException(status_code=404, detail="proposal not found")
    return p

@router.get(
    "",
    summary="Список заявок",
    description="Возвращает список заявок, с фильтрацией по статусу и пагинацией."
)
async def list(status: str | None = None, limit: int = 20, offset: int = 0, tenant_id: str = Depends(require_tenant)) -> Dict:
    """
    Принимает:
      - status: фильтр по статусу
      - limit: лимит
      - offset: смещение

    Возвращает:
      - items: список заявок
      - limit, offset: параметры пагинации
    """
    items = list_proposals(tenant_id, status, limit, offset)
    return {"items": items, "limit": limit, "offset": offset}

@router.post(
    "/{proposal_id}/approve",
    summary="Одобрить заявку",
    description="Помечает заявку как APPROVED и пытается применить изменения к графу.",
    response_model=CommitResponse,
)
async def approve(proposal_id: str, tenant_id: str = Depends(require_tenant), x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    """
    Принимает:
      - proposal_id: идентификатор заявки

    Возвращает:
      - результат коммита (см. /commit): {ok, status, graph_version, ...}
    """
    p = get_proposal(proposal_id)
    if not p or p["tenant_id"] != tenant_id:
        raise HTTPException(status_code=404, detail="proposal not found")
    set_proposal_status(proposal_id, ProposalStatus.APPROVED.value)
    res = commit_proposal(proposal_id)
    if not res.get("ok"):
        status = res.get("status") or "FAILED"
        code = 409 if status == "CONFLICT" else 400
        raise HTTPException(status_code=code, detail=res)
    return res

@router.post(
    "/{proposal_id}/reject",
    summary="Reject Proposal",
    description="Marks a proposal as REJECTED. It cannot be committed afterwards."
)
async def reject(proposal_id: str, tenant_id: str = Depends(require_tenant), x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    """
    Принимает:
      - proposal_id: идентификатор заявки

    Возвращает:
      - ok: True
      - status: REJECTED
    """
    p = get_proposal(proposal_id)
    if not p or p["tenant_id"] != tenant_id:
        raise HTTPException(status_code=404, detail="proposal not found")
    set_proposal_status(proposal_id, ProposalStatus.REJECTED.value)
    return {"ok": True, "status": ProposalStatus.REJECTED.value}

@router.get(
    "/{proposal_id}/diff",
    summary="Diff по заявке",
    description="Генерирует наглядный diff (до/после) по операциям заявки для ревью."
)
async def diff(proposal_id: str, tenant_id: str = Depends(require_tenant)) -> Dict:
    """
    Принимает:
      - proposal_id: идентификатор заявки

    Возвращает:
      - diff: объект различий (до/после) и фрагменты доказательств (evidence)
    """
    p = get_proposal(proposal_id)
    if not p or p["tenant_id"] != tenant_id:
        raise HTTPException(status_code=404, detail="proposal not found")
    return build_diff(proposal_id)

@router.get(
    "/{proposal_id}/impact",
    summary="Calculate Proposal Impact",
    description="Analyzes which parts of the graph will be affected by this proposal (Impact Analysis)."
)
async def impact(proposal_id: str, depth: int = 1, types: str | None = None, max_nodes: int | None = None, max_edges: int | None = None, tenant_id: str = Depends(require_tenant)) -> Dict:
    """
    Принимает:
      - proposal_id: идентификатор заявки
      - depth: глубина анализа

    Возвращает:
      - подграф влияния: узлы и связи, затрагиваемые предложенными изменениями
    """
    p = get_proposal(proposal_id)
    if not p or p["tenant_id"] != tenant_id:
        raise HTTPException(status_code=404, detail="proposal not found")
    type_list = [t for t in (types or "").split(",") if t]
    return impact_subgraph_for_proposal(proposal_id, depth=depth, types=type_list or None, max_nodes=max_nodes, max_edges=max_edges)
