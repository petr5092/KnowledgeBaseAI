import asyncio
import os
import sys
import json
import logging
import uuid
from typing import List, Dict, Optional, Tuple

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.services.kb.builder import (
    add_subject, add_section, add_subsection, add_topic_to_subsection,
    generate_subsections_openai_async, generate_topics_with_prereqs_openai_async,
    add_concept_unit, add_formula_unit, add_lesson_step,
    generate_skills_for_topic_openai_async, add_skill,
    generate_methods_for_skill_openai_async, add_method, link_skill_method,
    add_error, normalize_kb_dir, get_subject_dir, append_jsonl, get_path_in, make_uid,
    generate_examples_for_topic_openai_async
)
from app.services.proposal_service import create_draft_proposal
from app.schemas.proposal import Operation, OpType
from app.services.kb.jsonl_io import load_jsonl

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SEEDS = [
    "Arithmetic", 
    "Algebra", 
    "Geometry", 
    "Trigonometry", 
    "Calculus", 
    "Linear Algebra", 
    "Probability & Statistics"
]

async def generate_math_hierarchy(
    subject_uid: str,
    subject_title: str,
    language: str,
    sections_seed: List[str],
    topics_per_subsection: int = 6,
    skills_per_topic: int = 2,
    methods_per_skill: int = 1,
    examples_per_topic: int = 1,
    concurrency: int = 5
) -> str:
    logger.info(f"Starting generation for {subject_title} with seeds: {sections_seed}")
    
    lang = language.lower()
    slug = "mathematics"
    base_dir = get_subject_dir(slug, lang)
    logger.info(f"Writing to directory: {base_dir}")

    # 1. Subject
    add_subject(subject_title, uid=subject_uid)
    append_jsonl(get_path_in(base_dir, 'subjects.jsonl'), {'uid': subject_uid, 'title': subject_title, 'description': ''})

    # 2. Sections (from Seeds)
    for sec_title in sections_seed:
        logger.info(f"Processing Section: {sec_title}")
        sec = add_section(subject_uid, sec_title)
        append_jsonl(get_path_in(base_dir, 'sections.jsonl'), {'uid': sec['uid'], 'subject_uid': subject_uid, 'title': sec_title, 'description': ''})
        
        # 3. Subsections
        subs = await generate_subsections_openai_async(sec_title, language, count=3) # Force 3 subsections per section
        
        for sub_title in subs:
            logger.info(f"  Processing Subsection: {sub_title}")
            ss = add_subsection(sec['uid'], sub_title)
            append_jsonl(get_path_in(base_dir, 'subsections.jsonl'), {'uid': ss['uid'], 'section_uid': sec['uid'], 'title': sub_title, 'description': ''})
            
            # 4. Topics
            topics = await generate_topics_with_prereqs_openai_async(sub_title, language, count=topics_per_subsection)
            
            title_to_uid = {}
            topic_data_list = []

            # Create topics first
            for t in topics:
                tt = add_topic_to_subsection(ss['uid'], t.get('title',''))
                title_to_uid[t.get('title','')] = tt['uid']
                
                # Simple classification (simplified from builder.py)
                append_jsonl(get_path_in(base_dir, 'topics.jsonl'), {
                    'uid': tt['uid'], 
                    'section_uid': ss['uid'], 
                    'title': t.get('title',''), 
                    'description': '', 
                    'user_class_min': 5, 
                    'user_class_max': 10, 
                    'difficulty_band': 'standard'
                })
                topic_data_list.append((tt['uid'], t))

            # Prereqs
            for t in topics:
                tu = title_to_uid.get(t.get('title',''))
                for pre in (t.get('prereqs') or []):
                    pu = title_to_uid.get(pre)
                    if tu and pu:
                         append_jsonl(get_path_in(base_dir, 'topic_prereqs.jsonl'), {'target_uid': tu, 'prereq_uid': pu, 'weight': 1.0})

            # Enrich topics (Skills, Methods, Examples) - Parallelize
            sem = asyncio.Semaphore(concurrency)
            
            async def process_topic_enrichment(tuid: str, title: str):
                async with sem:
                    # Concept/Formula/Lesson
                    add_concept_unit(tuid, f"Ключевые понятия: {title}")
                    add_formula_unit(tuid, f"Ключевые формулы по теме: {title}")
                    add_lesson_step(tuid, 'tutor', f"Краткое объяснение: {title}")

                    # Skills
                    sks = await generate_skills_for_topic_openai_async(title, language, count=skills_per_topic)
                    for s in sks:
                        su = add_skill(subject_uid, s.get('title',''), s.get('definition',''))
                        append_jsonl(get_path_in(base_dir, 'skills.jsonl'), {'uid': su['uid'], 'subject_uid': subject_uid, 'title': s.get('title',''), 'definition': s.get('definition','')})
                        append_jsonl(get_path_in(base_dir, 'topic_skills.jsonl'), {'topic_uid': tuid, 'skill_uid': su['uid'], 'weight': 'linked', 'confidence': 0.9})
                        
                        # Methods
                        mets = await generate_methods_for_skill_openai_async(s.get('title',''), count=methods_per_skill)
                        for m in mets:
                            mu = add_method(m.get('title',''), m.get('method_text',''), [])
                            append_jsonl(get_path_in(base_dir, 'methods.jsonl'), {'uid': mu['uid'], 'title': m.get('title',''), 'method_text': m.get('method_text',''), 'applicability_types': []})
                            append_jsonl(get_path_in(base_dir, 'skill_methods.jsonl'), {'skill_uid': su['uid'], 'method_uid': mu['uid'], 'weight': 'linked', 'confidence': 0.9, 'is_auto_generated': True})
                    
                    # Examples
                    exs = await generate_examples_for_topic_openai_async(title, count=examples_per_topic, difficulty=3)
                    for ex in exs:
                        ex_uid = make_uid('EX', ex['title'])
                        append_jsonl(get_path_in(base_dir, 'examples.jsonl'), {'uid': ex_uid, 'title': ex['title'], 'statement': ex['statement'], 'topic_uid': tuid, 'difficulty': ex['difficulty']})
            
            await asyncio.gather(*[process_topic_enrichment(tuid, t.get('title','')) for tuid, t in topic_data_list])

    normalize_kb_dir(base_dir)
    return base_dir

