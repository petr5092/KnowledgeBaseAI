# KnowledgeBaseAI 2.0 — PRD & Tech Spec (Production Final)

**Version:** 2.0-FINAL
**Status:** Approved for Development
**Scope:** Core Platform (Graph Engine, Ingestion, API, Math, UX, Ops)
**Target:** EdTech / Corporate Learning / R&D Knowledge Systems

---

## SYSTEM INVARIANTS (Нарушать запрещено)

1.  **Graph-First Source of Truth**
    Neo4j — единственный источник структуры.
    Vector DB — производный индекс.
    Любая рассинхронизация → Graph → Vector Reindex.

2.  **No Direct Writes**
    Ни пользователь, ни агент, ни сервис **не пишут в граф напрямую**.
    Единственный путь изменений: `Proposal → Validate → Commit`.

3.  **Tenant Isolation = P0 Security**
    Любая утечка данных между `tenant_id` — критический инцидент.

4.  **Determinism Over Cleverness**
    Повторяемость важнее “умности”.
    Одинаковый вход → одинаковый результат.

---

# EPIC 1: Graph Core & Data Integrity

**Цель:** Превратить граф в математически корректную, педагогически осмысленную систему.

---

## Feature 1.1: Strict Ontology Enforcement

### Story 1.1.1: Node & Relation Validation

**As a** System Architect
**I want** DAO-уровень, который валидирует типы узлов и связей
**So that** граф не деградировал со временем

### Acceptance Criteria

1.  Разрешённые узлы:
    *   `Concept`, `Skill`, `Method`, `Error`, `Assessment`, `SourceChunk`, `Goal`
2.  Разрешённые связи:
    *   `PART_OF`, `PREREQ`, `BASED_ON`, `AFFECTS`, `TESTED_BY`
3.  Обязательные поля узла:
    *   `uid`, `tenant_id`, `status`, `created_at`, `updated_at`
4.  Любая неизвестная метка → ошибка до Commit

### Test Cases

*   ❌ `CREATE (:Unicorn)` → `422`
*   ❌ `(:Error)-[:PREREQ]->(:Skill)` → `422`
*   ✅ `(:Skill)-[:BASED_ON]->(:Concept)` → `200`

---

## Feature 1.2: Integrity Gate (Pre-Commit)

### Story 1.2.1: Cycle & Dangler Detection

**As a** Learning Methodologist
**I want** запрет циклов и «висячих» навыков
**So that** обучение было проходимым

### Acceptance Criteria

1.  Проверяются только изменяемые подграфы (diff-based check)
2.  Запрещены циклы `PREREQ`
3.  `Skill` без `BASED_ON` → Commit blocked

### Test Cases

*   ❌ `A → B → A` → Integrity Error
*   ❌ Skill без Concept → Rejected
*   ✅ DAG → Success

---

# EPIC 2: Safe Mutation Engine (Proposals)

**Цель:** Реализовать “Git for Knowledge Graphs”, но без потери рассудка.

---

## Feature 2.1: Deterministic Proposal Model

### Story 2.1.1: Proposal Immutability

**As a** DevOps Engineer
**I want** Proposal с детерминированным хешем
**So that** ingestion был идемпотентен

### Acceptance Criteria

1.  `proposal_checksum = hash(canonical_json(operations))`
2.  Canonical JSON:
    *   отсортированные ключи
    *   отсортированные операции
3.  Proposal immutable после создания

### Test Cases

*   ✅ Один файл + один конфиг → один checksum
*   ❌ Разный порядок ключей → checksum тот же

---

## Feature 2.2: Rebase Protocol (⚠️ зона боли)

### Story 2.2.1: Minimal-Safe Rebase (Intentionally Limited)

**As a** Backend Service
**I want** простой и предсказуемый rebase
**So that** мы не писали “git rebase для графа” 6 месяцев

### Acceptance Criteria

1.  **FAST_REBASE**:
    *   Нет пересечения `target_id` → auto-apply
2.  **NO_REBASE**:
    *   Любое пересечение → `CONFLICT`
3.  **Нет умных merge’ов**
    *   Никаких попыток “догадаться”, что имел в виду агент

> ⚠️ Осознанное ограничение:
> **Сложный Auto-Rebase запрещён архитектурно.**

### Test Cases

*   ✅ User A → Node X, User B → Node Y → OK
*   ❌ Node X удалён, связь к X → CONFLICT

---

# EPIC 3: Ingestion Pipeline & AI

