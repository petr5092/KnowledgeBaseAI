# Глубокий анализ архитектуры и кодовой базы KnowledgeBaseAI

## Общее устройство
- Платформа знаний опирается на Neo4j для канонического графа, Postgres для curriculum, и векторное хранилище для семантической дедупликации. Есть два API‑слоя: монолит `fastapi_app.py` и модульная Headless‑платформа в `src/*`. Дополнительно — Flask UI для админских операций и визуализации.
- Данные управления (Subjects/Sections/Topics/Skills/Methods/Goals/Objectives/Links/Examples/ContentUnits) хранятся в `kb/*.jsonl`, с импортом в Neo4j.
- Асинхронные генерации (OpenAI) присутствуют в `kb_builder.py` и `src/services/ai_engine/ai_engine.py`, контролируются через FastAPI и Flask.

## Дерево проекта (высокоуровневое)
- `neo4j_utils.py` — работа с графом: импорт, веса, роадмапы, анализ
- `fastapi_app.py` — монолитный FastAPI: персонализация, роадмапы, админ‑эндпоинты
- `web_app.py` — Flask UI с CRUD JSONL и прокси на FastAPI
- `kb_builder.py` — генерации канона (смешанный синхронный/асинхронный режим)
- `kb_jobs.py` — асинхронные джобы (импорт, веса, пререквизиты, аналитика)
- `services/` — утилиты: выбор вопросов, Postgres curriculum
- `src/` — Headless платформа: конфиг/логирование, API роутеры, сервисы графа/векторов/AI, фоновые задачи
- `docker-compose.yml`, `traefik/traefik.yml` — оркестрация и маршрутизация
- `requirements.txt` — зависимости (FastAPI/Flask/Neo4j/OpenAI/Chromadb/Structlog/Prometheus/Redis/ARQ/httpx/NetworkX)

## Ключевые модули и функции

### Neo4j утилиты
- `neo4j_utils.py:compute_user_weight` `/root/KnowledgeBaseAI/neo4j_utils.py:19` — перерасчёт пользовательского веса из базового и `score`.
- `neo4j_utils.py:compute_topic_user_weight` `/root/KnowledgeBaseAI/neo4j_utils.py:26` — статлес вес темы, с чтением базового веса из Neo4j.
- `neo4j_utils.py:compute_skill_user_weight` `/root/KnowledgeBaseAI/neo4j_utils.py:49` — статлес вес навыка, аналогично теме.
- `neo4j_utils.py:knowledge_level_from_weight` `/root/KnowledgeBaseAI/neo4j_utils.py:72` — маппинг веса→уровень.
- `neo4j_utils.py:get_driver` `/root/KnowledgeBaseAI/neo4j_utils.py:99` — инициализация драйвера Neo4j из env.
- `neo4j_utils.py:ensure_constraints` `/root/KnowledgeBaseAI/neo4j_utils.py:109` — создание индексов/констрейнтов.
- `neo4j_utils.py:ensure_weight_defaults(_repo)` `/root/KnowledgeBaseAI/neo4j_utils.py:138`, `/root/KnowledgeBaseAI/neo4j_utils.py:146` — установка дефолтных static/dynamic весов.
- `neo4j_utils.py:sync_from_jsonl` `/root/KnowledgeBaseAI/neo4j_utils.py:159` — импорт JSONL в Neo4j: узлы, связи, цели/задачи, контент‑юниты.
- `neo4j_utils.py:build_graph_from_neo4j` `/root/KnowledgeBaseAI/neo4j_utils.py:299` — сбор графа для визуализатора.
- `neo4j_utils.py:analyze_knowledge` `/root/KnowledgeBaseAI/neo4j_utils.py:362` — метрики качества: сироты, покрытие, агрегаты.
- `neo4j_utils.py:update_dynamic_weight` `/root/KnowledgeBaseAI/neo4j_utils.py:400` — обновление глобального веса темы.
- `neo4j_utils.py:update_skill_dynamic_weight` `/root/KnowledgeBaseAI/neo4j_utils.py:426` — обновление веса навыка и пересчёт адаптивных весов связей.
- `neo4j_utils.py:get_current_knowledge_level` `/root/KnowledgeBaseAI/neo4j_utils.py:453` — текущие веса темы.
- `neo4j_utils.py:get_current_skill_level` `/root/KnowledgeBaseAI/neo4j_utils.py:463` — текущие веса навыка.
- `neo4j_utils.py:build_adaptive_roadmap` `/root/KnowledgeBaseAI/neo4j_utils.py:473` — глобальная дорожная карта: темы→skills→methods.
- `neo4j_utils.py:build_user_roadmap_stateless` `/root/KnowledgeBaseAI/neo4j_utils.py:503` — персональная дорожная карта без записи в граф; учитывает пререквизиты.
- `neo4j_utils.py:recompute_relationship_weights` `/root/KnowledgeBaseAI/neo4j_utils.py:635` — пересчёт `adaptive_weight` на `Skill→Method`.
- `neo4j_utils.py:recompute_adaptive_for_skill` `/root/KnowledgeBaseAI/neo4j_utils.py:644` — локальный пересчёт для одного навыка.
- `neo4j_utils.py:search_titles` `/root/KnowledgeBaseAI/neo4j_utils.py:705` — поиск по `title`.
- `neo4j_utils.py:health` `/root/KnowledgeBaseAI/neo4j_utils.py:716` — быстрая проверка Neo4j.
- `neo4j_utils.py:list_items` `/root/KnowledgeBaseAI/neo4j_utils.py:727` — списки сущностей по типу.
- `neo4j_utils.py:get_node_details` `/root/KnowledgeBaseAI/neo4j_utils.py:755` — детали узла, включая связи и веса.
- `neo4j_utils.py:fix_orphan_section` `/root/KnowledgeBaseAI/neo4j_utils.py:793` — подвязка секции к предмету при сиротстве.
- `neo4j_utils.py:compute_static_weights` `/root/KnowledgeBaseAI/neo4j_utils.py:804` — эвристика статичных весов + монотоничность по PREREQ.
- `neo4j_utils.py:analyze_prereqs` `/root/KnowledgeBaseAI/neo4j_utils.py:854` — цикл/межпредметные ошибки/аномалии.
- `neo4j_utils.py:add_prereqs_heuristic` `/root/KnowledgeBaseAI/neo4j_utils.py:911` — добавление пререквизитов по правилам.
- `neo4j_utils.py:link_remaining_skills_methods` `/root/KnowledgeBaseAI/neo4j_utils.py:941` — автосвязи skills→methods по заранее заданным парам.
- `neo4j_utils.py:link_skill_to_best` `/root/KnowledgeBaseAI/neo4j_utils.py:976` — выбрать лучший метод для навыка и связать.

