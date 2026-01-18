
import json
import random
import sys
import os

# Target topics (top 20 from MATH-FULL-V1 based on query)
TARGET_TOPICS = [
    {"uid": "TOP-SLOZHENIE-I-VYCHITANIE-fce82b", "title": "Сложение и вычитание"},
    {"uid": "TOP-UMNOZHENIE-I-DELENIE-bb242b", "title": "Умножение и деление"},
    {"uid": "TOP-RABOTA-S-DROBYAMI-1d735c", "title": "Работа с дробями"},
    {"uid": "TOP-PROCENTY-I-IH-VYCHISLENI-b55c05", "title": "Проценты и их вычисление"},
    {"uid": "TOP-STEPENI-I-KORNI-179a43", "title": "Степени и корни"},
    {"uid": "TOP-ALGEBRAICHESKIE-VYRAZHEN-66ffd6", "title": "Алгебраические выражения"},
    {"uid": "TOP-KOMMUTATIVNOST-SLOZHENIY-301b90", "title": "Коммутативность сложения"},
    {"uid": "TOP-ASSOCIATIVNOST-SLOZHENIY-762768", "title": "Ассоциативность сложения"},
    {"uid": "TOP-KOMMUTATIVNOST-UMNOZHENI-5bc9c8", "title": "Коммутативность умножения"},
    {"uid": "TOP-ASSOCIATIVNOST-UMNOZHENI-7449e4", "title": "Ассоциативность умножения"},
    {"uid": "TOP-DISTRIBUTIVNOST-UMNOZHEN-ad4285", "title": "Дистрибутивность умножения относительно сложения"},
    {"uid": "TOP-NEITRALNYE-ELEMENTY-SLOZ-3b109a", "title": "Нейтральные элементы сложения и умножения"},
    {"uid": "TOP-BYUDZHETIROVANIE-I-UPRAV-0fb820", "title": "Бюджетирование и управление финансами"},
    {"uid": "TOP-KULINARNYE-RASCHETY-PROP-6cc956", "title": "Кулинарные расчеты: пропорции и порции"},
    {"uid": "TOP-IZMERENIE-I-RASCHET-PLOS-820d97", "title": "Измерение и расчет площади и объема"},
    {"uid": "TOP-SRAVNENIE-CEN-I-VYBOR-VY-7cc033", "title": "Сравнение цен и выбор выгодных предложений"},
    {"uid": "TOP-RASCHET-VREMENI-PLANIROV-a19346", "title": "Расчет времени: планирование и расписание"},
    {"uid": "TOP-ANALIZ-DANNYH-STATISTIKA-bbdd1d", "title": "Анализ данных: статистика в повседневной жизни"},
    {"uid": "TOP-SLOZHENIE-I-VYCHITANIE-A-7c0292", "title": "Сложение и вычитание алгебраических выражений"},
    {"uid": "TOP-UMNOZHENIE-I-DELENIE-ALG-dd5c83", "title": "Умножение и деление алгебраических выражений"}
]

# Micro-lesson templates for specific topics
MICRO_LESSONS_CUSTOM = {
    "TOP-SLOZHENIE-I-VYCHITANIE-fce82b": [
        "Сложение натуральных чисел",
        "Вычитание с переходом через десяток",
        "Свойства сложения",
        "Решение текстовых задач на сложение"
    ],
    "TOP-UMNOZHENIE-I-DELENIE-bb242b": [
        "Таблица умножения",
        "Деление с остатком",
        "Распределительное свойство",
        "Умножение в столбик"
    ],
    "TOP-RABOTA-S-DROBYAMI-1d735c": [
        "Что такое дробь",
        "Сложение дробей с одинаковыми знаменателями",
        "Приведение к общему знаменателю",
        "Умножение дробей"
    ],
    "TOP-PROCENTY-I-IH-VYCHISLENI-b55c05": [
        "Понятие процента",
        "Перевод дробей в проценты",
        "Нахождение процента от числа"
    ],
    "TOP-STEPENI-I-KORNI-179a43": [
        "Квадрат и куб числа",
        "Свойства степеней",
        "Квадратный корень"
    ]
}

def generate_units():
    units = []
    
    for topic in TARGET_TOPICS:
        t_uid = topic["uid"]
        t_title = topic["title"]
        
        # Get specific micro lessons or generate generic ones
        micros = MICRO_LESSONS_CUSTOM.get(t_uid)
        if not micros:
            micros = [
                f"Основные понятия: {t_title}",
                f"Практические примеры: {t_title}",
                f"Сложные случаи: {t_title}"
            ]
        
        # 1. Generate Micro-lessons (group of 3 units)
        for idx, m_title in enumerate(micros):
            m_id = idx + 1
            # I Do
            units.append({
                "uid": f"UNIT-{t_uid}-M{m_id}-IDO",
                "topic_uid": t_uid,
                "branch": "lesson",
                "type": "lesson_i_do",
                "complexity": 0.2,
                "payload": {
                    "text": f"Теория: {m_title}. Объяснение от учителя (I Do). Здесь мы разбираем основные концепции темы '{t_title}'.",
                    "video_url": "http://video.example.com/1",
                    "micro_lesson_title": m_title,
                    "order": m_id
                }
            })
            # We Do
            units.append({
                "uid": f"UNIT-{t_uid}-M{m_id}-WEDO",
                "topic_uid": t_uid,
                "branch": "lesson",
                "type": "lesson_we_do",
                "complexity": 0.4,
                "payload": {
                    "text": f"Практика: {m_title}. Решаем вместе (We Do). Совместное решение задач по теме '{t_title}'.",
                    "micro_lesson_title": m_title,
                    "order": m_id
                }
            })
            # You Do
            units.append({
                "uid": f"UNIT-{t_uid}-M{m_id}-YOUDO",
                "topic_uid": t_uid,
                "branch": "lesson",
                "type": "lesson_you_do",
                "complexity": 0.6,
                "payload": {
                    "text": f"Задание: {m_title}. Реши самостоятельно (You Do). Проверь свои знания по теме '{t_title}'.",
                    "micro_lesson_title": m_title,
                    "order": m_id
                }
            })
            
        # 2. Final Test for the Topic
        units.append({
            "uid": f"UNIT-{t_uid}-FINAL-TEST",
            "topic_uid": t_uid,
            "branch": "lesson",
            "type": "lesson_test",
            "complexity": 0.8,
            "payload": {
                "text": f"Финальный тест по теме {t_title}. Проверь, как ты усвоил материал.",
                "question_count": 10
            }
        })
        
    return units

def append_to_file(units, filepath):
    # Read existing uids to avoid duplicates
    existing_uids = set()
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    existing_uids.add(obj['uid'])
                except:
                    pass
    
    with open(filepath, 'a', encoding='utf-8') as f:
        count = 0
        for u in units:
            if u['uid'] not in existing_uids:
                f.write(json.dumps(u, ensure_ascii=False) + '\n')
                count += 1
        print(f"Appended {count} new units to {filepath}")

if __name__ == "__main__":
    new_units = generate_units()
    # Path relative to where we run it (project root in container usually has /app)
    # But here we use absolute path on host which maps to container
    target_file = "/root/KnowledgeBaseAI/backend/app/kb/content_units.jsonl"
    append_to_file(new_units, target_file)
