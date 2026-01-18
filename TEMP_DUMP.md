# Полный дамп кодовой базы (Codebase Dump)

Этот файл содержит исходный код ключевых компонентов системы для детального анализа и отладки.
Собранные файлы охватывают логику Ingestion, валидации целостности (Integrity), работу с графом (Neo4j) и систему пропозалов.

**Содержание:**
1.  `backend/app/services/ingestion/academic.py` — Логика парсинга (подтверждает иерархию Subject -> Section -> Subsection -> Topic).
2.  `backend/app/services/ingestion/corporate.py` — Альтернативная стратегия ingestion.
3.  `backend/app/services/kb/builder.py` — Низкоуровневый билдер графа.
4.  `backend/app/services/graph/neo4j_repo.py` — Взаимодействие с БД Neo4j.
5.  `backend/app/services/proposal_service.py` — Логика обработки изменений (Proposals).
6.  `backend/app/schemas/proposal.py` — Pydantic модели операций.
7.  `backend/app/services/integrity.py` — Правила валидации графа (включая проверку иерархии).
8.  `backend/app/api/ingestion.py` — API эндпоинт генерации.
9.  `backend/app/api/admin_graph.py` — API администратора.
10. `backend/app/core/canonical.py` — Канонические константы (ALLOWED_LABELS).
11. `backend/app/services/kb/jsonl_io.py` — Работа с JSONL файлами и генерация UID.

---
# Full Codebase Dump for Debugging

--------------------------------------------------------------------------------
## File: backend/app/services/ingestion/academic.py
--------------------------------------------------------------------------------
```python
import json
import uuid
from typing import List, Any, Dict
from app.services.ingestion.interface import IngestionStrategy
from app.schemas.proposal import Operation, OpType
from app.services.kb.builder import openai_chat_async
from app.services.kb.jsonl_io import make_uid

class AcademicIngestionStrategy(IngestionStrategy):
    async def process(self, content: Any, **kwargs) -> List[Operation]:
        text = str(content)
        domain_context = kwargs.get("domain_context", "Academic Subject")
        
        # 1. Parse TOC via LLM
        prompt = f"""
        Context: {domain_context}.
        You are an expert curriculum designer.
        Parse the following Table of Contents (TOC) into a strict JSON structure.
        
        Input text:
        {text[:4000]}
        
        Output JSON format:
        {{
            "subject": "Subject Title",
            "sections": [
                {{
                    "title": "Section Title",
                    "subsections": [
                        {{
                            "title": "Subsection Title",
                            "topics": [
                                {{ "title": "Topic Title" }}
                            ]
                        }}
                    ]
                }}
            ]
        }}
        
        If the hierarchy is flat, infer logical grouping.
        Return ONLY valid JSON.
        """
        
        messages = [{"role": "user", "content": prompt}]
        res = await openai_chat_async(messages, temperature=0.1)
        if not res.get("ok"):
            raise ValueError(f"LLM Error: {res.get('error')}")
            
        try:
            # Clean up markdown code blocks if present
            raw = res.get("content", "").strip()
            if raw.startswith("```json"):
                raw = raw[7:]
            if raw.endswith("```"):
                raw = raw[:-3]
            data = json.loads(raw)
        except json.JSONDecodeError:
            raise ValueError("Failed to parse LLM response as JSON")
            
        # 2. Generate Operations
        ops: List[Operation] = []
        
        # Subject
        subj_title = data.get("subject", "Untitled Subject")
        subj_uid = make_uid("SUB", subj_title)
        
        ops.append(Operation(
            op_id=uuid.uuid4().hex,
            op_type=OpType.MERGE_NODE,
            temp_id=subj_uid,
            properties_delta={"uid": subj_uid, "title": subj_title, "labels": ["Subject"]},
            match_criteria={"uid": subj_uid},
            evidence={"source": "ingestion", "strategy": "academic"}
        ))
        
        for sec in data.get("sections", []):
            sec_title = sec.get("title")
            if not sec_title: continue
            sec_uid = make_uid("SEC", sec_title)
            
            # Create Section
            ops.append(Operation(
                op_id=uuid.uuid4().hex,
                op_type=OpType.MERGE_NODE,
                temp_id=sec_uid,
                properties_delta={"uid": sec_uid, "title": sec_title, "labels": ["Section"]},
                match_criteria={"uid": sec_uid},
                evidence={"source": "ingestion"}
            ))
            
            # Link Subject -> Section
            ops.append(Operation(
                op_id=uuid.uuid4().hex,
                op_type=OpType.MERGE_REL,
                properties_delta={"type": "CONTAINS"},
                match_criteria={"start_uid": subj_uid, "end_uid": sec_uid, "type": "CONTAINS"},
                evidence={"source": "ingestion"}
            ))
            
            for sub in sec.get("subsections", []):
                sub_title = sub.get("title")
                if not sub_title: continue
                sub_uid = make_uid("SUBSEC", sub_title)
                
                # Create Subsection
                ops.append(Operation(
                    op_id=uuid.uuid4().hex,
                    op_type=OpType.MERGE_NODE,
                    temp_id=sub_uid,
                    properties_delta={"uid": sub_uid, "title": sub_title, "labels": ["Subsection"]},
                    match_criteria={"uid": sub_uid},
                    evidence={"source": "ingestion"}
                ))
                
                # Link Section -> Subsection
                ops.append(Operation(
                    op_id=uuid.uuid4().hex,
                    op_type=OpType.MERGE_REL,
                    properties_delta={"type": "CONTAINS"},
                    match_criteria={"start_uid": sec_uid, "end_uid": sub_uid, "type": "CONTAINS"},
                    evidence={"source": "ingestion"}
                ))
                
                for top in sub.get("topics", []):
                    top_title = top.get("title")
                    if not top_title: continue
                    top_uid = make_uid("TOP", top_title)
                    
                    # Create Topic
                    ops.append(Operation(
                        op_id=uuid.uuid4().hex,
                        op_type=OpType.MERGE_NODE,
                        temp_id=top_uid,
                        properties_delta={"uid": top_uid, "title": top_title, "labels": ["Topic"]},
                        match_criteria={"uid": top_uid},
                        evidence={"source": "ingestion"}
                    ))
                    
                    # Link Subsection -> Topic
                    ops.append(Operation(
                        op_id=uuid.uuid4().hex,
                        op_type=OpType.MERGE_REL,
                        properties_delta={"type": "CONTAINS"},
                        match_criteria={"start_uid": sub_uid, "end_uid": top_uid, "type": "CONTAINS"},
                        evidence={"source": "ingestion"}
                    ))
                    
        return ops
```

--------------------------------------------------------------------------------
## File: backend/app/services/ingestion/corporate.py
--------------------------------------------------------------------------------
```python
import json
import uuid
from typing import List, Any, Dict
from app.services.ingestion.interface import IngestionStrategy
from app.schemas.proposal import Operation, OpType
from app.services.kb.builder import openai_chat_async
from app.services.kb.jsonl_io import make_uid

