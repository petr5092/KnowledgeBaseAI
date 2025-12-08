import os
import json
import re
import uuid
import requests
from typing import Dict, List, Tuple, Set, Optional

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


def rewrite_jsonl(filepath: str, records: List[Dict]) -> None:
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def get_path(name: str) -> str:
    return os.path.join(KB_DIR, name)


def _translit_en(s: str) -> str:
    mapping = {
        'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh','з':'z','и':'i','й':'i','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'h','ц':'c','ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya',
        'А':'a','Б':'b','В':'v','Г':'g','Д':'d','Е':'e','Ё':'e','Ж':'zh','З':'z','И':'i','Й':'i','К':'k','Л':'l','М':'m','Н':'n','О':'o','П':'p','Р':'r','С':'s','Т':'t','У':'u','Ф':'f','Х':'h','Ц':'c','Ч':'ch','Ш':'sh','Щ':'sch','Ъ':'','Ы':'y','Ь':'','Э':'e','Ю':'yu','Я':'ya'
    }
    out = []
    for ch in s:
        if ch.isascii():
            out.append(ch)
        else:
            out.append(mapping.get(ch, ''))
    return ''.join(out)

def make_uid(prefix: str, title: str) -> str:
    t = _translit_en(title)
    t = t.lower()
    allowed = ''.join(ch if ch.isalnum() else '-' for ch in t)
    # collapse dashes
    slug = re.sub(r'-{2,}', '-', allowed).strip('-')
    if not slug:
        slug = 'item'
    slug = slug.replace('--','-')[:24]
    base = slug.upper()
    return f"{prefix}-{base}-{uuid.uuid4().hex[:6]}"


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


def add_subject(title: str, description: str = '', uid: Optional[str] = None) -> Dict:
    uid = uid or make_uid('SUB', title)
    append_jsonl(get_path('subjects.jsonl'), {'uid': uid, 'title': title, 'description': description})
    return {'uid': uid}


def add_section(subject_uid: str, title: str, description: str = '', uid: Optional[str] = None) -> Dict:
    uid = uid or make_uid('SEC', title)
    append_jsonl(get_path('sections.jsonl'), {'uid': uid, 'subject_uid': subject_uid, 'title': title, 'description': description})
    return {'uid': uid}


def add_topic(section_uid: str, title: str, description: str = '', uid: Optional[str] = None) -> Dict:
    uid = uid or make_uid('TOP', title)
    append_jsonl(get_path('topics.jsonl'), {'uid': uid, 'section_uid': section_uid, 'title': title, 'description': description})
    return {'uid': uid}


def add_skill(subject_uid: str, title: str, definition: str = '', uid: Optional[str] = None) -> Dict:
    uid = uid or make_uid('SKL', title)
    append_jsonl(get_path('skills.jsonl'), {'uid': uid, 'subject_uid': subject_uid, 'title': title, 'definition': definition})
    return {'uid': uid}


def add_method(title: str, method_text: str = '', applicability_types: Optional[List[str]] = None, uid: Optional[str] = None) -> Dict:
    uid = uid or make_uid('MET', title)
    append_jsonl(get_path('methods.jsonl'), {'uid': uid, 'title': title, 'method_text': method_text, 'applicability_types': applicability_types or []})
    return {'uid': uid}


def link_topic_skill(topic_uid: str, skill_uid: str, weight: str = 'linked', confidence: float = 0.9) -> Dict:
    append_jsonl(get_path('topic_skills.jsonl'), {'topic_uid': topic_uid, 'skill_uid': skill_uid, 'weight': weight, 'confidence': confidence})
    return {'ok': True}


def link_topic_skill_fallback(topic_uid: str, skill_uid: str, weight: str = 'linked', confidence: float = 0.9) -> Dict:
    append_jsonl(get_path('skill_topics.jsonl'), {'topic_uid': topic_uid, 'skill_uid': skill_uid, 'weight': weight, 'confidence': confidence})
    return {'ok': True}


def link_skill_method(skill_uid: str, method_uid: str, weight: str = 'primary', confidence: float = 0.9, is_auto_generated: bool = False) -> Dict:
    append_jsonl(get_path('skill_methods.jsonl'), {'skill_uid': skill_uid, 'method_uid': method_uid, 'weight': weight, 'confidence': confidence, 'is_auto_generated': is_auto_generated})
    return {'ok': True}


def add_example(title: str, statement: str = '', topic_uid: Optional[str] = None, difficulty: int = 3, uid: Optional[str] = None) -> Dict:
    uid = uid or make_uid('EX', title)
    append_jsonl(get_path('examples.jsonl'), {'uid': uid, 'title': title, 'statement': statement, 'topic_uid': topic_uid, 'difficulty': difficulty})
    return {'uid': uid}


