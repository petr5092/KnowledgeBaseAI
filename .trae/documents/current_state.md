Ниже — единый «живой» технический документ по backend-части KnowledgeBaseAI (`/root/KnowledgeBaseAI/backend`). Он написан так, чтобы:

- фиксировать **текущее состояние** максимально подробно;
- служить **единым документом на всю историю проекта** (есть раздел “История изменений”, который можно пополнять);
- содержать **дорожную карту** развития и улучшений.

---

# KnowledgeBaseAI Backend — Архитектура и техническая документация (Living Doc)

**Область документа:** только `backend/` (FastAPI + сервисы).  
**Роль backend:** headless-платформа для работы с графом знаний (Neo4j), учебными планами (Postgres), генерацией/обогащением контента (OpenAI), векторным поиском/дедупликацией (Qdrant), фоновыми задачами (Redis+ARQ), и API для фронтенда.

---

## 0) История изменений (заполняемый журнал)

Формат записи (рекомендуемый шаблон):

- **Дата / Версия**
- **Изменения**
- **Миграции/совместимость**
- **Риски**
- **Ссылки на PR/коммиты**

Пример (заготовка):

- **2025-12-13 / v0.x (текущее состояние)**
  - Добавлены/присутствуют: FastAPI API, GraphQL (strawberry), JWT auth, admin endpoints, KB rebuild pipeline, ARQ worker, Qdrant concepts.
  - Хранилища: Neo4j (граф), Postgres (users + curricula + расширенная схема), Redis (jobs/progress/state).
  - Ограничения: часть логики имеет fallback на JSONL-файлы в `kb/`.

---

## 1) Быстрый обзор архитектуры

### 1.1. Основные подсистемы

1) **HTTP API (FastAPI)**  
   Точка входа: `backend/src/main.py`.  
   Роутеры: `backend/src/api/*.py`.

2) **Graph Storage (Neo4j)**  
   Репозиторий/драйвер: `backend/src/services/graph/neo4j_repo.py`.  
   Основная логика графа/импорта/весов/аналитики: `backend/src/services/graph/utils.py`.

3) **Relational Storage (Postgres)**  
   - Пользователи/аутентификация: `backend/src/services/auth/users_repo.py` (таблица `users` создаётся “на лету”).  
   - Учебные планы (curricula): `backend/src/services/curriculum/repo.py`.  
   - Полная SQL-схема (расширенная): `backend/schemas/postgres.sql` (частично не используется текущим кодом напрямую, но задаёт целевую модель).

4) **Background Jobs (Redis + ARQ)**  
   Worker: `backend/src/tasks/worker.py`.  
   Maintenance endpoints: `backend/src/api/maintenance.py`.  
   Прогресс: Redis pub/sub + WebSocket `backend/src/api/ws.py`.

5) **AI / Generation (OpenAI)**  
   - “AI engine” (структурный JSON): `backend/src/services/ai_engine/ai_engine.py`.  
   - “KB builder” (генерация предмета/тем/навыков/методов/примеров, JSONL): `backend/src/services/kb/builder.py`.  
   - Используется в admin endpoints и construct endpoints.

6) **Vector Search (Qdrant)**  
   `backend/src/services/vector/qdrant_service.py` — embeddings + upsert + similarity search.

7) **GraphQL API (strawberry)**  
   `backend/src/api/graphql.py` — GraphQL schema поверх Neo4j + fallback на JSONL для examples.

---

## 2) Структура проекта (backend)

Ключевые директории/файлы:

- `backend/src/main.py` — создание `FastAPI`, middleware, подключение роутеров, startup hooks.
- `backend/src/config/settings.py` — конфигурация через `pydantic-settings`.
- `backend/src/core/logging.py` — настройка `structlog` (если установлен).
- `backend/src/api/*` — HTTP API.
- `backend/src/services/*` — бизнес-логика.
- `backend/src/tasks/worker.py` — ARQ worker (Redis jobs).
- `backend/schemas/postgres.sql` — целевая SQL-схема.
- `backend/scripts/*` — утилиты для загрузки/генерации/линковки/очистки (операционные скрипты).
- `backend/tests/*` — pytest тесты.