### Монолит FastAPI
- `fastapi_app.py:startup_event` `/root/KnowledgeBaseAI/fastapi_app.py:72` — дефолтные веса при запуске.
- `fastapi_app.py:/knowledge_level/{topic_uid}` `/root/KnowledgeBaseAI/fastapi_app.py:110` — текущий уровень темы.
- `fastapi_app.py:/skill_level/{skill_uid}` `/root/KnowledgeBaseAI/fastapi_app.py:123` — текущий уровень навыка.
- `fastapi_app.py:/roadmap` `/root/KnowledgeBaseAI/fastapi_app.py:136` — глобальная дорожная карта.
- `fastapi_app.py:/user/roadmap` `/root/KnowledgeBaseAI/fastapi_app.py:178` — персональная дорожная карта (stateless).
- `fastapi_app.py:/adaptive/questions` `/root/KnowledgeBaseAI/fastapi_app.py:215` — выбор задач по темам и диап. сложностей.
- `fastapi_app.py:/kb/rebuild_async` `/root/KnowledgeBaseAI/fastapi_app.py:233` — запуск джобы по пересборке KB.
- `fastapi_app.py:/kb/rebuild_status` `/root/KnowledgeBaseAI/fastapi_app.py:237` — статус джобы.
- `fastapi_app.py:/recompute_links` `/root/KnowledgeBaseAI/fastapi_app.py:242` — пересчёт адаптивных весов связей.
- Админ‑curriculum: `/admin/curriculum` `/root/KnowledgeBaseAI/fastapi_app.py:265`, `/admin/curriculum/nodes` `/root/KnowledgeBaseAI/fastapi_app.py:279`, `/curriculum/{code}/graph_view` `/root/KnowledgeBaseAI/fastapi_app.py:287`.
- Генерации канона: `/admin/generate_subject` `/root/KnowledgeBaseAI/fastapi_app.py:305`, `/admin/generate_subject_import` `/root/KnowledgeBaseAI/fastapi_app.py:322`.

