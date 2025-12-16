from src.schemas.proposal import Operation, OpType, ProposalStatus
from src.services.proposal_service import create_draft_proposal
from src.db.pg import ensure_tables, get_conn
from src.workers.commit import commit_proposal
import json

def test_commit_rejects_dangling_skill_without_based_on():
    ensure_tables()
    ops = [
        Operation(op_id="1", op_type=OpType.CREATE_NODE, target_id="S-DANGLING", properties_delta={"type":"Skill","uid":"S-DANGLING","name":"Dangling Skill"}, evidence={"source_chunk_id":"SC-1","quote":"q"}),
        # No BASED_ON relation provided
    ]
    p = create_draft_proposal("tenant-int", 0, ops)
    conn = get_conn(); conn.autocommit=True
    with conn.cursor() as cur:
        cur.execute("INSERT INTO proposals (proposal_id, tenant_id, base_graph_version, proposal_checksum, status, operations_json) VALUES (%s,%s,%s,%s,%s,%s)", (p.proposal_id, p.tenant_id, p.base_graph_version, p.proposal_checksum, ProposalStatus.DRAFT.value, json.dumps([o.model_dump() for o in ops])))
    conn.close()
    res = commit_proposal(p.proposal_id)
    assert res["ok"] is False and res["status"] == "FAILED"
    assert "dangling_skills" in res.get("violations", {})
