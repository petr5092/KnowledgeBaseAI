from src.db.pg import ensure_tables, set_graph_version, add_graph_change
from src.services.rebase import rebase_check, RebaseResult
import uuid

def test_same_version():
    ensure_tables()
    tid = "tenant-" + uuid.uuid4().hex[:8]
    set_graph_version(tid, 10)
    assert rebase_check(tid, 10, ["A","B"]) == RebaseResult.SAME_VERSION

def test_fast_rebase_no_intersection():
    ensure_tables()
    tid = "tenant-" + uuid.uuid4().hex[:8]
    set_graph_version(tid, 20)
    add_graph_change(tid, 21, "X")
    add_graph_change(tid, 22, "Y")
    set_graph_version(tid, 22)
    assert rebase_check(tid, 20, ["A","B"]) == RebaseResult.FAST_REBASE

def test_conflict_with_intersection():
    ensure_tables()
    tid = "tenant-" + uuid.uuid4().hex[:8]
    set_graph_version(tid, 30)
    add_graph_change(tid, 31, "A")
    set_graph_version(tid, 31)
    assert rebase_check(tid, 30, ["A","B"]) == RebaseResult.CONFLICT
