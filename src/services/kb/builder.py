import os
import json
import requests
import asyncio
from typing import Dict, List, Tuple, Optional
from .jsonl_io import load_jsonl, append_jsonl, rewrite_jsonl, get_path, tokens, make_uid, normalize_skill_topics_to_topic_skills, normalize_kb

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def openai_chat(messages: List[Dict], model: str = 'gpt-4o-mini', temperature: float = 0.2) -> Dict:
    def _load_env_file() -> None:
        env_path = os.path.join(os.path.dirname(os.path.dirname(BASE_DIR)), '.env')
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

async def openai_chat_async(messages: List[Dict], model: str = 'gpt-4o-mini', temperature: float = 0.2) -> Dict:
    def _load_env_file() -> None:
        env_path = os.path.join(os.path.dirname(os.path.dirname(BASE_DIR)), '.env')
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
    import httpx
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(url, headers=headers, json=payload)
    if r.status_code != 200:
        return {'ok': False, 'error': r.text}
    data = r.json()
    content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
    return {'ok': True, 'content': content}

def generate_goals_and_objectives() -> Dict:
    topics = load_jsonl(get_path('topics.jsonl'))
    existing_goals = load_jsonl(get_path('topic_goals.jsonl'))
    existing_objs = load_jsonl(get_path('topic_objectives.jsonl'))
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
            record = {'uid': f"GOAL-{tuid}-MASTER", 'topic_uid': tuid, 'title': f"Достичь уверенного решения: {title}"}
            append_jsonl(get_path('topic_goals.jsonl'), record)
            added_goals += 1
        if not by_topic_objs.get(tuid):
            obj_records = [
                {'uid': f"OBJ-{tuid}-BASICS", 'topic_uid': tuid, 'title': f"Освоить базовые понятия: {title}"},
                {'uid': f"OBJ-{tuid}-APPLY", 'topic_uid': tuid, 'title': f"Применять методы к задачам: {title}"},
            ]
            for rec in obj_records:
                append_jsonl(get_path('topic_objectives.jsonl'), rec)
                added_objs += 1
    return {'added_goals': added_goals, 'added_objectives': added_objs}

def autolink_skills_methods(max_links_per_skill: int = 2) -> Dict:
    skills = load_jsonl(get_path('skills.jsonl'))
    methods = load_jsonl(get_path('methods.jsonl'))
    existing = load_jsonl(get_path('skill_methods.jsonl'))
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
            record = {'skill_uid': suid, 'method_uid': muid, 'weight': 'primary' if score >= 0.2 else 'secondary', 'confidence': round(min(0.95, 0.5 + score), 3), 'is_auto_generated': True}
            append_jsonl(get_path('skill_methods.jsonl'), record)
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

def link_topic_prereq(target_topic_uid: str, prereq_topic_uid: str, weight: float = 1.0) -> Dict:
    append_jsonl(get_path('topic_prereqs.jsonl'), {'target_uid': target_topic_uid, 'prereq_uid': prereq_topic_uid, 'weight': float(weight)})
    return {'ok': True}

def add_content_unit(topic_uid: str, branch: str, unit_type: str, content: Dict, complexity: float = 0.0, uid: Optional[str] = None) -> Dict:
    uid = uid or make_uid('UNIT', f"{topic_uid}-{unit_type}")
    append_jsonl(get_path('content_units.jsonl'), {'uid': uid, 'topic_uid': topic_uid, 'branch': branch, 'type': unit_type, 'payload': content, 'complexity': float(complexity)})
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
    out = {}
    out['theory'] = generate_theory_for_topic_openai(topic_uid)
    out['examples'] = generate_examples_for_topic_openai(topic_uid, count=examples_count)
    skills = [r.get('skill_uid') for r in load_jsonl(get_path('topic_skills.jsonl')) if r.get('topic_uid') == topic_uid]
    out['methods'] = [generate_methods_for_skill_openai(su, count=3) for su in skills]
    return {'ok': True, 'bundle': out}

