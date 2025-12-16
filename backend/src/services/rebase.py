from enum import Enum
from typing import List
from src.db.pg import get_graph_version, get_changed_targets_since

class RebaseResult(str, Enum):
    SAME_VERSION = "SAME_VERSION"
    FAST_REBASE = "FAST_REBASE"
    CONFLICT = "CONFLICT"

def rebase_check(tenant_id: str, base_graph_version: int, target_ids: List[str]) -> RebaseResult:
    current = get_graph_version(tenant_id)
    if current == base_graph_version:
        return RebaseResult.SAME_VERSION
    changed = set(get_changed_targets_since(tenant_id, base_graph_version))
    intersect = changed.intersection(set(target_ids))
    if intersect:
        return RebaseResult.CONFLICT
    return RebaseResult.FAST_REBASE
