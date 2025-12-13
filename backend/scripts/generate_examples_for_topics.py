#!/usr/bin/env python3
import os
import json
from typing import List, Dict, Set

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


def append_jsonl(filename: str, items: List[Dict]):
    path = os.path.join(KB_DIR, filename)
    with open(path, 'a', encoding='utf-8') as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")


def make_example_uid(topic_uid: str, idx: int = 1) -> str:
    return f"EX_{topic_uid}_{idx}"


def generate_statement(title: str, description: str) -> str:
    # Простая генерация формулировки задачи на основе названия темы
    base = title.strip()
    desc = (description or '').strip()
    prompt = f"Сформулируйте учебную задачу по теме: {base}."
    if desc:
        prompt += f" Ориентируйтесь на описание: {desc}."
    return prompt


def main():
    topics = load_jsonl('topics.jsonl')
    sections = load_jsonl('sections.jsonl')
    examples = load_jsonl('examples.jsonl')

    sec_to_subject = {s.get('uid'): s.get('subject_uid') for s in sections}
    topics_with_examples: Set[str] = {ex.get('topic_uid') for ex in examples if ex.get('topic_uid')}

    new_examples: List[Dict] = []
    for t in topics:
        t_uid = t.get('uid')
        if not t_uid:
            continue
        if t_uid in topics_with_examples:
            continue  # уже есть хотя бы один пример
        sec_uid = t.get('section_uid')
        subj_uid = sec_to_subject.get(sec_uid)
        ex_uid = make_example_uid(t_uid, 1)
        title = f"Пример: {t.get('title')}"
        statement = generate_statement(t.get('title', ''), t.get('description', ''))
        # Включаем оба поля сложности для совместимости (ES и Neo4j/PG)
        new_examples.append({
            'uid': ex_uid,
            'subject_uid': subj_uid,
            'topic_uid': t_uid,
            'title': title,
            'statement': statement,
            'difficulty': 2,
            'difficulty_level': 'medium'
        })

    if not new_examples:
        print('Все темы уже имеют примеры — новых записей не требуется')
        return

    append_jsonl('examples.jsonl', new_examples)
    print(f"Сгенерировано {len(new_examples)} примеров -> {os.path.join(KB_DIR, 'examples.jsonl')}\nПервый: {new_examples[0]['uid']} — {new_examples[0]['title']}")


if __name__ == '__main__':
    main()