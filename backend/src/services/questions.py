import os
import json
from functools import lru_cache
from typing import Dict, List, Set
from src.config.settings import settings
from src.services.graph.neo4j_repo import Neo4jRepo

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(BASE_DIR))), 'kb')

def load_jsonl(filename: str) -> List[Dict]:
    path = os.path.join(KB_DIR, filename)
    data: List[Dict] = []
    if not os.path.exists(path):
        return data
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return data

@lru_cache(maxsize=1)
def get_examples_indexed():
    ex = load_jsonl('examples.jsonl')
    by_topic: Dict[str, List[Dict]] = {}
    for e in ex:
        tuid = e.get('topic_uid')
        if not tuid:
            continue
        by_topic.setdefault(tuid, []).append(e)
    return {"all": ex, "by_topic": by_topic}

def select_examples_for_topics(
    topic_uids: List[str],
    limit: int,
    difficulty_min: int = 1,
    difficulty_max: int = 5,
    exclude_uids: Set[str] | None = None,
):
    exclude = exclude_uids or set()
    pool: List[Dict] = []
    if settings.neo4j_uri and settings.neo4j_user and settings.neo4j_password.get_secret_value():
        try:
            repo = Neo4jRepo()
            rows = repo.read(
                (
                    "UNWIND $t AS tuid "
                    "MATCH (t:Topic {uid:tuid})-[:HAS_QUESTION]->(q:Question) "
                    "RETURN q.uid AS uid, q.title AS title, q.statement AS statement, q.difficulty AS difficulty, t.uid AS topic_uid"
                ),
                {"t": topic_uids}
            )
            def _norm(x):
                try:
                    xf = float(x)
                except Exception:
                    return 0.6
                return xf if xf <= 1.0 else max(0.0, min(1.0, xf / 5.0))
            for r in rows:
                d_raw = r.get('difficulty', 3)
                try:
                    d_int = int(float(d_raw))
                except Exception:
                    d_int = 3
                if d_int < difficulty_min or d_int > difficulty_max:
                    continue
                if r.get('uid') in exclude:
                    continue
                r['difficulty'] = _norm(d_raw)
                pool.append(r)
            repo.close()
        except Exception:
            pool = []
    if not pool:
        idx = get_examples_indexed()
        def _norm(x):
            try:
                xf = float(x)
            except Exception:
                return 0.6
            return xf if xf <= 1.0 else max(0.0, min(1.0, xf / 5.0))
        for tu in topic_uids:
            for e in idx["by_topic"].get(tu, []):
                d_raw = e.get('difficulty', 3)
                try:
                    d = int(float(d_raw))
                except Exception:
                    d = 3
                if d < difficulty_min or d > difficulty_max:
                    continue
                if e.get('uid') in exclude:
                    continue
                e['difficulty'] = _norm(d_raw)
                pool.append(e)
    selected: List[Dict] = []
    seen_by_topic: Dict[str, int] = {tu: 0 for tu in topic_uids}
    for e in pool:
        tu = e.get('topic_uid')
        if len(selected) >= limit:
            break
        if seen_by_topic.get(tu, 0) <= 1:
            selected.append(e)
            seen_by_topic[tu] = seen_by_topic.get(tu, 0) + 1
    if len(selected) < limit:
        for e in pool:
            if e in selected:
                continue
            selected.append(e)
            if len(selected) >= limit:
                break
    return selected

def all_topic_uids_from_examples() -> List[str]:
    idx = get_examples_indexed()
    return list(idx["by_topic"].keys())

