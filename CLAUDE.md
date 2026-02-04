# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

KnowledgeBaseAI is a graph-based knowledge management platform for adaptive learning, designed for the StudyNinja ecosystem. It combines a FastAPI backend with Neo4j graph database, PostgreSQL, Qdrant vector database, and a React TypeScript frontend.

**Core Purpose**: Provides a stateless service for working with knowledge graphs, adaptive curriculum generation, mastery tracking, and AI-powered content generation.

## System Architecture

### Multi-Database Architecture

The system uses three complementary databases:

- **Neo4j (Graph)**: Primary knowledge graph storing subjects, topics, skills, methods, examples, and their relationships (CONTAINS, PREREQ, USES_SKILL, etc.)
- **PostgreSQL (Relational)**: User data, authentication, mastery scores, session data, proposals system
- **Qdrant (Vector)**: Semantic search over knowledge base entities using embeddings

### Key Backend Concepts

**Multi-tenancy**: The system is multi-tenant via `X-Tenant-ID` header (extracted from headers or JWT tokens). Tenant context is stored in `contextvars` and flows through all operations.

**Canonical Schema**: The graph enforces a strict canonical schema defined in `backend/app/core/canonical.py`:
- Allowed node labels: Subject, Section, Subsection, Topic, Skill, Method, Goal, Objective, Example, Error, ContentUnit, Concept, Formula, TaskType
- Allowed edge types: CONTAINS, PREREQ, USES_SKILL, LINKED, TARGETS, HAS_EXAMPLE, HAS_UNIT, MEASURES, BASED_ON
- All text is normalized (NFKC, whitespace normalized) before hashing

**Proposals System**: All graph modifications go through a proposal workflow (create → review → commit) to ensure data quality and auditability. See `/v1/proposals` endpoints.

**Unified Engine**: The `/v1/engine/*` endpoints provide the main API surface for:
- Graph viewport/navigation
- Roadmap generation (learning path planning)
- Adaptive question selection
- Next best topic recommendations
- Mastery updates

### Frontend Architecture

React + TypeScript with Redux Toolkit for state management. Key libraries:
- **vis-network**: Main graph visualization on Explore page
- **ReactFlow**: Alternative graph editor on Edit page
- **d3**: Visualizations and analytics
- **react-router-dom v7**: Routing

The frontend has multiple pages:
- **Explore**: Interactive graph visualization using vis-network
- **Edit**: Graph editing interface using ReactFlow
- **Roadmap**: Learning path visualization
- **Practice**: Adaptive question practice
- **Analytics**: Graph statistics and metrics
- **Settings**: User preferences

## Development Commands

### Environment Setup

Copy one of the environment templates and configure:
```bash
cp .env.example .env.dev
# Edit .env.dev with your configuration
```

