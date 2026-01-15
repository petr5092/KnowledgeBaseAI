# Архитектура KnowledgeBaseAI

## Общее описание
- Ядро KnowledgeBaseAI предоставляет REST API для чтения и безопасной модификации графа знаний.
- Три основных слоя:
  - `app/api` — HTTP-роуты FastAPI.
  - `app/services` — бизнес‑логика: граф, валидация, reasoning, индексатор вектора.
  - `app/repositories` и `app/db` — доступ к Neo4j и Postgres.
- Асинхронные воркеры (`app/workers`, `app/tasks`) обслуживают конвейер событий и индексацию.

## Директории и роли
- API: [main.py](file:///c:/Users/freak/TRAE/KnowledgeBaseAI/backend/app/main.py), [admin_graph.py](file:///c:/Users/freak/TRAE/KnowledgeBaseAI/backend/app/api/admin_graph.py), [graph.py](file:///c:/Users/freak/TRAE/KnowledgeBaseAI/backend/app/api/graph.py)
- Core: контекст, логирование, канон — [canonical.py](file:///c:/Users/freak/TRAE/KnowledgeBaseAI/backend/app/core/canonical.py), [context.py](file:///c:/Users/freak/TRAE/KnowledgeBaseAI/backend/app/core/context.py)
- Services:
  - Граф и Neo4j: [neo4j_repo.py](file:///c:/Users/freak/TRAE/KnowledgeBaseAI/backend/app/services/graph/neo4j_repo.py), [graph_service.py](file:///c:/Users/freak/TRAE/KnowledgeBaseAI/backend/app/services/graph/graph_service.py)
  - Целостность: [integrity.py](file:///c:/Users/freak/TRAE/KnowledgeBaseAI/backend/app/services/integrity.py)
  - Reasoning/roadmap: [roadmap_planner.py](file:///c:/Users/freak/TRAE/KnowledgeBaseAI/backend/app/services/roadmap_planner.py)
  - Векторная индексация: [vector_sync.py](file:///c:/Users/freak/TRAE/KnowledgeBaseAI/backend/app/workers/vector_sync.py), [indexer.py](file:///c:/Users/freak/TRAE/KnowledgeBaseAI/backend/app/services/vector/indexer.py)
- Workers:
  - Коммит предложений: [commit.py](file:///c:/Users/freak/TRAE/KnowledgeBaseAI/backend/app/workers/commit.py)
  - Outbox publisher: [outbox_publisher.py](file:///c:/Users/freak/TRAE/KnowledgeBaseAI/backend/app/workers/outbox_publisher.py)
  - Планировщик задач: [worker.py](file:///c:/Users/freak/TRAE/KnowledgeBaseAI/backend/app/tasks/worker.py)
- DB: Postgres DAO — [pg.py](file:///c:/Users/freak/TRAE/KnowledgeBaseAI/backend/app/db/pg.py)

## Канон графа
- Разрешённые узлы и связи описаны в [CANONICAL_SPEC.md](file:///c:/Users/freak/TRAE/KnowledgeBaseAI/docs/CANONICAL_SPEC.md).
- Проверка канона централизована: `check_canon_compliance` в [integrity.py](file:///c:/Users/freak/TRAE/KnowledgeBaseAI/backend/app/services/integrity.py).

## Мультитенантность
- `tenant_id` обязателен для всех операций записи.
- Все запросы к Neo4j фильтруются по `tenant_id` в репозитории [neo4j_repo.py](file:///c:/Users/freak/TRAE/KnowledgeBaseAI/backend/app/services/graph/neo4j_repo.py).
- Извлечение `tenant_id` из заголовка `X-Tenant-ID` или JWT — [context.py](file:///c:/Users/freak/TRAE/KnowledgeBaseAI/backend/app/core/context.py).

## Роли и безопасность
- Проверки ролей реализованы через зависимости FastAPI в слое API.
- Админские операции доступны только при `require_admin`.
- Любые изменения графа идут через Proposal Pipeline.

## Proposal Pipeline
- Создание и коммит описаны в [proposals.py](file:///c:/Users/freak/TRAE/KnowledgeBaseAI/backend/app/api/proposals.py) и [commit.py](file:///c:/Users/freak/TRAE/KnowledgeBaseAI/backend/app/workers/commit.py).
- Операции: `CREATE_NODE`, `UPDATE_NODE`, `DELETE_NODE`, `CREATE_REL`, `UPDATE_REL`, `DELETE_REL` — [schemas/proposal.py](file:///c:/Users/freak/TRAE/KnowledgeBaseAI/backend/app/schemas/proposal.py).
- Этапы:
  - Сохранение заявки в Postgres Outbox
  - Integrity Gate: циклы `PREREQ`, канон, правила `BASED_ON`
  - Коммит в Neo4j с учётом `tenant_id`
  - Запись в журнал аудита и `graph_version`
  - Публикация события `graph_committed` в Redis
  - Индексация Qdrant воркером `vector_sync`

## События и индексация
- Outbox в Postgres: `events_outbox` — [pg.py](file:///c:/Users/freak/TRAE/KnowledgeBaseAI/backend/app/db/pg.py).
- Публикация событий — [publisher.py](file:///c:/Users/freak/TRAE/KnowledgeBaseAI/backend/app/events/publisher.py).
- Консьюминг и индексация — [vector_sync.py](file:///c:/Users/freak/TRAE/KnowledgeBaseAI/backend/app/workers/vector_sync.py).

## Интеграция с LMS/StudyNinja
- Чтение графа и построение дорожной карты — [graph.py](file:///c:/Users/freak/TRAE/KnowledgeBaseAI/backend/app/api/graph.py), [roadmap_planner.py](file:///c:/Users/freak/TRAE/KnowledgeBaseAI/backend/app/services/roadmap_planner.py).
- Прогресс пользователя хранится во внешнем LMS, в ядре не создаются узлы `User`.

