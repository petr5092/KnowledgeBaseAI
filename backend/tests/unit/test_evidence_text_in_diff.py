from src.workers.ingestion import normalize_text, chunk_text, embed_chunks
from src.services.proposal_service import create_draft_proposal
from src.schemas.proposal import Operation, OpType, ProposalStatus
from src.db.pg import ensure_tables, get_conn
from src.services.diff import build_diff
import json

def test_diff_contains_chunk_text():
    ensure_tables()
    txt = normalize_text("evidence text alpha beta gamma " * 10)
    chunks = chunk_text(txt, max_len=64)
    embed_chunks("tenant-z", "doc-z", chunks)
    ev = {"source_chunk_id": chunks[0]["chunk_id"], "quote": "alpha beta"}
    ops = [Operation(op_id="1", op_type=OpType.CREATE_NODE, target_id="Z-N1", properties_delta={"type":"Concept","uid":"Z-N1","name":"Z"}, evidence=ev)]
    p = create_draft_proposal("tenant-z", 0, ops)
    conn = get_conn(); conn.autocommit=True
    with conn.cursor() as cur:
        cur.execute("INSERT INTO proposals (proposal_id, tenant_id, base_graph_version, proposal_checksum, status, operations_json) VALUES (%s,%s,%s,%s,%s,%s)", (p.proposal_id, p.tenant_id, p.base_graph_version, p.proposal_checksum, ProposalStatus.DRAFT.value, json.dumps([o.model_dump() for o in ops])))
    conn.close()
    df = build_diff(p.proposal_id)
    item = df["items"][0]
    assert item["evidence_chunk"]["chunk_id"] == chunks[0]["chunk_id"]
    assert isinstance(item["evidence_chunk"]["text"], str) and len(item["evidence_chunk"]["text"]) > 0
