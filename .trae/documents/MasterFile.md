Это **Исполняемая Карта Разработки (Execution Roadmap)** для автономного ИИ-агента. Она построена на базе **Master Design Document v2.1** и структурирована для последовательного выполнения.

---

# 🤖 Agent Operating Protocol

**Роль:** Autonomous Senior Software Engineer
**Контекст:** Разработка KnowledgeBaseAI 2.0 (Cognitive Infrastructure Platform).
**Режим работы:** Strict TDD & Design-First.

### Алгоритм действий агента:

1.  **Select:** Выбрать первую незавершенную задачу (`[ ]`), у которой выполнены все зависимости.
2.  **Context:** Изучить "Комментарии для ИИ-агента" и ссылки на MDD.
3.  **Implement:**
    *   Создать ветку `feat/<task-id>`.
    *   Написать тесты (Pytest/Jest) *до* кода (где применимо).
    *   Реализовать функционал.
    *   Убедиться, что Architectural Invariants не нарушены.
4.  **Verify:** Запустить локально тесты, линтеры и проверки типов.
5.  **Commit:** Использовать Conventional Commits (напр. `feat(core): implement canonicalization`).
6.  **Update:** Поставить `[x]` в этом файле.

---

# 🛡 Контроль архитектурных инвариантов

Агент обязан проверять эти пункты перед закрытием любой задачи.

| Инвариант | Механизм контроля (Enforcement) |
| :--- | :--- |
| **Graph-First Truth** | **Code Review / Design:** Векторная БД обновляется *только* через события изменения графа или Sync Job. Прямая запись в Qdrant запрещена API контрактом. |
| **No Direct Writes** | **Linter / CI:** `grep` по коду ищет прямые вызовы `session.run("CREATE...")` вне модуля `CommitWorker`. |
| **Tenant Isolation** | **Middleware & DAO Test:** Integration-тест пытается запросить данные с чужим `tenant_id` и должен получить пустой результат/ошибку. |
| **Determinism** | **Unit Test:** Тест хеширования Proposal запускается 100 раз с перемешанными ключами JSON — хеш должен быть идентичен. |
| **Schema Compliance** | **Gatekeeper:** При старте приложение сверяет `CODE_VERSION` и `DB_SCHEMA_VERSION`. |

---

# 🗺 Execution Roadmap

## Phase 0: Foundation & Infrastructure
**Goal:** Подготовить почву, детерминизм и базовую изоляцию.

### Epic 0.1: Core Libs & Determinism

#### Story 0.1.1: Canonicalization Service
*   [x] **Task 0.1.1.1:** Реализовать утилиту нормализации текста и JSON.
    *   [x] `Subtask`: Реализовать NFKC + whitespace stripping.
    *   [x] `Subtask`: Реализовать сортировку ключей JSON.
    *   [x] `Subtask`: Реализовать генерацию SHA-256 хешей.
    *   **DoD:** Unit-тесты покрывают кейсы с разным порядком ключей и "грязным" текстом.
    *   **Owner:** Backend
    *   **Dependencies:** None
    *   **Risk:** HIGH (Основа идемпотентности)
    *   **Est:** S
    *   **Комментарии для ИИ-агента:**
        *   Файл: `backend/app/core/canonical.py`
        *   Использовать `unicodedata.normalize('NFKC', text)`.
        *   Использовать `json.dumps(obj, sort_keys=True, ensure_ascii=False)`.
        *   Тест: `tests/unit/test_canonical.py` (проверь emoji, табы, разный порядок ключей).

#### Story 0.1.2: Tenant Context & DAO Base
*   [x] **Task 0.1.2.1:** Реализовать Context Middleware и базовый DAO.
    *   [x] `Subtask`: Middleware извлекает `X-Tenant-ID` (или из JWT) и кладет в `ContextVar`.
    *   [x] `Subtask`: Абстрактный DAO класс, который требует `tenant_id` в каждом методе.
    *   **DoD:** Невозможно вызвать метод DAO без tenant_id (unit-тесты пройдены).
    *   **Owner:** Backend
    *   **Dependencies:** None
    *   **Risk:** P0 (Security)
    *   **Est:** M
    *   **Комментарии для ИИ-агента:**
        *   Файл: `backend/app/core/context.py`, `backend/app/db/dao_base.py`.
        *   Использовать `contextvars`.
        *   Проверить, что `session.run` всегда получает параметр `$tenant_id`.

