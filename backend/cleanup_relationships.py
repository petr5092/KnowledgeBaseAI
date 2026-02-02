import asyncio
from app.services.graph.neo4j_repo import Neo4jRepo

async def cleanup():
    repo = Neo4jRepo()
    print("Connected to Neo4j. Cleaning up old relationships...")
    
    # Delete HAS_SECTION, HAS_SUBSECTION, HAS_TOPIC
    repo.write("MATCH ()-[r:HAS_SECTION|HAS_SUBSECTION|HAS_TOPIC]->() DELETE r")
    
    print("Old relationships deleted.")
    repo.close()

if __name__ == "__main__":
    asyncio.run(cleanup())