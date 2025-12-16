# Technical Specification: KnowledgeBaseAI 2.0 — FINAL

**Version:** 2.0-FINAL
**Status:** Ready for Development (Detailed)
**Date:** 2025-12-16

## Содержание

1. Архитектурные принципы и границы системы
2. Компоненты и ответственность сервисов
3. Данные и онтология (Graph Schema)
4. Proposal/Diff: форматы, операции, детерминизм
5. Ingestion Pipeline: E2E процесс, статусы, ретраи, DLQ
6. Rebase: режимы, конфликты, протокол решения
7. Commit: атомарность, integrity gate, аудит, версионирование
8. Multi-tenancy: изоляция, безопасность, производительность
9. Vector Indexing: incremental, full reindex, dual-index
10. Math Core: веса, уверенность, decay, глобальная сложность
11. Roadmap Engine: поиск путей, режимы, объяснимость
12. AI Orchestrator: роли агентов, guardrails, доказательность
13. HITL Review: API, UI, частичный аппрув, Rerun alignment
14. API Contracts: эндпоинты, статусы, коды ошибок, схемы ответов
15. Frontend: Optimistic UI, транзакции, rollback, синхронизация
16. Observability: метрики, логи, трейсинг, SLO/SLI, алерты
17. Evaluation: golden dataset, метрики ingestion/roadmap, CI gates
18. Schema Versioning & Migrations: типы миграций, backfill, rollback
19. Security: угрозы, меры, секреты, rate limits, abuse control
20. DoD: критерии готовности по подсистемам
21. План внедрения: MVP → расширение → масштабирование

---

## 0. Архитектурный манифест (System Invariants)

### 0.1 Graph-First Source of Truth

* **Neo4j** хранит каноническую структуру знаний: сущности, связи, свойства, статусы жизненного цикла.
* **Vector DB** хранит производные эмбеддинги, которые:

  * строятся *из графа и источников*,
  * могут быть пересобраны без потери знаний,
  * не являются источником структуры.

**AC**

* Любой ответ/рекомендация, опирающаяся на векторный поиск, должна быть “привязана” к граф-узлам или source chunks.
* При рассинхроне VectorDB → выполняется reindex без изменения графа.

### 0.2 Safety via Proposals

* Прямая запись в граф запрещена всем подсистемам, кроме **Commit Worker**, который применяет **валидированный Proposal**.

**AC**

* Любые операции изменения графа фиксируются как Proposal и commit transaction.
* Любая попытка “обойти” Proposal (raw write) блокируется архитектурно и тестами.

### 0.3 Strict Tenant Isolation (P0)

* Все данные “замкнуты” в `tenant_id`.
* Утечка между тенантами — инцидент P0.

**AC**

* Поиск и чтение графа без tenant-фильтра невозможно технически (DAO enforcement + тесты).

### 0.4 Event-Driven Robustness

* Асинхронные процессы: ingestion, reindex, аналитика, heavy checks.
* Доставка at-least-once → требуется идемпотентность.

**AC**

* Повтор события не создаёт дублей и не вызывает двойных коммитов/реиндексов.

---

## 1. Компоненты системы (Service Decomposition)

### 1.1 API Service (FastAPI)

**Ответственность**

* AuthN/AuthZ, tenant extraction, rate limiting integration.
* CRUD чтения (graph overlay, stats, search).
* Interactive write mode (низкий риск, sync commit).
* Управление задачами ingestion: submit, status, diff, commit.
* HITL review endpoints.

**Не делает**

* тяжёлые парсинги и эмбеддинги,
* прямые записи в граф (кроме interactive low-risk commit через единый commit-путь).

### 1.2 Async Workers (ARQ/Celery)

**Типы воркеров**

