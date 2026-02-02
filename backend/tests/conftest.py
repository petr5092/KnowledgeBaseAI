import warnings, pytest
warnings.filterwarnings("ignore")
from app.db.pg import get_conn, ensure_tables
from app.events.publisher import get_redis
from app.services.graph.neo4j_repo import get_driver
import os
from app.services import impact as impact_mod

@pytest.fixture(autouse=True)
def _clean_db():
    ensure_tables()
    conn = get_conn(); conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("DELETE FROM events_outbox")
        cur.execute("DELETE FROM proposals")
        cur.execute("DELETE FROM audit_log")
        cur.execute("DELETE FROM graph_changes")
        cur.execute("DELETE FROM tenant_graph_version")
    conn.close()
    try:
        r = get_redis()
        r.delete("events:graph_committed")
    except Exception:
        ...
    try:
        impact_mod._CACHE.clear()
        os.environ.pop("INTEGRITY_TEST_SLEEP_MS", None)
        os.environ.pop("INTEGRITY_CHECK_THRESHOLD_MS", None)
        os.environ.pop("IMPACT_CACHE_TTL_S", None)
    except Exception:
        ...
    try:
        drv = get_driver()
        with drv.session() as s:
            s.run("MATCH (n) DETACH DELETE n")
        drv.close()
    except Exception:
        ...
    yield
