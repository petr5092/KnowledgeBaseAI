# Аудит репозитория KnowledgeBaseAI (Phase 0)

## Обзор модулей
- Граф/Neo4j: [neo4j_repo.py](file:///root/KnowledgeBaseAI/backend/src/services/graph/neo4j_repo.py), [neo4j_writer.py](file:///root/KnowledgeBaseAI/backend/src/services/graph/neo4j_writer.py), [graph_service.py](file:///root/KnowledgeBaseAI/backend/src/services/graph/graph_service.py), [utils.py](file:///root/KnowledgeBaseAI/backend/src/services/graph/utils.py), API: [graph.py](file:///root/KnowledgeBaseAI/backend/src/api/graph.py), [admin_graph.py](file:///root/KnowledgeBaseAI/backend/src/api/admin_graph.py), импорт: [push_to_neo4j.py](file:///root/KnowledgeBaseAI/backend/scripts/push_to_neo4j.py)
- Векторинг/Qdrant: [qdrant_service.py](file:///root/KnowledgeBaseAI/backend/src/services/vector/qdrant_service.py), [workers/vector_sync.py](file:///root/KnowledgeBaseAI/backend/src/workers/vector_sync.py), [workers/ingestion.py](file:///root/KnowledgeBaseAI/backend/src/workers/ingestion.py), эмбеддинги: [embeddings/provider.py](file:///root/KnowledgeBaseAI/backend/src/services/embeddings/provider.py)
- LLM/генерация: [admin_generate.py](file:///root/KnowledgeBaseAI/backend/src/api/admin_generate.py), [ai_engine.py](file:///root/KnowledgeBaseAI/backend/src/services/ai_engine/ai_engine.py), [kb/builder.py](file:///root/KnowledgeBaseAI/backend/src/services/kb/builder.py)
- Proposals/Commit/Outbox: схемы [schemas/proposal.py](file:///root/KnowledgeBaseAI/backend/src/schemas/proposal.py), сервис [services/proposal_service.py](file:///root/KnowledgeBaseAI/backend/src/services/proposal_service.py), коммит [workers/commit.py](file:///root/KnowledgeBaseAI/backend/src/workers/commit.py), outbox [workers/outbox_publisher.py](file:///root/KnowledgeBaseAI/backend/src/workers/outbox_publisher.py), события [events/publisher.py](file:///root/KnowledgeBaseAI/backend/src/events/publisher.py)
- Assessment/Questions: API [assessment.py](file:///root/KnowledgeBaseAI/backend/src/api/assessment.py), вопросы [services/questions.py](file:///root/KnowledgeBaseAI/backend/src/services/questions.py)
- Roadmap/Planner: [services/roadmap_planner.py](file:///root/KnowledgeBaseAI/backend/src/services/roadmap_planner.py), API [graph.py](file:///root/KnowledgeBaseAI/backend/src/api/graph.py#L187-L205)
- Assistant/Tools: [api/assistant.py](file:///root/KnowledgeBaseAI/backend/src/api/assistant.py), фронт [frontend/src/api.ts](file:///root/KnowledgeBaseAI/frontend/src/api.ts), [frontend/src/schemas.ts](file:///root/KnowledgeBaseAI/frontend/src/schemas.ts)
- Maintenance pipelines: [api/maintenance.py](file:///root/KnowledgeBaseAI/backend/src/api/maintenance.py), [services/jobs/rebuild.py](file:///root/KnowledgeBaseAI/backend/src/services/jobs/rebuild.py), [workers/integrity_async.py](file:///root/KnowledgeBaseAI/backend/src/workers/integrity_async.py)
- Интеграции/API слой: регистратор роутов [main.py](file:///root/KnowledgeBaseAI/backend/src/main.py), GraphQL [api/graphql.py](file:///root/KnowledgeBaseAI/backend/src/api/graphql.py) (опционально)

## Сущности графа (labels) и использование
| Label        | Где создаётся/используется |
|--------------|----------------------------|
| Subject      | MERGE в [utils.py](file:///root/KnowledgeBaseAI/backend/src/services/graph/utils.py#L103), выборки/иерархия в [utils.py](file:///root/KnowledgeBaseAI/backend/src/services/graph/utils.py#L145-L157) |
| Section      | MERGE в [utils.py](file:///root/KnowledgeBaseAI/backend/src/services/graph/utils.py#L104), иерархия [utils.py](file:///root/KnowledgeBaseAI/backend/src/services/graph/utils.py#L151-L157) |
| Topic        | MERGE в [utils.py](file:///root/KnowledgeBaseAI/backend/src/services/graph/utils.py#L105), выборки prereq [roadmap_planner.py](file:///root/KnowledgeBaseAI/backend/src/services/roadmap_planner.py#L12-L20) |
| Skill        | MERGE в [utils.py](file:///root/KnowledgeBaseAI/backend/src/services/graph/utils.py#L106), выборки связей [utils.py](file:///root/KnowledgeBaseAI/backend/src/services/graph/utils.py#L294-L296) |
| Method       | MERGE в [utils.py](file:///root/KnowledgeBaseAI/backend/src/services/graph/utils.py#L107), LINKED-цепочки [utils.py](file:///root/KnowledgeBaseAI/backend/src/services/graph/utils.py#L296-L297) |
| ContentUnit  | MERGE в [utils.py](file:///root/KnowledgeBaseAI/backend/src/services/graph/utils.py#L109), ветви обучения (legacy) [utils.py](file:///root/KnowledgeBaseAI/backend/src/services/graph/utils.py#L122-L124) |
| Goal         | MERGE в [utils.py](file:///root/KnowledgeBaseAI/backend/src/services/graph/utils.py#L127), TARGETS (legacy направление) [utils.py](file:///root/KnowledgeBaseAI/backend/src/services/graph/utils.py#L128) |
| Objective    | MERGE в [utils.py](file:///root/KnowledgeBaseAI/backend/src/services/graph/utils.py#L130), TARGETS (legacy направление) [utils.py](file:///root/KnowledgeBaseAI/backend/src/services/graph/utils.py#L131) |
| SourceChunk  | MERGE в [neo4j_writer.py](file:///root/KnowledgeBaseAI/backend/src/services/graph/neo4j_writer.py#L19-L20) как доказательства (EVIDENCED_BY) |
| Question     | Связь HAS_QUESTION из Topic [questions.py](file:///root/KnowledgeBaseAI/backend/src/services/questions.py#L53) |

## Связи графа (relationship types) и использование
| Relationship       | Где используется |
|--------------------|------------------|
| CONTAINS           | Subject→Section, Section→Topic: [utils.py](file:///root/KnowledgeBaseAI/backend/src/services/graph/utils.py#L110-L111), выборки [roadmap_planner.py](file:///root/KnowledgeBaseAI/backend/src/services/roadmap_planner.py#L12-L20) |
| PREREQ             | Topic→Topic: [roadmap_planner.py](file:///root/KnowledgeBaseAI/backend/src/services/roadmap_planner.py#L13), [utils.py](file:///root/KnowledgeBaseAI/backend/src/services/graph/utils.py#L121) |
| USES_SKILL         | Topic→Skill: [utils.py](file:///root/KnowledgeBaseAI/backend/src/services/graph/utils.py#L113, L294-L296) |
| LINKED             | Skill→Method: [utils.py](file:///root/KnowledgeBaseAI/backend/src/services/graph/utils.py#L125) |
| TARGETS            | Topic→Goal/Objective (legacy): [utils.py](file:///root/KnowledgeBaseAI/backend/src/services/graph/utils.py#L128, L131, L487-L488) |
| HAS_SKILL          | Subject→Skill (legacy): [utils.py](file:///root/KnowledgeBaseAI/backend/src/services/graph/utils.py#L112, L463) |
| HAS_LEARNING_PATH  | Topic→ContentUnit (legacy): [utils.py](file:///root/KnowledgeBaseAI/backend/src/services/graph/utils.py#L122) |
| HAS_PRACTICE_PATH  | Topic→ContentUnit (legacy): [utils.py](file:///root/KnowledgeBaseAI/backend/src/services/graph/utils.py#L123) |
| HAS_MASTERY_PATH   | Topic→ContentUnit (legacy): [utils.py](file:///root/KnowledgeBaseAI/backend/src/services/graph/utils.py#L124) |
| HAS_QUESTION       | Topic→Question (legacy): [questions.py](file:///root/KnowledgeBaseAI/backend/src/services/questions.py#L53) |
| EVIDENCED_BY       | Node/Rel→SourceChunk (legacy): [neo4j_writer.py](file:///root/KnowledgeBaseAI/backend/src/services/graph/neo4j_writer.py#L19-L21, L38-L40, L59-L60) |

## Семантика прогресса
- Поля: `static_weight`, `dynamic_weight`, `confidence` на узлах Topic/Skill [utils.py](file:///root/KnowledgeBaseAI/backend/src/services/graph/utils.py#L285-L327, L364-L366)
- Использование в Roadmap: приоритизация тем по dynamic_weight и prereqs [roadmap_planner.py](file:///root/KnowledgeBaseAI/backend/src/services/roadmap_planner.py#L6-L37), [utils.py](file:///root/KnowledgeBaseAI/backend/src/services/graph/utils.py#L323-L327)
- Обновление mastery: пока явного единого метода нет; обновления implied через assessment/analytics. Требуется унификация в Phase 3/4.

## Импорт/генерация/коммит в Neo4j
- Импорт JSONL: [scripts/push_to_neo4j.py](file:///root/KnowledgeBaseAI/backend/scripts/push_to_neo4j.py) — прямой MERGE/UNWIND (обходит Proposal-пайплайн)
- LLM генерация: [api/admin_generate.py](file:///root/KnowledgeBaseAI/backend/src/api/admin_generate.py), [services/kb/builder.py](file:///root/KnowledgeBaseAI/backend/src/services/kb/builder.py) — отдает JSON, далее импорт в граф (местами прямые записи)
- Proposal-пайплайн: создание [schemas/proposal.py](file:///root/KnowledgeBaseAI/backend/src/schemas/proposal.py), проверка/коммит [workers/commit.py](file:///root/KnowledgeBaseAI/backend/src/workers/commit.py), запись в Neo4j [neo4j_writer.py](file:///root/KnowledgeBaseAI/backend/src/services/graph/neo4j_writer.py), событие Outbox [workers/outbox_publisher.py](file:///root/KnowledgeBaseAI/backend/src/workers/outbox_publisher.py)
- Вывод: существуют обходные пути прямых записей (импорт/maintenance), требуется сведение к единому конвейеру (Phase 1).

## Vector pipeline (Qdrant)
- Текущие коллекции:
  - `concepts` — отдельный сервис для Concept [qdrant_service.py](file:///root/KnowledgeBaseAI/backend/src/services/vector/qdrant_service.py#L8-L26)
  - `kb_entities` — общий индекс для событий graph_committed [workers/vector_sync.py](file:///root/KnowledgeBaseAI/backend/src/workers/vector_sync.py#L9-L20, L33-L69)
- Источники текста: `name`/`title` узла, либо `definition` для Concept [qdrant_service.py](file:///root/KnowledgeBaseAI/backend/src/services/vector/qdrant_service.py#L21-L27)
- Эмбеддинги: OpenAI text-embedding-3-small (1536) для Concepts; generic provider для kb_entities, размер из настроек [vector_sync.py](file:///root/KnowledgeBaseAI/backend/src/workers/vector_sync.py#L33-L55)
- Требуется унификация: векторить только Concept, Method, ContentUnit, Example; стандартные payload и коллекции (Phase 5).

## API surface
- Роуты регистрируются в [main.py](file:///root/KnowledgeBaseAI/backend/src/main.py#L216-L234). Основные:
  - `/v1/graph/*` — roadmap, adaptive_questions, viewport, explain_relation [api/graph.py](file:///root/KnowledgeBaseAI/backend/src/api/graph.py)
  - `/v1/assessment/*` — получение вопросов/оценка [api/assessment.py](file:///root/KnowledgeBaseAI/backend/src/api/assessment.py)
  - `/v1/proposals/*` — заявки/коммит [api/proposals.py](file:///root/KnowledgeBaseAI/backend/src/api/proposals.py)
  - `/v1/assistant/*` — ассистент/инструменты [api/assistant.py](file:///root/KnowledgeBaseAI/backend/src/api/assistant.py)
  - `/v1/maintenance/*` — обслуживание/валидации [api/maintenance.py](file:///root/KnowledgeBaseAI/backend/src/api/maintenance.py)
  - Админ-генерация/граф: [api/admin_generate.py](file:///root/KnowledgeBaseAI/backend/src/api/admin_generate.py), [api/admin_graph.py](file:///root/KnowledgeBaseAI/backend/src/api/admin_graph.py)
- Дубли и расхождения форматов присутствуют; потребуется стандартизация под LMS StudyNinja (Phase 6).

## Ключевые выводы Phase 0
- Обнаружены неканоничные связи: HAS_SKILL, HAS_LEARNING_PATH/HAS_PRACTICE_PATH/HAS_MASTERY_PATH, HAS_QUESTION, TARGETS (направление), EVIDENCED_BY.
- Существуют прямые записи в Neo4j вне Proposal-пайплайна (импорт/maintenance).
- Векторинг неоднороден и выходит за рамки канона (общая коллекция kb_entities).
- Не единая метрика знания: используются static_weight/dynamic_weight вместо mastery.