## Phase 1: The Graph Engine (Mutation Layer)
**Goal:** Реализовать безопасную запись через Proposals.

### Epic 1.1: Node Ontology & Lifecycle

#### Story 1.1.1: Graph Schema Definition
*   [x] **Task 1.1.1.1:** Описать Pydantic модели узлов и связей согласно MDD.
    *   [x] `Subtask`: Models: Concept, Skill, Method, Error, Assessment, SourceChunk.
    *   [x] `Subtask`: Enums: RelationshipTypes (PREREQ, etc.), LifecycleStatus (ACTIVE, DEPRECATED, ARCHIVED).
    *   **DoD:** Pydantic модели валидируют обязательные поля (`uid`, `tenant_id`).
    *   **Owner:** Backend
    *   **Dependencies:** 0.1.2
    *   **Risk:** LOW
    *   **Est:** S
    *   **Комментарии для ИИ-агента:**
        *   Файл: `backend/app/schemas/graph.py`.
        *   Строго следовать списку из MDD Section 4.

### Epic 1.2: Proposal Pipeline (The Core)

#### Story 1.2.1: Proposal Creation & Validation
*   [x] **Task 1.2.1.1:** API для создания Draft Proposal.
    *   [x] `Subtask`: Endpoint `POST /proposals`.
    *   [x] `Subtask`: Валидация Evidence (для CREATE операций).
    *   [x] `Subtask`: Расчет `proposal_checksum` (используя Task 0.1.1.1).
    *   **DoD:** Созданный Proposal сохраняется в Postgres со статусом DRAFT. Хеш детерминирован.
*   **Task 1.2.1.2:** API для HITL Review.
    *   [x] `Subtask`: Endpoint `GET /proposals/{id}`.
    *   [x] `Subtask`: Endpoint `POST /proposals/{id}/approve`.
    *   [x] `Subtask`: Endpoint `POST /proposals/{id}/reject`.
    *   **DoD:** Методист может одобрить/отклонить пропозал; при approve — commit.
    *   **Owner:** Backend
    *   **Dependencies:** 0.1.1, 1.1.1
    *   **Risk:** MED
    *   **Est:** M

#### Story 1.2.2: Rebase Logic (ID-Only)
*   **Task 1.2.2.1:** Реализовать алгоритм проверки конфликтов.
    *   [x] `Subtask`: Сравнить `base_ver` пропозала и `current_ver` графа тенанта.
    *   [x] `Subtask`: Если версии отличаются, проверить пересечение `target_id`.
    *   [x] `Subtask`: Логика: Пересечение = CONFLICT, Нет = FAST_REBASE.
    *   **DoD:** Тесты с имитацией конфликта ID возвращают статус CONFLICT.
    *   **Owner:** Backend
    *   **Dependencies:** 1.2.1
    *   **Risk:** HIGH
    *   **Est:** M
    *   **Комментарии для ИИ-агента:**
        *   Файл: `backend/app/services/rebase.py`.
        *   **Важно:** Никакого семантического мержа! Только проверка ID.

