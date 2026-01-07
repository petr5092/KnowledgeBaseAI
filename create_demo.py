from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', 'password')

def create_demo_node():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as session:
        # Create Demo Topic
        session.run('MERGE (n:Topic {uid: "TOP-DEMO", title: "Demo Topic", description: "Default demo node for initial load"})')
        # Link to Subject
        session.run('MATCH (a {uid: "SUB-MATH"}), (b {uid: "TOP-DEMO"}) MERGE (a)-[:HAS_TOPIC]->(b)')
        print("Demo node created and linked to SUB-MATH")
    driver.close()

if __name__ == "__main__":
    create_demo_node()

