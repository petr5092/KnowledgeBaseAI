from src.events.publisher import publish_graph_committed
from src.workers.vector_sync import consume_graph_committed
from src.services.graph.neo4j_repo import get_driver
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance
from src.config.settings import settings
import uuid

def test_rescore_entities_on_event():
    drv = get_driver()
    tid = "t-"+uuid.uuid4().hex[:6]
    uid = "C-"+uuid.uuid4().hex[:6]
    with drv.session() as s:
        s.run("MERGE (n:Concept {uid:$u, tenant_id:$t}) SET n.name=$name", {"u": uid, "t": tid, "name": "RescoreName"})
    drv.close()
    publish_graph_committed({"tenant_id": tid, "targets":[uid]})
    res = consume_graph_committed()
    assert res["processed"] >= 1
    client = QdrantClient(url=str(settings.qdrant_url))
    info = client.get_collections()
    names = [c.name for c in info.collections]
    assert "kb_entities" in names