---

## 3) Точка входа и жизненный цикл приложения

### 3.1. FastAPI app

Файл: `backend/src/main.py`

- Создаётся `app = FastAPI(title="Headless Knowledge Graph Platform")`.
- Подключаются роутеры:
  - `/v1/graph` (`src/api/graph.py`)
  - `/v1/construct` (`src/api/construct.py`)
  - `/v1/analytics` (`src/api/analytics.py`)
  - `/ws/*` (`src/api/ws.py`)
  - `/v1/curriculum` (`src/api/curriculum.py`)
  - `/v1/admin/*` (`src/api/admin.py`, `admin_curriculum.py`, `admin_generate.py`)
  - `/v1/levels` (`src/api/levels.py`)
  - `/v1/maintenance` (`src/api/maintenance.py`)
  - `/v1/auth` (`src/api/auth.py`)
  - `/v1/validation` (`src/api/validation.py`)
  - GraphQL: `app.include_router(graphql_router, prefix="/v1/graphql")` (если импорт удался)

### 3.2. Startup hook

`on_startup()` в `src/main.py`:

- `setup_logging()` (`src/core/logging.py`)
- логирует `neo4j_uri`
- `ensure_bootstrap_admin()` (`src/services/auth/users_repo.py`) — создаёт/повышает admin пользователя при наличии env-переменных.

### 3.3. Middleware метрик

В `src/main.py` есть middleware, который инкрементит `REQ_COUNTER` и измеряет `LATENCY` через `prometheus_client` (если пакет доступен; иначе используются заглушки).

### 3.4. Healthcheck

`GET /health` возвращает:
- наличие OpenAI ключа
- наличие Neo4j URI

---

## 4) Конфигурация (Settings)

Файл: `backend/src/config/settings.py`

### 4.1. Источники конфигурации

`SettingsConfigDict(env_file=(ENV_FILE or "../.env", "../.env.dev", "../.env.stage", "../.env.prod"))`

То есть backend читает env из файлов, выбираемых переменной `ENV_FILE`, плюс стандартные `.env.*`.

### 4.2. Ключевые переменные

- `APP_ENV`: dev|stage|prod
- `PG_DSN`: Postgres DSN (нужен для auth/users и curricula)
- `OPENAI_API_KEY`
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
- `QDRANT_URL` (по умолчанию `http://qdrant:6333`)
- `PROMETHEUS_ENABLED` (флаг есть, но в коде включение/экспорт метрик не полностью оформлены)
- `CORS_ALLOW_ORIGINS` (есть, но CORS middleware в `main.py` не подключён)
- `ADMIN_API_KEY` (есть, но в коде не используется как основной механизм)
- JWT:
  - `JWT_SECRET_KEY`
  - `JWT_ACCESS_TTL_SECONDS` (default 900)
  - `JWT_REFRESH_TTL_SECONDS` (default 1209600)
- Bootstrap admin:
  - `BOOTSTRAP_ADMIN_EMAIL`
  - `BOOTSTRAP_ADMIN_PASSWORD`
- Домены/letsencrypt (для деплоя):
  - `KB_DOMAIN`, `KB_ALT_DOMAIN`, `LETSENCRYPT_EMAIL`

---

## 5) Хранилища и модель данных

### 5.1. Neo4j — “канонический” граф знаний

#### 5.1.1. Узлы (labels)

По коду `src/services/graph/utils.py` и `src/api/graphql.py` используются:

- `Subject`
- `Section`
- `Topic`
- `Skill`
- `Method`
- `Goal`
- `Objective`
- `ContentUnit`
- `Example` / `Question` (встречается `HAS_QUESTION` к `q`, в GraphQL — `q` с полями `statement`, `difficulty`)
- `Error`
- (в админке есть `User` узлы, которые можно purge’ить, но canonical snapshot запрещает user nodes)

