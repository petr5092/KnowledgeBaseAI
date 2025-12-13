# KnowledgeBaseAI

[![CI](https://github.com/AndrewHakmi/KnowledgeBaseAI/actions/workflows/ci.yml/badge.svg)](https://github.com/AndrewHakmi/KnowledgeBaseAI/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-BUSL--1.1-blue)](#license)
[![Backend](https://img.shields.io/badge/backend-FastAPI-009688)](./backend/README.md)
[![Frontend](https://img.shields.io/badge/frontend-React%20%2B%20Vite-61DAFB)](./frontend/README.md)
[![Graph](https://img.shields.io/badge/graph-Neo4j-4581C3)](https://neo4j.com/)
[![Vector](https://img.shields.io/badge/vector-Qdrant-FF4D4D)](https://qdrant.tech/)

KnowledgeBaseAI is a **knowledge graph platform** that turns fragmented learning content into a structured, queryable, and explainable graph of concepts, skills, methods, and prerequisites.

It is designed to power:

- adaptive learning paths
- curriculum planning
- knowledge analytics and quality control
- AI-assisted knowledge construction

## Live

- UI: https://kb.studyninja.ru, https://kb.xteam.pro
- API: https://api.kb.studyninja.ru, https://api.kb.xteam.pro

## Why it matters

Most learning platforms store content as pages and videos. KnowledgeBaseAI stores it as a **graph**:

- prerequisites become explicit
- gaps and inconsistencies become measurable
- learning paths become computable
- explanations become traceable ("why this topic next")

## What you can build on top

- LMS integrations (progress in, recommendations out)
- adaptive roadmaps per learner
- content QA dashboards (coverage, orphan nodes, missing links)
- AI copilots for curriculum designers

## Product highlights

- **Stateless core**: user progress can live in an external LMS; the platform focuses on graph intelligence.
- **Graph-first model**: subjects → sections → topics → skills → methods, with prerequisites and weighted links.
- **Admin tooling**: generate/import knowledge bases, recompute weights, validate snapshots.
- **Observability-ready**: Prometheus metrics, structured logging.

## Quickstart (Docker)

```bash
cp .env.example .env.dev
ENV_FILE=.env.dev docker compose --env-file .env.dev up -d --build
```

## Documentation (technical)

This README stays product-focused. Technical details live in dedicated docs:

- Backend overview: [`backend/README.md`](./backend/README.md)
- Frontend overview: [`frontend/README.md`](./frontend/README.md)
- Backend development: [`backend/development.md`](./backend/development.md)
- Backend deployment: [`backend/deployment.md`](./backend/deployment.md)
- Frontend development: [`frontend/development.md`](./frontend/development.md)
- Frontend deployment: [`frontend/deployment.md`](./frontend/deployment.md)

## Technical summary (short)

- Backend: FastAPI (Python 3.12)
- Frontend: React + TypeScript + Vite
- Storage: Neo4j (graph), Postgres (users/auth), Qdrant (vectors)
- Jobs: Redis + ARQ
- Edge: Traefik (TLS + routing)

## Security model (short)

- JWT authentication (`/v1/auth/*`)
- Admin endpoints protected by role-based access (`/v1/admin/*`)
- Bootstrap first admin via env on first deploy

## Roadmap (global)

### Phase 1 — Platform hardening
- production-grade auth hardening (rate limiting, password policy, audit logs)
- migrations for Postgres schema
- operational playbooks (backup/restore, incident response)

### Phase 2 — Integrations & ecosystem
- LMS connectors (import progress, export recommendations)
- OpenAPI client generation and SDKs
- webhooks/events for downstream systems

### Phase 3 — Intelligence layer
- improved graph quality scoring and anomaly detection
- explainable recommendations (traceable paths)
- hybrid retrieval (graph + vectors) for assistants

### Phase 4 — Productization
- multi-tenant support
- admin UI for curriculum designers
- enterprise deployment options

## Contributing

- Please read the development guides (backend/frontend).
- Use feature branches and open PRs.
- Never commit secrets (production env files must be ignored).

## License

This project is licensed under the **Business Source License 1.1 (BUSL-1.1)**.

See: [`LICENSE`](./LICENSE)