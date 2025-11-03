#!/usr/bin/env python3
import os
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


def main():
    sections = load_jsonl('sections.jsonl')
    topics = load_jsonl('topics.jsonl')
    examples = load_jsonl('examples.jsonl')

    # Index examples by topic
    examples_by_topic: Dict[str, List[Dict]] = {}
    for e in examples:
        top = e.get('topic_uid')
        if not top:
            continue
        examples_by_topic.setdefault(top, []).append(e)

    # Load skill-topic links (if exist)
    skill_topics = load_jsonl('skill_topics.jsonl')
    skills_by_topic: Dict[str, List[str]] = {}
    for st in skill_topics:
        skills_by_topic.setdefault(st.get('topic_uid'), []).append(st.get('skill_uid'))

    theories_path = os.path.join(KB_DIR, 'theories.jsonl')
    lesson_steps_path = os.path.join(KB_DIR, 'lesson_steps.jsonl')
    example_skills_path = os.path.join(KB_DIR, 'example_skills.jsonl')

    with open(theories_path, 'w', encoding='utf-8') as f_theory, \
         open(lesson_steps_path, 'w', encoding='utf-8') as f_steps, \
         open(example_skills_path, 'w', encoding='utf-8') as f_ex_sk:

        # Section theories
        for sec in sections:
            uid = f"THE_SEC_{sec.get('uid')}"
            rec = {
                'uid': uid,
                'title': f"Теория раздела: {sec.get('title')}",
                'content': sec.get('description') or '',
                'section_uid': sec.get('uid')
            }
            f_theory.write(json.dumps(rec, ensure_ascii=False) + '\n')

        # Topic theories + lesson steps
        for top in topics:
            top_uid = top.get('uid')
            the_uid = f"THE_TOP_{top_uid}"
            theory = {
                'uid': the_uid,
                'title': f"Теория темы: {top.get('title')}",
                'content': top.get('description') or '',
                'topic_uid': top_uid
            }
            f_theory.write(json.dumps(theory, ensure_ascii=False) + '\n')

            skill_uids = skills_by_topic.get(top_uid, [])
            topic_examples = examples_by_topic.get(top_uid, [])
            example_uid = topic_examples[0]['uid'] if topic_examples else None

            # I do (teacher)
            step1 = {
                'uid': f"STEP_{top_uid}_1",
                'step_type': 'I_do',
                'order_index': 1,
                'topic_uid': top_uid,
                'resource_uids': [the_uid],
                'skill_uids': skill_uids
            }
            f_steps.write(json.dumps(step1, ensure_ascii=False) + '\n')

            # We do (guided)
            step2 = {
                'uid': f"STEP_{top_uid}_2",
                'step_type': 'We_do',
                'order_index': 2,
                'topic_uid': top_uid,
                'resource_uids': [example_uid] if example_uid else [],
                'skill_uids': skill_uids
            }
            f_steps.write(json.dumps(step2, ensure_ascii=False) + '\n')

            # You do (independent)
            step3 = {
                'uid': f"STEP_{top_uid}_3",
                'step_type': 'You_do',
                'order_index': 3,
                'topic_uid': top_uid,
                'resource_uids': [example_uid] if example_uid else [],
                'skill_uids': skill_uids
            }
            f_steps.write(json.dumps(step3, ensure_ascii=False) + '\n')

            # Link examples to skills (inherit topic's skills)
            for ex in topic_examples:
                for suid in skill_uids:
                    f_ex_sk.write(json.dumps({'example_uid': ex['uid'], 'skill_uid': suid}, ensure_ascii=False) + '\n')

    print(f'Theories -> {theories_path}')
    print(f'Lesson steps -> {lesson_steps_path}')
    print(f'Example-skills -> {example_skills_path}')


if __name__ == '__main__':
    main()