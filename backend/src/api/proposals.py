from fastapi import APIRouter, HTTPException, Depends
from typing import Dict
from src.schemas.proposal import Proposal, Operation, ProposalStatus
from src.db.pg import get_conn, ensure_tables
from src.services.proposal_service import create_draft_proposal
from src.core.context import get_tenant_id
from src.workers.commit import commit_proposal
from src.db.pg import get_proposal, set_proposal_status, list_proposals
from src.services.diff import build_diff

router = APIRouter(prefix="/v1/proposals")

def require_tenant() -> str:
    tid = get_tenant_id()
    if not tid:
        raise HTTPException(status_code=400, detail="tenant_id missing")
    return tid

@router.post("")
async def create_proposal(payload: Dict, tenant_id: str = Depends(require_tenant)) -> Dict:
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

@router.post("/{proposal_id}/commit")
async def commit(proposal_id: str, tenant_id: str = Depends(require_tenant)) -> Dict:
    res = commit_proposal(proposal_id)
    if not res.get("ok"):
        status = res.get("status") or "FAILED"
        code = 409 if status == "CONFLICT" else 400
        raise HTTPException(status_code=code, detail=res)
    return res

@router.get("/{proposal_id}")
async def get(proposal_id: str, tenant_id: str = Depends(require_tenant)) -> Dict:
    p = get_proposal(proposal_id)
    if not p or p["tenant_id"] != tenant_id:
        raise HTTPException(status_code=404, detail="proposal not found")
    return p

@router.get("")
async def list(status: str | None = None, limit: int = 20, offset: int = 0, tenant_id: str = Depends(require_tenant)) -> Dict:
    items = list_proposals(tenant_id, status, limit, offset)
    return {"items": items, "limit": limit, "offset": offset}

@router.post("/{proposal_id}/approve")
async def approve(proposal_id: str, tenant_id: str = Depends(require_tenant)) -> Dict:
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

@router.post("/{proposal_id}/reject")
async def reject(proposal_id: str, tenant_id: str = Depends(require_tenant)) -> Dict:
    p = get_proposal(proposal_id)
    if not p or p["tenant_id"] != tenant_id:
        raise HTTPException(status_code=404, detail="proposal not found")
    set_proposal_status(proposal_id, ProposalStatus.REJECTED.value)
    return {"ok": True, "status": ProposalStatus.REJECTED.value}

@router.get("/{proposal_id}/diff")
async def diff(proposal_id: str, tenant_id: str = Depends(require_tenant)) -> Dict:
    p = get_proposal(proposal_id)
    if not p or p["tenant_id"] != tenant_id:
        raise HTTPException(status_code=404, detail="proposal not found")
    return build_diff(proposal_id)