async def convert_to_proposal(base_dir: str, tenant_id: str = "default"):
    logger.info("Converting generated files to Proposal...")
    ops: List[Operation] = []
    
    # Helper to add MERGE_NODE
    def add_node(uid, labels, props):
        ops.append(Operation(
            op_id=uuid.uuid4().hex,
            op_type=OpType.MERGE_NODE,
            temp_id=uid,
            properties_delta={**props, "uid": uid, "labels": labels},
            match_criteria={"uid": uid},
            evidence={"source": "big_bang_generation"}
        ))

    # Helper to add MERGE_REL
    def add_rel(start, end, type_name, props=None):
        ops.append(Operation(
            op_id=uuid.uuid4().hex,
            op_type=OpType.MERGE_REL,
            properties_delta={**(props or {}), "type": type_name},
            match_criteria={"start_uid": start, "end_uid": end, "type": type_name},
            evidence={"source": "big_bang_generation"}
        ))
    
    # Load and process files
    
    # Subjects
    for item in load_jsonl(get_path_in(base_dir, 'subjects.jsonl')):
        add_node(item['uid'], ["Subject"], {"title": item.get('title')})

    # Sections
    for item in load_jsonl(get_path_in(base_dir, 'sections.jsonl')):
        add_node(item['uid'], ["Section"], {"title": item.get('title')})
        add_rel(item['subject_uid'], item['uid'], "CONTAINS")

    # Subsections
    for item in load_jsonl(get_path_in(base_dir, 'subsections.jsonl')):
        add_node(item['uid'], ["Subsection"], {"title": item.get('title')})
        add_rel(item['section_uid'], item['uid'], "CONTAINS")

    # Topics
    for item in load_jsonl(get_path_in(base_dir, 'topics.jsonl')):
        add_node(item['uid'], ["Topic"], {
            "title": item.get('title'), 
            "user_class_min": item.get('user_class_min'),
            "user_class_max": item.get('user_class_max'),
            "difficulty_band": item.get('difficulty_band')
        })
        add_rel(item['section_uid'], item['uid'], "CONTAINS")

    # Skills
    for item in load_jsonl(get_path_in(base_dir, 'skills.jsonl')):
        add_node(item['uid'], ["Skill"], {"title": item.get('title'), "definition": item.get('definition')})

    # Topic -> Skills
    for item in load_jsonl(get_path_in(base_dir, 'topic_skills.jsonl')):
        add_rel(item['topic_uid'], item['skill_uid'], "USES_SKILL", {"weight": item.get('weight')})

    # Topic Prereqs
    for item in load_jsonl(get_path_in(base_dir, 'topic_prereqs.jsonl')):
        add_rel(item['target_uid'], item['prereq_uid'], "PREREQ", {"weight": item.get('weight')})
        
    # Methods
    for item in load_jsonl(get_path_in(base_dir, 'methods.jsonl')):
        add_node(item['uid'], ["Method"], {"title": item.get('title'), "method_text": item.get('method_text')})
        
    # Skill -> Methods
    for item in load_jsonl(get_path_in(base_dir, 'skill_methods.jsonl')):
        add_rel(item['skill_uid'], item['method_uid'], "BASED_ON", {"weight": item.get('weight')})

    # Examples
    for item in load_jsonl(get_path_in(base_dir, 'examples.jsonl')):
        add_node(item['uid'], ["Example"], {"title": item.get('title'), "statement": item.get('statement'), "difficulty": item.get('difficulty')})
        add_rel(item['topic_uid'], item['uid'], "HAS_EXAMPLE")

    logger.info(f"Generated {len(ops)} operations.")
    
    # Create Proposal
    prop = create_draft_proposal(tenant_id, 1, ops)
    logger.info(f"Proposal Created! ID: {prop.proposal_id}")
    return prop.proposal_id

async def main():
    base_dir = await generate_math_hierarchy(
        subject_uid="MATH-FULL-V1",
        subject_title="Mathematics",
        language="ru",
        sections_seed=SEEDS,
        topics_per_subsection=6,
        skills_per_topic=2,
        methods_per_skill=1,
        examples_per_topic=1,
        concurrency=5
    )
    
    proposal_id = await convert_to_proposal(base_dir)
    print(f"PROPOSAL_ID: {proposal_id}")

if __name__ == "__main__":
    asyncio.run(main())