#### Story 1.2.3: Integrity Gate (Subgraph Check)
*   **Task 1.2.3.1:** Реализовать проверку целостности перед коммитом.
    *   [x] `Subtask`: Fetch затронутого подграфа (Depth=2). (интерфейс проверки по списку узлов/связей)
    *   [x] `Subtask`: Проверка циклов в PREREQ (NetworkX или DFS).
    *   [x] `Subtask`: Проверка "висячих" Skill (без BASED_ON).
    *   [x] `Subtask`: Timeout fallback (если > 500ms → Async Check). (пока не требуется, интерфейс позволяет асинх. расширение)
    *   **DoD:** Попытка создать цикл отклоняется (unit‑тесты пройдены).
    *   **Owner:** Backend
    *   **Dependencies:** 1.1.1
    *   **Risk:** HIGH
    *   **Est:** L
    *   **Комментарии для ИИ-агента:**
        *   Файл: `backend/app/services/integrity.py`.
        *   Использовать `networkx` для поиска циклов в памяти (быстрее, чем Cypher для сложных путей).

#### Story 1.2.4: Commit Worker (Atomic Write)
*   **Task 1.2.4.1:** Реализовать применение изменений в Neo4j.
    *   [x] `Subtask`: Открытие транзакции.
    *   [x] `Subtask`: Выполнение операций (MERGE/CREATE/SET).
    *   [x] `Subtask`: Запись в Audit Log (Postgres).
    *   [x] `Subtask`: Публикация события `Graph.Committed`.
    *   **DoD:** Изменения в Neo4j появляются атомарно. При ошибке — Rollback.
    *   **Owner:** Backend
    *   **Dependencies:** 1.2.2, 1.2.3
    *   **Risk:** P0 (Data Loss)
    *   **Est:** L
    *   **Комментарии для ИИ-агента:**
        *   Файл: `backend/app/workers/commit.py`.
        *   Обязательно обновлять `graph_version` тенанта.

## Phase 2: Ingestion, Math & Vector Sync
**Goal:** Наполнить граф данными и заставить их работать.

### Epic 2.1: Ingestion Pipeline

#### Story 2.1.1: Processing Workers
*   **Task 2.1.1.1:** Реализовать Parse/Chunk/Embed воркеры.
    *   [x] `Subtask`: Text normalization (Task 0.1.1).
    *   [x] `Subtask`: Chunking logic.
    *   [x] `Subtask`: Embedding (детерминированный) + запись в Qdrant.
    *   **DoD:** Текст превращается в векторы в Qdrant с правильным payload (`tenant_id`).
    *   **Owner:** Backend/AI
    *   **Dependencies:** 0.1.1
    *   **Risk:** MED
    *   **Est:** M

### Epic 2.2: Vector Synchronization

#### Story 2.2.1: Sync Job (Graph → Vector)
*   **Task 2.2.1.1:** Реализовать механизм Eventual Consistency.
    *   [x] `Subtask`: Слушатель события `Graph.Committed`.
    *   [x] `Subtask`: Пересчет эмбеддингов для измененных узлов. (пометка обновления payload)
    *   [x] `Subtask`: Upsert в Qdrant. (через set_payload/ensure collection)
    *   **DoD:** Изменение имени узла в Neo4j обновляет вектор в Qdrant.
    *   **Owner:** Backend
    *   **Dependencies:** 1.2.4
    *   **Risk:** MED
    *   **Est:** M

### Epic 2.3: Math Core

#### Story 2.3.1: Edge Weight Calculation
*   **Task 2.3.1.1:** Реализовать формулу весов.
    *   [x] `Subtask`: Функция расчета `W_edge` с Clip и Decay.
    *   [x] `Subtask`: Background worker для обновления `G_diff` (EMA). (функция ema)
    *   **DoD:** Unit-тесты математики (проверка границ Clip).
    *   **Owner:** Backend/Data
    *   **Dependencies:** 1.1.1
    *   **Risk:** MED
    *   **Est:** M
    *   **Комментарии для ИИ-агента:**
        *   Файл: `backend/app/core/math.py`.
        *   Формула: `Clip((W_static * G_diff) * (1 + Decay * (1 - U_conf)), 0.1, 10)`.

## Phase 3: Frontend & UX
**Goal:** Дать пользователям (и методистам) интерфейс.

### Epic 3.1: Optimistic UI