#### 5.1.2. Связи (relationships)

Основные:

- `(:Subject)-[:CONTAINS]->(:Section)`
- `(:Section)-[:CONTAINS]->(:Topic)`
- `(:Subject)-[:HAS_SKILL]->(:Skill)`
- `(:Topic)-[:USES_SKILL]->(:Skill)` (есть `weight`, `confidence`)
- `(:Skill)-[:LINKED]->(:Method)` (есть `weight`, `confidence`, `adaptive_weight`)
- `(:Topic)-[:PREREQ]->(:Topic)` (есть `weight`, `confidence`)
- `(:Topic)-[:TARGETS]->(:Goal|:Objective)`
- `(:Topic)-[:HAS_LEARNING_PATH|HAS_PRACTICE_PATH|HAS_MASTERY_PATH]->(:ContentUnit)`
- `(:Topic)-[:HAS_QUESTION]->(q)` (вопросы/примеры)
- `(:Error)-[:TRIGGERS]->(:Skill)`
- `(:Error)-[:ILLUSTRATED_BY]->(q)` (пример/вопрос)

#### 5.1.3. Ограничения/индексы

`ensure_constraints()` в `src/services/graph/utils.py` создаёт уникальные constraints по `uid` для основных сущностей и индексы по `title`, а также scope-уникальность для некоторых пар.

#### 5.1.4. Веса (static/dynamic/adaptive)

- `static_weight` и `dynamic_weight` для `Topic` и `Skill`.
- `compute_static_weights()` вычисляет веса эвристически по тексту (словарь “сложных терминов”, длина текста).
- `update_dynamic_weight()` / `update_skill_dynamic_weight()` корректируют `dynamic_weight` на основе `score`.
- `recompute_relationship_weights()` и `recompute_adaptive_for_skill()` выставляют `r.adaptive_weight` на `LINKED` ребрах равным текущему весу навыка.

#### 5.1.5. Импорт из JSONL

`sync_from_jsonl()` в `src/services/graph/utils.py`:
- читает `kb/*.jsonl` (subjects/sections/topics/skills/methods/topic_skills/skill_methods/topic_prereqs/content_units/topic_goals/topic_objectives)
- создаёт/обновляет узлы и связи в Neo4j через `UNWIND` батчи.

---

### 5.2. Postgres — пользователи и curricula (+ целевая расширенная схема)

#### 5.2.1. Users (реально используется)

`src/services/auth/users_repo.py`:
- `ensure_users_table()` создаёт таблицу `users` при первом обращении.
- поля: `id SERIAL`, `email UNIQUE`, `password_hash`, `role`, `is_active`, `created_at`.

Это “операционная” схема, независимая от `schemas/postgres.sql`.

#### 5.2.2. Curricula (реально используется)

`src/services/curriculum/repo.py` использует таблицы:
- `curricula(code, title, standard, language, status, id...)` (ожидается в БД)
- `curriculum_nodes(curriculum_id, kind, canonical_uid, order_index, is_required)`

В `schemas/postgres.sql` эти таблицы не показаны (значит: либо есть отдельная миграция вне репозитория, либо схема неполная/рассинхронизирована).

#### 5.2.3. Расширенная схема (целевая/планируемая)

`backend/schemas/postgres.sql` описывает богатую модель:
- subjects/sections/topics/skills/methods/examples/errors
- связи topic_skills, skill_methods, skill_dependencies, prerequisites DAG, attempts и т.д.

Фактически текущий runtime больше опирается на Neo4j как “источник истины” для графа, а Postgres — для auth и curricula.

---

### 5.3. Redis — фоновые задачи и состояние пайплайна

Используется для:
- ARQ jobs queue
- pub/sub прогресса: канал `progress:{job_id}`
- состояния:
  - `kb:rebuild:{job_id}` (TTL 24h)
  - `kb:validate:{job_id}` (TTL 24h)
  - `kb:published:current` (метаданные публикации)

---

### 5.4. Qdrant — векторное хранилище “concepts”