* Parser Worker: извлечение текста, нормализация, чанкинг.
* Embedding Worker: эмбеддинги чанков/узлов, запись в Vector DB.
* Graph Agent Worker: извлечение сущностей/связей → Proposal.
* Commit Worker: применяет Proposal атомарно, запускает integrity gate, пишет audit log.
* Analytics Worker: пересчёт глобальной сложности.
* Decay Worker: nightly decay уверенности.
* Reindex Worker: incremental/full reindex.

### 1.3 DAO/Repository Layer

**Ответственность**

* Все запросы в Neo4j проходят через DAO.
* DAO всегда инжектирует `tenant_id`.
* DAO запрещает небезопасные запросы (вставка raw fragments).

### 1.4 Storage

* Neo4j (Graph)
* PostgreSQL (Users, tasks, proposals metadata, audit, schema_version, job state)
* Vector DB (Qdrant)
* Object Storage (MinIO/S3) для исходных файлов и нормализованных артефактов
* Redis (idempotency keys, ephemeral locks, caching task state)

---

## 2. Онтология и модель данных (Graph Schema)

### 2.1 Узлы (Nodes)

Каждый узел обязан иметь:

* `tenant_id`
* `uid` (стабильный внешний идентификатор)
* `type`/labels
* `name`, `name_norm` (нормализованное)
* `status`: `ACTIVE | DEPRECATED | ARCHIVED`
* `created_at`, `updated_at`
* `provenance`: ссылка на proposal/agent/user

**Типы узлов (минимум)**

1. **Concept/Topic** — что изучаем
2. **Skill** — что умеем делать
3. **Method** — как делаем (алгоритм, приём)
4. **Error** — типовая ошибка/антипаттерн
5. **Assessment/Task** — контроль (задача/тест/вопрос)
6. **SourceChunk** — кусок источника (цитируемый фрагмент)
7. **Goal** — цель (экзамен/компетенция/роль/гипотеза)

*(Можно расширять: Role, Competency, Paper, Author — но базу держим универсальной.)*

### 2.2 Связи (Relationships)

Все связи тоже имеют:

* `tenant_id`
* `uid`
* `status`
* `created_at`, `updated_at`

**Ключевые типы**

* `PART_OF` (иерархия)
* `PREREQ` (зависимость)
* `BASED_ON` (skill → concept)
* `USES_METHOD` (skill/concept → method)
* `AFFECTS` (error → skill/concept)
* `TESTED_BY` (skill/concept → assessment)
* `EVIDENCED_BY` (node/rel → sourcechunk)
* `REPLACED_BY` (deprecated → new)

### 2.3 Кардинальности и правила целостности (Integrity Rules)

**Примеры обязательных правил**

* Skill обязан иметь хотя бы 1 `BASED_ON → Concept`
* Error обязан иметь хотя бы 1 `AFFECTS → (Skill|Concept)`
* Assessment обязан проверять ≥1 `Skill` (через `TESTED_BY` или прямую связь)
* PREREQ-граф обязан быть ацикличным
* PART_OF-граф должен иметь один “корень” на подграф (по policy пространства)

**AC**

* Integrity gate блокирует commit, если хотя бы одно правило нарушено.

---

## 3. Proposal/Diff: детальный контракт

### 3.1 Общие требования

* Proposal — **immutable draft**, хранится в Postgres и/или Neo4j как “draft nodes”.
* Proposal детерминирован:

  * стабильный порядок операций,
  * стабильная нормализация строк,
  * одинаковые входы → одинаковый checksum.

### 3.2 Поля Proposal (расширенно)

* идентификаторы: proposal_id, task_id, tenant_id
* fingerprints: doc_fingerprint, config_hash, proposal_checksum
* versioning: base_graph_version
* risk: risk_level, risk_reasons[]
* operations[]
* rebase_history[]
* status: DRAFT | WAITING_REVIEW | APPROVED | REJECTED | CONFLICT | COMMITTING | DONE | FAILED

### 3.3 Operations: общая структура

Операция содержит:

* `op_id`
* `op_type`
* `targets` (target_id или temp_id)
* `properties_delta`
* `match_criteria` (для merge)
* `evidence` (source_chunk_id, quote, confidence)
* `semantic_impact`: `COSMETIC | STRUCTURAL | SEMANTIC`
* `requires_review`: boolean