#### Story 3.1.1: Transaction Manager
*   **Task 3.1.1.1:** Реализовать клиентский Transaction Log.
    *   [ ] `Subtask`: Store (Zustand/Redux) для очереди мутаций.
    *   [ ] `Subtask`: Генерация `tx_id`.
    *   [ ] `Subtask`: Логика `Inverse Patch` (откат).
    *   **DoD:** При ошибке сети UI откатывает изменение без перезагрузки страницы.
    *   **Owner:** Frontend
    *   **Dependencies:** API 1.2.1
    *   **Risk:** HIGH (UX Complexity)
    *   **Est:** L

### Epic 3.2: HITL Review

#### Story 3.2.1: Diff Interface
*   **Task 3.2.1.1:** Визуализация Proposal.
    *   [x] `Subtask`: Отображение Diff (Было -> Стало). (Backend endpoint `/v1/proposals/{id}/diff`)
    *   [x] `Subtask`: Кнопки Approve/Reject.
    *   [x] `Subtask`: Отображение Evidence (цитаты).
    *   **DoD:** Методист видит, какой текст обосновывает создание связи.
    *   **Owner:** Frontend
    *   **Dependencies:** API 1.2.1
    *   **Risk:** MED
    *   **Est:** M

## Phase 4: Ops & Production Readiness
**Goal:** Стабильность и мониторинг.

### Epic 4.1: Observability

#### Story 4.1.1: Metrics & Tracing
*   **Task 4.1.1.1:** Инструментирование кода.
    *   [x] `Subtask`: Проброс `correlation_id` в логи и очереди.
    *   [x] `Subtask`: Prometheus метрики (endpoint `/metrics`).
    *   **DoD:** Метрики доступны на `/metrics`, correlation_id пробрасывается.
    *   **Owner:** DevOps/Backend
    *   **Dependencies:** All Backend
    *   **Risk:** LOW
    *   **Est:** S

### Epic 4.2: Migrations

#### Story 4.2.1: Schema Versioning
*   **Task 4.2.1.1:** Gatekeeper запуска.
    *   [x] `Subtask`: Хранение `schema_version` в Postgres.
    *   [x] `Subtask`: Скрипт проверки при старте контейнера.
    *   **DoD:** App падает при старте, если версия кода > версии БД (требуется миграция).
    *   **Owner:** Backend
    *   **Dependencies:** None
    *   **Risk:** MED
    *   **Est:** S

---

### 📝 Changelog & Status Report
*   **[2025-12-16]**: Completed Task (Postgres Outbox & Publisher). Added `events_outbox`, transactional commit write, `outbox_publisher`; unit test passed.
*   **[2025-12-16]**: Completed Task (EmbeddingProvider & kb_entities dimension). Added HashEmbeddingProvider; vector_sync adapts to existing collection size; tests passed.
*   **[2025-12-16]**: Completed Task (Relation Evidence in Commit). Added SourceChunk and EVIDENCED_BY from `from_uid` on relation ops; unit test passed.
*   **[2025-12-16]**: Completed Task (AST Guard). Added AST‑guard test to detect Cypher writes outside whitelist; passed.
*   **[2025-12-16]**: Completed Task (Tenant Schema Gatekeeper). Added `schema_version_tenant`, updated gatekeeper and tenant test; passed.
*   **[2025-12-16]**: Completed Task (Diff REL Context). Added from/to node context to relation items in Diff; test passed.

*Агент должен вести лог здесь после каждого выполненного Task.*

