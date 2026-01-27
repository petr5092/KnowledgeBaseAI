import psycopg2
from app.config.settings import settings

def get_conn():
    dsn = str(settings.pg_dsn) if settings.pg_dsn else ""
    if not dsn:
        print("PG_DSN not configured")
        return None
    return psycopg2.connect(dsn)

def init_db():
    conn = get_conn()
    if not conn:
        return

    print("Connected to DB")
    
    queries = [
        """
        CREATE TABLE IF NOT EXISTS curricula (
            id SERIAL PRIMARY KEY,
            code VARCHAR(64) UNIQUE NOT NULL,
            title VARCHAR(255),
            standard VARCHAR(64),
            language VARCHAR(2),
            status VARCHAR(16) DEFAULT 'draft'
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS curriculum_nodes (
            id SERIAL PRIMARY KEY,
            curriculum_id INTEGER REFERENCES curricula(id) ON DELETE CASCADE,
            canonical_uid VARCHAR(128) NOT NULL,
            kind VARCHAR(16),
            order_index INTEGER DEFAULT 0,
            is_required BOOLEAN DEFAULT TRUE
        );
        """
    ]

    try:
        with conn:
            with conn.cursor() as cur:
                for q in queries:
                    print(f"Executing: {q.strip()[:50]}...")
                    cur.execute(q)
        print("Tables created successfully.")
    except Exception as e:
        print(f"Error creating tables: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()
