from src.events.publisher import publish_graph_committed
from src.workers.vector_sync import consume_graph_committed
from src.services.graph.neo4j_repo import get_driver
from qdrant_client import QdrantClient
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
    scroll = client.scroll(collection_name="kb_entities", with_payload=True, limit=10)[0]
    assert isinstance(scroll, list)
