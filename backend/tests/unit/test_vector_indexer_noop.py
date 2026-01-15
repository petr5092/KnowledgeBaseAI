from app.services.vector.indexer import index_entities

def test_indexer_noop_empty():
    res = index_entities(tenant_id="public", uids=[], collection="kb_entities", dim=16)
    assert isinstance(res, dict)
    assert res.get("processed", 0) == 0
