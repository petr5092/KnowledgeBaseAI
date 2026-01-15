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
    
    # 1. Total count of Questions and Examples
    query_total = """
    MATCH (n)
    WHERE n:Question OR n:Example
    RETURN labels(n) as labels, count(n) as count
    """
    res_total = repo.read(query_total)
    print("--- Total Counts ---")
    for r in res_total:
        print(f"{r['labels']}: {r['count']}")

    # 2. Distribution by Topic (Questions)
    print("\n--- Question Distribution by Topic (Top 20) ---")
    query_dist_q = """
    MATCH (t:Topic)
    OPTIONAL MATCH (t)-[:HAS_QUESTION|:CONTAINS]->(q:Question)
    WITH t, count(q) as q_count
    ORDER BY q_count DESC
    RETURN t.title as topic, q_count
    LIMIT 20
    """
    res_dist_q = repo.read(query_dist_q)
    for r in res_dist_q:
        print(f"{r['topic']}: {r['q_count']}")

    # 3. Topics with ZERO questions
    query_zero_q = """
    MATCH (t:Topic)
    WHERE NOT EXISTS { (t)-[:HAS_QUESTION|:CONTAINS]->(:Question) }
    RETURN count(t) as zero_count
    """
    res_zero = repo.read(query_zero_q)
    print(f"\nTopics with 0 Questions: {res_zero[0]['zero_count'] if res_zero else 0}")

    # 4. Distribution by Topic (Examples - fallback)
    print("\n--- Example Distribution by Topic (Top 10) ---")
    query_dist_ex = """
    MATCH (t:Topic)
    OPTIONAL MATCH (t)-[:HAS_EXAMPLE]->(ex:Example)
    WITH t, count(ex) as ex_count
    ORDER BY ex_count DESC
    RETURN t.title as topic, ex_count
    LIMIT 10
    """
    res_dist_ex = repo.read(query_dist_ex)
    for r in res_dist_ex:
        print(f"{r['topic']}: {r['ex_count']}")

    repo.close()

if __name__ == "__main__":
    asyncio.run(main())
