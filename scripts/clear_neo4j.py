import os
from neo4j import GraphDatabase


def get_env(name: str, default: str | None = None) -> str:
    val = os.getenv(name, default)
    if not val:
        raise RuntimeError(f"Missing required env var: {name}")
    return val


def clear_nodes_and_relationships(session):
    # Delete all nodes and relationships
    session.run("MATCH (n) DETACH DELETE n")


def drop_constraints(session):
    # Drop all constraints (Neo4j 5 syntax)
    res = session.run("SHOW CONSTRAINTS")
    names = [rec.get("name") for rec in res]
    for name in names:
        try:
            session.run(f"DROP CONSTRAINT {name} IF EXISTS")
        except Exception as e:
            # Continue even if a specific constraint cannot be dropped
            print(f"Warning: failed to drop constraint {name}: {e}")


def drop_indexes(session):
    # Drop all indexes (Neo4j 5 syntax)
    res = session.run("SHOW INDEXES")
    names = [rec.get("name") for rec in res]
    for name in names:
        try:
            session.run(f"DROP INDEX {name} IF EXISTS")
        except Exception as e:
            print(f"Warning: failed to drop index {name}: {e}")


def main():
    uri = get_env("NEO4J_URI")
    user = get_env("NEO4J_USER")
    password = get_env("NEO4J_PASSWORD")

    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session() as session:
        # Drop schema first, then data, then schema again in case remnants remain
        drop_indexes(session)
        drop_constraints(session)
        clear_nodes_and_relationships(session)
        # Second pass to ensure an empty schema state
        drop_indexes(session)
        drop_constraints(session)

    driver.close()
    print("Neo4j fully cleared: nodes, relationships, indexes, and constraints removed.")


if __name__ == "__main__":
    main()