### 3.4 Whitelist для normalization_only

**Разрешённые поля**

* alias/synonyms
* name_norm
* исправление опечатки имени (при доказанной близости)

**Запрещено**

* менять PREREQ
* менять fundamental
* менять смысловые определения/описания без evidence

### 3.5 Deterministic canonicalization

**Правила**

* строки нормализуются (trim, unicode normalize)
* операции сортируются (op_type, target id)
* JSON canonical (sorted keys) перед checksum
* если порядок элементов массива неважен — он сортируется по ключу

**AC**

* reorder полей в исходном JSON не меняет checksum результата.

---

## 4. Ingestion Pipeline (E2E) — максимально подробно

### 4.1 Статусы задач (Task Lifecycle)

* QUEUED
* PARSING
* CHUNKING
* EMBEDDING
* ALIGNMENT
* PROPOSAL_READY
* WAITING_REVIEW
* APPROVED
* COMMITTING
* DONE
* FAILED
* CONFLICT

### 4.2 Шаги пайплайна

1. **Submit**

   * файл → S3
   * создаётся task record в Postgres (tenant, user, config hash, doc fingerprint)
   * публикуется событие `Ingestion.Submitted`

2. **Parse**

   * извлечение текста/структуры (заголовки, списки)
   * сохранение нормализованного текста в S3
   * событие `Ingestion.Parsed`

3. **Chunk**

   * семантическое разбиение
   * каждому chunk: `chunk_id`, offsets, ссылки на исходник
   * событие `Ingestion.Chunked`

4. **Embeddings**

   * вычисление эмбеддингов chunk
   * запись в VectorDB с payload: tenant_id, chunk_id, doc_id
   * событие `Ingestion.ChunksIndexed`

5. **Alignment + Extraction**

   * LLM-агент извлекает сущности, связи, определения, ошибки, методы
   * ищет кандидатов в графе и VectorDB
   * формирует Proposal (Draft)
   * событие `Graph.Proposal.Created`

6. **Review**

   * LOW risk → авто-апрув по правилам
   * MEDIUM/HIGH → HITL

7. **Commit**

   * Rebase check
   * Integrity gate
   * Neo4j transaction apply
   * Audit log write
   * событие `Graph.Committed`

8. **Incremental indexing**

   * пересчитать embeddings затронутых узлов (если нужно)
   * обновить VectorDB
   * событие `Vector.IncrementalUpdated`

### 4.3 Retry/DLQ политика

* каждый шаг имеет `idempotency_key`
* на повторе шаг проверяет, выполнен ли он уже (Redis + Postgres state)
* после 3 retry → DLQ + task FAILED

**AC**

* “убийство воркера” в середине шага не ломает задачу: повтор безопасен.

---

## 5. Rebase: реалистичный протокол

### 5.1 FAST_REBASE

* проверка пересечения: proposal targets vs changes since base_version
* если пересечения нет → обновить base_version и продолжить commit

### 5.2 SAFE_REBASE

* если пересечение есть, но тип конфликтов “мягкий”:

  * пересчитать match_criteria
  * пересобрать Proposal на подграфе
  * повысить risk

### 5.3 CONFLICT

* если узел депрекейтнут/архивирован
* если PREREQ структура менялась
* если нарушаются кардинальности

**AC**

* Auto-rebase не меняет семантику и не создаёт новых сущностей “молча”.

---

## 6. Commit: атомарность, integrity, аудит

### 6.1 Commit Worker: порядок действий

1. lock proposal (чтобы не применили дважды)
2. check base_graph_version → rebase / conflict
3. validate proposal schema + references
4. integrity gate (на затронутом подграфе)
5. apply operations в одной транзакции Neo4j
6. write audit log (Postgres) с revert data
7. update graph_version (tenant-scoped)
8. publish Graph.Committed

