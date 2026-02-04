# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

KnowledgeBaseAI is a knowledge graph visualization and AI-assisted learning platform. It combines a FastAPI backend with a React+TypeScript+Vite frontend, using Neo4j for graph storage, PostgreSQL for relational data, Qdrant for vector search, and Redis for caching/events.

**Core concept**: The system manages a knowledge graph where nodes represent educational concepts, skills, topics, and resources. It provides adaptive learning paths (roadmaps), AI-assisted navigation, and a proposal-based system for safe graph mutations.

## Tech Stack

**Backend**: Python 3.11+, FastAPI, Neo4j 5.26, PostgreSQL 15, Qdrant, Redis
**Frontend**: React 19, TypeScript, Vite, vis-network, React Router, Redux Toolkit
**Infrastructure**: Docker Compose, Traefik (reverse proxy with TLS)

## Development Commands

### Full Stack (Docker)

```bash
# Start all services (production profile)
docker-compose up -d --build

# Start dev services with hot reload
make up-dev

# Initialize data (first time setup)
docker exec knowledgebase-fastapi-dev-1 python scripts/load_data.py
docker exec knowledgebase-fastapi-dev-1 python scripts/push_to_neo4j.py

# View logs
make logs

# Restart individual services
make restart-backend
make restart-frontend
```

### Backend (Python)

```bash
cd backend

# Run tests (pytest)
pytest                           # All tests
pytest tests/unit               # Unit tests only
pytest tests/integration        # Integration tests only
pytest -k test_name             # Specific test

# Run FastAPI locally (requires services running)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Database migrations (Alembic)
alembic revision --autogenerate -m "description"
alembic upgrade head
alembic downgrade -1
```

### Frontend (TypeScript + React)

```bash
cd frontend

# Install dependencies
npm install

# Development server (HMR)
npm run dev

# Build for production
npm run build

# Run tests (Vitest)
npm test

# Lint
npm run lint
```

## Architecture

### Backend: Proposal-Based Graph Mutations

**Critical**: All graph changes go through a Proposal → Review → Commit pipeline (`/v1/proposals`). Direct writes to Neo4j are prohibited outside `backend/app/workers/commit.py`.

**Flow**:
1. Client submits proposal via `POST /v1/proposals` with operations (CREATE_NODE, CREATE_RELATION, etc.)
2. System validates canonical compliance, integrity checks (cycles, orphans, hierarchy)
3. Proposal stored in PostgreSQL with status `draft` → `ready` → `approved`
4. Background worker (`commit_proposal`) applies changes to Neo4j atomically
5. Outbox pattern publishes `graph.committed` event to Redis
6. Vector sync worker re-indexes affected entities in Qdrant

**Key files**:
- `backend/app/api/proposals.py` - API endpoints
- `backend/app/workers/commit.py` - Commit worker
- `backend/app/services/integrity.py` - Validation rules
- `backend/app/core/canonical.py` - Canonical normalization

### Backend: Multi-Tenancy

- Header `X-Tenant-ID` required for write operations and admin endpoints
- Context stored in `app/core/context.py` using `ContextVar`
- All Neo4j nodes have `tenant_id` property
- Schema versioning per tenant in PostgreSQL (`tenant_schema_version` table)

### Backend: Data Layer

**Neo4j** (`backend/app/services/graph/neo4j_repo.py`):
- Stores knowledge graph: Subject → Section → Subsection → Topic hierarchy
- Nodes: Concept, Skill, Resource, Topic, etc.
- Relationships: PREREQ, CONTAINS, USES_SKILL, BASED_ON
- Read-only access via `Neo4jRepo.read()`, writes via proposal system

**PostgreSQL** (`backend/app/db/pg.py`):
- Proposals, graph version tracking, curriculum definitions, user auth
- Outbox pattern for event publishing

**Qdrant** (`backend/app/services/vector/qdrant_service.py`):
- Vector embeddings for semantic search
- Auto-syncs when graph changes (via `graph.committed` events)

### Frontend: Graph Visualization (vis-network)

**Key component**: `frontend/src/pages/ExplorePage.tsx`

**State Management**:
- `GraphContext` (frontend/src/context/GraphContext.tsx) stores viewport, camera position, node positions
- On navigation away, saves camera/positions; on return, restores without re-fetching if context is valid
- Disables vis-network auto-stabilization and fit to preserve user's view

