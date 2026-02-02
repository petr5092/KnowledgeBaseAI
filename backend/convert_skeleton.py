import hashlib
import re
import json
import os

INPUT_FILE = "/root/KnowledgeBaseAI/SKELETON_DATASET.md"
OUTPUT_DIR = "/root/KnowledgeBaseAI/backend/app/kb/ru/mathematics"

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

def transliterate(text):
    # Simple transliteration map (Cyrillic to Latin)
    mapping = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'j', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
        ' ': '-'
    }
    result = []
    for char in text.lower():
        if char in mapping:
            result.append(mapping[char])
        elif char.isalnum() or char == '-':
            result.append(char)
        # Ignore other characters
    return "".join(result).upper()

def generate_uid(prefix, title):
    slug = transliterate(title)
    if len(slug) > 30: # Increased slug length slightly
        slug = slug[:30]
    hash_digest = hashlib.md5(title.encode('utf-8')).hexdigest()[:6]
    return f"{prefix}-{slug}-{hash_digest}"

def determine_grade_range(title, section_title, subsection_title):
    title_lower = title.lower()
    sec_lower = section_title.lower() if section_title else ""
    subsec_lower = subsection_title.lower() if subsection_title else ""

    # Rules (regex pattern, min, max)
    # Order matters: more specific first
    rules = [
        (r"натуральные", 1, 6), # 5-6 класс закрепление
        (r"целые", 6, 6),
        (r"арифметика|сложение|вычитание|умножение|деление", 1, 4), # Начальная школа
        (r"счет|цифры", 1, 1),
        (r"дроби|рациональные", 5, 6),
        (r"проценты", 5, 6),
        (r"геометрические фигуры", 1, 4), # Простые фигуры в начальной школе
        (r"величины|время|масса|длина", 1, 4),
        (r"действительные", 8, 11),
        (r"комплексные", 10, 11),
        (r"многочлены|факторизация", 7, 9),
        (r"квадратные уравнения|дискриминант", 8, 9),
        (r"линейные уравнения", 7, 8),
        (r"неравенства", 8, 9),
        (r"линейная функция", 7, 7),
        (r"линейные функции", 7, 7),
        (r"квадратичная функция", 8, 9),
        (r"степенн|корень|корни", 8, 11),
        (r"показательная|логарифм|экспоненциальные", 10, 11),
        (r"тригонометр|синус|косинус|тангенс", 9, 11), 
        (r"производная|интеграл|предел", 10, 11),
        (r"треугольники|четырехугольники|окружность|углы", 7, 9),
        (r"многогранники|тела вращения|стереометрия|пространственная", 10, 11),
        (r"векторы", 9, 11),
        (r"вероятность|статистика|комбинаторика|случайные|выборка|средние|разброс|корреляция", 7, 11),
        (r"логика|множества|высказывания|кванторы|отношени|отображени|эквивалентность|порядок", 7, 11),
        (r"матрицы|определители", 10, 11),
        (r"графы|деревья|пути|циклы", 7, 11),
        (r"систему счисления", 8, 9),
        (r"пропорции", 6, 6),
        (r"функци|график|монотонность|обратная", 7, 11),
        (r"текстовые задачи", 1, 6), # Сквозная тема, начиная с 1 класса
        (r"геометрия", 1, 11), # Default geometry fallback override for primary school context if needed
    ]

    # Check topic title first
    for pattern, mn, mx in rules:
        if re.search(pattern, title_lower):
            return mn, mx

    # Check subsection title
    for pattern, mn, mx in rules:
        if re.search(pattern, subsec_lower):
            return mn, mx
            
    # Check section title (Broad fallbacks)
    if "геометрия" in sec_lower:
        if "аналитическая" in sec_lower:
            return 9, 11
        return 7, 11 # Default geometry
    if "тригонометрия" in sec_lower:
        return 10, 11
    if "анализ" in sec_lower: # Mathematical analysis
        return 10, 11
    if "числа" in sec_lower: # Numbers structure
        return 5, 11
    if "алгебра" in sec_lower:
        return 7, 11
        
    # Default fallback
    return 1, 11

