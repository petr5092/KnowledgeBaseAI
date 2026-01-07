import os
from dotenv import load_dotenv

load_dotenv()

vars_to_check = [
    "PG_DSN", "NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD", 
    "REDIS_URL", "QDRANT_URL", "OPENAI_API_KEY", "JWT_SECRET_KEY",
    "DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_PORT"
]

for v in vars_to_check:
    val = os.getenv(v)
    if val:
        if "PASSWORD" in v or "KEY" in v or "SECRET" in v:
            print(f"{v}: [REDACTED]")
        else:
            print(f"{v}: {val}")
    else:
        print(f"{v}: Not set")