`src/services/vector/qdrant_service.py`:
- коллекция `concepts` (создаётся при импорте модуля, если доступен Qdrant)
- embeddings: OpenAI `text-embedding-3-small` (1536)
- `query_similar()` возвращает `(id, score)`.

---

## 6) API: контракты, эндпоинты, DTO, ошибки

### 6.1. Общие принципы

- Версионирование REST: префикс `/v1/...`
- Авторизация: JWT Bearer в `Authorization: Bearer <token>`
- Админские роуты: `/v1/admin/*` защищены dependency `require_admin` (`src/api/deps.py`)

---

### 6.2. Health

**GET `/health`**  
Ответ: `{ "openai": boolean, "neo4j": boolean }`

---

### 6.3. Auth API (`src/api/auth.py`)

База: `/v1/auth`

#### POST `/register`
Request:
```json
{ "email": "user@example.com", "password": "..." }
```
Responses:
- `200`: `{ "ok": true, "id": <int>, "email": "..." }`
- `409`: user already exists
- `503`: postgres not configured
- `500`: db error

#### POST `/login`
Request:
```json
{ "email": "...", "password": "..." }
```
Response `200`:
```json
{ "access_token": "...", "refresh_token": "...", "token_type": "bearer" }
```
Errors:
- `401`: invalid credentials
- `403`: user disabled
- `503`: postgres not configured

#### POST `/refresh`
Request:
```json
{ "refresh_token": "..." }
```
Response `200`: новые access/refresh токены.  
Errors: `401`, `403`, `503`.

#### GET `/me`
Header: `Authorization: Bearer <access>`  
Response:
```json
{ "id": 1, "email": "...", "role": "user|admin" }
```

---

### 6.4. Admin API

#### `/v1/admin/purge_users` (`src/api/admin.py`)
Удаляет `(:User)` и `:COMPLETED` связи в Neo4j (не Postgres users).  
Response: `{ deleted_users, deleted_completed_rels }`

#### Curricula admin (`src/api/admin_curriculum.py`)
- POST `/v1/admin/curriculum` — создать curriculum (Postgres)
- POST `/v1/admin/curriculum/nodes` — добавить узлы
- GET `/v1/admin/curriculum/graph_view?code=...` — получить view

#### Генерация предмета (`src/api/admin_generate.py`)
- POST `/v1/admin/generate_subject` — генерирует JSONL KB через OpenAI (без импорта в Neo4j)
- POST `/v1/admin/generate_subject_import` — генерирует + `sync_from_jsonl()` + `compute_static_weights()` + `analyze_knowledge()`

---

### 6.5. Graph API (`src/api/graph.py`)

База: `/v1/graph`

#### GET `/viewport?center_uid=...&depth=1`
Возвращает соседей из Neo4j:
```json
{ "nodes": [...], "edges": [...], "center_uid": "...", "depth": 1 }
```

#### POST `/chat`
Request:
```json
{ "question": "...", "from_uid": "...", "to_uid": "..." }
```
Делает `relation_context()` в Neo4j и просит OpenAI объяснить связь.

#### POST `/roadmap`
Request:
```json
{ "subject_uid": null, "progress": { "TOP-...": 0.2 }, "limit": 30 }
```
Response: `{ "items": [...] }` — результат `plan_route()`.

#### POST `/adaptive_questions`
Request:
```json
{
  "subject_uid": null,
  "progress": {},
  "count": 10,
  "difficulty_min": 1,
  "difficulty_max": 5,
  "exclude": ["EX-..."]
}
```
Response: `{ "questions": [...] }`  
Источник вопросов: Neo4j `(:Topic)-[:HAS_QUESTION]->(:Question)` или fallback `kb/examples.jsonl`.

---

### 6.6. Construct API (`src/api/construct.py`)

База: `/v1/construct`

#### POST `/magic_fill`
Синхронно генерирует concepts/skills через AI engine и пытается дедуплицировать/сохранить concepts в Qdrant.

