
import os
import sys

# Add backend path to sys.path to allow imports
sys.path.append(os.path.join(os.path.dirname(__file__), "app"))

from app.services.graph.neo4j_repo import Neo4jRepo

def fix_classes():
    print("Connecting to Neo4j...")
    repo = Neo4jRepo()
    
    # Mapping of keywords to (min_class, max_class)
    curriculum_map = {
        # Начальная школа (1-4)
        "Сложение": (1, 4),
        "Вычитание": (1, 4),
        "Счет": (1, 1),
        "Числа от 1 до": (1, 2),
        "Таблица умножения": (2, 3),
        "Умножение": (2, 4),
        "Деление": (2, 4),
        "Порядок действий": (3, 4),
        "Единицы измерения": (1, 4),
        
        # 5-6 классы
        "Натуральные числа": (5, 5),
        "Дроби": (5, 6),
        "Смешанные числа": (5, 6),
        "Десятичные": (5, 6),
        "Проценты": (5, 9),
        "Отношения и пропорции": (6, 6),
        "Положительные и отрицательные": (6, 6),
        "Рациональные числа": (6, 6),
        "Модуль числа": (6, 7),
        "Координатная плоскость": (6, 7),
        
        # Алгебра 7-9
        "Алгебраические выражения": (7, 9),
        "Степень": (7, 11),
        "Одночлены": (7, 7),
        "Многочлены": (7, 7),
        "Формулы сокращенного умножения": (7, 9),
        "Линейная функция": (7, 7),
        "Системы уравнений": (7, 9),
        "Квадратные корни": (8, 9),
        "Квадратные уравнения": (8, 9),
        "Квадратичная функция": (8, 9),
        "Неравенства": (8, 9),
        "Прогрессии": (9, 9),
        
        # Геометрия 7-9
        "Геометрия": (7, 11),
        "Треугольник": (7, 9),
        "Параллельные прямые": (7, 7),
        "Соотношения в треугольнике": (7, 9),
        "Четырехугольники": (8, 8),
        "Площадь": (8, 9),
        "Подобие": (8, 9),
        "Окружность": (8, 9),
        "Векторы": (9, 11),
        "Движение": (9, 9),
        
        # 10-11 классы
        "Тригонометр": (10, 11),
        "Синус": (9, 11),
        "Косинус": (9, 11),
        "Тангенс": (9, 11),
        "Производн": (10, 11),
        "Первообразн": (11, 11),
        "Интеграл": (11, 11),
        "Логарифм": (10, 11),
        "Показательн": (10, 11),
        "Степенн": (10, 11),
        "Многогранник": (10, 11),
        "Тела вращения": (11, 11),
        "Объем": (11, 11),
        "Вероятност": (7, 11),
        "Статистик": (7, 11),
        "Статистич": (7, 11),
        "Распределен": (10, 11),
        "Регресс": (10, 11),
        "Предельн": (10, 11),
        "Теорем": (7, 11),
        "Анализ": (10, 11),
        "Дисперси": (10, 11),
        "Ожидани": (10, 11), # Математическое ожидание
        "Гипотез": (10, 11),
        "Закон": (10, 11) # Закон больших чисел и т.д. (риск ложных срабатываний, но в математике обычно ок)
    }

    print("Fetching all topics...")
    all_topics = repo.read("MATCH (t:Topic) RETURN t.uid as uid, t.title as title")
    print(f"Found {len(all_topics)} topics. calculating classes...")

    updates = []
    
    for row in all_topics:
        uid = row['uid']
        title = row['title'] or ""
        t_lower = title.lower()
        
        cur_min = 1
        cur_max = 1
        found_match = False
        
        for key, (mn, mx) in curriculum_map.items():
            if key.lower() in t_lower:
                found_match = True
                cur_min = max(cur_min, mn)
                cur_max = max(cur_max, mx)
        
        if not found_match:
            # Fallback - assume intermediate/advanced if not explicitly elementary
            cur_min = 7
            cur_max = 11
            
        updates.append({"uid": uid, "mn": cur_min, "mx": cur_max})

    print(f"Applying {len(updates)} updates in batches...")
    
    batch_size = 50
    for i in range(0, len(updates), batch_size):
        batch = updates[i:i+batch_size]
        repo.write(
            """
            UNWIND $batch as item
            MATCH (t:Topic {uid: item.uid})
            SET t.user_class_min = item.mn, t.user_class_max = item.mx
            """,
            {"batch": batch}
        )
        print(f"  Processed {i + len(batch)} / {len(updates)}")

    repo.close()
    print("Done.")

if __name__ == "__main__":
    fix_classes()
