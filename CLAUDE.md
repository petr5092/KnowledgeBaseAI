# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

KnowledgeBaseAI is a knowledge graph visualization and management platform integrated with an AI assistant. It consists of a React + TypeScript frontend using vis-network for graph visualization, and a FastAPI backend with Neo4j (graph database), PostgreSQL (metadata), Qdrant (vector search), and Redis (caching/events).

The system uses a **Proposal-based workflow** for all graph modifications: changes are drafted as Proposals, validated for integrity, reviewed, and committed atomically. This ensures graph consistency and provides an audit trail.

## Architecture

### Backend (FastAPI + Python)

- **Multi-tenant** architecture with `X-Tenant-ID` header for isolation
- **Dual-database design**:
  - **Neo4j**: Stores the knowledge graph (Topics, Skills, Prerequisites)
  - **PostgreSQL**: Stores metadata (users, proposals, curriculum definitions, graph versions)
  - **Qdrant**: Vector embeddings for semantic search
  - **Redis**: Event publishing and caching

- **Key API Groups** (see `backend/app/api/`):
  - `/v1/engine/*`: Core graph operations (viewport, roadmap, adaptive questions)
  - `/v1/proposals/*`: Proposal creation and commit workflow
  - `/v1/admin/*`: Admin operations for graph and curriculum management
  - `/v1/assistant/*`: AI assistant chat with tool calling
  - `/v1/auth/*`: JWT-based authentication

- **Proposal System** (`backend/app/schemas/proposal.py`):
  - All graph writes go through atomic Proposals
  - Operations: CREATE_NODE, CREATE_REL, UPDATE_NODE, UPDATE_REL, MERGE_NODE
  - Validation includes: canonical compliance, prereq cycle detection, integrity checks
  - Commits are transactional and publish events to Redis

- **Curriculum System** (see `CURRICULUM_ARCHITECTURE.md`):
  - Curricula act as "filters" or "prisms" over the global knowledge graph
  - Defined in PostgreSQL with references to Neo4j node UIDs
  - Used for LMS integration (ФГОС, corporate standards)

### Frontend (React + TypeScript + Vite)

- **State Management**: Redux Toolkit with slices for graph, chat, auth
- **Visualization**: `vis-network` for interactive graph rendering (see `frontend/src/pages/ExplorePage.tsx`)
- **Key Features**:
  - Graph exploration with depth-based viewport rendering
  - Node details sidebar with AI integration
  - Persistent camera and layout state in GraphContext
  - Filter by node kind (concept/skill/resource)

## Development Commands

### Backend

```bash
# Run tests
cd backend
pytest                           # All tests
pytest -k test_name             # Single test
pytest tests/unit/              # Unit tests only
pytest tests/integration/       # Integration tests only

# Database migrations (Alembic)
cd backend
alembic upgrade head            # Apply migrations
alembic revision --autogenerate -m "description"  # Create migration

# Run backend directly (outside Docker)
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Scripts for graph operations
python backend/scripts/load_data.py           # Load JSONL data to Postgres
python backend/scripts/push_to_neo4j.py       # Push graph to Neo4j
python backend/scripts/clear_graph.py         # Clear Neo4j (preserve schema)
python backend/scripts/migrate_graph_to_canon.py  # Migrate to canonical format
```

### Frontend

```bash
cd frontend
npm install                     # Install dependencies
npm run dev                     # Dev server (http://localhost:5173)
npm run build                   # Production build
npm run lint                    # Lint code
npm run test                    # Run tests (Vitest)
```

### Docker

```bash
# Production deployment
make up-prod                    # Start production stack
docker compose --env-file .env.prod up -d

# Development mode
make up-dev                     # Start dev stack with hot reload
docker compose --env-file .env.dev --profile dev up -d

# Logs
make logs                       # View service logs
docker logs knowledgebase-fastapi-1 --tail 200

# Restart services
make restart-backend
make restart-frontend
```

### Initial Setup

```bash
# 1. Configure environment
cp .env.example .env.prod
# Edit .env.prod with your settings (DB passwords, API keys, domains)

# 2. Start infrastructure
docker-compose up -d

# 3. Initialize databases (inside container)
docker exec knowledgebase-fastapi-dev-1 python scripts/load_data.py
docker exec knowledgebase-fastapi-dev-1 python scripts/push_to_neo4j.py
```

## Key Concepts

### Canonical Graph Format

The system enforces a canonical format (see `backend/app/core/canonical.py`):
- **Allowed Node Labels**: Subject, Section, Subsection, Topic, Skill, Method, Example, Error, Goal, Objective, ContentUnit
- **Allowed Edge Types**: CONTAINS, PREREQ, USES_SKILL, APPLIES_METHOD, DEMONSTRATES, TRIGGERS_ERROR, HAS_GOAL, HAS_OBJECTIVE, BASED_ON
- All text is normalized (NFKC, whitespace collapsed)
- Canonical JSON uses sorted keys for deterministic checksums