#### POST `/magic_fill/queue`
Ставит ARQ job `magic_fill_job`, возвращает:
```json
{ "job_id": "...", "ws": "/ws/progress?job_id=..." }
```

#### POST `/propose`
Генерирует concepts/skills из произвольного текста (без записи).

---

### 6.7. Curriculum API (`src/api/curriculum.py`)

База: `/v1/curriculum`

#### POST `/pathfind`
Request: `{ "target_uid": "TOP-..." }`  
Строит транзитивное замыкание PREREQ в Neo4j и делает топологическую сортировку.

---

### 6.8. Levels API (`src/api/levels.py`)

База: `/v1/levels`

- GET `/topic/{uid}` — возвращает уровень (stateless) по topic
- GET `/skill/{uid}` — аналогично по skill

Фактически использует `get_user_topic_level/get_user_skill_level` из `graph/utils.py` (сейчас это больше “обёртка” над текущими весами).

---

### 6.9. User API (`src/api/user.py`)

База: `/v1/user`

- POST `/compute_topic_weight` — вычисляет user_weight от base_weight и score
- POST `/compute_skill_weight` — аналогично
- POST `/roadmap` — план роадмапа по progress (через `plan_route`)

---

### 6.10. Analytics API (`src/api/analytics.py`)

База: `/v1/analytics`

- GET `/stats` — считает базовые метрики графа по `read_graph()` (Neo4j).  
  Блок `ai/quality` сейчас возвращает заглушки.

---

### 6.11. Maintenance API (`src/api/maintenance.py`)

База: `/v1/maintenance`

Ключевые операции:

- POST `/kb/rebuild_async` — запускает `kb_rebuild_job` (ARQ) или fallback thread job.
- POST `/kb/pipeline_async?auto_publish=...` — rebuild + validate + (опционально) publish.
- GET `/kb/rebuild_status?job_id=...` — статус из Redis или fallback.
- GET `/kb/rebuild_state?job_id=...` — состояние пайплайна.
- GET `/kb/validate_state?job_id=...` — результат валидации.
- POST `/kb/validate_async?job_id=...&subject_uid=...` — ставит validate job.
- POST `/kb/publish?job_id=...` — публикует, если validate ok.
- GET `/kb/published` — мета текущей публикации.
- POST `/recompute_links` — пересчёт adaptive_weight на LINKED ребрах.

---

### 6.12. Validation API (`src/api/validation.py`)

База: `/v1/validation`

- POST `/graph_snapshot`
Request:
```json
{ "snapshot": { "nodes": [...], "edges": [...] } }
```
Response:
```json
{ "ok": true|false, "errors": [...], "warnings": [...] }
```

Валидация (`src/services/validation.py`) проверяет:
- наличие nodes
- допустимые типы узлов/ребер
- отсутствие `user` nodes
- корректность ссылок source/target
- циклы в prereq-графе
- orphan nodes (warning)

---

### 6.13. WebSocket прогресса (`src/api/ws.py`)

- WS `/ws/progress?job_id=...`
- Подписка на Redis pub/sub `progress:{job_id}`
- Отправляет JSON payload клиенту

---

## 7) Фоновые задачи (ARQ worker)

Файл: `backend/src/tasks/worker.py`

### 7.1. Jobs

- `magic_fill_job(ctx, job_id, topic_uid, topic_title)`  
  Сейчас демонстрационный: публикует несколько шагов с `sleep`.

- `kb_rebuild_job(ctx, job_id, auto_publish=False)`  
  Стадии:
  1) `sync_from_jsonl()`
  2) `compute_static_weights()`
  3) `add_prereqs_heuristic()`
  4) `analyze_knowledge()`
  Затем ставит `kb_validate_job`.

  Пишет state в Redis `kb:rebuild:{job_id}` и публикует progress.

- `kb_validate_job(ctx, job_id, subject_uid=None, auto_publish=False)`  
  Делает:
  - `build_graph_from_neo4j(subject_filter=...)`
  - `validate_canonical_graph_snapshot(...)`
  Пишет `kb:validate:{job_id}` и публикует progress.
  Если `auto_publish` и ok — пишет `kb:published:current`.