def link_example_skill(example_uid: str, skill_uid: str, role: str = 'target') -> Dict:
    append_jsonl(get_path('example_skills.jsonl'), {'example_uid': example_uid, 'skill_uid': skill_uid, 'role': role})
    return {'ok': True}


def add_error(title: str, error_text: str = '', triggers: Optional[List[str]] = None, uid: Optional[str] = None) -> Dict:
    uid = uid or make_uid('ERR', title)
    append_jsonl(get_path('errors.jsonl'), {'uid': uid, 'title': title, 'error_text': error_text, 'triggers': triggers or []})
    return {'uid': uid}


def link_error_skill(error_uid: str, skill_uid: str) -> Dict:
    append_jsonl(get_path('error_skills.jsonl'), {'error_uid': error_uid, 'skill_uid': skill_uid})
    return {'ok': True}


def link_error_example(error_uid: str, example_uid: str) -> Dict:
    append_jsonl(get_path('error_examples.jsonl'), {'error_uid': error_uid, 'example_uid': example_uid})
    return {'ok': True}


def add_topic_goal(topic_uid: str, title: str, uid: Optional[str] = None) -> Dict:
    uid = uid or make_uid('GOAL', title)
    append_jsonl(get_path('topic_goals.jsonl'), {'uid': uid, 'topic_uid': topic_uid, 'title': title})
    return {'uid': uid}


def add_topic_objective(topic_uid: str, title: str, uid: Optional[str] = None) -> Dict:
    uid = uid or make_uid('OBJ', title)
    append_jsonl(get_path('topic_objectives.jsonl'), {'uid': uid, 'topic_uid': topic_uid, 'title': title})
    return {'uid': uid}


def add_lesson_step(topic_uid: str, role: str, text: str) -> Dict:
    append_jsonl(get_path('lesson_steps.jsonl'), {'topic_uid': topic_uid, 'role': role, 'text': text})
    return {'ok': True}


def add_theory(topic_uid: str, text: str) -> Dict:
    append_jsonl(get_path('theories.jsonl'), {'topic_uid': topic_uid, 'text': text})
    return {'ok': True}


def normalize_skill_topics_to_topic_skills() -> Dict:
    src = load_jsonl(get_path('skill_topics.jsonl'))
    dst = load_jsonl(get_path('topic_skills.jsonl'))
    pairs = {(d.get('topic_uid'), d.get('skill_uid')) for d in dst if d.get('topic_uid') and d.get('skill_uid')}
    added = 0
    for r in src:
        tu, su = r.get('topic_uid'), r.get('skill_uid')
        if not tu or not su:
            continue
        if (tu, su) in pairs:
            continue
        append_jsonl(get_path('topic_skills.jsonl'), {'topic_uid': tu, 'skill_uid': su, 'weight': r.get('weight', 'linked'), 'confidence': r.get('confidence', 0.9)})
        pairs.add((tu, su))
        added += 1
    return {'added': added}


