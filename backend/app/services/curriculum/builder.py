import json
import uuid
from typing import Dict, List, Optional
from app.services.curriculum import repo
from app.services.graph.neo4j_repo import Neo4jRepo
from app.services.kb.builder import openai_chat_async

async def generate_curriculum_llm(goal: str, audience: str, subject_uids: Optional[List[str]] = None, language: str = "ru") -> Dict:
    """
    Generates a curriculum based on a goal using LLM to select from existing graph topics.
    """
    
    # 1. Fetch Candidates from Graph
    repo_graph = Neo4jRepo()
    try:
        if subject_uids:
            query = "MATCH (s:Subject)-[:CONTAINS*]->(t:Topic) WHERE s.uid IN $subs RETURN t.uid as uid, t.title as title, s.title as subject"
            rows = repo_graph.read(query, {"subs": subject_uids})
        else:
            query = "MATCH (t:Topic) RETURN t.uid as uid, t.title as title, 'Unknown' as subject LIMIT 500"
            rows = repo_graph.read(query)
    finally:
        repo_graph.close()
        
    if not rows:
        return {"ok": False, "error": "No topics found in graph"}
        
    candidates = [{"uid": r["uid"], "title": r["title"], "subject": r.get("subject")} for r in rows]
    
    # 2. Ask LLM to select and order
    prompt = f"""
    You are an expert curriculum designer.
    Goal: "{goal}"
    Target Audience: "{audience}"
    
    Available Topics (Candidates):
    {json.dumps(candidates[:300], ensure_ascii=False)} 
    (List truncated to 300 items if longer)
    
    Task:
    Select the most relevant topics from the candidates list to achieve the goal.
    Order them logically (from basic to advanced).
    
    Return JSON:
    {{
        "title": "Suggested Curriculum Title",
        "standard": "Suggested Standard (e.g. CEFR B1, Corporate Policy, etc)",
        "selected_uids": ["uid1", "uid2", ...]
    }}
    """
    
    messages = [{"role": "user", "content": prompt}]
    res = await openai_chat_async(messages, temperature=0.2)
    
    if not res.get("ok"):
        return {"ok": False, "error": f"LLM error: {res.get('error')}"}
        
    try:
        raw = res.get("content", "").strip()
        if raw.startswith("```json"):
            raw = raw[7:]
        if raw.endswith("```"):
            raw = raw[:-3]
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"ok": False, "error": "Failed to parse LLM response"}
        
    # 3. Save to DB
    curr_code = f"GEN-{uuid.uuid4().hex[:8].upper()}"
    title = data.get("title", f"Curriculum: {goal}")
    standard = data.get("standard", "Custom")
    
    create_res = repo.create_curriculum(curr_code, title, standard, language)
    if not create_res.get("ok"):
        return create_res
        
    nodes = []
    for idx, uid in enumerate(data.get("selected_uids", [])):
        nodes.append({
            "kind": "topic",
            "canonical_uid": uid,
            "order_index": idx + 1,
            "is_required": True
        })
        
    if nodes:
        repo.add_curriculum_nodes(curr_code, nodes)
        
    return {
        "ok": True, 
        "code": curr_code, 
        "title": title, 
        "items_count": len(nodes)
    }