class CorporateIngestionStrategy(IngestionStrategy):
    async def process(self, content: Any, **kwargs) -> List[Operation]:
        text = str(content)
        domain_context = kwargs.get("domain_context", "Corporate Manual")
        
        # 1. Parse Text via LLM
        prompt = f"""
        Context: {domain_context}.
        You are a knowledge engineer analyzing a corporate manual/document.
        Analyze the text and extract a structured hierarchy.
        Also identify key "Skills" (actions/competencies) required for each Topic (instruction).
        
        Input text:
        {text[:6000]}
        
        Output JSON format:
        {{
            "subject": "Document Title",
            "sections": [
                {{
                    "title": "Chapter/Section Title",
                    "subsections": [
                        {{
                            "title": "Subchapter Title",
                            "topics": [
                                {{ 
                                    "title": "Topic/Instruction Title",
                                    "skills": ["Skill 1", "Skill 2"]
                                }}
                            ]
                        }}
                    ]
                }}
            ]
        }}
        
        Return ONLY valid JSON.
        """
        
        messages = [{"role": "user", "content": prompt}]
        res = await openai_chat_async(messages, temperature=0.1)
        if not res.get("ok"):
            raise ValueError(f"LLM Error: {res.get('error')}")
            
        try:
            raw = res.get("content", "").strip()
            if raw.startswith("```json"):
                raw = raw[7:]
            if raw.endswith("```"):
                raw = raw[:-3]
            data = json.loads(raw)
        except json.JSONDecodeError:
            raise ValueError("Failed to parse LLM response as JSON")
            
        # 2. Generate Operations
        ops: List[Operation] = []
        
        # Subject
        subj_title = data.get("subject", "Untitled Manual")
        subj_uid = make_uid("SUB", subj_title)
        
        ops.append(Operation(
            op_id=uuid.uuid4().hex,
            op_type=OpType.MERGE_NODE,
            temp_id=subj_uid,
            properties_delta={"uid": subj_uid, "title": subj_title, "labels": ["Subject"]},
            match_criteria={"uid": subj_uid},
            evidence={"source": "ingestion", "strategy": "corporate"}
        ))
        
        for sec in data.get("sections", []):
            sec_title = sec.get("title")
            if not sec_title: continue
            sec_uid = make_uid("SEC", sec_title)
            
            ops.append(Operation(
                op_id=uuid.uuid4().hex,
                op_type=OpType.MERGE_NODE,
                temp_id=sec_uid,
                properties_delta={"uid": sec_uid, "title": sec_title, "labels": ["Section"]},
                match_criteria={"uid": sec_uid},
                evidence={"source": "ingestion"}
            ))
            
            ops.append(Operation(
                op_id=uuid.uuid4().hex,
                op_type=OpType.MERGE_REL,
                properties_delta={"type": "CONTAINS"},
                match_criteria={"start_uid": subj_uid, "end_uid": sec_uid, "type": "CONTAINS"},
                evidence={"source": "ingestion"}
            ))
            
            for sub in sec.get("subsections", []):
                sub_title = sub.get("title")
                if not sub_title: continue
                sub_uid = make_uid("SUBSEC", sub_title)
                
                ops.append(Operation(
                    op_id=uuid.uuid4().hex,
                    op_type=OpType.MERGE_NODE,
                    temp_id=sub_uid,
                    properties_delta={"uid": sub_uid, "title": sub_title, "labels": ["Subsection"]},
                    match_criteria={"uid": sub_uid},
                    evidence={"source": "ingestion"}
                ))
                
                ops.append(Operation(
                    op_id=uuid.uuid4().hex,
                    op_type=OpType.MERGE_REL,
                    properties_delta={"type": "CONTAINS"},
                    match_criteria={"start_uid": sec_uid, "end_uid": sub_uid, "type": "CONTAINS"},
                    evidence={"source": "ingestion"}
                ))
                
                for top in sub.get("topics", []):
                    top_title = top.get("title")
                    if not top_title: continue
                    top_uid = make_uid("TOP", top_title)
                    
                    ops.append(Operation(
                        op_id=uuid.uuid4().hex,
                        op_type=OpType.MERGE_NODE,
                        temp_id=top_uid,
                        properties_delta={"uid": top_uid, "title": top_title, "labels": ["Topic"]},
                        match_criteria={"uid": top_uid},
                        evidence={"source": "ingestion"}
                    ))
                    
                    ops.append(Operation(
                        op_id=uuid.uuid4().hex,
                        op_type=OpType.MERGE_REL,
                        properties_delta={"type": "CONTAINS"},
                        match_criteria={"start_uid": sub_uid, "end_uid": top_uid, "type": "CONTAINS"},
                        evidence={"source": "ingestion"}
                    ))
                    
                    # Skills
                    for skill_title in top.get("skills", []):
                        if not skill_title: continue
                        skill_uid = make_uid("SKL", skill_title)
                        
                        # Create Skill
                        ops.append(Operation(
                            op_id=uuid.uuid4().hex,
                            op_type=OpType.MERGE_NODE,
                            temp_id=skill_uid,
                            properties_delta={"uid": skill_uid, "title": skill_title, "labels": ["Skill"]},
                            match_criteria={"uid": skill_uid},
                            evidence={"source": "ingestion"}
                        ))
                        
                        # Link Topic -> Skill
                        ops.append(Operation(
                            op_id=uuid.uuid4().hex,
                            op_type=OpType.MERGE_REL,
                            properties_delta={"type": "USES_SKILL"},
                            match_criteria={"start_uid": top_uid, "end_uid": skill_uid, "type": "USES_SKILL"},
                            evidence={"source": "ingestion"}
                        ))
                    
        return ops
```

--------------------------------------------------------------------------------
## File: backend/app/services/kb/builder.py
--------------------------------------------------------------------------------
```python
import os
import json
import requests
import asyncio
from typing import Dict, List, Tuple, Optional
from app.config.settings import settings
from .jsonl_io import load_jsonl, append_jsonl, rewrite_jsonl, get_path, get_subject_dir, get_path_in, normalize_kb_dir, tokens, make_uid, normalize_skill_topics_to_topic_skills, normalize_kb

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
    key = settings.openai_api_key.get_secret_value()
    if not key:
        _load_env_file()
        key = settings.openai_api_key.get_secret_value()
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
    key = settings.openai_api_key.get_secret_value()
    if not key:
        _load_env_file()
        key = settings.openai_api_key.get_secret_value()
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

def add_subsection(section_uid: str, title: str, description: str = '', uid: Optional[str] = None) -> Dict:
    uid = uid or make_uid('SUBSEC', title)
    append_jsonl(get_path('subsections.jsonl'), {'uid': uid, 'section_uid': section_uid, 'title': title, 'description': description})
    return {'uid': uid}

def add_topic(section_uid: str, title: str, description: str = '', uid: Optional[str] = None) -> Dict:
    uid = uid or make_uid('TOP', title)
    append_jsonl(get_path('topics.jsonl'), {'uid': uid, 'section_uid': section_uid, 'title': title, 'description': description})
    return {'uid': uid}

def add_topic_to_subsection(subsection_uid: str, title: str, description: str = '', uid: Optional[str] = None) -> Dict:
    uid = uid or make_uid('TOP', title)
    append_jsonl(get_path('topics.jsonl'), {'uid': uid, 'section_uid': subsection_uid, 'title': title, 'description': description})
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
    uid = make_uid('UNIT', f"{topic_uid}-lesson_step")
    payload = {'role': role, 'text': text}
    append_jsonl(get_path('content_units.jsonl'), {'uid': uid, 'topic_uid': topic_uid, 'branch': 'lesson', 'type': 'lesson_step', 'payload': payload, 'complexity': 0.1})
    return {'uid': uid}

def add_theory(topic_uid: str, text: str) -> Dict:
    uid = make_uid('UNIT', f"{topic_uid}-theory")
    payload = {'text': text}
    append_jsonl(get_path('content_units.jsonl'), {'uid': uid, 'topic_uid': topic_uid, 'branch': 'theory', 'type': 'theory', 'payload': payload, 'complexity': 0.2})
    return {'uid': uid}

def add_concept_unit(topic_uid: str, text: str) -> Dict:
    uid = make_uid('UNIT', f"{topic_uid}-concept")
    payload = {'text': text}
    append_jsonl(get_path('content_units.jsonl'), {'uid': uid, 'topic_uid': topic_uid, 'branch': 'theory', 'type': 'concept', 'payload': payload, 'complexity': 0.2})
    return {'uid': uid}

def add_formula_unit(topic_uid: str, text: str) -> Dict:
    uid = make_uid('UNIT', f"{topic_uid}-formula")
    payload = {'text': text}
    append_jsonl(get_path('content_units.jsonl'), {'uid': uid, 'topic_uid': topic_uid, 'branch': 'theory', 'type': 'formula', 'payload': payload, 'complexity': 0.3})
    return {'uid': uid}

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
    text = res.get('content', '')[:max_tokens*4]
    return add_theory(topic_uid, text)

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

def enrich_topic(subject_uid: str, topic_uid: str, title: str) -> Dict:
    content_units = load_jsonl(get_path('content_units.jsonl'))
    have_concept = any((u.get('topic_uid')==topic_uid and u.get('type')=='concept') for u in content_units)
    have_formula = any((u.get('topic_uid')==topic_uid and u.get('type')=='formula') for u in content_units)
    if not have_concept:
        add_concept_unit(topic_uid, f"Ключевые понятия: {title}")
    if not have_formula:
        add_formula_unit(topic_uid, f"Ключевые формулы по теме: {title}")
    add_lesson_step(topic_uid, 'tutor', f"Краткое объяснение: {title}")
    examples = load_jsonl(get_path('examples.jsonl'))
    if not any(e.get('topic_uid')==topic_uid for e in examples):
        add_example(f"Пример: {title}", "Краткая постановка задачи", topic_uid, difficulty=3)
    errors = load_jsonl(get_path('errors.jsonl'))
    if not any((ex.get('title')==f"Типовые ошибки: {title}") for ex in errors):
        err = add_error(f"Типовые ошибки: {title}", "Перечень типовых ошибок")
        link_error_example(err['uid'], next((e.get('uid') for e in load_jsonl(get_path('examples.jsonl')) if e.get('topic_uid')==topic_uid), None) or "")
    skills = load_jsonl(get_path('skills.jsonl'))
    s_titles = {s.get('title') for s in skills}
    s1 = f"Понимание {title}"
    s2 = f"Применение {title}"
    suids: List[str] = []
    if s1 not in s_titles:
        suids.append(add_skill(subject_uid, s1).get('uid'))
    else:
        suids.append(next(s.get('uid') for s in skills if s.get('title')==s1))
    if s2 not in s_titles:
        suids.append(add_skill(subject_uid, s2).get('uid'))
    else:
        suids.append(next(s.get('uid') for s in skills if s.get('title')==s2))
    for su in suids:
        link_topic_skill(topic_uid, su, weight='linked', confidence=0.9)
    return {'ok': True}

def enrich_all_topics() -> Dict:
    topics = load_jsonl(get_path('topics.jsonl'))
    subjects = load_jsonl(get_path('subjects.jsonl'))
    subj_uid = next((s.get('uid') for s in subjects if (s.get('title') or '').strip().upper()=='MATH'), None) or (subjects[0].get('uid') if subjects else '')
    for t in topics:
        tu = t.get('uid')
        title = t.get('title','')
        if tu and title:
            enrich_topic(subj_uid, tu, title)
    normalize_kb()
    return {'ok': True, 'topics': len(topics)}

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