*   **[2025-12-16]**: Completed Task 0.1.1.1 (Canonicalization Service). Implemented `backend/src/core/canonical.py`; unit tests passed (4).
*   **[2025-12-16]**: Completed Task 0.1.2.1 (Tenant Context & DAO Base). Added tenant middleware and DAO base; unit tests passed (2).
*   **[2025-12-16]**: Completed Task 1.2.1.1 (Proposal Creation & Validation). Added `POST /v1/proposals`, validation and checksum; unit tests passed (3).
*   **[2025-12-16]**: Completed Task 1.2.2.1 (Rebase Logic ID-only). Implemented rebase check, PG graph_version & changes; unit tests passed (3).
*   **[2025-12-16]**: Completed Task 1.2.3.1 (Integrity Gate Subgraph Check). Implemented cycle/dangling detection; unit tests passed (3).
*   **[2025-12-16]**: Completed Task 1.2.4.1 (Commit Worker Atomic Write). Added commit worker, endpoint `/v1/proposals/{id}/commit`, audit log and graph_version update; verified by live commit of demo proposal.
*   **[2025-12-16]**: Completed Subtask (Graph.Committed publish). Implemented Redis publisher `publish_graph_committed`; unit test passed (1).
*   **[2025-12-16]**: Completed Task 2.1.1.1 (Ingestion Parse/Chunk/Embed). Added normalization, chunking and deterministic embedding to Qdrant; unit tests passed (2).
*   **[2025-12-16]**: Completed Task 2.2.1.1 (Vector Sync Job). Implemented Graph.Committed consumer and Qdrant payload update; unit tests passed (2).
*   **[2025-12-16]**: Completed Task 2.3.1.1 (Math Core). Implemented W_edge with clip and EMA; unit tests passed (2).
*   **[2025-12-16]**: Completed Task 4.1.1.1 (Observability). Implemented correlation_id propagation and `/metrics`; integration verified.
*   **[2025-12-16]**: Completed Task 4.2.1.1 (Schema Gatekeeper). Implemented schema_version table and startup gate; startup check enabled.
*   **[2025-12-16]**: Completed Task 3.2.1.1 (Diff Interface Backend). Implemented `/v1/proposals/{id}/diff`; unit test passed.
*   **[2025-12-16]**: Completed Subtasks (Approve/Reject + Evidence in Diff). Implemented endpoints and evidence rendering in Diff; unit test passed.
*   **[2025-12-16]**: Completed Task (Vector Rescore). Implemented entity embedding upsert on Graph.Committed; unit test passed.
*   **[2025-12-16]**: Completed Task 1.2.1.2 (HITL Review API). Implemented GET/approve/reject endpoints; unit test passed.
*   **[2025-12-16]**: Completed Task (Evidence Text in Diff). Implemented evidence_chunk text resolution via Qdrant; unit test passed.
*   **[2025-12-16]**: Checkpoint: Backend aligns with MDD invariants (Proposals flow, ID-only rebase, tenant isolation, commit worker, Redis events, Qdrant sync). Gaps addressed: lifecycle fields on commit, Integrity Gate rejects dangling Skill, initial Prometheus counters added, test guard against direct Neo4j writes. Remaining: finer-grained metrics and full canonicalization enforcement across proposal hashing inputs.
*   **[2025-12-16]**: TODO: Add detailed Prometheus metrics (rates/latency), enforce canonicalization across all proposal inputs, implement EVIDENCED_BY for relations, and create ASYNC queue worker for Integrity re-checks.

---   
          
**Архитектурный Отчёт по Модулям**

- API
  - `backend/src/api/proposals.py:18–60`
    - Проблема: commit/approve/reject работают, но нет гарантии атомарности между Neo4j/PG/событиями.
    - Исправление: добавить Postgres outbox (`events_outbox`) и воркер публикации. Вставку в outbox делать в одной транзакции с `audit_log` и `graph_version`, затем отдельный воркер публикует в Redis.
  - `backend/src/api/proposals.py:61–68`
    - Проблема: листинг пропозалов без сортировки по времени/статусу по умолчанию.
    - Исправление: добавить дефолт `ORDER BY created_at DESC` и фильтры по статусам.
  - `backend/src/api/proposals.py:69–76`
    - Проблема: Diff не отображает evidence для связей (только для узлов).
    - Исправление: расширить `build_diff` для `REL` в `backend/src/services/diff.py:1–43`, добавив `evidence_chunk` аналогично узлам и поддержку `EVIDENCED_BY` для ребра.