def openai_chat(messages: List[Dict], model: str = 'gpt-4o-mini', temperature: float = 0.2) -> Dict:
    def _load_env_file() -> None:
        env_path = os.path.join(BASE_DIR, '.env')
        if os.path.exists(env_path):
            try:
                with open(env_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        if '=' in line:
                            k, v = line.split('=', 1)
                            k = k.strip()
                            v = v.strip().strip('"').strip("'")
                            if k and v and k not in os.environ:
                                os.environ[k] = v
            except Exception:
                pass
    key = os.getenv('OPENAI_API_KEY')
    if not key:
        _load_env_file()
        key = os.getenv('OPENAI_API_KEY')
    if not key:
        return {'ok': False, 'error': 'missing OPENAI_API_KEY'}
    url = 'https://api.openai.com/v1/chat/completions'
    headers = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
    payload = {'model': model, 'messages': messages, 'temperature': temperature}
    r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
    if r.status_code != 200:
        return {'ok': False, 'error': r.text}
    data = r.json()
    content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
    return {'ok': True, 'content': content}


def generate_theory_for_topic_openai(topic_uid: str, max_tokens: int = 600) -> Dict:
    topics = load_jsonl(get_path('topics.jsonl'))
    topic = next((t for t in topics if t.get('uid') == topic_uid), None)
    if not topic:
        return {'ok': False, 'error': 'topic not found'}
    skills = [r.get('skill_uid') for r in load_jsonl(get_path('topic_skills.jsonl')) if r.get('topic_uid') == topic_uid]
    skill_defs = {s.get('uid'): s for s in load_jsonl(get_path('skills.jsonl'))}
    methods_by_skill = {}
    for sm in load_jsonl(get_path('skill_methods.jsonl')):
        su, mu = sm.get('skill_uid'), sm.get('method_uid')
        if su in skills:
            methods_by_skill.setdefault(su, []).append(mu)
    method_defs = {m.get('uid'): m for m in load_jsonl(get_path('methods.jsonl'))}
    ctx_skills = [skill_defs[k].get('title') for k in skills if k in skill_defs]
    ctx_methods = [method_defs[k].get('title') for v in methods_by_skill.values() for k in v if k in method_defs]
    messages = [
        {'role': 'system', 'content': 'Пиши краткую точную теорию по теме на русском, без лишних слов.'},
        {'role': 'user', 'content': json.dumps({'topic': topic.get('title'), 'skills': ctx_skills, 'methods': ctx_methods}, ensure_ascii=False)}
    ]
    res = openai_chat(messages)
    if not res.get('ok'):
        return res
    append_jsonl(get_path('theories.jsonl'), {'topic_uid': topic_uid, 'text': res.get('content', '')[:max_tokens*4]})
    return {'ok': True}


def generate_examples_for_topic_openai(topic_uid: str, count: int = 3, difficulty: int = 3) -> Dict:
    topics = load_jsonl(get_path('topics.jsonl'))
    topic = next((t for t in topics if t.get('uid') == topic_uid), None)
    if not topic:
        return {'ok': False, 'error': 'topic not found'}
    messages = [
        {'role': 'system', 'content': 'Сгенерируй краткие учебные задачи по теме. Верни JSONL c полями title и statement.'},
        {'role': 'user', 'content': topic.get('title')}
    ]
    res = openai_chat(messages)
    if not res.get('ok'):
        return res
    lines = [l for l in res.get('content', '').splitlines() if l.strip()]
    added = 0
    for l in lines:
        try:
            obj = json.loads(l)
            ex_uid = make_uid('EX', obj.get('title','Example'))
            append_jsonl(get_path('examples.jsonl'), {'uid': ex_uid, 'title': obj.get('title',''), 'statement': obj.get('statement',''), 'topic_uid': topic_uid, 'difficulty': difficulty})
            added += 1
            if added >= count:
                break
        except Exception:
            continue
    return {'ok': True, 'added': added}


def generate_methods_for_skill_openai(skill_uid: str, count: int = 3) -> Dict:
    skills = load_jsonl(get_path('skills.jsonl'))
    skill = next((s for s in skills if s.get('uid') == skill_uid), None)
    if not skill:
        return {'ok': False, 'error': 'skill not found'}
    messages = [
        {'role': 'system', 'content': 'Предложи компактные методы решения, верни JSONL с полями title и method_text.'},
        {'role': 'user', 'content': skill.get('title')}
    ]
    res = openai_chat(messages)
    if not res.get('ok'):
        return res
    lines = [l for l in res.get('content','').splitlines() if l.strip()]
    added = 0
    created_method_uids: List[str] = []
    for l in lines:
        try:
            obj = json.loads(l)
            muid = make_uid('MET', obj.get('title','Method'))
            append_jsonl(get_path('methods.jsonl'), {'uid': muid, 'title': obj.get('title',''), 'method_text': obj.get('method_text',''), 'applicability_types': []})
            link_skill_method(skill_uid, muid, weight='core', confidence=0.9, is_auto_generated=True)
            created_method_uids.append(muid)
            added += 1
            if added >= count:
                break
        except Exception:
            continue
    return {'ok': True, 'added': added, 'method_uids': created_method_uids}


def generate_topic_bundle_openai(topic_uid: str, examples_count: int = 5) -> Dict:
    """
    Сгенерировать полный пакет для темы: теория, примеры, методы для связанных навыков.
    """
    out = {}
    out['theory'] = generate_theory_for_topic_openai(topic_uid)
    out['examples'] = generate_examples_for_topic_openai(topic_uid, count=examples_count)
    skills = [r.get('skill_uid') for r in load_jsonl(get_path('topic_skills.jsonl')) if r.get('topic_uid') == topic_uid]
    out['methods'] = [generate_methods_for_skill_openai(su, count=3) for su in skills]
    return {'ok': True, 'bundle': out}


def rebuild_subject_math_with_openai(section_title: str = 'Generated Section') -> Dict:
    """
    Пересобрать базу знаний для SUB-MATH:
    - гарантировать предмет/раздел/темы из skill_topics
    - нормализовать topic_skills
    - сгенерировать теорию/примеры/методы для каждой темы
    - выполнить нормализацию KB
    """
    subject_uid = 'SUB-MATH'
    boot = bootstrap_subject_from_skill_topics(subject_uid, section_title=section_title)
    topics = [t.get('uid') for t in load_jsonl(get_path('topics.jsonl')) if t.get('section_uid') in {s.get('uid') for s in load_jsonl(get_path('sections.jsonl')) if s.get('subject_uid') == subject_uid}]
    bundles = []
    for tu in topics:
        bundles.append(generate_topic_bundle_openai(tu, examples_count=5))
    normalize_kb()
    return {'ok': True, 'subjects_updated': 1, 'topics_processed': len(topics), 'bundles': bundles}


def truth_check_openai(text: str, context: Optional[str] = None) -> Dict:
    messages = [
        {'role': 'system', 'content': 'Проверь истинность утверждения. Ответь JSON с полями verdict (true/false) и confidence (0..1).'},
        {'role': 'user', 'content': json.dumps({'text': text, 'context': context or ''}, ensure_ascii=False)}
    ]
    res = openai_chat(messages)
    if not res.get('ok'):
        return res
    try:
        obj = json.loads(res.get('content','').strip())
        return {'ok': True, 'verdict': bool(obj.get('verdict')), 'confidence': float(obj.get('confidence', 0.0))}
    except Exception:
        return {'ok': False, 'error': 'parse failed', 'raw': res.get('content','')}


def normalize_kb() -> Dict:
    files = ['subjects.jsonl','sections.jsonl','topics.jsonl','skills.jsonl','methods.jsonl','skill_methods.jsonl','skill_topics.jsonl','topic_skills.jsonl','examples.jsonl','example_skills.jsonl','errors.jsonl','error_skills.jsonl','error_examples.jsonl','topic_goals.jsonl','topic_objectives.jsonl','lesson_steps.jsonl','theories.jsonl']
    stats: Dict[str, Dict] = {}
    for name in files:
        path = get_path(name)
        items = load_jsonl(path)
        rewrite_jsonl(path, items)
        stats[name] = {'count': len(items)}
    return {'ok': True, 'stats': stats}


def bootstrap_subject_from_skill_topics(subject_uid: str, section_title: str = 'Generated Section') -> Dict:
    subjects = load_jsonl(get_path('subjects.jsonl'))
    sections = load_jsonl(get_path('sections.jsonl'))
    topics = load_jsonl(get_path('topics.jsonl'))
    skill_topics = load_jsonl(get_path('skill_topics.jsonl'))
    # ensure subject
    subj = next((s for s in subjects if s.get('uid') == subject_uid), None)
    if subj is None:
        add_subject('Математика', uid=subject_uid)
        subjects = load_jsonl(get_path('subjects.jsonl'))
    # ensure section under subject
    sec = next((s for s in sections if s.get('subject_uid') == subject_uid and s.get('title') == section_title), None)
    if sec is None:
        sec_uid = make_uid('SEC', section_title)
        add_section(subject_uid, section_title, uid=sec_uid)
        sections = load_jsonl(get_path('sections.jsonl'))
        sec = next((s for s in sections if s.get('uid') == sec_uid), None)
    sec_uid = sec.get('uid')
    # create topics for each unique topic_uid from skill_topics if missing
    existing_topic_uids = {t.get('uid') for t in topics}
    new_topics = 0
    for rec in skill_topics:
        tuid = rec.get('topic_uid')
        if not tuid or tuid in existing_topic_uids:
            continue
        title = f"Автоген: {tuid}"
        add_topic(sec_uid, title, uid=tuid)
        existing_topic_uids.add(tuid)
        new_topics += 1
    # ensure skills exist for all skill_uids referenced by skill_topics
    skills = load_jsonl(get_path('skills.jsonl'))
    existing_skill_uids = {s.get('uid') for s in skills}
    new_skills = 0
    for rec in skill_topics:
        suid = rec.get('skill_uid')
        if not suid:
            continue
        if suid not in existing_skill_uids:
            add_skill(subject_uid, title=f"Autogen skill {suid}", uid=suid)
            existing_skill_uids.add(suid)
            new_skills += 1
    # mirror skill_topics into topic_skills to guarantee UI/Neo4j sync compatibility
    normalize_skill_topics_to_topic_skills()
    # generate default goals/objectives for created topics
    generate_goals_and_objectives()
    return {'ok': True, 'new_topics': new_topics, 'new_skills': new_skills}


if __name__ == '__main__':
    pass
