from fastapi.testclient import TestClient
from src.main import app
from src.db.pg import ensure_tables, get_conn
from src.services.proposal_service import create_draft_proposal
from src.schemas.proposal import Operation, OpType, ProposalStatus
from src.services.graph.neo4j_repo import get_driver
import uuid, json

def test_api_impact_endpoint_filters_types():
    ensure_tables()
    tid = "tenant-api-impact"
    fu = "F-"+uuid.uuid4().hex[:6]
    tu = "T-"+uuid.uuid4().hex[:6]
    drv = get_driver()
    with drv.session() as s:
        s.run("MERGE (a:Concept {uid:$fu, tenant_id:$tid})", {"fu": fu, "tid": tid})
        s.run("MERGE (b:Concept {uid:$tu, tenant_id:$tid})", {"tu": tu, "tid": tid})
        s.run("MERGE (a:Concept {uid:$fu, tenant_id:$tid})-[:LINKED]->(b:Concept {uid:$tu, tenant_id:$tid})", {"fu": fu, "tu": tu, "tid": tid})
        s.run("MERGE (a:Concept {uid:$fu, tenant_id:$tid})-[:BASED_ON]->(b:Concept {uid:$tu, tenant_id:$tid})", {"fu": fu, "tu": tu, "tid": tid})
    drv.close()
    ops = [Operation(op_id="1", op_type=OpType.CREATE_REL, target_id="E-"+uuid.uuid4().hex[:6], properties_delta={"type":"LINKED","from_uid":fu,"to_uid":tu}, evidence={"source_chunk_id":"SC-1","quote":"q"})]
    p = create_draft_proposal(tid, 0, ops)
    conn = get_conn(); conn.autocommit=True
    with conn.cursor() as cur:
        cur.execute("INSERT INTO proposals (proposal_id, tenant_id, base_graph_version, proposal_checksum, status, operations_json) VALUES (%s,%s,%s,%s,%s,%s)", (p.proposal_id, p.tenant_id, p.base_graph_version, p.proposal_checksum, ProposalStatus.DRAFT.value, json.dumps([o.model_dump() for o in ops])))
    conn.close()
    client = TestClient(app)
    r = client.get(f"/v1/proposals/{p.proposal_id}/impact?types=LINKED", headers={"Authorization":"Bearer test","X-Tenant-ID":tid})
    assert r.status_code == 200
    data = r.json()
    assert "edges" in data
    assert len(data["edges"]) >= 1
