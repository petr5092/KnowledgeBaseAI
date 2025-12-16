from src.schemas.proposal import Operation, OpType, ProposalStatus
from src.services.proposal_service import create_draft_proposal
from src.db.pg import ensure_tables, get_conn
from src.workers.commit import commit_proposal
from src.services.graph.neo4j_repo import get_driver
import json, uuid

def test_evidenced_by_relation_created_for_node():
    ensure_tables()
    tid = "tenant-ev"
    uid = "C-"+uuid.uuid4().hex[:6]
    ev = {"source_chunk_id":"CH-"+uuid.uuid4().hex[:8],"quote":"evidence line"}
    ops = [Operation(op_id="1", op_type=OpType.CREATE_NODE, target_id=uid, properties_delta={"type":"Concept","uid":uid,"name":"Concept Ev"}, evidence=ev)]
    p = create_draft_proposal(tid, 0, ops)
    conn = get_conn(); conn.autocommit=True
    with conn.cursor() as cur:
        cur.execute("INSERT INTO proposals (proposal_id, tenant_id, base_graph_version, proposal_checksum, status, operations_json) VALUES (%s,%s,%s,%s,%s,%s)", (p.proposal_id, p.tenant_id, p.base_graph_version, p.proposal_checksum, ProposalStatus.DRAFT.value, json.dumps([o.model_dump() for o in ops])))
    conn.close()
    res = commit_proposal(p.proposal_id)
    assert res["ok"] is True
    drv = get_driver()
    with drv.session() as s:
        cy = "MATCH (n {uid:$u, tenant_id:$t})-[:EVIDENCED_BY]->(sc:SourceChunk {uid:$cid, tenant_id:$t}) RETURN COUNT(sc) AS c"
        c = s.run(cy, {"u": uid, "t": tid, "cid": ev["source_chunk_id"]}).single()["c"]
    drv.close()
    assert c >= 1
