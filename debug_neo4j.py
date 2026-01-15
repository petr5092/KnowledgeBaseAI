import asyncio
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from src.services.graph.neo4j_repo import Neo4jRepo

async def main():
    repo = Neo4jRepo()
    subject_uid = "SUB-MATEMATIKA-6f0cfe"
    
    print(f"Checking subject: {subject_uid}")
    
    # Check if subject exists
    query_sub = "MATCH (s:Subject {uid: $uid}) RETURN s"
    res_sub = repo.read(query_sub, {"uid": subject_uid})
    print(f"Subject exists: {len(res_sub) > 0}")
    if res_sub:
        print(f"Subject data: {res_sub[0]}")

    # Check relationships
    query_rels = """
    MATCH (s:Subject {uid: $uid})-[:CONTAINS]->(sec:Section)
    RETURN count(sec) as section_count
    """
    res_rels = repo.read(query_rels, {"uid": subject_uid})
    print(f"Section count: {res_rels[0]['section_count'] if res_rels else 0}")

    query_topics = """
    MATCH (s:Subject {uid: $uid})-[:CONTAINS]->(sec:Section)-[:CONTAINS]->(t:Topic)
    RETURN count(t) as topic_count
    """
    res_topics = repo.read(query_topics, {"uid": subject_uid})
    print(f"Topic count (via Section): {res_topics[0]['topic_count'] if res_topics else 0}")
    
    query_topics_sub = """
    MATCH (s:Subject {uid: $uid})-[:CONTAINS]->(sec:Section)-[:CONTAINS]->(subsec:Subsection)-[:CONTAINS]->(t:Topic)
    RETURN count(t) as topic_count
    """
    res_topics_sub = repo.read(query_topics_sub, {"uid": subject_uid})
    print(f"Topic count (via Subsection): {res_topics_sub[0]['topic_count'] if res_topics_sub else 0}")

    repo.close()

if __name__ == "__main__":
    asyncio.run(main())
