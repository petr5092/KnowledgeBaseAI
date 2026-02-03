import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'backend'))
from app.services.graph.neo4j_repo import Neo4jRepo

repo = Neo4jRepo()
row = repo.read(
    "MATCH (t:Topic {uid: 'TOPIC-MULT-TABLE'}) RETURN t.title, t.description, t.user_class_min", 
    {}
)
print(row)
repo.close()
