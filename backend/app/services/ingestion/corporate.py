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