async def generate_subsections_openai_async(section_title: str, language: str, count: int = 3) -> List[str]:
    messages = [
        {'role': 'system', 'content': 'Сгенерируй подразделы для раздела, верни JSONL с полем title.'},
        {'role': 'user', 'content': json.dumps({'section': section_title, 'lang': language, 'count': count}, ensure_ascii=False)}
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
            if len(titles) >= count:
                break
        except Exception:
            continue
    return titles

async def generate_topics_with_prereqs_openai_async(subsection_title: str, language: str, count: int = 10) -> List[Dict]:
    messages = [
        {'role': 'system', 'content': 'Сгенерируй темы подраздела, верни JSONL с полями title и prereqs (массив строк). Без циклов, только логические пререквизиты.'},
        {'role': 'user', 'content': json.dumps({'subsection': subsection_title, 'lang': language, 'count': count}, ensure_ascii=False)}
    ]
    res = await openai_chat_async(messages)
    if not res.get('ok'):
        return []
    items: List[Dict] = []
    for l in [x for x in res.get('content', '').splitlines() if x.strip()]:
        try:
            obj = json.loads(l)
            items.append({'title': obj.get('title',''), 'prereqs': obj.get('prereqs') or []})
            if len(items) >= count:
                break
        except Exception:
            continue
    return items

async def generate_subject_with_llm(subject_title: str, language: str, limits: Dict | None = None) -> Dict:
    limits = limits or {}
    sec_count = int(limits.get('sections', 8))
    topics_per_sub = int(limits.get('topics_per_subsection', 10))
    lang = language.lower()
    slug = (subject_title or 'subject').strip().lower().replace(' ', '-')
    base_dir = get_subject_dir(slug, lang)
    subj_uid = make_uid('SUB', subject_title)
    append_jsonl(get_path_in(base_dir, 'subjects.jsonl'), {'uid': subj_uid, 'title': subject_title, 'description': ''})
    sections = await generate_sections_openai_async(subject_title, language, count=sec_count)
    section_uids: List[str] = []
    for sec_title in sections:
        sec = add_section(subj_uid, sec_title)
        append_jsonl(get_path_in(base_dir, 'sections.jsonl'), {'uid': sec['uid'], 'subject_uid': subj_uid, 'title': sec_title, 'description': ''})
        section_uids.append(sec['uid'])
        subs = await generate_subsections_openai_async(sec_title, language, count=3)
        for sub_title in subs:
            ss = add_subsection(sec['uid'], sub_title)
            append_jsonl(get_path_in(base_dir, 'subsections.jsonl'), {'uid': ss['uid'], 'section_uid': sec['uid'], 'title': sub_title, 'description': ''})
            topics = await generate_topics_with_prereqs_openai_async(sub_title, language, count=topics_per_sub)
            title_to_uid: Dict[str, str] = {}
            def _classify(sub_title: str, topic_title: str) -> Dict:
                st = (sub_title or '').lower()
                tt = (topic_title or '').lower()
                def rng(a,b): return {'user_class_min':a,'user_class_max':b}
                if 'логик' in st or 'logic' in st: d=rng(5,7); band='foundation'
                elif 'множе' in st or 'set' in st: d=rng(6,8); band='foundation'
                elif 'числ' in st or 'number' in st: d=rng(6,8); band='basic'
                elif 'арифм' in st or 'arith' in st: d=rng(6,8); band='basic'
                elif 'алгебр' in st or 'algebra' in st: d=rng(7,9); band='core'
                elif 'функ' in st or 'function' in st: d=rng(8,10); band='core'
                elif 'геом' in st or 'geometry' in st: d=rng(6,9); band='core'
                elif 'координ' in st or 'analytic' in st: d=rng(8,11); band='advanced'
                elif 'тригон' in st or 'trig' in st: d=rng(8,11); band='advanced'
                elif 'комбин' in st or 'вероят' in st or 'prob' in st: d=rng(7,10); band='advanced'
                elif 'стат' in st or 'stat' in st: d=rng(7,10); band='advanced'
                elif 'линейн' in st or 'матриц' in st or 'вектор' in st or 'linear' in st: d=rng(9,11); band='advanced'
                elif 'анализ' in st or 'предел' in st or 'производ' in st or 'интеграл' in st or 'calculus' in st: d=rng(10,11); band='advanced'
                elif 'дискрет' in st or 'граф' in st or 'discrete' in st: d=rng(9,11); band='advanced'
                else: d=rng(7,10); band='standard'
                return {'user_class_min': d['user_class_min'], 'user_class_max': d['user_class_max'], 'difficulty_band': band}
            for t in topics:
                tt = add_topic_to_subsection(ss['uid'], t.get('title',''))
                title_to_uid[t.get('title','')] = tt['uid']
                cls = _classify(sub_title, t.get('title',''))
                append_jsonl(get_path_in(base_dir, 'topics.jsonl'), {'uid': tt['uid'], 'section_uid': ss['uid'], 'title': t.get('title',''), 'description': '', 'user_class_min': cls['user_class_min'], 'user_class_max': cls['user_class_max'], 'difficulty_band': cls['difficulty_band']})
            edges: List[Tuple[str,str]] = []
            for t in topics:
                tu = title_to_uid.get(t.get('title',''))
                for pre in (t.get('prereqs') or []):
                    pu = title_to_uid.get(pre)
                    if tu and pu:
                        edges.append((tu, pu))
            # DAG check with pruning
            adj: Dict[str, List[str]] = {}
            for a, b in edges:
                adj.setdefault(a, []).append(b)
            visited: Dict[str, int] = {}
            def _dfs(u: str) -> bool:
                visited[u] = 1
                for v in adj.get(u, []):
                    if visited.get(v, 0) == 1:
                        return False
                    if visited.get(v, 0) == 0:
                        if not _dfs(v):
                            return False
                visited[u] = 2
                return True
            good: List[Tuple[str,str]] = []
            for a, b in edges:
                for k in list(visited.keys()):
                    visited[k] = 0
                adj.setdefault(a, [])
                if b not in adj[a]:
                    adj[a].append(b)
                ok = True
                for node in title_to_uid.values():
                    if visited.get(node, 0) == 0:
                        if not _dfs(node):
                            ok = False
                            break
                if ok:
                    good.append((a, b))
                adj[a].remove(b)
            for a, b in good:
                append_jsonl(get_path_in(base_dir, 'topic_prereqs.jsonl'), {'target_uid': a, 'prereq_uid': b, 'weight': 1.0})
            # Enrichment via LLM (theory/examples) and simple scaffold for units/skills/methods/errors
            for title, tuid in title_to_uid.items():
                # Theory
                th = generate_theory_for_topic_openai(tuid, max_tokens=600)
                # Examples
                generate_examples_for_topic_openai(tuid, count=3, difficulty=3)
                # Concept/formula/lesson_step (scaffold without LLM texts)
                add_concept_unit(tuid, f"Ключевые понятия: {title}")
                add_formula_unit(tuid, f"Ключевые формулы по теме: {title}")
                add_lesson_step(tuid, 'tutor', f"Краткое объяснение: {title}")
                # Skills/methods (LLM)
                sks = await generate_skills_for_topic_openai_async(title, language, count=2)
                skill_uids: List[str] = []
                for s in sks:
                    su = add_skill(subj_uid, s.get('title',''), s.get('definition',''))
                    skill_uids.append(su['uid'])
                    append_jsonl(get_path_in(base_dir, 'skills.jsonl'), {'uid': su['uid'], 'subject_uid': subj_uid, 'title': s.get('title',''), 'definition': s.get('definition','')})
                    append_jsonl(get_path_in(base_dir, 'topic_skills.jsonl'), {'topic_uid': tuid, 'skill_uid': su['uid'], 'weight': 'linked', 'confidence': 0.9})
                    mets = await generate_methods_for_skill_openai_async(s.get('title',''), count=2)
                    for m in mets:
                        mu = add_method(m.get('title',''), m.get('method_text',''), [])
                        append_jsonl(get_path_in(base_dir, 'methods.jsonl'), {'uid': mu['uid'], 'title': m.get('title',''), 'method_text': m.get('method_text',''), 'applicability_types': []})
                        append_jsonl(get_path_in(base_dir, 'skill_methods.jsonl'), {'skill_uid': su['uid'], 'method_uid': mu['uid'], 'weight': 'linked', 'confidence': 0.9, 'is_auto_generated': True})
                # Errors
                err = add_error(f"Типовые ошибки: {title}", "Перечень типовых ошибок")
                append_jsonl(get_path_in(base_dir, 'errors.jsonl'), {'uid': err['uid'], 'title': f"Типовые ошибки: {title}", 'error_text': "Перечень типовых ошибок", 'triggers': []})
    normalize_kb_dir(base_dir)
    return {'ok': True, 'base_dir': base_dir}

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

async def generate_subject_openai_async(subject_uid: str, subject_title: str, language: str, domain_context: str = "Academic Subject", sections_seed: Optional[List[str]] = None, topics_per_section: int = 6, skills_per_topic: int = 3, methods_per_skill: int = 2, examples_per_topic: int = 3, concurrency: int = 4) -> Dict:
    add_subject(subject_title, uid=subject_uid)
    sec_titles = sections_seed or await generate_sections_openai_async(subject_title, language, domain_context=domain_context, count=5)
    sec_uids: List[str] = []
    for st in sec_titles:
        sec = add_section(subject_uid, st)
        sec_uids.append(sec['uid'])
    topic_defs: List[Tuple[str, Dict]] = []
    for st, suid in zip(sec_titles, sec_uids):
        tdefs = await generate_topics_for_section_openai_async(st, language, domain_context=domain_context, count=topics_per_section)
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

def bootstrap_subject_from_skill_topics(subject_uid: str, subject_title: str = 'Subject', section_title: str = 'Generated Section') -> Dict:
    subjects = load_jsonl(get_path('subjects.jsonl'))
    sections = load_jsonl(get_path('sections.jsonl'))
    topics = load_jsonl(get_path('topics.jsonl'))
    skill_topics = load_jsonl(get_path('skill_topics.jsonl'))
    subj = next((s for s in subjects if s.get('uid') == subject_uid), None)
    if subj is None:
        add_subject(subject_title, uid=subject_uid)
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
```

--------------------------------------------------------------------------------
## File: backend/app/services/graph/neo4j_repo.py
--------------------------------------------------------------------------------
```python
import time
from typing import List, Dict, Tuple, Callable, Any, Optional
from neo4j import GraphDatabase
from app.config.settings import settings
from app.core.correlation import get_correlation_id
from app.core.logging import logger


def get_driver():
    uri = settings.neo4j_uri
    user = settings.neo4j_user
    password = settings.neo4j_password.get_secret_value()
    if not (uri and user and password):
        raise RuntimeError('Missing Neo4j connection environment variables')
    return GraphDatabase.driver(uri, auth=(user, password))

class Neo4jRepo:
    def __init__(self, uri: Optional[str] = None, user: Optional[str] = None, password: Optional[str] = None, max_retries: int = 3, backoff_sec: float = 0.8):
        self.uri = uri or settings.neo4j_uri
        # Force localhost if neo4j hostname fails
        if 'neo4j:7687' in self.uri:
            import socket
            try:
                socket.gethostbyname('neo4j')
            except:
                self.uri = self.uri.replace('neo4j:7687', 'localhost:7687')
        
        self.user = user or settings.neo4j_user
        self.password = password or settings.neo4j_password.get_secret_value()
        if not self.uri or not self.user or not self.password:
            raise RuntimeError('Missing Neo4j connection environment variables')
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        self.max_retries = max_retries
        self.backoff_sec = backoff_sec

    def close(self):
        self.driver.close()

    def _retry(self, fn: Callable[[Any], Any]) -> Any:
        attempt = 0
        last_exc = None
        while attempt < self.max_retries:
            try:
                with self.driver.session() as session:
                    return fn(session)
            except Exception as e:
                last_exc = e
                attempt += 1
                time.sleep(self.backoff_sec * attempt)
        raise last_exc

    def write(self, query: str, params: Dict | None = None) -> None:
        def _fn(session):
            cid = get_correlation_id() or ""
            logger.info("neo4j_write", correlation_id=cid)
            session.execute_write(lambda tx: tx.run(query, **(params or {})))
        return self._retry(_fn)

    def read(self, query: str, params: Dict | None = None) -> List[Dict]:
        def _fn(session):
            def reader(tx):
                cid = get_correlation_id() or ""
                logger.info("neo4j_read", correlation_id=cid)
                res = tx.run(query, **(params or {}))
                return [dict(r) for r in res]
            return session.execute_read(reader)
        return self._retry(_fn)

    def _chunks(self, rows: List[Dict], size: int) -> List[List[Dict]]:
        return [rows[i:i+size] for i in range(0, len(rows), size)]

    def write_unwind(self, query: str, rows: List[Dict], chunk_size: int = 500) -> None:
        if not rows:
            return
        for chunk in self._chunks(rows, chunk_size):
            def _fn(session):
                cid = get_correlation_id() or ""
                logger.info("neo4j_write_unwind", correlation_id=cid, rows=len(chunk))
                session.execute_write(lambda tx: tx.run(query, rows=chunk))
            self._retry(_fn)

def read_graph(subject_uid: str | None = None, tenant_id: str | None = None) -> Tuple[List[Dict], List[Dict]]:
    drv = get_driver()
    nodes: List[Dict] = []
    edges: List[Dict] = []
    s = drv.session()
    try:
        query = (
            "MATCH (s:Subject) "
            "WHERE ($tid IS NULL OR s.tenant_id = $tid) "
            "WITH collect(s) AS subs "
            "MATCH (a)-[r]->(b) "
            "WHERE ($tid IS NULL OR a.tenant_id = $tid) AND ($tid IS NULL OR b.tenant_id = $tid) "
            "RETURN collect({id:id(a), uid:coalesce(a.uid,''), label:coalesce(a.title,''), labels:labels(a)}) AS ns, "
            "       collect({source:id(a), target:id(b), rel:type(r)}) AS es"
        )
        res = s.run(query, {"tid": tenant_id}).single()
        ns = res["ns"] if res else []
        es = res["es"] if res else []
        nodes = [{"id": n["id"], "uid": n.get("uid"), "label": n.get("label"), "labels": n.get("labels", [])} for n in ns]
        edges = [{"from": e.get("source"), "to": e.get("target"), "type": e.get("rel")} for e in es]
    finally:
        try:
            s.close()
        except Exception:
            ...
    drv.close()
    return nodes, edges

def relation_context(from_uid: str, to_uid: str, tenant_id: str | None = None) -> Dict:
    drv = get_driver()
    ctx: Dict = {}
    s = drv.session()
    try:
        res = s.run(
            (
                "MATCH (a {uid:$from})-[r]->(b {uid:$to}) "
                "WHERE ($tid IS NULL OR (a.tenant_id = $tid AND b.tenant_id = $tid)) "
                "RETURN type(r) AS rel, properties(r) AS props, a.title AS a_title, b.title AS b_title"
            ), {"from": from_uid, "to": to_uid, "tid": tenant_id}
        ).single()
        if res:
            ctx = {"rel": res["rel"], "props": res["props"], "from_title": res["a_title"], "to_title": res["b_title"]}
    finally:
        try:
            s.close()
        except Exception:
            ...
    drv.close()
    return ctx

def neighbors(center_uid: str, depth: int = 1, tenant_id: str | None = None) -> Tuple[List[Dict], List[Dict]]:
    drv = get_driver()
    nodes: List[Dict] = []
    edges: List[Dict] = []
    depth = max(0, min(int(depth), 6))
    s = drv.session()
    try:
        query = (
            "MATCH p=(c {uid:$uid})-[*0.." + str(depth) + "]-(n) "
            "WHERE ($tid IS NULL OR (c.tenant_id = $tid AND all(x in nodes(p) WHERE x.tenant_id = $tid))) "
            "RETURN collect(DISTINCT n) AS ns, collect(DISTINCT relationships(p)) AS rs"
        )
        res = s.run(query, {"uid": center_uid, "tid": tenant_id})
        row = None
        try:
            row = res.single()
        except Exception:
            try:
                row = next(iter(res))
            except Exception:
                row = None
        ns = row["ns"] if row else []
        rs = row["rs"] if row else []
        seen = set()
        for n in ns:
            nid = getattr(n, "element_id", None) or n.id
            if nid in seen:
                continue
            seen.add(nid)
            # kind - это первая метка (например, Topic, Subject)
            kind = list(n.labels)[0] if n.labels else "Unknown"
            nodes.append({
                "id": nid, 
                "uid": n.get("uid"), 
                "name": n.get("name"), 
                "title": n.get("title"),
                "kind": kind,            # Добавили kind
                "labels": list(n.labels)
            })
        added = set()
        for rels in rs:
            for r in rels:
                key = (r.start_node["uid"], r.end_node["uid"], r.type)
                if key in added:
                    continue
                added.add(key)
                edges.append({
                    "source": r.start_node["uid"], # Было from
                    "target": r.end_node["uid"],   # Было to
                    "kind": r.type,                # Было type
                    "weight": r.get("weight", 1.0)
                })
    finally:
        try:
            s.close()
        except Exception:
            ...
    drv.close()
    return nodes, edges

def node_by_uid(uid: str, tenant_id: str) -> Dict:
    drv = get_driver()
    data: Dict = {}
    s = drv.session()
    try:
        rows = s.run(
            "MATCH (n) WHERE n.uid=$uid AND (n.tenant_id=$tid OR n.tenant_id IS NULL) "
            "RETURN properties(n) AS p, labels(n) AS labels ORDER BY coalesce(n.created_at,'') DESC LIMIT 1",
            {"uid": uid, "tid": tenant_id}
        ).data()
        if rows:
            r0 = rows[0]
            if r0.get("p"):
                data = dict(r0["p"])
                data["labels"] = r0.get("labels", [])
            if data and not data.get("name"):
                nm = data.get("title")
                if nm:
                    data["name"] = nm
        if not data:
            rows2 = s.run(
                "MATCH (n) WHERE n.uid=$uid RETURN properties(n) AS p, labels(n) AS labels ORDER BY coalesce(n.created_at,'') DESC LIMIT 1",
                {"uid": uid}
            ).data()
            if rows2:
                r2 = rows2[0]
                if r2.get("p"):
                    data = dict(r2["p"])
                    data["labels"] = r2.get("labels", [])
        if not data:
            rows3 = s.run("MATCH (n {uid:$uid}) RETURN properties(n) AS p, labels(n) AS labels ORDER BY coalesce(n.created_at,'') DESC LIMIT 1", {"uid": uid}).data()
            if rows3:
                r3 = rows3[0]
                if r3.get("p"):
                    data = dict(r3["p"])
                    data["labels"] = r3.get("labels", [])
    finally:
        try:
            s.close()
        except Exception:
            ...
    drv.close()
    if not data:
        try:
            drv2 = get_driver()
            s2 = drv2.session()
            try:
                rows = s2.run("MATCH (n {uid:$uid}) RETURN properties(n) AS p, labels(n) AS labels LIMIT 1", {"uid": uid}).data()
                if rows:
                    r = rows[0]
                    if r.get("p"):
                        data = dict(r["p"])
                        data["labels"] = r.get("labels", [])
            finally:
                try:
                    s2.close()
                except Exception:
                    ...
        finally:
            try:
                drv2.close()
            except Exception:
                ...
    if data and not data.get("name"):
        try:
            drv3 = get_driver()
            s3 = drv3.session()
            try:
                rows = s3.run("MATCH (n {uid:$uid}) RETURN coalesce(n.name,n.title) AS nm LIMIT 1", {"uid": uid}).data()
                if rows and rows[0].get("nm"):
                    data["name"] = rows[0]["nm"]
            finally:
                try:
                    s3.close()
                except Exception:
                    ...
        finally:
            try:
                drv3.close()
            except Exception:
                ...
    if not data:
        data = {"uid": uid, "lifecycle_status": "ACTIVE", "labels": ["Concept"]}
    else:
        if not data.get("lifecycle_status"):
            data["lifecycle_status"] = "ACTIVE"
        if not data.get("created_at"):
            from datetime import datetime
            data["created_at"] = datetime.utcnow().isoformat()
        if not data.get("labels"):
            data["labels"] = ["Concept"]
    if "created_at" not in data or not data.get("created_at"):
        from datetime import datetime
        data["created_at"] = datetime.utcnow().isoformat()
    return data

def relation_by_pair(from_uid: str, to_uid: str, typ: str, tenant_id: str) -> Dict:
    drv = get_driver()
    data: Dict = {}
    s = drv.session()
    try:
        res = s.run(
            f"MATCH (a {{uid:$fu, tenant_id:$tid}})-[r:{typ}]->(b {{uid:$tu, tenant_id:$tid}}) RETURN properties(r) AS p",
            {"fu": from_uid, "tu": to_uid, "tid": tenant_id},
        )
        row = None
        try:
            row = res.single()
        except Exception:
            try:
                row = next(iter(res))
            except Exception:
                row = None
        if row:
            try:
                data = dict(row["p"])
            except Exception:
                ...
    finally:
        try:
            s.close()
        except Exception:
            ...
    drv.close()
    return data

def get_node_details(uid: str, tenant_id: str | None = None) -> Dict:
    drv = get_driver()
    data = {}
    s = drv.session()
    try:
        # Получаем свойства узла
        res = s.run("MATCH (n {uid:$uid}) WHERE ($tid IS NULL OR n.tenant_id = $tid) RETURN n", {"uid": uid, "tid": tenant_id})
        row = None
        try:
            row = res.single()
        except Exception:
            try:
                row = next(iter(res))
            except Exception:
                row = None
        if not row:
            return {}
        node = row["n"]
        data = dict(node)
        data["labels"] = list(node.labels)
        # Kind
        data["kind"] = list(node.labels)[0] if node.labels else "Unknown"
        
        # Получаем входящие связи
        in_res = s.run("MATCH (n {uid:$uid})<-[r]-(other) WHERE ($tid IS NULL OR (n.tenant_id = $tid AND other.tenant_id = $tid)) RETURN type(r) as rel, other.uid as uid, other.title as title", {"uid": uid, "tid": tenant_id})
        data["incoming"] = [{"rel": r["rel"], "uid": r["uid"], "title": r["title"]} for r in in_res]
        
        # Получаем исходящие связи
        out_res = s.run("MATCH (n {uid:$uid})-[r]->(other) WHERE ($tid IS NULL OR (n.tenant_id = $tid AND other.tenant_id = $tid)) RETURN type(r) as rel, other.uid as uid, other.title as title", {"uid": uid, "tid": tenant_id})
        data["outgoing"] = [{"rel": r["rel"], "uid": r["uid"], "title": r["title"]} for r in out_res]
    finally:
        try:
            s.close()
        except Exception:
            ...
    drv.close()
    return data
```

--------------------------------------------------------------------------------
## File: backend/app/services/proposal_service.py
--------------------------------------------------------------------------------
```python
import uuid
from typing import Dict, Any, List
from app.core.canonical import canonical_hash_from_json, normalize_text
from app.schemas.proposal import Operation, Proposal

EVIDENCE_REQUIRED_OPS = {"CREATE_NODE", "CREATE_REL"}

def validate_operations(ops: List[Operation]) -> None:
    for op in ops:
        if op.op_type in EVIDENCE_REQUIRED_OPS:
            if not op.evidence or not (op.evidence.get("source_chunk_id") and op.evidence.get("quote")):
                raise ValueError(f"evidence required for {op.op_type}")

def _deep_normalize(obj):
    if isinstance(obj, dict):
        return {k: _deep_normalize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_normalize(v) for v in obj]
    if isinstance(obj, str):
        return normalize_text(obj)
    return obj

def compute_checksum(ops: List[Operation]) -> str:
    ops_obj = [op.model_dump() for op in sorted(ops, key=lambda o: (o.op_type, o.target_id or o.temp_id or o.op_id))]
    ops_obj = _deep_normalize(ops_obj)
    return canonical_hash_from_json(ops_obj)

def create_draft_proposal(tenant_id: str, base_graph_version: int, ops: List[Operation]) -> Proposal:
    validate_operations(ops)
    checksum = compute_checksum(ops)
    pid = f"P-{uuid.uuid4().hex[:20]}"
    return Proposal(
        proposal_id=pid,
        tenant_id=tenant_id,
        base_graph_version=base_graph_version,
        proposal_checksum=checksum,
        operations=ops,
    )
```

--------------------------------------------------------------------------------
## File: backend/app/schemas/proposal.py
--------------------------------------------------------------------------------
```python
from enum import Enum
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

class ProposalStatus(str, Enum):
    DRAFT = "DRAFT"
    WAITING_REVIEW = "WAITING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CONFLICT = "CONFLICT"
    COMMITTING = "COMMITTING"
    DONE = "DONE"
    FAILED = "FAILED"

class OpType(str, Enum):
    CREATE_NODE = "CREATE_NODE"
    CREATE_REL = "CREATE_REL"
    MERGE_NODE = "MERGE_NODE"
    MERGE_REL = "MERGE_REL"
    UPDATE_NODE = "UPDATE_NODE"
    UPDATE_REL = "UPDATE_REL"
    DELETE_NODE = "DELETE_NODE"
    DELETE_REL = "DELETE_REL"

class Operation(BaseModel):
    op_id: str
    op_type: OpType
    target_id: Optional[str] = None
    temp_id: Optional[str] = None
    properties_delta: Dict[str, Any] = {}
    match_criteria: Dict[str, Any] = {}
    evidence: Dict[str, Any] = {}
    semantic_impact: str = Field(default="COSMETIC")
    requires_review: bool = False

class Proposal(BaseModel):
    proposal_id: str
    task_id: Optional[str] = None
    tenant_id: str
    base_graph_version: int = 0
    proposal_checksum: str
    status: ProposalStatus = ProposalStatus.DRAFT
    operations: List[Operation]
```

--------------------------------------------------------------------------------
## File: backend/app/services/integrity.py
--------------------------------------------------------------------------------
```python
from typing import Dict, List, Set, Tuple
import networkx as nx
import os
from app.core.canonical import ALLOWED_NODE_LABELS, ALLOWED_EDGE_TYPES

def check_canon_compliance(nodes: List[Dict], rels: List[Dict]) -> List[str]:
    violations = []
    for n in nodes:
        # Check node labels
        # Assuming n['type'] corresponds to the primary label
        typ = str(n.get("type") or "")
        if typ and typ not in ALLOWED_NODE_LABELS:
            violations.append(f"Node type not allowed: {typ} (uid={n.get('uid')})")
    
    for r in rels:
        typ = str(r.get("type") or "")
        if typ and typ not in ALLOWED_EDGE_TYPES:
            violations.append(f"Edge type not allowed: {typ} (uid={r.get('uid')})")
    return violations

def check_prereq_cycles(rels: List[Dict]) -> List[Tuple[str, str]]:
    """
    rels: list of {'type': 'PREREQ', 'from_uid': str, 'to_uid': str}
    """
    g = nx.DiGraph()
    for r in rels:
        if str(r.get("type")) != "PREREQ":
            continue
        a = str(r.get("from_uid"))
        b = str(r.get("to_uid"))
        if a and b:
            g.add_edge(a, b)
    cycles = list(nx.simple_cycles(g))
    violations: List[Tuple[str, str]] = []
    for cyc in cycles:
        if len(cyc) == 1:
            violations.append((cyc[0], cyc[0]))
        else:
            for i in range(len(cyc)):
                violations.append((cyc[i], cyc[(i + 1) % len(cyc)]))
    return violations

def check_orphan_skills(nodes: List[Dict], rels: List[Dict]) -> List[str]:
    """
    nodes: list of {'type': 'Skill', 'uid': str}
    rels: list of {'type': 'USES_SKILL', 'from_uid': str, 'to_uid': str}
    """
    skills: Set[str] = set()
    for n in nodes:
        if str(n.get("type")) == "Skill":
            uid = str(n.get("uid"))
            if uid:
                skills.add(uid)
    
    connected_skills: Set[str] = set()
    for r in rels:
        if str(r.get("type")) == "USES_SKILL":
            # Topic -> Skill
            to_uid = str(r.get("to_uid"))
            if to_uid:
                connected_skills.add(to_uid)
                
    orphans = sorted(list(skills.difference(connected_skills)))
    return orphans

def check_hierarchy_compliance(nodes: List[Dict], rels: List[Dict]) -> List[str]:
    """
    Ensures:
    - Topic has incoming CONTAINS from Subsection
    - Subsection has incoming CONTAINS from Section
    - Section has incoming CONTAINS from Subject
    
    Only checks nodes present in the list (if a node is created/merged, it must have a parent link in the same changeset OR be valid otherwise).
    Warning: This local check might be too strict for partial updates if not handled carefully.
    For now, we strictly check: IF a node of type T is in 'nodes', it MUST have an incoming CONTAINS in 'rels'.
    """
    violations = []
    
    # Index parents by child_uid
    parents: Dict[str, str] = {} # child -> parent
    for r in rels:
        if str(r.get("type")) == "CONTAINS":
            parents[str(r.get("to_uid"))] = str(r.get("from_uid"))
            
    for n in nodes:
        typ = str(n.get("type"))
        uid = str(n.get("uid"))
        if not uid: continue
        
        if typ == "Topic":
            if uid not in parents:
                violations.append(f"Topic {uid} missing parent Subsection")
        elif typ == "Subsection":
            if uid not in parents:
                violations.append(f"Subsection {uid} missing parent Section")
        elif typ == "Section":
            if uid not in parents:
                violations.append(f"Section {uid} missing parent Subject")
                
    return violations

def integrity_check_subgraph(nodes: List[Dict], rels: List[Dict]) -> Dict:
    canon_violations = check_canon_compliance(nodes, rels)
    cyc = check_prereq_cycles(rels)
    orphans = check_orphan_skills(nodes, rels)
    hierarchy = check_hierarchy_compliance(nodes, rels)
    
    ok = (len(cyc) == 0) and (len(orphans) == 0) and (len(canon_violations) == 0) and (len(hierarchy) == 0)
    return {
        "ok": ok, 
        "prereq_cycles": cyc, 
        "orphan_skills": orphans, 
        "canon_violations": canon_violations,
        "hierarchy_violations": hierarchy
    }

def check_skill_based_on_rules(nodes: List[Dict], rels: List[Dict], min_required: int = 1, max_allowed: int | None = None) -> Dict:
    skills: Set[str] = set()
    for n in nodes:
        if str(n.get("type")) == "Skill":
            uid = str(n.get("uid"))
            if uid:
                skills.add(uid)
    counts: Dict[str, int] = {s: 0 for s in skills}
    for r in rels:
        if str(r.get("type")) == "BASED_ON":
            fu = str(r.get("from_uid"))
            if fu in counts:
                counts[fu] = counts.get(fu, 0) + 1
    too_few = sorted([s for s, c in counts.items() if c < int(min_required)])
    too_many: List[str] = []
    if isinstance(max_allowed, int) and max_allowed > 0:
        too_many = sorted([s for s, c in counts.items() if c > max_allowed])
    ok = (len(too_few) == 0) and (len(too_many) == 0)
    return {"ok": ok, "too_few": too_few, "too_many": too_many}
```

--------------------------------------------------------------------------------
## File: backend/app/api/ingestion.py
--------------------------------------------------------------------------------
```python
from fastapi import APIRouter, HTTPException, Depends, Header, Security
from fastapi.security import HTTPBearer
from typing import Dict, Any, Literal
from pydantic import BaseModel
from app.services.ingestion.academic import AcademicIngestionStrategy
from app.services.ingestion.corporate import CorporateIngestionStrategy
from app.services.proposal_service import create_draft_proposal
from app.db.pg import get_conn, ensure_tables
from app.schemas.proposal import ProposalStatus
from app.api.common import StandardResponse
from app.core.context import get_tenant_id
import json

router = APIRouter(prefix="/v1/ingestion", tags=["Ingestion"], dependencies=[Security(HTTPBearer())])

def require_tenant() -> str:
    tid = get_tenant_id()
    if not tid:
        raise HTTPException(status_code=400, detail="tenant_id missing")
    return tid

class GenerateProposalInput(BaseModel):
    content: str
    strategy_type: Literal["academic", "corporate"]
    domain_context: str = "General"

@router.post(
    "/generate_proposal",
    summary="Generate Proposal from Content",
    description="Analyzes content and generates a proposal to update the Knowledge Graph.",
    response_model=StandardResponse,
)
async def generate_proposal(payload: GenerateProposalInput, tenant_id: str = Depends(require_tenant), x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    """
    Inputs:
      - content: Text or structured content
      - strategy_type: 'academic' (TOC based) or 'corporate' (Manual based)
      - domain_context: Context hint for LLM
      
    Returns:
      - proposal_id: Created proposal ID
    """
    strategy = None
    if payload.strategy_type == "academic":
        strategy = AcademicIngestionStrategy()
    elif payload.strategy_type == "corporate":
        strategy = CorporateIngestionStrategy()
    else:
        raise HTTPException(status_code=400, detail="Unknown strategy")
        
    try:
        ops = await strategy.process(payload.content, domain_context=payload.domain_context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")
        
    if not ops:
        raise HTTPException(status_code=400, detail="No operations generated")
        
    try:
        ensure_tables()
        # Create Proposal Object
        p = create_draft_proposal(tenant_id, 0, ops)
        
        # Save to DB
        conn = get_conn()
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO proposals (proposal_id, tenant_id, base_graph_version, proposal_checksum, status, operations_json) VALUES (%s,%s,%s,%s,%s,%s)",
                (
                    p.proposal_id,
                    p.tenant_id,
                    p.base_graph_version,
                    p.proposal_checksum,
                    ProposalStatus.DRAFT.value,
                    json.dumps(p.model_dump()["operations"]),
                ),
            )
        conn.close()
        
        return {"items": [{"proposal_id": p.proposal_id, "status": ProposalStatus.DRAFT.value, "ops_count": len(ops)}], "meta": {}}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save proposal: {str(e)}")
```

--------------------------------------------------------------------------------
## File: backend/app/api/admin_graph.py
--------------------------------------------------------------------------------
```python
from fastapi import APIRouter, Depends, HTTPException, Header, Security
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
import uuid
import json

from app.api.deps import require_admin
from app.services.graph.neo4j_repo import Neo4jRepo
from app.schemas.proposal import Proposal, Operation, ProposalStatus, OpType
from app.services.proposal_service import create_draft_proposal
from app.workers.commit import commit_proposal
from app.db.pg import get_conn, ensure_tables, get_graph_version, set_proposal_status

from app.core.canonical import ALLOWED_NODE_LABELS, ALLOWED_EDGE_TYPES

router = APIRouter(prefix="/v1/admin/graph", dependencies=[Depends(require_admin), Security(HTTPBearer())], tags=["Админка: граф"])



class NodeCreateInput(BaseModel):
    uid: str = Field(..., min_length=1, max_length=128)
    labels: List[str] = Field(..., min_length=1)
    props: Dict[str, Any] = Field(default_factory=dict)


class NodePatchInput(BaseModel):
    set: Dict[str, Any] = Field(default_factory=dict)
    unset: List[str] = Field(default_factory=list)


class EdgeCreateInput(BaseModel):
    edge_uid: Optional[str] = Field(default=None, min_length=1, max_length=128)
    from_uid: str = Field(..., min_length=1, max_length=128)
    to_uid: str = Field(..., min_length=1, max_length=128)
    type: str = Field(..., min_length=1, max_length=64)
    props: Dict[str, Any] = Field(default_factory=dict)


class EdgePatchInput(BaseModel):
    set: Dict[str, Any] = Field(default_factory=dict)
    unset: List[str] = Field(default_factory=list)


def _validate_labels(labels: List[str]) -> List[str]:
    clean = []
    for l in labels:
        if l not in ALLOWED_NODE_LABELS:
            raise HTTPException(status_code=400, detail=f"label not allowed: {l}")
        clean.append(l)
    return clean


def _validate_edge_type(t: str) -> str:
    if t not in ALLOWED_EDGE_TYPES:
        raise HTTPException(status_code=400, detail=f"edge type not allowed: {t}")
    return t


def _validate_props(props: Dict[str, Any]) -> Dict[str, Any]:
    if "uid" in props:
        raise HTTPException(status_code=400, detail="props.uid is not allowed")
    if len(props.keys()) > 50:
        raise HTTPException(status_code=400, detail="too many props")
    return props


async def _execute_admin_proposal(tenant_id: str, ops: List[Operation]) -> Dict:
    ensure_tables()
    base_ver = get_graph_version(tenant_id)
    
    # Bypass evidence validation for admin by providing dummy evidence if needed, 
    # but create_draft_proposal calls validate_operations which checks for evidence.
    # We should add dummy evidence.
    for op in ops:
        if not op.evidence:
            op.evidence = {"source": "admin_api", "user": "admin"}

    p = create_draft_proposal(tenant_id, base_ver, ops)
    
    conn = get_conn()
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO proposals (proposal_id, tenant_id, base_graph_version, proposal_checksum, status, operations_json) VALUES (%s,%s,%s,%s,%s,%s)",
            (
                p.proposal_id,
                p.tenant_id,
                p.base_graph_version,
                p.proposal_checksum,
                ProposalStatus.APPROVED.value, # Immediately APPROVED
                json.dumps(p.model_dump()["operations"]),
            ),
        )
    conn.close()
    
    # Commit immediately
    res = commit_proposal(p.proposal_id)
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res)
    
    return res


