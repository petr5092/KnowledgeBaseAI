
import sys
import os
import json
sys.path.append("/root/KnowledgeBaseAI/backend")

from app.services.graph.neo4j_repo import Neo4jRepo

def check_db():
    repo = Neo4jRepo()
    print("Checking Knowledge Base (Neo4j)...")

    # 1. Total Questions
    query_total = "MATCH (q:Question) RETURN count(q) as count"
    res_total = repo.read(query_total)
    total = res_total[0]['count'] if res_total else 0
    print(f"Total Questions (Nodes) in DB: {total}")

    # 1b. Total Examples
    query_ex = "MATCH (e:Example) RETURN count(e) as count"
    res_ex = repo.read(query_ex)
    total_ex = res_ex[0]['count'] if res_ex else 0
    print(f"Total Examples (Nodes) in DB: {total_ex}")

    # 2. Visual Questions
    query_visual = "MATCH (q:Question) WHERE q.is_visual = true RETURN count(q) as count"
    res_visual = repo.read(query_visual)
    visual = res_visual[0]['count'] if res_visual else 0
    print(f"Visual Questions (Nodes): {visual}")
    
    # 3. Questions by Type
    query_types = "MATCH (q:Question) RETURN q.type as type, count(q) as count ORDER BY count DESC"
    res_types = repo.read(query_types)
    print("\nQuestions by Type:")
    for r in res_types:
        print(f"  - {r['type']}: {r['count']}")

    # Check JSONL files
    print("\nChecking JSONL files...")
    try:
        from app.services.questions import get_examples_indexed
        idx = get_examples_indexed()
        all_ex = idx["all"]
        print(f"Total Examples in JSONL: {len(all_ex)}")
        
        visual_jsonl = [e for e in all_ex if e.get('is_visual')]
        print(f"Visual Examples in JSONL: {len(visual_jsonl)}")
        
        if visual_jsonl:
            print("Sample Visual Example from JSONL:")
            e = visual_jsonl[0]
            print(f"  UID: {e.get('uid')}")
            print(f"  Topic: {e.get('topic_uid')}")
            print(f"  Prompt: {e.get('prompt') or e.get('statement')}")
            print(f"  Visualization: {json.dumps(e.get('visualization'), ensure_ascii=False)[:100]}...")
    except Exception as e:
        print(f"Error checking JSONL: {e}")


    # 4. Visual Questions Details (Sample)
    if visual > 0:
        print("\nSample Visual Questions:")
        query_sample = """
        MATCH (q:Question) 
        WHERE q.is_visual = true 
        RETURN q.uid as uid, q.prompt as prompt, q.topic_uid as topic_uid, q.visualization as visualization 
        LIMIT 3
        """
        res_sample = repo.read(query_sample)
        for r in res_sample:
            print(f"  UID: {r['uid']}")
            print(f"  Topic: {r['topic_uid']}")
            print(f"  Prompt: {r['prompt']}")
            vis = r['visualization']
            if isinstance(vis, str):
                try:
                    vis = json.loads(vis)
                except:
                    pass
            print(f"  Visualization: {json.dumps(vis, ensure_ascii=False)[:100]}...") # Truncate
            print("-" * 20)
    else:
        print("\nNo visual questions found.")

    # 5. Check Topics with Questions
    query_topics = """
    MATCH (t:Topic)-[:HAS_QUESTION|CONTAINS]->(q:Question)
    RETURN t.uid as topic, count(q) as count
    ORDER BY count DESC
    LIMIT 10
    """
    res_topics = repo.read(query_topics)
    print("\nTop 10 Topics with Questions:")
    for r in res_topics:
        print(f"  - {r['topic']}: {r['count']}")

if __name__ == "__main__":
    try:
        check_db()
    except Exception as e:
        print(f"Error: {e}")
