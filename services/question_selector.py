import os
import json
from functools import lru_cache
from typing import Dict, List, Set

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KB_DIR = os.path.join(os.path.dirname(BASE_DIR), 'kb')


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
    idx = get_examples_indexed()
    exclude = exclude_uids or set()
    pool: List[Dict] = []
    for tu in topic_uids:
        for e in idx["by_topic"].get(tu, []):
            d = int(e.get('difficulty', 3) or 3)
            if d < difficulty_min or d > difficulty_max:
                continue
            if e.get('uid') in exclude:
                continue
            pool.append(e)
    # simple diversity: round-robin by topic order
    selected: List[Dict] = []
    seen_by_topic: Dict[str, int] = {tu: 0 for tu in topic_uids}
    for e in pool:
        tu = e.get('topic_uid')
        if len(selected) >= limit:
            break
        if seen_by_topic.get(tu, 0) <= 1:  # cap first pass to 2 per topic
            selected.append(e)
            seen_by_topic[tu] = seen_by_topic.get(tu, 0) + 1
    # fallback fill if not enough
    if len(selected) < limit:
        for e in pool:
            if e in selected:
                continue
            selected.append(e)
            if len(selected) >= limit:
                break
    return selected