async def generate_sections_openai_async(subject_title: str, language: str, count: int = 5) -> List[str]:
    messages = [
        {'role': 'system', 'content': 'Сгенерируй разделы предмета, верни JSONL с полем title.'},
        {'role': 'user', 'content': json.dumps({'subject': subject_title, 'lang': language, 'count': count}, ensure_ascii=False)}
    ]
    res = await openai_chat_async(messages)
    if not res.get('ok'):
        return []
    titles: List[str] = []
    for l in [x for x in res.get('content', '').splitlines() if x.strip()]:
        try:
            obj = json.loads(l)
            t = (obj.get('title') or '').strip()
            if t:
                titles.append(t)
        except Exception:
            continue
    return titles[:count]

async def generate_topics_for_section_openai_async(section_title: str, language: str, count: int = 10) -> List[Dict]:
    messages = [
        {'role': 'system', 'content': 'Сгенерируй темы раздела, верни JSONL с полями title и description.'},
        {'role': 'user', 'content': json.dumps({'section': section_title, 'lang': language, 'count': count}, ensure_ascii=False)}
    ]
    res = await openai_chat_async(messages)
    if not res.get('ok'):
        return []
    items: List[Dict] = []
    for l in [x for x in res.get('content', '').splitlines() if x.strip()]:
        try:
            obj = json.loads(l)
            items.append({'title': obj.get('title',''), 'description': obj.get('description','')})
            if len(items) >= count:
                break
        except Exception:
            continue
    return items

async def generate_skills_for_topic_openai_async(topic_title: str, language: str, count: int = 3) -> List[Dict]:
    messages = [
        {'role': 'system', 'content': 'Сгенерируй навыки темы, верни JSONL с полями title и definition.'},
        {'role': 'user', 'content': json.dumps({'topic': topic_title, 'lang': language, 'count': count}, ensure_ascii=False)}
    ]
    res = await openai_chat_async(messages)
    if not res.get('ok'):
        return []
    items: List[Dict] = []
    for l in [x for x in res.get('content', '').splitlines() if x.strip()]:
        try:
            obj = json.loads(l)
            items.append({'title': obj.get('title',''), 'definition': obj.get('definition','')})
            if len(items) >= count:
                break
        except Exception:
            continue
    return items

async def generate_methods_for_skill_openai_async(skill_title: str, count: int = 2) -> List[Dict]:
    messages = [
        {'role': 'system', 'content': 'Предложи методы, верни JSONL с полями title и method_text.'},
        {'role': 'user', 'content': json.dumps({'skill': skill_title}, ensure_ascii=False)}
    ]
    res = await openai_chat_async(messages)
    if not res.get('ok'):
        return []
    items: List[Dict] = []
    for l in [x for x in res.get('content', '').splitlines() if x.strip()]:
        try:
            obj = json.loads(l)
            items.append({'title': obj.get('title',''), 'method_text': obj.get('method_text','')})
            if len(items) >= count:
                break
        except Exception:
            continue
    return items

async def generate_examples_for_topic_openai_async(topic_title: str, count: int = 3, difficulty: int = 3) -> List[Dict]:
    messages = [
        {'role': 'system', 'content': 'Сгенерируй учебные задачи, верни JSONL с полями title и statement.'},
        {'role': 'user', 'content': json.dumps({'topic': topic_title, 'count': count}, ensure_ascii=False)}
    ]
    res = await openai_chat_async(messages)
    if not res.get('ok'):
        return []
    items: List[Dict] = []
    for l in [x for x in res.get('content', '').splitlines() if x.strip()]:
        try:
            obj = json.loads(l)
            items.append({'title': obj.get('title',''), 'statement': obj.get('statement',''), 'difficulty': difficulty})
            if len(items) >= count:
                break
        except Exception:
            continue
    return items