### Flask UI
- Граф: `/api/graph` `/root/KnowledgeBaseAI/web_app.py:370`; локальный сбор `build_graph` `/root/KnowledgeBaseAI/web_app.py:194`.
- CRUD JSONL: `/api/subjects|sections|topics|skills|methods|skill_methods|topic_goals|topic_objectives` `/root/KnowledgeBaseAI/web_app.py:388` и далее.
- Нормализация: `/api/normalize_kb` `/root/KnowledgeBaseAI/web_app.py:533`.
- Синхронизация: `/api/neo4j_sync` `/root/KnowledgeBaseAI/web_app.py:764`.
- Аналитика: `/api/analysis` `/root/KnowledgeBaseAI/web_app.py:776`.
- Curriculum UI/Proxy: `/curriculum` `/root/KnowledgeBaseAI/web_app.py:360`, `/api/admin/curriculum*` `/root/KnowledgeBaseAI/web_app.py:806`, `/api/curriculum/graph_view` `/root/KnowledgeBaseAI/web_app.py:834`.
- Конструктор: `/constructor` `/root/KnowledgeBaseAI/web_app.py:365`, прокси генераций `/root/KnowledgeBaseAI/web_app.py:784`, `/root/KnowledgeBaseAI/web_app.py:795`.

### Генерации канона
- `kb_builder.py:openai_chat(_async)` `/root/KnowledgeBaseAI/kb_builder.py:305`, `/root/KnowledgeBaseAI/kb_builder.py:340` — прямые OpenAI вызовы.
- Множество `generate_*_openai(_async)` для теории/примеров/методов/секций/тем/скиллов — см. `/root/KnowledgeBaseAI/kb_builder.py:376`, `402`, `429`, `459`, `471`, `491`, `511`, `531`, `551`.
- Оркестратор `generate_subject_openai_async` `/root/KnowledgeBaseAI/kb_builder.py:571` — полная генерация предмета с записью в JSONL.
- Нормализация KB: `normalize_kb` `/root/KnowledgeBaseAI/kb_builder.py:639`.
- Bootstrap из `skill_topics`: `/root/KnowledgeBaseAI/kb_builder.py:650`.

### Джобы
- `kb_jobs.py:start_rebuild_async` `/root/KnowledgeBaseAI/kb_jobs.py:39`, `kb_jobs.py:get_job_status` `/root/KnowledgeBaseAI/kb_jobs.py:46` — тредовый раннер стадий: импорт→веса→пререквизиты→анализ, см. `_run_job` `/root/KnowledgeBaseAI/kb_jobs.py:10`.

### Headless платформа (`src/*`)
- Конфиг/логирование: `src/core/config.py` `/root/KnowledgeBaseAI/src/core/config.py:4`, `src/core/logging.py` `/root/KnowledgeBaseAI/src/core/logging.py:4`.
- Точка входа: `src/main.py` `/root/KnowledgeBaseAI/src/main.py:11` — метрики Prometheus и роутеры.
- API:
  - `src/api/graph.py` — вьюпорт `/v1/graph/viewport` `/root/KnowledgeBaseAI/src/api/graph.py:15`, чат с графом `/v1/graph/chat` `/root/KnowledgeBaseAI/src/api/graph.py:24`.
  - `src/api/construct.py` — `/v1/construct/magic_fill` `/root/KnowledgeBaseAI/src/api/construct.py:14`.
  - `src/api/analytics.py` — `/v1/analytics/stats` `/root/KnowledgeBaseAI/src/api/analytics.py:6`.
  - `src/api/ws.py` — `/ws/progress` `/root/KnowledgeBaseAI/src/api/ws.py:8`.
- Граф‑сервисы: `src/services/graph/neo4j_repo.py:read_graph` `/root/KnowledgeBaseAI/src/services/graph/neo4j_repo.py:13`, `relation_context` `/root/KnowledgeBaseAI/src/services/graph/neo4j_repo.py:34`; `graph_service.py` (DAG/связность/расстояния).
- AI‑движок: `src/services/ai_engine/ai_engine.py:generate_concepts_and_skills` `/root/KnowledgeBaseAI/src/services/ai_engine/ai_engine.py:22` — OpenAI + instructor, строгие схемы `GeneratedBundle`.
- Векторы: `src/services/vector/chroma_service.py:embed_text` `/root/KnowledgeBaseAI/src/services/vector/chroma_service.py:11`, `upsert_concept` `/root/KnowledgeBaseAI/src/services/vector/chroma_service.py:15`, `query_similar` `/root/KnowledgeBaseAI/src/services/vector/chroma_service.py:18`.
- Домен: `src/domain/models.py` — `Concept/Skill/Misconception/Relation` строгие модели.
- Утилиты: `src/utils/atomic_write.py:write_jsonl_atomic` `/root/KnowledgeBaseAI/src/utils/atomic_write.py:5`.
- Фоновые задачи: `src/tasks/worker.py` — публикация прогресса ARQ/Redis.