### Graph Traversal

- **Viewport** (`GET /v1/engine/viewport`): Returns nodes within N hops of a center node
- **Roadmap** (`POST /v1/engine/roadmap`): Generates personalized learning path based on progress and prerequisites
- **Adaptive Questions** (`POST /v1/engine/adaptive_questions`): Selects questions based on progress gaps and difficulty

### Multi-tenancy

- Tenants are isolated by `tenant_id` field in Neo4j and PostgreSQL
- Header: `X-Tenant-ID: <tenant-id>` (required for writes, optional for reads with default)
- DaoBase class (`backend/app/db/dao_base.py`) enforces tenant injection in queries

### Visualization State Management

The frontend uses `GraphContext` to preserve:
- Current viewport (nodes + edges)
- Selected node UID and depth
- Camera position (x, y, scale)
- Node positions (to prevent re-layout on navigation)
- Filter state (kind, depth)

When navigating away and back, the context is validated and restored if still valid.

## Testing

### Backend Tests

- **Location**: `backend/tests/`
- **Structure**:
  - `tests/unit/`: Fast, isolated tests (no external dependencies)
  - `tests/integration/`: Tests with real databases (use fixtures)
- **Fixtures**: `backend/tests/conftest.py` provides `_clean_db` to reset state
- **Mocking**: Use `monkeypatch` to mock external calls (Neo4j, OpenAI, Qdrant)

### Frontend Tests

- **Location**: `frontend/src/__tests__/`
- **Framework**: Vitest + jsdom
- Run with `npm run test`

## Common Patterns

### Adding a New API Endpoint

1. Create route in `backend/app/api/<module>.py`
2. Add Pydantic models for request/response
3. Use dependency injection for tenant/user via `deps.py`
4. Add integration test in `backend/tests/`

### Modifying the Graph Schema

1. Update canonical definitions in `backend/app/core/canonical.py`
2. Create Alembic migration if changing PostgreSQL schema
3. Update Neo4j schema via scripts if needed
4. Add validation rules in `backend/app/services/integrity.py`
5. Update proposal validation logic

### Adding Frontend Components

1. Place in `frontend/src/components/` or `frontend/src/pages/`
2. Use Redux hooks (`useSelector`, `useDispatch`) for state
3. Type with TypeScript interfaces
4. Follow existing patterns for API calls via `frontend/src/api.ts`

## Important Files

- `backend/app/main.py`: FastAPI application setup and middleware
- `backend/app/api/engine.py`: Core graph operations (viewport, roadmap, questions)
- `backend/app/api/proposals.py`: Proposal workflow endpoints
- `backend/app/workers/commit.py`: Proposal commit worker (applies operations to Neo4j)
- `backend/app/services/graph/neo4j_repo.py`: Neo4j query repository
- `backend/app/services/integrity.py`: Graph integrity checks
- `frontend/src/App.tsx`: React router and layout
- `frontend/src/pages/ExplorePage.tsx`: Main graph visualization page
- `frontend/src/context/GraphContext.tsx`: Graph state management
- `docker-compose.yml`: Service orchestration
- `CURRICULUM_ARCHITECTURE.md`: Curriculum system design

## Environment Variables

Key variables (see `.env.example`):
- `PG_DSN`: PostgreSQL connection string
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`: Neo4j configuration
- `QDRANT_URL`: Qdrant vector database URL
- `REDIS_URL`: Redis connection for events
- `OPENAI_API_KEY`: OpenAI API key for AI features
- `JWT_SECRET_KEY`: Secret for JWT token signing
- `KB_DOMAIN`, `KB_ALT_DOMAIN`: Primary and alternate domains for Traefik routing

## Troubleshooting

### Backend won't start
- Check database connectivity: `docker logs knowledgebase-postgres-1`
- Verify migrations: `docker exec knowledgebase-fastapi-1 alembic current`
- Check Neo4j status: `docker logs knowledgebase-neo4j-1`

### Frontend can't reach API
- Verify backend is running: `curl http://localhost:8000/health`
- Check CORS settings in `backend/app/main.py`
- Ensure API URL is correct in frontend config

### Graph visualization issues
- Check viewport API response: `GET /v1/engine/viewport?center_uid=<uid>&depth=2`
- Verify GraphContext state in React DevTools
- Check browser console for vis-network errors

### Test failures
- Clean database: Use `_clean_db` fixture
- Check test isolation (one test shouldn't affect another)
- Verify mocks are properly set up for external services
