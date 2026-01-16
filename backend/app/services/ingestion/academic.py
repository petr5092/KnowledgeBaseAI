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