**Graph rendering**:
- `viewport` API (`/v1/engine/viewport?center_uid=X&depth=2`) fetches subgraph
- Filters by node `kind` (concept/skill/resource) client-side without refetch
- Single click → sidebar with details; double click → recenter graph

### Frontend: Routing & State

- React Router for navigation (`/explore`, `/roadmap`, `/chat`)
- Redux Toolkit for global state (user progress, mastery scores)
- `frontend/src/api.ts` - centralized API client

## Key Patterns & Constraints

### Canonical Graph Specification

All graph operations must comply with `CANONICAL_SPEC.md` rules:
- Node labels must be in `ALLOWED_NODE_LABELS` (Subject, Topic, Skill, etc.)
- Edge types must be in `ALLOWED_EDGE_TYPES` (PREREQ, CONTAINS, etc.)
- Text normalization via `backend/app/core/canonical.py::normalize_text()`
- Deterministic JSON serialization for checksums

### Adaptive Learning Engine

**Roadmap Planning** (`backend/app/services/roadmap_planner.py`):
- Input: user progress (dict of uid → mastery score), subject_uid
- Output: prioritized list of topics to study next
- Algorithm: considers prerequisites, gaps, cognitive distance

**Assessment** (`backend/app/api/assessment.py`):
- Adaptive question selection based on difficulty and user level
- Bayesian mastery updates via `backend/app/services/reasoning/mastery_update.py`

### Error Handling

All API errors follow standardized format (`backend/app/api/common.py::ApiError`):
- `code`: machine-readable error code
- `message`: human-readable description
- `details`: optional structured data
- `correlation_id`: for request tracing

## Testing Guidelines

**Backend**:
- Unit tests mock external dependencies (Neo4j, PostgreSQL)
- Integration tests use real databases (cleaned via `conftest.py::_clean_db` fixture)
- Proposal tests validate entire pipeline: create → validate → commit → verify

**Frontend**:
- Vitest for unit tests
- Mock API responses in `__tests__` directories

## Environment Variables

Key vars (see `.env.example`, `.env.dev`, `.env.prod`):
- `PG_DSN`: PostgreSQL connection string
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`: Neo4j credentials
- `QDRANT_URL`: Vector DB endpoint
- `REDIS_URL`: Redis for events/cache
- `OPENAI_API_KEY`: For AI assistant and embeddings
- `JWT_SECRET_KEY`: Auth token signing
- `KB_DOMAIN`, `KB_ALT_DOMAIN`: Primary/alternate domains for Traefik routing

## Important Files

**Backend**:
- `backend/app/main.py` - FastAPI app initialization, middleware, routers
- `backend/app/api/engine.py` - Unified engine API (roadmap, viewport, pathfinding)
- `backend/app/api/assistant.py` - AI chat assistant with tool calling
- `backend/alembic/` - Database migration scripts

**Frontend**:
- `frontend/src/App.tsx` - Root component, routing setup
- `frontend/src/config/appConfig.ts` - Node colors, kinds, theme
- `frontend/src/context/GraphContext.tsx` - Graph state management
- `frontend/src/pages/ExplorePage.tsx` - Main graph visualization

## Running Migrations

Backend uses Alembic for schema migrations:

```bash
# Inside backend container or with PG_DSN set
cd backend
alembic upgrade head        # Apply all pending migrations
alembic current            # Check current revision
alembic history            # View migration history
```

On first deploy, FastAPI auto-creates tables via `backend/app/db/pg.py::ensure_tables()` if `SKIP_MIGRATIONS=false`.

## Deployment

Production uses Docker Compose with Traefik for TLS termination. See `docker-compose.yml` profiles:
- `prod`: Production frontend + backend
- `dev`: Dev frontend/backend with hot reload
- `infra`: Monitoring (Prometheus, Grafana)

Access points (configured via Traefik labels):
- Frontend: `https://${KB_DOMAIN}`
- API: `https://api.${KB_DOMAIN}`
- Neo4j Browser: `https://graph.${KB_DOMAIN}`
- Qdrant: `https://qdrant.${KB_DOMAIN}` (basic auth)
