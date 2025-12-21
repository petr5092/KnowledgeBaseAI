import os
import json

KB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'kb')
os.makedirs(KB_DIR, exist_ok=True)

SUBJECTS = [
    {"uid": "sub-math", "title": "Математика", "description": "Царица наук"},
    {"uid": "sub-cs", "title": "Computer Science", "description": "Наука о вычислениях"}
]

SECTIONS = [
    {"uid": "sec-algebra", "subject_uid": "sub-math", "title": "Алгебра", "order_index": 1},
    {"uid": "sec-geometry", "subject_uid": "sub-math", "title": "Геометрия", "order_index": 2},
    {"uid": "sec-algo", "subject_uid": "sub-cs", "title": "Алгоритмы", "order_index": 1}
]

TOPICS = [
    {"uid": "topic-linear-eq", "section_uid": "sec-algebra", "title": "Линейные уравнения", "accuracy_threshold": 0.8},
    {"uid": "topic-quadratic-eq", "section_uid": "sec-algebra", "title": "Квадратные уравнения", "accuracy_threshold": 0.85},
    {"uid": "topic-triangles", "section_uid": "sec-geometry", "title": "Треугольники", "accuracy_threshold": 0.8},
    {"uid": "topic-sorting", "section_uid": "sec-algo", "title": "Сортировка", "accuracy_threshold": 0.9}
]

SKILLS = [
    {"uid": "skill-solve-linear", "subject_uid": "sub-math", "title": "Решение линейных уравнений", "definition": "Умение находить корень линейного уравнения"},
    {"uid": "skill-calc-discriminant", "subject_uid": "sub-math", "title": "Вычисление дискриминанта", "definition": "b^2 - 4ac"},
    {"uid": "skill-bubble-sort", "subject_uid": "sub-cs", "title": "Пузырьковая сортировка", "definition": "Простой алгоритм сортировки"}
]

def write_jsonl(filename, data):
    path = os.path.join(KB_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
    print(f"Created {path}")

if __name__ == "__main__":
    write_jsonl('subjects.jsonl', SUBJECTS)
    write_jsonl('sections.jsonl', SECTIONS)
    write_jsonl('topics.jsonl', TOPICS)
    write_jsonl('skills.jsonl', SKILLS)
    # Пустые файлы для остальных, чтобы скрипт не падал
    write_jsonl('methods.jsonl', [])
    write_jsonl('examples.jsonl', [])
    write_jsonl('errors.jsonl', [])
    write_jsonl('skill_methods.jsonl', [])
    write_jsonl('skill_topics.jsonl', [])
    write_jsonl('theories.jsonl', [])
    write_jsonl('lesson_steps.jsonl', [])
    write_jsonl('example_skills.jsonl', [])
