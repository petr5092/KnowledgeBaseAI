from fastapi import APIRouter, HTTPException, Depends, Header, Security
from fastapi.security import HTTPBearer
from typing import Dict, Any, Literal
from pydantic import BaseModel
from app.services.ingestion.academic import AcademicIngestionStrategy
from app.services.ingestion.corporate import CorporateIngestionStrategy
from app.services.proposal_service import create_draft_proposal
from app.db.pg import get_conn, ensure_tables
from app.schemas.proposal import ProposalStatus
from app.api.common import StandardResponse
from app.core.context import get_tenant_id
import json

router = APIRouter(prefix="/v1/ingestion", tags=["Ingestion"], dependencies=[Security(HTTPBearer())])

def require_tenant() -> str:
    tid = get_tenant_id()
    if not tid:
        raise HTTPException(status_code=400, detail="tenant_id missing")
    return tid

class GenerateProposalInput(BaseModel):
    content: str
    strategy_type: Literal["academic", "corporate"]
    domain_context: str = "General"

@router.post(
    "/generate_proposal",
    summary="Generate Proposal from Content",
    description="Analyzes content and generates a proposal to update the Knowledge Graph.",
    response_model=StandardResponse,
)
async def generate_proposal(payload: GenerateProposalInput, tenant_id: str = Depends(require_tenant), x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    """
    Inputs:
      - content: Text or structured content
      - strategy_type: 'academic' (TOC based) or 'corporate' (Manual based)
      - domain_context: Context hint for LLM
      
    Returns:
      - proposal_id: Created proposal ID
    """
    strategy = None
    if payload.strategy_type == "academic":
        strategy = AcademicIngestionStrategy()
    elif payload.strategy_type == "corporate":
        strategy = CorporateIngestionStrategy()
    else:
        raise HTTPException(status_code=400, detail="Unknown strategy")
        
    try:
        ops = await strategy.process(payload.content, domain_context=payload.domain_context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")
        
    if not ops:
        raise HTTPException(status_code=400, detail="No operations generated")
        
    try:
        ensure_tables()
        # Create Proposal Object
        p = create_draft_proposal(tenant_id, 0, ops)
        
        # Save to DB
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
                    ProposalStatus.DRAFT.value,
                    json.dumps(p.model_dump()["operations"]),
                ),
            )
        conn.close()
        
        return {"items": [{"proposal_id": p.proposal_id, "status": ProposalStatus.DRAFT.value, "ops_count": len(ops)}], "meta": {}}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save proposal: {str(e)}")