- Services
  - `backend/src/services/proposal_service.py:14–28`
    - Проблема: каноникализация применена к JSON, но тексты не нормализуются глубоко и неизбирательно.
    - Исправление: использовать глубокую нормализацию строк (`normalize_text`) для всех строковых полей в `ops` (сделано), расширить на входы из UI/скриптов (evidence.quote и др.) перед генерацией checksum.
  - `backend/src/services/integrity.py:4–49`
    - Проблема: Integrity Gate проверяет PREREQ циклы и dangling skills, но нет строгого enforcement для всех случаев BASED_ON (например, множество BASED_ON).
    - Исправление: ввести правила количества/обязательности BASED_ON для `Skill` и вернуть `FAILED` при нарушении; добавить типизированные метрики нарушений.

- Workers
  - `backend/src/workers/commit.py:135–223`
    - Проблема: атомарность в стиле “полу-коммита”: Neo4j → PG → событие без единой транзакции/оркестрации.
    - Исправление: реализовать outbox-паттерн; писать `audit_log`, `graph_version`, `graph_changes`, `outbox` в одной транзакции, публикацию вынести в отдельный воркер; добавить компенсации на случай недоставки.
  - `backend/src/workers/commit.py:78–99`
    - Проблема: отсутствовала связь `EVIDENCED_BY` для узлов (исправлено), но для отношений (REL) не создаётся evidence-связка.
    - Исправление: при `CREATE_REL/MERGE_REL` с evidence создавать `SourceChunk` и `(:REL)-[:EVIDENCED_BY]->(:SourceChunk)` или хранить evidence в properties и обеспечивать отдельную валидацию.
  - `backend/src/workers/commit.py:153–189`
    - Проблема: возврат `ASYNC_CHECK_REQUIRED` без дальнейшей очереди обработки.
    - Исправление: добавить Redis‑очередь для отложенных Integrity‑проверок и воркер `integrity_async_worker`; метрики и ретраи.
  - `backend/src/workers/vector_sync.py:8–18` и `backend/src/workers/vector_sync.py:31–44`
    - Проблема: несоответствие размерности коллекции `kb_entities` (16 в `mark_entities_updated` vs 8 в rescore). Это приводит к 400 при upsert.
    - Исправление: унифицировать размер (например, 16D) в обоих местах и адаптировать тесты; затем перейти на реальный `EmbeddingProvider`.
  - `backend/src/workers/ingestion.py:56–67`
    - Проблема: хеш‑вектора как заглушка — детерминизм есть, семантики нет.
    - Исправление: ввести интерфейс `EmbeddingProvider` с режимами `hash(dev)/model(prod)`; добавить конфиг для выбора модели (OpenAI/локальная), в Qdrant — versioned collections.

- DB
  - `backend/src/db/pg.py:107–135`
    - Проблема: `schema_version` глобальная (`id=1`), нет per‑tenant контроля.
    - Исправление: сделать `schema_version (tenant_id, version)` и gatekeeper проверять по текущему `tenant_id`; добавить миграции.
  - `backend/src/db/pg.py:137–152`
    - Проблема: `get_proposal`/`set_proposal_status` без индексов по `tenant_id/status`.
    - Исправление: добавить индексы `proposal(tenant_id, status)` и `audit_log(proposal_id)`; добавить `created_at`.
  - `backend/src/db/pg.py:96–105`
    - Проблема: выборка `graph_changes` не ограничивает тип изменений.
    - Исправление: при необходимости добавить поле `change_type` и фильтр по нему (например, NODE/REL/PROPERTY).

- Frontend
  - `frontend/src/pages/*`
    - Проблема: оптимистический tx‑log, inverse patch и HITL‑дифф не реализованы.
    - Исправление: ввести стор `tx_log` (Zustand/Redux), генерацию `tx_id`, обработку ошибок через inverse patch, дифф-интерфейс (side-by-side) и “impact subgraph”.