@router.post("/nodes", summary="Создать узел", description="Создает узел с указанными метками и свойствами (без изменения uid).")
async def create_node(payload: NodeCreateInput, x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    labels = _validate_labels(payload.labels)
    props = _validate_props(payload.props)

    # Optional: Check existence (read-only)
    repo = Neo4jRepo()
    try:
        exists = repo.read("MATCH (n {uid:$uid}) WHERE ($tid IS NULL OR n.tenant_id=$tid) RETURN count(n) AS c", {"uid": payload.uid, "tid": x_tenant_id})
        if exists and int(exists[0].get("c") or 0) > 0:
            raise HTTPException(status_code=409, detail="node uid already exists")
    finally:
        repo.close()

    op = Operation(
        op_id=f"OP-{uuid.uuid4().hex[:8]}",
        op_type=OpType.CREATE_NODE,
        target_id=payload.uid,
        properties_delta={**props, "type": labels[0], "uid": payload.uid}, # Assuming first label is primary type
        requires_review=False
    )
    
    await _execute_admin_proposal(x_tenant_id, [op])
    return {"uid": payload.uid}


@router.get("/nodes/{uid}", summary="Получить узел", description="Возвращает метки и свойства узла по UID.")
async def get_node(uid: str, x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    repo = Neo4jRepo()
    try:
        rows = repo.read("MATCH (n {uid:$uid}) WHERE ($tid IS NULL OR n.tenant_id=$tid) RETURN labels(n) AS labels, properties(n) AS props", {"uid": uid, "tid": x_tenant_id})
        if not rows:
            raise HTTPException(status_code=404, detail="node not found")
        props = rows[0].get("props") or {}
        props.pop("uid", None)
        return {"uid": uid, "labels": rows[0].get("labels") or [], "props": props}
    finally:
        repo.close()


@router.patch("/nodes/{uid}", summary="Изменить узел", description="Устанавливает/удаляет свойства узла. UID менять нельзя.")
async def patch_node(uid: str, payload: NodePatchInput, x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    if "uid" in payload.set or "uid" in payload.unset:
        raise HTTPException(status_code=400, detail="uid cannot be modified")

    repo = Neo4jRepo()
    try:
        rows = repo.read("MATCH (n {uid:$uid}) WHERE ($tid IS NULL OR n.tenant_id=$tid) RETURN count(n) AS c", {"uid": uid, "tid": x_tenant_id})
        if not rows or int(rows[0].get("c") or 0) == 0:
            raise HTTPException(status_code=404, detail="node not found")
    finally:
        repo.close()

    # Construct props for update
    # Note: UPDATE_NODE in commit.py uses SET n += props. It doesn't handle unset/REMOVE.
    # We might need to handle unset by setting to null? Neo4j treats null as remove property?
    # Yes, SET n.prop = null removes the property.
    
    props = _validate_props(payload.set)
    for k in payload.unset:
        props[k] = None
        
    op = Operation(
        op_id=f"OP-{uuid.uuid4().hex[:8]}",
        op_type=OpType.UPDATE_NODE,
        target_id=uid,
        properties_delta=props,
        requires_review=False
    )
    
    await _execute_admin_proposal(x_tenant_id, [op])
    return {"ok": True}


@router.delete("/nodes/{uid}", summary="Удалить узел", description="Удаляет узел.")
async def delete_node(uid: str, detach: bool = False, x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    repo = Neo4jRepo()
    try:
        rows = repo.read("MATCH (n {uid:$uid}) WHERE ($tid IS NULL OR n.tenant_id=$tid) RETURN count(n) AS c", {"uid": uid, "tid": x_tenant_id})
        if not rows or int(rows[0].get("c") or 0) == 0:
            raise HTTPException(status_code=404, detail="node not found")
            
        if not detach:
            rels = repo.read("MATCH (n {uid:$uid})-[r]-() WHERE ($tid IS NULL OR n.tenant_id=$tid) RETURN count(r) AS c", {"uid": uid, "tid": x_tenant_id})
            if rels and int(rels[0].get("c") or 0) > 0:
                raise HTTPException(status_code=409, detail="node has relationships; use detach=true")
    finally:
        repo.close()

    op = Operation(
        op_id=f"OP-{uuid.uuid4().hex[:8]}",
        op_type=OpType.DELETE_NODE,
        target_id=uid,
        properties_delta={"detach": detach},
        requires_review=False
    )
    
    await _execute_admin_proposal(x_tenant_id, [op])
    return {"ok": True}


@router.post("/edges", summary="Создать связь", description="Создает отношение между узлами.")
async def create_edge(payload: EdgeCreateInput, x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    if payload.from_uid == payload.to_uid:
        raise HTTPException(status_code=400, detail="self-loop is not allowed")

    rel_type = _validate_edge_type(payload.type)
    props = _validate_props(payload.props)

    repo = Neo4jRepo()
    try:
        ok = repo.read(
            "MATCH (a {uid:$from}), (b {uid:$to}) WHERE ($tid IS NULL OR (a.tenant_id=$tid AND b.tenant_id=$tid)) RETURN count(a) AS ca, count(b) AS cb",
            {"from": payload.from_uid, "to": payload.to_uid, "tid": x_tenant_id},
        )
        if not ok or int(ok[0].get("ca") or 0) == 0 or int(ok[0].get("cb") or 0) == 0:
            raise HTTPException(status_code=404, detail="from/to node not found")
    finally:
        repo.close()

    edge_uid = payload.edge_uid or f"E-{uuid.uuid4().hex[:16]}"
    
    op = Operation(
        op_id=f"OP-{uuid.uuid4().hex[:8]}",
        op_type=OpType.CREATE_REL,
        target_id=edge_uid,
        properties_delta={**props, "type": rel_type, "uid": edge_uid, "from_uid": payload.from_uid, "to_uid": payload.to_uid},
        requires_review=False
    )
    
    await _execute_admin_proposal(x_tenant_id, [op])
    return {"edge_uid": edge_uid}


@router.get("/edges/{edge_uid}", summary="Получить связь", description="Возвращает from/to, тип и свойства связи по ее UID.")
async def get_edge(edge_uid: str, x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    repo = Neo4jRepo()
    try:
        rows = repo.read(
            "MATCH (a)-[r {uid:$uid}]->(b) WHERE ($tid IS NULL OR (a.tenant_id=$tid AND b.tenant_id=$tid)) RETURN a.uid AS from_uid, b.uid AS to_uid, type(r) AS type, properties(r) AS props",
            {"uid": edge_uid, "tid": x_tenant_id},
        )
        if not rows:
            raise HTTPException(status_code=404, detail="edge not found")
        props = rows[0].get("props") or {}
        props.pop("uid", None)
        return {
            "edge_uid": edge_uid,
            "from_uid": rows[0].get("from_uid"),
            "to_uid": rows[0].get("to_uid"),
            "type": rows[0].get("type"),
            "props": props,
        }
    finally:
        repo.close()


@router.get("/edges", summary="Список связей по паре узлов", description="Возвращает список связей между двумя узлами.")
async def list_edges(from_uid: str, to_uid: str, type: Optional[str] = None, x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    repo = Neo4jRepo()
    try:
        if type:
            rel_type = _validate_edge_type(type)
            query = (
                f"MATCH (a {{uid:$from}})-[r:{rel_type}]->(b {{uid:$to}}) "
                f"WHERE ($tid IS NULL OR (a.tenant_id=$tid AND b.tenant_id=$tid)) "
                f"RETURN r.uid AS edge_uid, properties(r) AS props"
            )
        else:
            query = (
                "MATCH (a {uid:$from})-[r]->(b {uid:$to}) "
                "WHERE ($tid IS NULL OR (a.tenant_id=$tid AND b.tenant_id=$tid)) "
                "RETURN r.uid AS edge_uid, type(r) AS type, properties(r) AS props"
            )

        rows = repo.read(query, {"from": from_uid, "to": to_uid, "tid": x_tenant_id})
        items = []
        for r in rows:
            props = r.get("props") or {}
            props.pop("uid", None)
            items.append({"edge_uid": r.get("edge_uid"), "type": r.get("type") or type, "props": props})
        return {"items": items}
    finally:
        repo.close()


@router.patch("/edges/{edge_uid}", summary="Изменить связь", description="Устанавливает/удаляет свойства отношения.")
async def patch_edge(edge_uid: str, payload: EdgePatchInput, x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    if "uid" in payload.set or "uid" in payload.unset:
        raise HTTPException(status_code=400, detail="uid cannot be modified")

    repo = Neo4jRepo()
    try:
        # Check existence and get current type/nodes if needed, but for patch we might not need them strictly if we trust UID
        # However, to filter by tenant, we need to check if the edge belongs to the tenant nodes
        rows = repo.read("MATCH (a)-[r {uid:$uid}]->(b) WHERE ($tid IS NULL OR (a.tenant_id=$tid AND b.tenant_id=$tid)) RETURN count(r) AS c", {"uid": edge_uid, "tid": x_tenant_id})
        if not rows or int(rows[0].get("c") or 0) == 0:
            raise HTTPException(status_code=404, detail="edge not found")
    finally:
        repo.close()

    props = _validate_props(payload.set)
    for k in payload.unset:
        props[k] = None

    op = Operation(
        op_id=f"OP-{uuid.uuid4().hex[:8]}",
        op_type=OpType.UPDATE_REL,
        target_id=edge_uid,
        properties_delta=props,
        requires_review=False
    )
    
    await _execute_admin_proposal(x_tenant_id, [op])
    return {"ok": True}


@router.delete("/edges/{edge_uid}", summary="Удалить связь", description="Удаляет отношение по UID.")
async def delete_edge(edge_uid: str, x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    repo = Neo4jRepo()
    try:
        rows = repo.read("MATCH (a)-[r {uid:$uid}]->(b) WHERE ($tid IS NULL OR (a.tenant_id=$tid AND b.tenant_id=$tid)) RETURN count(r) AS c", {"uid": edge_uid, "tid": x_tenant_id})
        if not rows or int(rows[0].get("c") or 0) == 0:
            raise HTTPException(status_code=404, detail="edge not found")
    finally:
        repo.close()

    op = Operation(
        op_id=f"OP-{uuid.uuid4().hex[:8]}",
        op_type=OpType.DELETE_REL,
        target_id=edge_uid,
        properties_delta={},
        requires_review=False
    )
    
    await _execute_admin_proposal(x_tenant_id, [op])
    return {"ok": True}
```

--------------------------------------------------------------------------------
## File: backend/app/core/canonical.py
--------------------------------------------------------------------------------
```python
import json
import re
import unicodedata
from hashlib import sha256
from typing import Any

_WS_RE = re.compile(r"\s+")

def normalize_text(text: str) -> str:
    t = unicodedata.normalize("NFKC", text)
    t = t.strip()
    t = _WS_RE.sub(" ", t)
    return t

def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))

def hash_sha256(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return sha256(data).hexdigest()

def canonical_hash_from_text(text: str) -> str:
    return hash_sha256(normalize_text(text))

def canonical_hash_from_json(obj: Any) -> str:
    return hash_sha256(canonical_json(obj))

ALLOWED_NODE_LABELS = {
    "Subject", "Section", "Subsection", "Topic", "Skill", "Method",
    "Goal", "Objective", "Example", "Error", "ContentUnit",
    "Concept", "Formula", "TaskType"
}

ALLOWED_EDGE_TYPES = {
    "CONTAINS", "PREREQ", "USES_SKILL", "LINKED", "TARGETS",
    "HAS_EXAMPLE", "HAS_UNIT", "MEASURES", "BASED_ON"
}
```

--------------------------------------------------------------------------------
## File: backend/app/services/kb/jsonl_io.py
--------------------------------------------------------------------------------
```python
import os
import json
import re
import uuid
from typing import Dict, List, Tuple, Set, Optional
from app.utils.atomic_write import write_jsonl_atomic

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

def get_subject_dir(subject_slug: str, language: str) -> str:
    base = os.path.join(KB_DIR, language.lower(), subject_slug.lower())
    os.makedirs(base, exist_ok=True)
    return base

def get_path_in(base_dir: str, name: str) -> str:
    os.makedirs(base_dir, exist_ok=True)
    return os.path.join(base_dir, name)

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
    files = ['subjects.jsonl','sections.jsonl','subsections.jsonl','topics.jsonl','skills.jsonl','methods.jsonl','skill_methods.jsonl','skill_topics.jsonl','topic_skills.jsonl','content_units.jsonl','examples.jsonl','example_skills.jsonl','errors.jsonl','error_skills.jsonl','error_examples.jsonl','topic_goals.jsonl','topic_objectives.jsonl']
    stats: Dict[str, Dict] = {}
    for name in files:
        path = get_path(name)
        items = load_jsonl(path)
        rewrite_jsonl(path, items)
        stats[name] = {'count': len(items)}
    return {'ok': True, 'stats': stats}

def normalize_kb_dir(base_dir: str) -> Dict:
    files = ['subjects.jsonl','sections.jsonl','subsections.jsonl','topics.jsonl','skills.jsonl','methods.jsonl','skill_methods.jsonl','skill_topics.jsonl','topic_skills.jsonl','content_units.jsonl','examples.jsonl','example_skills.jsonl','errors.jsonl','error_skills.jsonl','error_examples.jsonl','topic_goals.jsonl','topic_objectives.jsonl']
    stats: Dict[str, Dict] = {}
    for name in files:
        path = get_path_in(base_dir, name)
        items = load_jsonl(path)
        rewrite_jsonl(path, items)
        stats[name] = {'count': len(items)}
    return {'ok': True, 'stats': stats}
```

--------------------------------------------------------------------------------
## File: backend/app/api/ingestion.py
--------------------------------------------------------------------------------
```python
from fastapi import APIRouter, HTTPException, Depends, Header, Security
from fastapi.security import HTTPBearer
from typing import Dict, Any, Literal
from pydantic import BaseModel
from app.services.ingestion.academic import AcademicIngestionStrategy
from app.services.ingestion.corporate import CorporateIngestionStrategy
from app.services.proposal_service import create_draft_proposal
from app.db.pg import get_conn, ensure_tables
from app.schemas.proposal import ProposalStatus
from app.api.common import StandardResponse
from app.core.context import get_tenant_id
import json

router = APIRouter(prefix="/v1/ingestion", tags=["Ingestion"], dependencies=[Security(HTTPBearer())])

def require_tenant() -> str:
    tid = get_tenant_id()
    if not tid:
        raise HTTPException(status_code=400, detail="tenant_id missing")
    return tid

class GenerateProposalInput(BaseModel):
    content: str
    strategy_type: Literal["academic", "corporate"]
    domain_context: str = "General"

@router.post(
    "/generate_proposal",
    summary="Generate Proposal from Content",
    description="Analyzes content and generates a proposal to update the Knowledge Graph.",
    response_model=StandardResponse,
)
async def generate_proposal(payload: GenerateProposalInput, tenant_id: str = Depends(require_tenant), x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    """
    Inputs:
      - content: Text or structured content
      - strategy_type: 'academic' (TOC based) or 'corporate' (Manual based)
      - domain_context: Context hint for LLM
      
    Returns:
      - proposal_id: Created proposal ID
    """
    strategy = None
    if payload.strategy_type == "academic":
        strategy = AcademicIngestionStrategy()
    elif payload.strategy_type == "corporate":
        strategy = CorporateIngestionStrategy()
    else:
        raise HTTPException(status_code=400, detail="Unknown strategy")
        
    try:
        ops = await strategy.process(payload.content, domain_context=payload.domain_context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")
        
    if not ops:
        raise HTTPException(status_code=400, detail="No operations generated")
        
    try:
        ensure_tables()
        # Create Proposal Object
        p = create_draft_proposal(tenant_id, 0, ops)
        
        # Save to DB
        conn = get_conn()
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO proposals (proposal_id, tenant_id, base_graph_version, proposal_checksum, status, operations_json) VALUES (%s,%s,%s,%s,%s,%s)",
                (
                    p.proposal_id,
                    p.tenant_id,
                    p.base_graph_version,
                    p.proposal_checksum,
                    ProposalStatus.DRAFT.value,
                    json.dumps(p.model_dump()["operations"]),
                ),
            )
        conn.close()
        
        return {"items": [{"proposal_id": p.proposal_id, "status": ProposalStatus.DRAFT.value, "ops_count": len(ops)}], "meta": {}}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save proposal: {str(e)}")
```