## Данные и схема
- JSONL буферы: `kb/*.jsonl` — сущности: `subjects`, `sections`, `topics`, `skills`, `methods`, связи `skill_methods`, `topic_skills|skill_topics`, цели/задачи, `examples`, `content_units`, и пререквизиты `topic_prereqs`.
- Импорт в Neo4j — `sync_from_jsonl` создает констрейнты, индексы, узлы и связи: `Subject→Section→Topic`, `Topic→Goal|Objective`, `Subject→Skill`, `Skill→Method (LINKED)`, `Topic→Skill (USES_SKILL)`, `Topic→Topic (PREREQ)`, `Topic→ContentUnit (HAS_*_PATH)`.

## API сводка
- Flask API: получение графа, CRUD, нормализация, синхронизация, анализ, админ‑curriculum, прокси генерации.
- Монолит FastAPI: глобальные/персональные уровни, роадмапы, адаптивные вопросы, джобы пересборки, админ curriculum, генерации канона.
- Headless FastAPI: чат с графом (контекст связи и объяснение), конструктор (magic fill с дедупликацией), аналитика (заглушки), WebSocket прогресса.

## Наблюдаемость и DevOps
- Prometheus метрики в `src/main.py` (счетчик запросов, латентность).
- Traefik конфигурация: HTTP/HTTPS и Neo4j Bolt прокси, ACME TLS.
- Docker Compose: сервисы Flask/FastAPI/Neo4j/Postgres/Redis/Prometheus/Grafana и Qdrant (для векторов).

## Замеченные проблемы и несоответствия
- Несогласованность векторного стека: код использует `Chromadb` REST (`src/services/vector/chroma_service.py`), а Compose поднимает `qdrant`. Требуется унификация (либо заменить код на Qdrant, либо добавить сервис Chroma).
- Дублирование индексов в `ensure_constraints` `/root/KnowledgeBaseAI/neo4j_utils.py:121`–`135` — повторное объявление `*_title_idx`.
- Ошибка в `services/question_selector.py:select_examples_for_topics`: переменная `d` не определена при фильтрации сложности `/root/KnowledgeBaseAI/services/question_selector.py:68`–`73`. Должно быть `d_int` или прямое значение из `r`.
- Маппинг `knowledge_level_from_weight` кажется инвертированным: `w<0.3 → "high"` `/root/KnowledgeBaseAI/neo4j_utils.py:75`–`79`. Логично: низкий вес → низкий уровень; требуется исправление.
- Смешение архитектур: сосуществуют `fastapi_app.py` и модульная `src/main.py` с пересекающейся функциональностью; отсутствует единый слой для персонализации/админки.
- Записи JSONL выполняются небезопасно (прямой `append_jsonl`/`rewrite_jsonl`) в `web_app.py` и `kb_builder.py`; атомарная запись реализована только в `src/utils/atomic_write.py` и не применяется повсеместно.
- Отсутствуют автотесты в `tests/` (директория не обнаружена), что снижает уверенность при рефакторинге.
- Отсутствует полноценный `/v1/analytics/stats` (данные заглушечные), и учёт токенов/cost/latency для AI вызовов.
- Фоновая очередь для `/v1/construct/magic_fill` не реализована (в Headless — синхронный путь), тогда как WS прогресс есть.
- Curriculum pathfinding API отсутствует (требуется топологическая сортировка + ручные веса).

## Итог
- Кодовая база функциональна и покрывает базовые сценарии: импорт/веса/роадмапы/аналитика/генерация. Однако архитектура фрагментирована между монолитом и новой Headless‑структурой, есть технические долги (безопасность записи, недочёты в векторном стеке, баг в селекторе вопросов, инверсия уровней знание→вес). Рефакторинг должен сфокусироваться на унификации API, строгой записи данных, исправлении ошибок, а также интеграции фоновых задач и полноценной аналитики.
