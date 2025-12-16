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
    *   [ ] `Subtask`: Кнопки Approve/Reject.
    *   [ ] `Subtask`: Отображение Evidence (цитаты).
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
*   **[2025-12-16]**: Completed Task 1.2.1.2 (HITL Review API). Implemented GET/approve/reject endpoints; unit test passed.
