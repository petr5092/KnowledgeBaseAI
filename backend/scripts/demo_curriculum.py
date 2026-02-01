import asyncio
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), "../"))

# --- CONFIGURATION HACK FOR DEMO ---
# Try to load .env manually or set defaults
if not os.getenv("PG_DSN"):
    # Try 'postgres' db if 'knowledgebase' fails
    os.environ["PG_DSN"] = "postgresql://postgres:postgres@localhost:5432/postgres"
    print(f"DEBUG: Set default PG_DSN={os.environ['PG_DSN']}")

if not os.getenv("NEO4J_URI"):
    os.environ["NEO4J_URI"] = "bolt://localhost:7687"
    os.environ["NEO4J_USER"] = "neo4j"
    os.environ["NEO4J_PASSWORD"] = "password"
    print("DEBUG: Set default Neo4j credentials")

if not os.getenv("OPENAI_API_KEY"):
    print("WARNING: OPENAI_API_KEY not found. LLM calls will be mocked.")
    os.environ["OPENAI_API_KEY"] = "sk-mock-key"
    # Mock the openai_chat_async function if needed, but let's see if we can just handle it in the builder
    
from app.db.pg import ensure_tables
from app.services.ingestion.corporate import CorporateIngestionStrategy
from app.services.proposal_service import create_draft_proposal
from app.workers.commit import commit_proposal
from app.services.curriculum.builder import generate_curriculum_llm
from app.db.pg import get_conn
from app.schemas.proposal import ProposalStatus
import json
from unittest.mock import patch, MagicMock

# Mock LLM if key is fake
async def mock_openai_chat_async(messages, **kwargs):
    content = messages[0]["content"]
    if "Analyze the text" in content:
        # Corporate Ingestion Mock
        return {
            "ok": True,
            "content": json.dumps({
                "subject": "Security Policy",
                "sections": [
                    {
                        "title": "Password Security",
                        "subsections": [
                            {"title": "Requirements", "topics": [{"title": "Length", "skills": ["Change Password"]}]}
                        ]
                    }
                ]
            })
        }
    if "Select the most relevant topics" in content:
        # Curriculum Mock
        return {
            "ok": True,
            "content": json.dumps({
                "title": "Mocked Curriculum",
                "standard": "Mock Standard",
                "selected_uids": ["TOP-MOCK-1", "TOP-MOCK-2"]
            })
        }
    return {"ok": False, "error": "Unknown prompt"}

MANUAL_TEXT = """
Security Policy Manual
Version 1.0

1. Password Security
1.1. Passwords must be at least 12 characters long.
1.2. Passwords must be changed every 90 days.
1.3. Do not share passwords.

2. Physical Security
2.1. Badge access is required for all areas.
2.2. Visitors must be escorted.
2.3. Clean desk policy: lock computers when away.

3. Incident Response
3.1. Report suspicious emails to security@corp.com.
3.2. If a device is lost, call Helpdesk immediately.
"""

async def run_demo():
    # Apply mock if needed
    if os.environ["OPENAI_API_KEY"] == "sk-mock-key":
        print(">>> APPLYING LLM MOCK")
        import app.services.kb.builder
        import app.services.curriculum.builder
        import app.services.ingestion.corporate
        
        # Patch the function in all places it might be used
        app.services.kb.builder.openai_chat_async = mock_openai_chat_async
        # Also patch the imported reference in corporate.py
        app.services.ingestion.corporate.openai_chat_async = mock_openai_chat_async
        # Also patch the imported reference in curriculum/builder.py
        app.services.curriculum.builder.openai_chat_async = mock_openai_chat_async
        
    print(">>> 1. Ensuring DB tables...")
    ensure_tables()
    
    tenant_id = "demo-tenant"
    
    print(">>> 2. Ingesting Corporate Manual...")
    strategy = CorporateIngestionStrategy()
    ops = await strategy.process(MANUAL_TEXT, domain_context="Corporate Security")
    
    print(f"Generated {len(ops)} operations.")
    
    # Create Proposal
    p = create_draft_proposal(tenant_id, 0, ops)
    
    # Save Proposal to DB (needed for commit_proposal)
    conn = get_conn()
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO proposals (proposal_id, tenant_id, base_graph_version, proposal_checksum, status, operations_json) VALUES (%s,%s,%s,%s,%s,%s)",
            (
                p.proposal_id,
                p.tenant_id,
                p.base_graph_version,
                p.proposal_checksum,
                ProposalStatus.DRAFT.value,
                json.dumps(p.model_dump()["operations"]),
            ),
        )
    conn.close()
    print(f"Proposal {p.proposal_id} created.")
    
    print(">>> 3. Committing Proposal (Simulating Approval)...")
    res = commit_proposal(p.proposal_id)
    if not res["ok"]:
        print(f"Commit failed: {res}")
        return
    print("Graph updated successfully.")
    
    print(">>> 4. Generating Curriculums...")
    
    # Curriculum 1: Basic
    print("Generating 'New Employee Induction'...")
    c1 = await generate_curriculum_llm(
        goal="Teach basic security rules for new employees. Focus on passwords and badges.",
        audience="New Hires",
        language="en"
    )
    print(f"Result: {c1}")
    
    # Curriculum 2: Advanced
    print("Generating 'Security Officer Training'...")
    c2 = await generate_curriculum_llm(
        goal="Train security officers on incident response and enforcement.",
        audience="Security Staff",
        language="en"
    )
    print(f"Result: {c2}")
    
    print(">>> Demo Completed.")

if __name__ == "__main__":
    asyncio.run(run_demo())
