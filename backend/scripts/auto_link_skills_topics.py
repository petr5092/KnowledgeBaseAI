#!/usr/bin/env python3
import os
import re
import json
from typing import List, Dict

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
KB_DIR = os.path.join(BASE_DIR, 'kb')


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


def tokenize(text: str) -> List[str]:
    if not text:
        return []
    return [t for t in re.split(r"[^\w]+", text.lower()) if t]


def main():
    topics = load_jsonl('topics.jsonl')
    skills = load_jsonl('skills.jsonl')

    # Index skills by subject for coarse filtering
    skills_by_subject: Dict[str, List[Dict]] = {}
    for s in skills:
        subj = s.get('subject_uid')
        skills_by_subject.setdefault(subj, []).append(s)

    out_path = os.path.join(KB_DIR, 'skill_topics.jsonl')
    with open(out_path, 'w', encoding='utf-8') as out:
        total_links = 0
        for t in topics:
            subj = None
            # Find section to infer subject
            subj = None
            # Optional: If topics contain section_uid, we cannot map to subject directly
            # We'll rely on skills of any subject if subject is unknown
            candidate_skills = skills_by_subject.get(subj) or skills

            t_tokens = set(tokenize(t.get('title', '')))
            if not t_tokens:
                continue
            matches = []
            for s in candidate_skills:
                s_tokens = set(tokenize(s.get('title', '')))
                overlap = t_tokens & s_tokens
                if not overlap:
                    continue
                score = len(overlap) / max(1, len(t_tokens))
                weight = 'primary' if len(overlap) >= 2 else 'secondary'
                matches.append({
                    'topic_uid': t.get('uid'),
                    'skill_uid': s.get('uid'),
                    'confidence': round(min(1.0, 0.5 + score), 3),
                    'weight': weight
                })
            for m in matches:
                out.write(json.dumps(m, ensure_ascii=False) + '\n')
            total_links += len(matches)
        print(f'Generated {total_links} skill-topic links -> {out_path}')


if __name__ == '__main__':
    main()