### 6.2 Audit Log: формат

* tenant_id
* tx_id
* proposal_id
* operations_applied
* revert_operations
* who: user/agent
* correlation_id

**AC**

* Undo возможно по revert_operations без ручных правок базы.

---

## 7. Multi-tenancy: безопасность + производительность

### 7.1 Enforced DAO filtering

* DAO принимает `ctx` с tenant_id
* любой query builder добавляет фильтр tenant_id
* CI запрещает raw cypher в бизнес-логике (статический анализ)

### 7.2 Neo4j индексы (обязательные)

* composite index: `(tenant_id, uid)`
* composite index: `(tenant_id, name_norm)`
* index: `(tenant_id, status)`
* optional: `(tenant_id, fundamental)`

### 7.3 Пороги масштабирования

* Tier1: single db + strict indexes
* Tier2: database-per-tenant для крупных клиентов
* Tier3: Fabric / sharding

**AC**

* p95 roadmap latency не деградирует линейно от количества тенантов при правильной индексации.

---

## 8. Vector Indexing: incremental-first

### 8.1 Incremental update

На `Graph.Committed`:

* определить changed entities:

  * новые узлы
  * узлы с изменёнными текстовыми полями/определениями
  * связанные source chunks
* переэмбеддинг только этих объектов
* update/upsert в VectorDB (payload tenant_id)

### 8.2 Dual-index full reindex

* новый индекс строится параллельно
* чтение переключается атомарно
* смешивание запрещено

**AC**

* ≥95% коммитов → только incremental
* full reindex запускается только вручную/по migration policy

---

## 9. Math Core: полный набор определений

### 9.1 W_static

Как считается (детерминированно):

* нормализованная длина/плотность терминов/структурность
* шкала 0.1..1.0
* фиксируется при ingestion

### 9.2 G_diff

Глобальная сложность:

* считается по результатам пользователей (ошибки/время/успех)
* сглаживание (EMA или robust median window 7d)
* ограничение дневного изменения ≤ 5%

### 9.3 U_conf (EMA)

* тестовый score 0..1
* EMA с alpha=0.3 (или tenant-configurable)

### 9.4 Decay

* nightly decay: `U_conf *= exp(-λ * Δt)`
* λ configurable per domain

### 9.5 Propagation

* применяется по связям `BASED_ON` и `PREREQ` максимум 2 hops
* factor = `0.5^hop`

**AC**

* один тест не может “разогнать” уверенность всего графа.

---

## 10. Roadmap Engine: алгоритм + объяснимость

### 10.1 Входы

* target goal
* user overlay weights
* mode: fastest | thorough
* constraints: include/exclude topics, time budget, prerequisite strictness

### 10.2 Алгоритм

* A* или Dijkstra на подграфе
* cost = W_edge
* heuristic (для A*): оценка оставшейся стоимости (например, по среднему W_static * depth)

### 10.3 Выход

* ordered list of nodes
* reasons per step:

  * prerequisite required
  * low confidence
  * high global difficulty
  * fundamental dependency

**AC**

* roadmap всегда объясним, “почему этот шаг”.

---

## 11. AI Orchestrator: агенты и guardrails

### 11.1 Роли агентов

* Extractor: сущности/связи/цитаты
* Aligner: match/merge candidates
* Integrity advisor: выявляет потенциальные нарушения ещё до commit
* Tutor: объяснение roadmap и рекомендации
* Policy guard: проверка доказательности, запрет галлюцинаций

### 11.2 Общие правила

* no direct writes
* evidence required
* non-destructive only
* любые uncertain → marked as conflict/review

### 11.3 Guardrails на уровне системы

* любой response должен ссылаться на:

  * graph node ids
  * source chunk ids
* если нет evidence → ответ помечается как “hypothesis” и не влияет на граф

---

## 12. HITL Review: подробно

### 12.1 Risk level правила

LOW:

* cosmetic operations
* link non-PREREQ
* alias/synonyms

