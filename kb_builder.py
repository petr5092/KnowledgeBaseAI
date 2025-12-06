import os
import json
import re
from typing import Dict, List, Tuple, Set

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KB_DIR = os.path.join(BASE_DIR, 'kb')


def load_jsonl(filepath: str) -> List[Dict]:
    data: List[Dict] = []
    if not os.path.exists(filepath):
        return data
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return data


def append_jsonl(filepath: str, record: Dict) -> None:
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def tokens(text: str) -> Set[str]:
    if not text:
        return set()
    out: List[str] = []
    buf: List[str] = []
    for ch in text.lower():
        if ch.isalnum():
            buf.append(ch)
        else:
            if buf:
                out.append(''.join(buf))
                buf = []
    if buf:
        out.append(''.join(buf))
    return set(out)


def generate_goals_and_objectives() -> Dict:
    topics = load_jsonl(os.path.join(KB_DIR, 'topics.jsonl'))
    existing_goals = load_jsonl(os.path.join(KB_DIR, 'topic_goals.jsonl'))
    existing_objs = load_jsonl(os.path.join(KB_DIR, 'topic_objectives.jsonl'))

    by_topic_goals: Dict[str, List[Dict]] = {}
    for g in existing_goals:
        by_topic_goals.setdefault(g.get('topic_uid'), []).append(g)
    by_topic_objs: Dict[str, List[Dict]] = {}
    for o in existing_objs:
        by_topic_objs.setdefault(o.get('topic_uid'), []).append(o)

    added_goals = 0
    added_objs = 0
    for t in topics:
        tuid = t.get('uid')
        title = t.get('title') or 'Тема'
        if not by_topic_goals.get(tuid):
            record = {
                'uid': f"GOAL-{tuid}-MASTER",
                'topic_uid': tuid,
                'title': f"Достичь уверенного решения: {title}"
            }
            append_jsonl(os.path.join(KB_DIR, 'topic_goals.jsonl'), record)
            added_goals += 1
        if not by_topic_objs.get(tuid):
            obj_records = [
                {
                    'uid': f"OBJ-{tuid}-BASICS",
                    'topic_uid': tuid,
                    'title': f"Освоить базовые понятия: {title}"
                },
                {
                    'uid': f"OBJ-{tuid}-APPLY",
                    'topic_uid': tuid,
                    'title': f"Применять методы к задачам: {title}"
                }
            ]
            for rec in obj_records:
                append_jsonl(os.path.join(KB_DIR, 'topic_objectives.jsonl'), rec)
                added_objs += 1

    return {'added_goals': added_goals, 'added_objectives': added_objs}


def autolink_skills_methods(max_links_per_skill: int = 2) -> Dict:
    skills = load_jsonl(os.path.join(KB_DIR, 'skills.jsonl'))
    methods = load_jsonl(os.path.join(KB_DIR, 'methods.jsonl'))
    existing = load_jsonl(os.path.join(KB_DIR, 'skill_methods.jsonl'))

    existing_pairs: Set[Tuple[str, str]] = set()
    for sm in existing:
        su = sm.get('skill_uid')
        mu = sm.get('method_uid')
        if su and mu:
            existing_pairs.add((su, mu))

    added = 0
    for sk in skills:
        suid = sk.get('uid')
        stoks = tokens(sk.get('title', '')) | tokens(sk.get('definition', ''))
        candidates: List[Tuple[str, float, Dict]] = []
        for m in methods:
            muid = m.get('uid')
            mtoks = tokens(m.get('title', '')) | tokens(m.get('method_text', ''))
            if not mtoks:
                continue
            overlap = stoks & mtoks
            score = len(overlap) / max(len(stoks) or 1, len(mtoks))
            if score > 0:
                candidates.append((muid, score, m))
        candidates.sort(key=lambda x: x[1], reverse=True)
        links = 0
        for muid, score, m in candidates:
            if (suid, muid) in existing_pairs:
                continue
            record = {
                'skill_uid': suid,
                'method_uid': muid,
                'weight': 'primary' if score >= 0.2 else 'secondary',
                'confidence': round(min(0.95, 0.5 + score), 3),
                'is_auto_generated': True
            }
            append_jsonl(os.path.join(KB_DIR, 'skill_methods.jsonl'), record)
            existing_pairs.add((suid, muid))
            added += 1
            links += 1
            if links >= max_links_per_skill:
                break

    return {'added_links': added}
