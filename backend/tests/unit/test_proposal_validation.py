import pytest
from app.schemas.proposal import Operation, OpType
from app.services.proposal_service import validate_operations

def test_evidence_required_for_create():
    ops = [
        Operation(op_id="1", op_type=OpType.CREATE_NODE, temp_id="T1", properties_delta={"name": "X"}, evidence={"source_chunk_id": "S1", "quote": "q"}),
        Operation(op_id="2", op_type=OpType.CREATE_REL, temp_id="R1", properties_delta={"type": "PREREQ"}, evidence={"source_chunk_id": "S2", "quote": "q2"}),
    ]
    validate_operations(ops)  # should not raise

def test_validation_fails_without_evidence():
    ops = [
        Operation(op_id="1", op_type=OpType.CREATE_NODE, temp_id="T1", properties_delta={"name": "X"}, evidence={}),
    ]
    with pytest.raises(ValueError):
        validate_operations(ops)
