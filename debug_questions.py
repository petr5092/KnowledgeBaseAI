import asyncio
import os
import sys

# Load env vars manually
def load_env(path):
    with open(path) as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                k, v = line.strip().split('=', 1)
                os.environ[k] = v

load_env('/root/KnowledgeBaseAI/.env.dev')
os.environ['NEO4J_URI'] = 'bolt://localhost:7687'

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from src.services.graph.neo4j_repo import Neo4jRepo

async def main():
    repo = Neo4jRepo()
    topic_uid = "TOP-BULEVY-FUNKCII-8b2bf4"
    
    print(f"Checking topic: {topic_uid}")
    
    # Check Examples
    query_ex = """
    MATCH (t:Topic {uid: $uid})-[:HAS_EXAMPLE]->(ex:Example)
    RETURN ex.uid, ex.title, ex.statement, ex.content
    LIMIT 5
    """
    res_ex = repo.read(query_ex, {"uid": topic_uid})
    print(f"\nExamples found ({len(res_ex)}):")
    for r in res_ex:
        print(r)

    # Check Questions (if any exist with that label)
    query_q = """
    MATCH (t:Topic {uid: $uid})-[]-(q:Question)
    RETURN q.uid, q.text, q.statement, q.content
    LIMIT 5
    """
    res_q = repo.read(query_q, {"uid": topic_uid})
    print(f"\nQuestions found ({len(res_q)}):")
    for r in res_q:
        print(r)

    # Check ANY connected node with useful text
    query_dump = """
    MATCH (t:Topic {uid: $uid})-[r]-(n)
    RETURN labels(n) as labels, type(r) as rel, n.uid, n.title, n.statement, n.text, n.content, n.payload
    LIMIT 20
    """
    res_dump = repo.read(query_dump, {"uid": topic_uid})
    print(f"\nAll connected nodes ({len(res_dump)}):")
    for r in res_dump:
        print(f"Labels: {r['labels']}, Rel: {r['rel']}")
        print(f"  UID: {r['uid']}")
        if r.get('title'): print(f"  Title: {r['title']}")
        if r.get('statement'): print(f"  Statement: {r['statement']}")
        if r.get('text'): print(f"  Text: {r['text']}")
        if r.get('content'): print(f"  Content: {r['content']}")
        if r.get('payload'): print(f"  Payload: {r['payload']}")
        print("-" * 20)

    repo.close()

if __name__ == "__main__":
    asyncio.run(main())
