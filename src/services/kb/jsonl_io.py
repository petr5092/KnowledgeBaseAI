import os
import json
import re
import uuid
from typing import Dict, List, Tuple, Set, Optional
from src.utils.atomic_write import write_jsonl_atomic

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KB_DIR = os.path.join(os.path.dirname(os.path.dirname(BASE_DIR)), 'kb')

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
    items = load_jsonl(filepath)
    items.append(record)
    def _validate(rec: Dict) -> None:
        if not isinstance(rec, dict):
            raise ValueError("record must be dict")
    write_jsonl_atomic(filepath, items, _validate)

def rewrite_jsonl(filepath: str, records: List[Dict]) -> None:
    def _validate(rec: Dict) -> None:
        if not isinstance(rec, dict):
            raise ValueError("record must be dict")
    write_jsonl_atomic(filepath, records, _validate)

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

def normalize_kb() -> Dict:
    files = ['subjects.jsonl','sections.jsonl','topics.jsonl','skills.jsonl','methods.jsonl','skill_methods.jsonl','skill_topics.jsonl','topic_skills.jsonl','examples.jsonl','example_skills.jsonl','errors.jsonl','error_skills.jsonl','error_examples.jsonl','topic_goals.jsonl','topic_objectives.jsonl','lesson_steps.jsonl','theories.jsonl']
    stats: Dict[str, Dict] = {}
    for name in files:
        path = get_path(name)
        items = load_jsonl(path)
        rewrite_jsonl(path, items)
        stats[name] = {'count': len(items)}
    return {'ok': True, 'stats': stats}