def main():
    sections = []
    subsections = []
    topics = []
    prereqs = [] # List of (target_title, prereq_title)

    current_section = None
    current_subsection = None
    
    # Pre-scan to map titles to UIDs for prereq resolution
    topic_title_to_uid = {}

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # First pass: Parse structure and generate UIDs
    print(f"Reading {len(lines)} lines from {INPUT_FILE}")
    for i, line in enumerate(lines):
        line = line.strip()
        if i < 25:
             print(f"Line {i}: '{line}'")
        if not line:
            continue
        
        # Section
        match_sec = re.match(r'^## SECTION (\d+)\. (.+)$', line)
        if match_sec:
            title = match_sec.group(2).strip()
            uid = generate_uid("SEC", title)
            current_section = {
                "uid": uid,
                "subject_uid": "MATH-FULL-V1",
                "title": title,
                "description": ""
            }
            sections.append(current_section)
            current_subsection = None # Reset subsection
            continue

        # Subsection
        match_subsec = re.match(r'^### Subsection (\d+\.\d+)\. (.+)$', line)
        if match_subsec:
            if not current_section:
                print(f"Warning: Subsection found without Section: {line}")
                # Try to recover or default
            title = match_subsec.group(2).strip()
            uid = generate_uid("SUBSEC", title)
            current_subsection = {
                "uid": uid,
                "section_uid": current_section["uid"],
                "title": title,
                "description": ""
            }
            subsections.append(current_subsection)
            continue

        # Topic
        match_topic = re.match(r'^\* Тема: (.+)$', line)
        if match_topic:
            if not current_subsection:
                # Create a default subsection if none exists
                if current_section:
                    default_title = "General"
                    uid = generate_uid("SUBSEC", f"{current_section['title']} - {default_title}")
                    current_subsection = {
                        "uid": uid,
                        "section_uid": current_section["uid"],
                        "title": default_title,
                        "description": "Default subsection"
                    }
                    subsections.append(current_subsection)
                    print(f"Created default subsection for section: {current_section['title']}")
                else:
                    print(f"Warning: Topic found without Section/Subsection: {line}")
                    continue

            title = match_topic.group(1).strip()
            uid = generate_uid("TOP", title)
            
            # Determine grade range
            section_title = current_section["title"] if current_section else ""
            subsection_title = current_subsection["title"] if current_subsection else ""
            mn, mx = determine_grade_range(title, section_title, subsection_title)
            
            topic = {
                "uid": uid,
                "section_uid": current_subsection["uid"], # Links to SUBSECTION as per schema
                "title": title,
                "description": "",
                "user_class_min": mn,
                "user_class_max": mx,
                "difficulty_band": "standard"
            }
            topics.append(topic)
            topic_title_to_uid[title] = uid
            continue

        # Prereq
        match_prereq = re.match(r'^PREREQ: (.+)$', line) # Removed \s* anchor because strip() is called on line, but MD usually has indent.
        # Actually line is stripped above. So 'PREREQ: ...' should match if indent was removed.
        # Wait, the MD file has '* Тема: ...' then next line '  PREREQ: ...'.
        # line.strip() removes the indent. So 'PREREQ: ...' is correct.
        if match_prereq:
            if not topics:
                continue
            target_topic = topics[-1]
            prereq_str = match_prereq.group(1).strip()
            if prereq_str == "—" or prereq_str == "-":
                continue
            
            # Split by comma if multiple prereqs
            p_titles = [p.strip() for p in prereq_str.split(',')]
            for p_title in p_titles:
                prereqs.append((target_topic["title"], p_title))

    PREREQ_MAPPING = {
        "Арифметические операции": "Натуральные числа",
        "Координаты": "Декартовы координаты",
        "Многоугольники": "Треугольники",
        "Евклидова геометрия": "Точка и прямая",
        "Тождества": "Тригонометрические тождества",
        "Комбинаторика": "Перестановки",
        "Логика": "Высказывания",
        "Множества": "Понятие множества"
    }

    # Second pass: Resolve prereqs
    resolved_prereqs = []
    for target_title, prereq_title in prereqs:
        # Apply mapping if needed
        if prereq_title in PREREQ_MAPPING:
            print(f"Mapping '{prereq_title}' to '{PREREQ_MAPPING[prereq_title]}'")
            prereq_title = PREREQ_MAPPING[prereq_title]
        else:
             # Debug unmapped
             # pass 
             print(f"Checking '{prereq_title}' (len={len(prereq_title)})")

        target_uid = topic_title_to_uid.get(target_title)
        prereq_uid = topic_title_to_uid.get(prereq_title)
        
        if target_uid and prereq_uid:
            resolved_prereqs.append({
                "target_uid": target_uid,
                "prereq_uid": prereq_uid,
                "weight": 1.0
            })
        else:
            if not prereq_uid:
                print(f"Warning: Prereq topic not found: '{prereq_title}' for '{target_title}'")

    # Write files
    def write_jsonl(filename, data):
        path = os.path.join(OUTPUT_DIR, filename)
        with open(path, 'w', encoding='utf-8') as f:
            for item in data:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')
        print(f"Written {len(data)} records to {path}")

    write_jsonl("sections.jsonl", sections)
    write_jsonl("subsections.jsonl", subsections)
    write_jsonl("topics.jsonl", topics)
    write_jsonl("topic_prereqs.jsonl", resolved_prereqs)

if __name__ == "__main__":
    main()
