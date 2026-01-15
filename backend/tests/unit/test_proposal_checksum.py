from app.schemas.proposal import Operation, OpType
from app.services.proposal_service import compute_checksum

def test_checksum_stable_with_key_reordering():
    ops1 = [
        Operation(op_id="1", op_type=OpType.CREATE_NODE, temp_id="T1", properties_delta={"name": "Concept A"}, evidence={"source_chunk_id": "C1", "quote": "text"}),
        Operation(op_id="2", op_type=OpType.CREATE_NODE, temp_id="T2", properties_delta={"name": "Concept B"}, evidence={"source_chunk_id": "C2", "quote": "text"}),
    ]
    ops2 = [
        Operation(op_id="2", op_type=OpType.CREATE_NODE, temp_id="T2", properties_delta={"name": "Concept B"}, evidence={"source_chunk_id": "C2", "quote": "text"}),
        Operation(op_id="1", op_type=OpType.CREATE_NODE, temp_id="T1", properties_delta={"name": "Concept A"}, evidence={"source_chunk_id": "C1", "quote": "text"}),
    ]
    h1 = compute_checksum(ops1)
    h2 = compute_checksum(ops2)
    assert h1 == h2