### 7.2. Каналы прогресса

`publish_progress()` публикует в `progress:{job_id}` JSON вида:
```json
{ "step": "analysis", ... }
```

---

## 8) Генерация знаний и контента (AI)

### 8.1. AI Engine (структурный JSON)

`src/services/ai_engine/ai_engine.py`:
- `generate_concepts_and_skills(topic, language)` вызывает OpenAI chat с `response_format={"type":"json_object"}` и валидирует через Pydantic модели:
  - `GeneratedConcept(title, definition, reasoning)`
  - `GeneratedSkill(title, description)`
  - `GeneratedBundle(concepts, skills)`

Используется в:
- `construct/magic_fill`
- `construct/propose`

### 8.2. KB Builder (JSONL-ориентированный пайплайн)

`src/services/kb/builder.py`:
- содержит набор функций для записи в `kb/*.jsonl`:
  - add_subject/section/topic/skill/method/example/error/...
  - link_topic_skill, link_skill_method, link_topic_prereq, ...
- генерация через OpenAI:
  - синхронные `openai_chat` (requests)
  - асинхронные `openai_chat_async` (httpx)
- `generate_subject_openai_async(...)`:
  - создаёт subject/sections/topics
  - параллельно генерирует skills/methods/examples
  - добавляет goals/objectives
  - `normalize_kb()` (перезапись JSONL атомарно)

Используется в admin endpoints `/generate_subject*`.

---

## 9) Планирование роадмапа и вопросы

### 9.1. Roadmap planner

`src/services/roadmap_planner.py`:
- `plan_route(subject_uid, progress, limit, penalty_factor)`
- берёт topics и prereqs из Neo4j
- priority = `(1 - mastered) + penalty_factor * missing_prereqs`
- сортирует по priority desc

### 9.2. Questions selector

`src/services/questions.py`:
- пытается взять вопросы из Neo4j `HAS_QUESTION`
- иначе fallback на `kb/examples.jsonl`
- фильтрует по difficulty_min/max и exclude
- старается распределять по темам (не более ~2 на тему в начале)

---

## 10) Логирование и наблюдаемость

### 10.1. Логирование

`src/core/logging.py`:
- `logging.basicConfig(level=INFO)`
- если есть `structlog`, то JSON-логирование с timestamp + level.

### 10.2. Метрики

В `src/main.py` есть `prometheus_client.Counter/Histogram`, но:
- нет отдельного `/metrics` endpoint;
- `PROMETHEUS_ENABLED` не управляет включением middleware.

---

## 11) Безопасность (текущее состояние и риски)

### 11.1. JWT

`src/services/auth/jwt_tokens.py`:
- HS256
- exp задаётся datetime (PyJWT это поддерживает)
- отсутствие `JWT_SECRET_KEY` приводит к RuntimeError.

### 11.2. Admin доступ

`require_admin` (`src/api/deps.py`) проверяет:
- access token
- user exists в Postgres
- user.is_active
- role == admin

### 11.3. Риски текущей реализации

1) **Дублирование логики bearer token parsing** (`auth.py` и `deps.py` имеют похожий код).  
2) **Смешение источников истины**: Neo4j vs JSONL vs Postgres schema.  
3) **Qdrant client создаётся на import-time** (`qdrant_service.py`), что может ломать запуск при недоступном Qdrant.  
4) **CORS не включён**, хотя переменная есть.  
5) **Нет централизованного error handling** (нет глобальных exception handlers).  
6) **Нет миграций** (Postgres schema частично “ручная”, users table создаётся кодом).

---

## 12) Деплой и запуск

### 12.1. Локальная разработка

См. `backend/development.md`:
- Python 3.12
- `pip install -r requirements.txt`
- `uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload`
- `pytest -q`

### 12.2. Docker

`backend/Dockerfile.fastapi`:
- python:3.12-slim
- `pip install -r requirements.txt`
- запускает uvicorn