**Цель:** Превращать документы в граф **без галлюцинаций и дублей**.

---

## Feature 3.1: Resilient Task Lifecycle

### Story 3.1.1: Idempotent Workers

**As a** Platform
**I want** безопасные ретраи
**So that** падения воркеров не ломали данные

### Acceptance Criteria

1.  Каждый шаг проверяет `idempotency_key`
2.  Retry: 2s → 4s → 8s
3.  3 фейла → DLQ + FAILED

### Test Cases

*   ❌ Kill during chunking → Resume without duplicates
*   ❌ LLM timeout → Retry OK

---

## Feature 3.2: AI Guardrails

### Story 3.2.1: Evidence-Based Changes

**As a** Product Owner
**I want** видеть источник каждого знания
**So that** граф был объясним

### Acceptance Criteria

1.  `CREATE_*` / `MERGE_*` требуют:
    *   `source_chunk_id`
    *   `quote`
2.  Исключение: `normalization_only`

### Test Cases

*   ❌ CREATE без evidence → Rejected
*   ✅ Typo fix → OK

---

# EPIC 4: Core Math & Roadmap Engine

**Цель:** Сделать персонализацию устойчивой и объяснимой.

---

## Feature 4.1: Dynamic Weight Calculation

### Story 4.1.1: Weight Formula

**As a** Data Scientist
**I want** стабильную формулу весов
**So that** маршруты не “прыгали”

### Acceptance Criteria

1.  Формула:
    ```
    Clip(
      W_static * G_diff * (1 + Decay * (1 - U_conf)),
      W_min,
      W_max
    )
    ```
2.  `G_diff` сглажен (EMA / median window)
3.  Decay запускается фоново

### Test Cases

*   ✅ Test passed → weights ↓
*   ✅ Month idle → weights ↑
*   ❌ Spike ошибок → G_diff ≤ +5%

---

## Feature 4.2: Pathfinding Engine

### Story 4.2.1: Explainable Roadmap

**As a** Student
**I want** понимать, почему мне предлагают шаг
**So that** я доверял системе

### Acceptance Criteria

1.  A* / Dijkstra
2.  Каждый шаг имеет `reason`
3.  Modes: `fastest` / `thorough`

### Test Cases

*   ✅ Beginner → длинный путь
*   ✅ Expert → короткий путь

---

# EPIC 5: Multi-Tenancy & Security

**Цель:** Сделать утечку данных технически невозможной.

---

## Feature 5.1: Hard Tenant Enforcement

### Story 5.1.1: Context Injection

**As a** Security Officer
**I want** автоматический tenant-filter
**So that** разработчик не мог ошибиться

### Acceptance Criteria

1.  `tenant_id` берётся из JWT
2.  DAO инжектит фильтр автоматически
3.  Прямой Neo4j driver запрещён (lint rule)

### Test Cases

*   ❌ JWT A + tenant B → 403
*   ❌ Cypher injection → Blocked

---

# EPIC 6: Frontend & UX

**Цель:** Скрыть асинхронность от пользователя.

---

## Feature 6.1: Optimistic UI (⚠️ зона боли)

### Story 6.1.1: Transactional Rollback

**As a** User
**I want** мгновенный отклик
**So that** интерфейс не казался сломанным

### Acceptance Criteria

1.  Каждое действие = `client_tx_id`
2.  Store поддерживает snapshots
3.  Rollback откатывает **только** failed-tx

### Test Cases

*   ✅ Local patch applied instantly
*   ❌ Backend error → rollback one tx, no flicker

---

# EPIC 7: Observability & Reliability

**Цель:** Любую проблему можно воспроизвести и объяснить.

---

## Feature 7.1: Full Tracing

### Story 7.1.1: End-to-End Visibility

**As a** DevOps Engineer
**I want** видеть путь task_id целиком
**So that** дебаг занимал минуты, а не дни

### Acceptance Criteria

1.  `correlation_id` сквозной
2.  Трейс: Upload → Chunk → Agent → Proposal → Commit
3.  DLQ мониторится

### Test Cases

*   ✅ Complete trace visible
*   ❌ DLQ > 0 → Alert fired

---

# Definition of Done (Global)

Фича считается готовой, если:

1.  Нет прямых записей в граф
2.  Proposal детерминирован
3.  Tenant isolation проверена негативными тестами
4.  Roadmap меняется стабильно
5.  UI переживает rollback без потери данных
6.  Graph → Vector reindex возможен
7.  Все AC и Test Cases пройдены