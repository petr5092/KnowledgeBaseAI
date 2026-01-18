
from app.services.graph.neo4j_repo import Neo4jRepo
import json

repo = Neo4jRepo()
subject_uid = "MATH-FULL-V1"
query = """
MATCH (sub:Subject {uid: $su})
MATCH (sub)-[:CONTAINS*]->(t:Topic)
RETURN t.uid AS uid, t.title AS title
LIMIT 20
"""
rows = repo.read(query, {"su": subject_uid})
print(json.dumps(rows, ensure_ascii=False, indent=2))
repo.close()