Required environment variables:
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `PG_DSN`
- `OPENAI_API_KEY` (for AI features)
- `JWT_SECRET_KEY`, `BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_PASSWORD`
- `QDRANT_URL` (defaults to http://qdrant:6333)

### Docker Compose Operations

**Development mode** (with hot reload):
```bash
make up-dev
# Or explicitly:
docker compose --env-file .env.dev --profile dev up -d traefik fastapi-dev frontend-dev frontend-prod-hot
```

**Production mode**:
```bash
make up-prod
# Or explicitly:
docker compose --env-file .env.prod up -d traefik fastapi frontend
```

**Restart services**:
```bash
make restart-backend  # Restart FastAPI container
make restart-frontend # Rebuild and restart frontend
```

**View logs**:
```bash
make logs  # Show recent logs from traefik, fastapi, frontend
```

**Individual service logs**:
```bash
docker logs knowledgebase-fastapi-1 -f
docker logs knowledgebase-frontend-1 -f
docker logs knowledgebase-neo4j-1 -f
```

### Backend Development

**Install dependencies locally** (for IDE support):
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows
pip install -r requirements.txt
```

**Run tests**:
```bash
# From project root
pytest

# Run specific test file
pytest tests/unit/test_math_ontology_builder.py

# Run with verbose output
pytest -v

# Run tests matching pattern
pytest -k "test_kb_generate"
```

**Database migrations**:
```bash
cd backend
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

**Manual backend run** (outside Docker):
```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Development

**Install dependencies**:
```bash
cd frontend
npm install
```

**Run development server**:
```bash
npm run dev
# Runs on http://localhost:5173
```

**Build for production**:
```bash
npm run build
```

**Run tests**:
```bash
npm test        # Run vitest
npm run lint    # Run ESLint
```

**Preview production build**:
```bash
npm run preview
```

## Key Service Modules

### Backend Services

- `backend/app/services/graph/`: Neo4j repository and graph operations
  - `neo4j_repo.py`: Core Neo4j driver wrapper with retry logic
  - `graph_service.py`: Higher-level graph operations

- `backend/app/services/reasoning/`: Adaptive learning algorithms
  - `gaps.py`: Knowledge gap analysis
  - `next_best_topic.py`: Recommendation engine for next topics
  - `mastery_update.py`: Updates user mastery scores based on performance

- `backend/app/services/curriculum/`: Curriculum and roadmap generation
  - `repo.py`: Graph queries for curriculum data

- `backend/app/services/kb/`: Knowledge base content generation
  - `builder.py`: LLM-based content generation utilities

- `backend/app/services/ingestion/`: Import external content (PDF, text, TOC)

- `backend/app/services/auth/`: Authentication and user management
  - `users_repo.py`: User CRUD operations, bootstrap admin creation

- `backend/app/services/vector/`: Qdrant vector database operations

- `backend/app/services/visualization/`: Graph layout and geometry
  - `geometry.py`: Coordinate system transformations, layout algorithms

### API Routers

- `backend/app/api/engine.py`: Unified engine endpoints (viewport, roadmap, questions, navigation)
- `backend/app/api/auth.py`: Authentication (login, refresh, register)
- `backend/app/api/proposals.py`: Proposal system for graph modifications
- `backend/app/api/admin.py`: Admin operations (users, tenants)
- `backend/app/api/admin_graph.py`: Graph admin operations (import, export, reset)
- `backend/app/api/assistant.py`: AI assistant chat interface
- `backend/app/api/analytics.py`: Graph analytics and metrics
- `backend/app/api/ingestion.py`: Content ingestion from external sources
- `backend/app/api/maintenance.py`: Health checks and system status
- `backend/app/api/validation.py`: Schema validation utilities
- `backend/app/api/ws.py`: WebSocket connections for real-time updates

## Database Schema Migrations

Migrations are managed by Alembic and run automatically on container startup via `docker-entrypoint.sh`.

**Skip migrations** (for development):
```bash
SKIP_MIGRATIONS=true docker compose up
```

The entrypoint script:
1. Waits for PostgreSQL to be ready (up to 60s)
2. Runs `alembic upgrade head`
3. Starts the application

**Schema Version Gate**: `backend/app/core/migrations.py` contains `check_and_gatekeep()` which validates the database schema version on startup. If schema is incompatible, the app will refuse to start.

## Logging and Observability

**Structured Logging**: Uses `structlog` for JSON-formatted logs. See `backend/app/core/logging.py`.

**Context Tracking**:
- `X-Correlation-ID`: Traces requests across service boundaries
- `X-Request-ID`: Unique identifier per HTTP request
- `X-Tenant-ID`: Multi-tenant context

**Prometheus Metrics**: Available at `/metrics` endpoint when `PROMETHEUS_ENABLED=true`.
- `http_requests_total`: Request counter by method, path, status
- `http_request_latency_ms`: Request latency histogram

**Monitoring Stack** (optional):
```bash
docker compose --profile monitoring up prometheus grafana
```
- Prometheus: http://prom.${KB_DOMAIN}
- Grafana: http://grafana.${KB_DOMAIN}

## Coordinate System

The visualization system recently changed from canvas-based to logical Cartesian coordinates:
- Origin (0,0) is at center
- Y-axis increases upward (mathematical convention)
- All layout algorithms work in logical space
- Frontend is responsible for canvas transformations

See `backend/app/services/visualization/geometry.py` for coordinate utilities.

## Common Development Workflows

### Adding a New Graph Node Type

1. Add to `ALLOWED_NODE_LABELS` in `backend/app/core/canonical.py`
2. Create schema in `backend/app/schemas/` if needed
3. Add validation logic if required
4. Update frontend type definitions in `frontend/src/schemas.ts`

### Adding a New API Endpoint

1. Create or update router in `backend/app/api/`
2. Define Pydantic request/response models
3. Include router in `backend/app/main.py`
4. Add to appropriate OpenAPI tag
5. Update frontend API client in `frontend/src/api.ts`

### Testing with Neo4j Browser

Access Neo4j Browser at http://localhost:7474 (or graph.${KB_DOMAIN} in production).

Useful Cypher queries:
```cypher
// View all node types
MATCH (n) RETURN DISTINCT labels(n), COUNT(n)

// View all relationship types
MATCH ()-[r]->() RETURN DISTINCT type(r), COUNT(r)

// View specific topic with relationships
MATCH (t:Topic {uid: "your-topic-uid"})-[r]-(n)
RETURN t, r, n

// Check for orphaned nodes
MATCH (n) WHERE NOT (n)--() RETURN n LIMIT 10
```

## Traefik Routing

All services are proxied through Traefik with automatic HTTPS via Let's Encrypt.

Service URLs (replace ${KB_DOMAIN} with your domain):
- Frontend: https://${KB_DOMAIN}
- API: https://api.${KB_DOMAIN}
- Neo4j Browser: https://graph.${KB_DOMAIN}
- Qdrant: https://qdrant.${KB_DOMAIN}
- Adminer (PostgreSQL): https://adminer.${KB_DOMAIN}
- Traefik Dashboard: https://traefik.${KB_DOMAIN}

Alternative domain (`KB_ALT_DOMAIN`) mirrors all routes for multi-domain support.

## Dependencies

### Backend Key Dependencies
- FastAPI 0.115.0: Web framework
- Neo4j 5.23.0: Graph database driver
- SQLAlchemy 2.0+: PostgreSQL ORM
- Alembic 1.13+: Database migrations
- Pydantic 2.9.2: Data validation
- OpenAI SDK 1.52.0+: LLM integration
- Instructor 1.5.0+: Structured outputs from LLMs
- Qdrant Client 1.7.0+: Vector database
- Strawberry GraphQL 0.211.0: GraphQL API (optional)
- pytest 8.3.2: Testing framework

### Frontend Key Dependencies
- React 19.2.0
- TypeScript 5.9.3
- Redux Toolkit 2.11.2
- React Router v7.9.0
- vis-network 9.1.9: Graph visualization
- reactflow 11.11.4: Graph editing
- d3 7.9.0: Data visualization
- Vite 7.2.4: Build tool
- Vitest 4.0.16: Testing framework

## Testing Strategy

**Backend**: pytest-based unit tests in `tests/` directory. Focus on:
- KB generation logic (`test_kb_generate_smart.py`)
- Math ontology builder (`test_math_ontology_builder.py`)
- Graph operations and canonical transformations

**Frontend**: Vitest with jsdom for component and utility testing.

**Configuration**: `pytest.ini` configures warning suppression for cleaner output.

## Security Notes

- **Authentication**: JWT-based with access and refresh tokens
- **Multi-tenancy**: Enforced via middleware, tenant context flows through all operations
- **Admin Bootstrap**: First admin user is created on startup from `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD`
- **Secrets**: Use SecretStr from Pydantic for sensitive config (API keys, passwords)
- **CORS**: Configured via `CORS_ALLOW_ORIGINS` environment variable

## Known Patterns

### Graph Queries
Always use the `Neo4jRepo` class with retry logic. Direct driver usage should be avoided except in low-level utilities.

### Async Operations
FastAPI endpoints are async. Use `await` for all I/O operations including Neo4j queries (via thread pool executor), database queries, and LLM calls.

### Error Handling
Use `ApiError` from `backend/app/api/common.py` for consistent error responses. All errors include `request_id` and `correlation_id` for tracing.

### LLM Calls
Use `openai_chat_async` from `backend/app/services/kb/builder.py` for LLM interactions. It handles rate limiting, retries, and structured outputs via Instructor.