### 12.3. Production

См. `backend/deployment.md`:
- деплой через docker compose + Traefik
- обязательные env: Neo4j, PG_DSN, JWT_SECRET_KEY, bootstrap admin.

---

# 13) Дорожная карта улучшений (план развития)

Ниже — roadmap, ориентированный на повышение надёжности, безопасности, наблюдаемости и консистентности данных. Разбит по этапам; каждый пункт можно переносить в “Историю изменений”.

## Этап A (ближайший): стабилизация и консистентность

1) **Единый источник истины для KB**
   - Определить: Neo4j — canonical storage, JSONL — только import/export артефакт, Postgres — только users/curricula (или наоборот).
   - Убрать “тихий fallback” на JSONL там, где это критично, либо явно маркировать режимы.

2) **Миграции Postgres**
   - Ввести Alembic (или аналог) и привести `schemas/postgres.sql` и реальную БД к одному источнику.
   - Вынести `users` table creation из runtime-кода в миграции.

3) **Нормализация API ошибок**
   - Ввести единый формат ошибок (например `{error_code, message, details, trace_id}`).
   - Добавить глобальные exception handlers FastAPI.

4) **CORS**
   - Подключить CORSMiddleware и использовать `CORS_ALLOW_ORIGINS`.

## Этап B: наблюдаемость и эксплуатация

5) **Prometheus /metrics**
   - Добавить endpoint `/metrics` (условно при `PROMETHEUS_ENABLED`).
   - Добавить метрики по job pipeline (успех/ошибка, длительность стадий).

6) **Структурные логи**
   - Везде использовать `logger = structlog.get_logger()` и добавлять контекст (job_id, user_id, request_id).
   - Добавить request-id middleware.

7) **Healthchecks расширенные**
   - Проверка доступности Neo4j/Redis/Postgres/Qdrant (опционально, с таймаутами).

## Этап C: безопасность

8) **JWT hardening**
   - Добавить `aud/iss`, rotation strategy, refresh token revocation (хранилище refresh sessions).
   - Rate limiting на auth endpoints.

9) **Admin API key**
   - Либо удалить `ADMIN_API_KEY`, либо реально внедрить как альтернативный механизм (например для сервисных вызовов).

## Этап D: качество данных и графа

10) **Валидация KB как обязательный gate**
   - Запрет publish без validate ok.
   - Расширить `validate_canonical_graph_snapshot`:
     - проверка обязательных связей (subject->section->topic)
     - проверка coverage targets/skills/methods
     - проверка cross-subject prereqs (частично уже есть в `analyze_prereqs`)

11) **Версионирование KB**
   - Ввести понятие “KB release”: версия, метаданные, diff, откат.
   - Хранить snapshot (например в S3/MinIO) и ссылку в Redis/Postgres.

## Этап E: производительность

12) **Neo4j driver lifecycle**
   - Пул/синглтон драйвера вместо создания/закрытия на каждый запрос (сейчас часто `get_driver()` + `close()`).
   - Таймауты и retry policy централизованно.

13) **Qdrant init**
   - Убрать создание коллекции на import-time; сделать lazy init или отдельный startup task.

## Этап F: тестирование

14) **Контрактные тесты API**
   - pytest + httpx TestClient
   - фикстуры для Neo4j/Redis/Postgres (docker-compose test stack)

15) **Тесты пайплайна**
   - unit tests для validate, planner, jsonl normalization
   - интеграционные тесты rebuild/validate/publish

---

# 14) Рекомендуемый формат дальнейшего ведения документа

Чтобы документ оставался “единым на всю историю”:

1) Любое изменение backend сопровождается:
   - записью в “История изменений”
   - обновлением соответствующего раздела (API/Storage/Jobs/etc.)
2) Для крупных изменений добавлять:
   - “Decision record” (коротко: проблема → варианты → решение → последствия)
3) Для KB pipeline — фиксировать:
   - версию схемы JSONL
   - версию граф-модели Neo4j (labels/relations/properties)
   - версию validate правил