async def generate_subject_openai_async(subject_uid: str, subject_title: str, language: str, sections_seed: Optional[List[str]] = None, topics_per_section: int = 6, skills_per_topic: int = 3, methods_per_skill: int = 2, examples_per_topic: int = 3, concurrency: int = 4) -> Dict:
    add_subject(subject_title, uid=subject_uid)
    sec_titles = sections_seed or await generate_sections_openai_async(subject_title, language, count=5)
    sec_uids: List[str] = []
    for st in sec_titles:
        sec = add_section(subject_uid, st)
        sec_uids.append(sec['uid'])
    topic_defs: List[Tuple[str, Dict]] = []
    for st, suid in zip(sec_titles, sec_uids):
        tdefs = await generate_topics_for_section_openai_async(st, language, count=topics_per_section)
        for td in tdefs:
            tuid = add_topic(suid, td['title'], td.get('description',''))['uid']
            topic_defs.append((tuid, td))
    sem = asyncio.Semaphore(concurrency)
    async def process_topic(tuid: str, td: Dict):
        async with sem:
            skills = await generate_skills_for_topic_openai_async(td['title'], language, count=skills_per_topic)
            for sk in skills:
                suid = add_skill(subject_uid, sk['title'], sk.get('definition',''))['uid']
                append_jsonl(get_path('topic_skills.jsonl'), {'topic_uid': tuid, 'skill_uid': suid, 'weight': 'core', 'confidence': 0.9})
                methods = await generate_methods_for_skill_openai_async(sk['title'], count=methods_per_skill)
                for m in methods:
                    muid = make_uid('MET', m['title'])
                    append_jsonl(get_path('methods.jsonl'), {'uid': muid, 'title': m['title'], 'method_text': m['method_text'], 'applicability_types': []})
                    link_skill_method(suid, muid, weight='primary', confidence=0.9, is_auto_generated=True)
            examples = await generate_examples_for_topic_openai_async(td['title'], count=examples_per_topic, difficulty=3)
            for ex in examples:
                ex_uid = make_uid('EX', ex['title'])
                append_jsonl(get_path('examples.jsonl'), {'uid': ex_uid, 'title': ex['title'], 'statement': ex['statement'], 'topic_uid': tuid, 'difficulty': ex['difficulty']})
    await asyncio.gather(*[process_topic(tu, td) for tu, td in topic_defs])
    generate_goals_and_objectives()
    normalize_kb()
    return {'ok': True, 'subjects': 1, 'sections': len(sec_uids), 'topics': len(topic_defs)}

def rebuild_subject_math_with_openai(section_title: str = 'Generated Section') -> Dict:
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

def bootstrap_subject_from_skill_topics(subject_uid: str, section_title: str = 'Generated Section') -> Dict:
    subjects = load_jsonl(get_path('subjects.jsonl'))
    sections = load_jsonl(get_path('sections.jsonl'))
    topics = load_jsonl(get_path('topics.jsonl'))
    skill_topics = load_jsonl(get_path('skill_topics.jsonl'))
    subj = next((s for s in subjects if s.get('uid') == subject_uid), None)
    if subj is None:
        add_subject('Математика', uid=subject_uid)
        subjects = load_jsonl(get_path('subjects.jsonl'))
    sec = next((s for s in sections if s.get('subject_uid') == subject_uid and s.get('title') == section_title), None)
    if sec is None:
        sec_uid = make_uid('SEC', section_title)
        add_section(subject_uid, section_title, uid=sec_uid)
        sections = load_jsonl(get_path('sections.jsonl'))
        sec = next((s for s in sections if s.get('uid') == sec_uid), None)
    sec_uid = sec.get('uid')
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
    normalize_skill_topics_to_topic_skills()
    generate_goals_and_objectives()
    return {'ok': True, 'new_topics': new_topics, 'new_skills': new_skills}
