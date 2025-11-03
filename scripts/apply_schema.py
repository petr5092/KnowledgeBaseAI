#!/usr/bin/env python3
import os
import psycopg2

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'schemas', 'postgres.sql')

def main():
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'database': os.getenv('DB_NAME', 'knowledge_base'),
        'user': os.getenv('DB_USER', 'kb_user'),
        'password': os.getenv('DB_PASSWORD', 'kb_password'),
        'port': int(os.getenv('DB_PORT', '5432')),
    }
    with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
        sql = f.read()
    conn = psycopg2.connect(**db_config)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        print('Schema applied successfully')
    finally:
        conn.close()

if __name__ == '__main__':
    main()