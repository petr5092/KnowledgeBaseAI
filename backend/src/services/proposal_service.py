import uuid
from typing import Dict, Any, List
from src.core.canonical import canonical_hash_from_json, normalize_text
from src.schemas.proposal import Operation, Proposal

EVIDENCE_REQUIRED_OPS = {"CREATE_NODE", "CREATE_REL", "MERGE_NODE", "MERGE_REL"}

def validate_operations(ops: List[Operation]) -> None:
    for op in ops:
        if op.op_type in EVIDENCE_REQUIRED_OPS:
            if not op.evidence or not (op.evidence.get("source_chunk_id") and op.evidence.get("quote")):
                raise ValueError(f"evidence required for {op.op_type}")

def _deep_normalize(obj):
    if isinstance(obj, dict):
        return {k: _deep_normalize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_normalize(v) for v in obj]
    if isinstance(obj, str):
        return normalize_text(obj)
    return obj

def compute_checksum(ops: List[Operation]) -> str:
    ops_obj = [op.model_dump() for op in sorted(ops, key=lambda o: (o.op_type, o.target_id or o.temp_id or o.op_id))]
    ops_obj = _deep_normalize(ops_obj)
    return canonical_hash_from_json(ops_obj)

def create_draft_proposal(tenant_id: str, base_graph_version: int, ops: List[Operation]) -> Proposal:
    validate_operations(ops)
    checksum = compute_checksum(ops)
    pid = f"P-{uuid.uuid4().hex[:20]}"
    return Proposal(
        proposal_id=pid,
        tenant_id=tenant_id,
        base_graph_version=base_graph_version,
        proposal_checksum=checksum,
        operations=ops,
    )