MEDIUM:

* merge node with confidence < threshold
* creating PREREQ

HIGH:

* replacing/deprecating major nodes
* structural changes affecting large subgraphs

### 12.2 UI requirements

* diff view: added/merged/conflicts
* evidence viewer: цитата + ссылка на chunk
* “approve partial” (опционально): можно аппрувить подмножество операций
* rerun alignment после ручной коррекции

---

## 13. API Contracts (расширенно)

### 13.1 Ingestion

* submit: принимает файл + metadata + config
* task status: полный state + logs + progress
* diff: выдаёт Proposal
* commit: запускает commit pipeline
* reject: архивирует proposal

### 13.2 Graph read

* overlay: подграф с пользовательскими весами
* stats: counts, health metrics
* integrity: cycles/orphans/cardinality violations

### 13.3 User learning

* feedback: score + evidence
* roadmap: goal + mode + constraints → path + reasons

### 13.4 Domain errors

* 403 TENANT_FORBIDDEN
* 409 STALE_PROPOSAL (rebase required)
* 422 VALIDATION_FAILED
* 500 COMMIT_INTEGRITY_VIOLATION
* 429 RATE_LIMIT

---

## 14. Frontend: Optimistic UI без мерцания

### 14.1 Транзакционная модель

* client_tx_id
* local op log: список pending операций
* state = reduce(base + pending + confirmed remote)

### 14.2 Rollback

* remove failed tx from log
* recompute derived state
* preserve newer user inputs (последующие tx остаются)

**AC**

* откат одной операции не ломает другие.

---

## 15. Observability: SLO/SLI + метрики

### 15.1 Tracing

* correlation_id проходит через API → workers → DB
* любой task_id можно проследить end-to-end

### 15.2 Метрики (минимум)

Ingestion:

* tasks queued/processing/failed
* avg duration per step
* DLQ size

Graph:

* commit success rate
* integrity violations count
* merge rate

Vector:

* incremental updates count
* reindex duration

LLM:

* token usage
* error rate
* latency

### 15.3 Алерты

* DLQ > 0
* commit failure spike
* tenant leakage test failure
* roadmap p95 regression

---

## 16. Evaluation: контроль качества

### 16.1 Golden dataset

* пары “text → expected graph diff”
* покрытие: topics, prereqs, errors, methods

### 16.2 Метрики ingestion

* precision/recall nodes/edges
* merge correctness rate
* conflict rate

### 16.3 Метрики roadmap

* stability score (≤20% change per new result)
* regret metric (predicted vs actual time)
* usefulness proxy (рост U_conf по шагам)

**CI gate**

* регрессия выше порога блокирует merge

---

## 17. Schema Versioning & migrations

### 17.1 schema_version

* хранится централизованно
* сервисы проверяют совместимость при старте

### 17.2 rename миграции (Concept → KnowledgeUnit)

* dual-write
* backfill
* switch reads
* deprecate old
* controlled removal

**AC**

* миграция воспроизводима и откатываема.

---

## 18. Security: меры

* JWT validation
* tenant enforcement
* rate limiting
* input validation against injections
* secrets management (env vault)
* audit logs immutable (append-only)

---

## 19. Definition of Done (расширенный)

Pipeline:

* E2E ingestion + commit + audit + incremental vector update

Safety:

* zero direct writes
* proposal determinism verified

Isolation:

* negative tests on tenant mismatch

Reliability:

* poison message → DLQ, task failed gracefully
* worker kill → retry & completion

UX:

* optimistic UI stable rollback

Performance:

* p95 roadmap within target on load test

---

## 20. План внедрения

### MVP

* Ingestion async (parse/chunk/embed/proposal)
* Proposal + HITL basic
* Commit worker + integrity gate
* tenant enforcement DAO
* overlay + roadmap basic
* incremental indexing minimal
* observability minimal

### Next

* SAFE_REBASE
* advanced eval pipeline
* database-per-tenant tier2
* dual-index full reindex automation