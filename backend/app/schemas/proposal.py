from enum import Enum
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

class ProposalStatus(str, Enum):
    DRAFT = "DRAFT"
    WAITING_REVIEW = "WAITING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CONFLICT = "CONFLICT"
    COMMITTING = "COMMITTING"
    DONE = "DONE"
    FAILED = "FAILED"

class OpType(str, Enum):
    CREATE_NODE = "CREATE_NODE"
    CREATE_REL = "CREATE_REL"
    MERGE_NODE = "MERGE_NODE"
    MERGE_REL = "MERGE_REL"
    UPDATE_NODE = "UPDATE_NODE"
    UPDATE_REL = "UPDATE_REL"
    DELETE_NODE = "DELETE_NODE"
    DELETE_REL = "DELETE_REL"

class Operation(BaseModel):
    op_id: str
    op_type: OpType
    target_id: Optional[str] = None
    temp_id: Optional[str] = None
    properties_delta: Dict[str, Any] = {}
    match_criteria: Dict[str, Any] = {}
    evidence: Dict[str, Any] = {}
    semantic_impact: str = Field(default="COSMETIC")
    requires_review: bool = False

class Proposal(BaseModel):
    proposal_id: str
    task_id: Optional[str] = None
    tenant_id: str
    base_graph_version: int = 0
    proposal_checksum: str
    status: ProposalStatus = ProposalStatus.DRAFT
    operations: List[Operation]
