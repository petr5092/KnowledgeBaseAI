# KnowledgeBaseAI Backend

FastAPI backend for KnowledgeBaseAI: stateless knowledge graph API, admin tooling, background jobs, and authentication.

## Tech stack

- Python 3.12
- FastAPI + Uvicorn
- Neo4j (graph storage)
- Postgres (users/auth, curriculum repository)
- Redis + ARQ (background jobs)
- Qdrant (vector search)
- Prometheus (metrics)

## Architecture overview

- `src/main.py` — FastAPI application entrypoint, routers, middleware.
- `src/config/settings.py` — typed settings via `pydantic-settings`.
- `src/api/*` — HTTP API routers.
- `src/services/*` — domain logic (graph, curriculum, AI, vector, planner).
- `src/services/auth/*` — JWT auth, password hashing, users repository.

## Authentication & authorization

### JWT

- Access token: short-lived (`JWT_ACCESS_TTL_SECONDS`, default 900s)
- Refresh token: long-lived (`JWT_REFRESH_TTL_SECONDS`, default 1209600s)
- Algorithm: HS256

Required env:

- `JWT_SECRET_KEY`

### Bootstrap first admin

On application startup, if both variables are set:

- `BOOTSTRAP_ADMIN_EMAIL`
- `BOOTSTRAP_ADMIN_PASSWORD`

backend will ensure an admin user exists (idempotent):

- if user exists u0016 promotes to `admin`
- if not u0016 creates new admin user

### Protected routes

All `/v1/admin/*` routes require an **admin** access token:

- `Authorization: Bearer <access_token>`

## API

### Health

- `GET /health`

### Auth

- `POST /v1/auth/register`
- `POST /v1/auth/login`
- `POST /v1/auth/refresh`
- `GET /v1/auth/me`

### Admin (JWT admin only)

- `POST /v1/admin/purge_users`
- `POST /v1/admin/curriculum`
- `POST /v1/admin/curriculum/nodes`
- `GET /v1/admin/curriculum/graph_view`
- `POST /v1/admin/generate_subject`
- `POST /v1/admin/generate_subject_import`

### Graph / user-facing

See `src/api/*` routers for the full list. Key endpoints are documented in the root README.

## Configuration

Backend reads env from the root env file selected by `ENV_FILE` (see root docs).

Key variables:

- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
- `PG_DSN`
- `REDIS_URL` (if used by ARQ)
- `QDRANT_URL`
- `OPENAI_API_KEY`
- `JWT_SECRET_KEY`, `JWT_ACCESS_TTL_SECONDS`, `JWT_REFRESH_TTL_SECONDS`
- `BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_PASSWORD`

## Development

See: [`development.md`](./development.md)

## Deployment

See: [`deployment.md`](./deployment.md)

## Testing

```bash
pytest -q
```