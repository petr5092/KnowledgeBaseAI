
import asyncio
import json
import os
from app.services.graph.neo4j_repo import Neo4jRepo

def get_path(filename):
    return os.path.join(os.path.dirname(__file__), 'app/kb', filename)

def load_jsonl(filepath):
    data = []
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    try:
                        data.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    return data

async def load_units():
    repo = Neo4jRepo()
    print("Connected to Neo4j")
    
    # Content Units
    units = load_jsonl(get_path('content_units.jsonl'))
    print(f"Loading {len(units)} content units...")
    
    count = 0
    for u in units:
        payload_str = json.dumps(u.get('payload', {}), ensure_ascii=False)
        params = {
            'uid': u['uid'],
            'topic_uid': u['topic_uid'],
            'branch': u.get('branch', 'theory'),
            'type': u.get('type', 'concept'),
            'complexity': u.get('complexity', 0.5),
            'payload': payload_str
        }
        repo.write("""
            MERGE (u:ContentUnit {uid: $uid})
            SET u.branch = $branch, u.type = $type, u.complexity = $complexity, u.payload = $payload
            WITH u
            MATCH (t:Topic {uid: $topic_uid})
            MERGE (t)-[:HAS_UNIT]->(u)
        """, params)
        count += 1
        if count % 100 == 0:
            print(f"Loaded {count} units...")
            
    print(f"Finished loading {count} units.")
    repo.close()

if __name__ == "__main__":
    asyncio.run(load_units())