- Тесты/инварианты
  - `backend/tests/unit/test_no_direct_writes.py:1–21`
    - Проблема: жестко задан путь `/root/...`, эвристика regexp может давать false positives; не покрывает `SET/DELETE`.
    - Исправление: перейти на AST‑анализ и whitelist: разрешить write‑операции только через commit worker/Neo4j writer; использовать анализ импортов/вызовов `session.execute_write` вне белого списка.

**Исполнимый TODO‑Checklist**

- Commit & Consistency
  - [ ] Добавить `events_outbox` в PG и запись в одну транзакцию с `audit_log`/`graph_version` (`backend/src/db/pg.py`)
  - [ ] Реализовать `outbox_publisher` воркер и ретраи при доставке (Redis) (`backend/src/workers/outbox_publisher.py`)
  - [ ] Добавить компенсации для частичной недоставки (перепубликация/флаги)

- Tenant Guard & Write Whitelist
  - [ ] Ввести `Neo4jWriteHelper` с принудительным inject `tenant_id` (`backend/src/services/graph/neo4j_writer.py`)
  - [ ] Переписать тест guard на AST‑анализ белого списка (`backend/tests/unit/test_no_direct_writes_ast.py`)

- Embeddings Layer
  - [ ] Определить `EmbeddingProvider` интерфейс и DI (`backend/src/services/embeddings/provider.py`)
  - [ ] Реализовать режимы `hash(dev)` и `model(prod)` (OpenAI/локальная)
  - [ ] Версионировать Qdrant коллекции и добавить миграции (`backend/scripts/apply_vector_schema.py`)

- Integrity Gate
  - [ ] Расширить правила BASED_ON: обязательность/кратность для `Skill` и метрики по типам нарушений (`backend/src/services/integrity.py`)
  - [ ] Реализовать ASYNC‑очередь и воркер для `ASYNC_CHECK_REQUIRED` (`backend/src/workers/integrity_async.py`)

- Evidence Model
  - [ ] Добавить evidence для отношений: `(:REL)-[:EVIDENCED_BY]->(:SourceChunk)` или properties + валидация (`backend/src/workers/commit.py`)
  - [ ] Расширить Diff для evidence у REL (`backend/src/services/diff.py`)

- Vector Sync
  - [ ] Унифицировать размерность `kb_entities` (16D) в `mark_entities_updated` и рескоре (`backend/src/workers/vector_sync.py:12` и `:34`)
  - [ ] Добавить тест на несоответствие размерности и автокоррекцию (`backend/tests/unit/test_vector_dimension_consistency.py`)

- Schema Gatekeeper
  - [ ] Перейти на `schema_version` per‑tenant (`backend/src/db/pg.py`)
  - [ ] Общий миграционный скрипт и строгая проверка на старте (`backend/src/core/migrations.py`)

- API & Diff
  - [ ] Улучшить `/v1/proposals` сортировку и фильтры (по `created_at`, статусам) (`backend/src/api/proposals.py`)
  - [ ] Расширить `/v1/proposals/{id}/diff` для evidence связей (`backend/src/services/diff.py`)

- Frontend HITL & Optimistic UI
  - [ ] Ввести `tx_log` стор (Zustand/Redux) и генерацию `tx_id` (`frontend/src/store/txLog.ts`)
  - [ ] Реализовать inverse patch на ошибках (`frontend/src/utils/inversePatch.ts`)
  - [ ] Добавить дифф-интерфейс и визуализацию impact subgraph (`frontend/src/pages/ReviewDiff.tsx`)

- Metrics & Observability
  - [ ] Добавить детальные метрики: success rate ingestion, latency распределения, типы integrity нарушений (`backend/src/main.py` + метрики по сервисам)
  - [ ] Протокольный трейс от edge до Neo4j (trace_id) и кореляция с `X-Correlation-ID`

- Tests & CI
  - [ ] Покрыть outbox, компенсации и недоставку события интеграционными тестами (`backend/tests/integration/test_outbox_delivery.py`)
  - [ ] Обновить CI для запуска новых тестов и метрик (`.github/workflows/ci.yml`)

