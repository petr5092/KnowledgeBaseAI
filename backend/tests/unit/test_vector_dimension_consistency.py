from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance
from src.config.settings import settings
from src.services.graph.neo4j_repo import get_driver
from src.events.publisher import publish_graph_committed
from src.workers.vector_sync import consume_graph_committed
import uuid

def test_vector_sync_respects_existing_collection_dimension():
    client = QdrantClient(url=str(settings.qdrant_url))
    cols = [c.name for c in client.get_collections().collections]
    if "kb_entities" not in cols:
        client.create_collection("kb_entities", vectors_config=VectorParams(size=12, distance=Distance.COSINE))
    drv = get_driver()
    tid = "tenant-dim"
    uid = "C-"+uuid.uuid4().hex[:6]
    with drv.session() as s:
        s.run("MERGE (n:Concept {uid:$u, tenant_id:$t}) SET n.name=$name", {"u": uid, "t": tid, "name": "DimensionCheck"})
    drv.close()
    publish_graph_committed({"tenant_id": tid, "targets":[uid]})
    res = consume_graph_committed()
    assert res["processed"] >= 1
