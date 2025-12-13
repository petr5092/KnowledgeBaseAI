# Отчёт о рефакторинге (51d1a78)
## Выполненные изменения
- Исправлена фильтрация сложности вопросов: `/root/KnowledgeBaseAI/services/question_selector.py:68`–`74`.
- Исправлена логика уровней знания по весу: `/root/KnowledgeBaseAI/neo4j_utils.py:72`–`79`.
- Убраны дубли индексов в `ensure_constraints`: `/root/KnowledgeBaseAI/neo4j_utils.py:121`–`136`.
- Внедрён AtomicWrite в операции записи JSONL:
  - `/root/KnowledgeBaseAI/web_app.py:43`–`56`, `/root/KnowledgeBaseAI/web_app.py:50`–`56`.
  - `/root/KnowledgeBaseAI/kb_builder.py:30`–`40`, `/root/KnowledgeBaseAI/kb_builder.py:36`–`40`.
- Переведён векторный сервис на Qdrant:
  - Добавлен `qdrant_service`: `/root/KnowledgeBaseAI/src/services/vector/qdrant_service.py`.
  - Обновлён конструктор: `/root/KnowledgeBaseAI/src/api/construct.py:4`–`7`, `/root/KnowledgeBaseAI/src/api/construct.py:31`–`37`.
  - Добавлена зависимость: `/root/KnowledgeBaseAI/requirements.txt`.
- Реализована очередь для конструктора:
  - Эндпоинт `/v1/construct/magic_fill/queue`: `/root/KnowledgeBaseAI/src/api/construct.py:31`–`37`.
  - Воркер ARQ: `/root/KnowledgeBaseAI/src/tasks/worker.py`.
  - WebSocket прогресс: `/root/KnowledgeBaseAI/src/api/ws.py`.
- Реализованы реальные аналитические метрики:
  - `/v1/analytics/stats`: `/root/KnowledgeBaseAI/src/api/analytics.py:6`–`18`.
- Добавлен `curriculum.pathfind` без APOC:
  - Эндпоинт: `/root/KnowledgeBaseAI/src/api/curriculum.py`.
  - Подключён роутер: `/root/KnowledgeBaseAI/src/main.py:32`–`35`.
## Проверки
- Линейная проверка импортов и зависимостей по изменённым файлам.
- Векторный сервис: Qdrant URL берётся из `QDRANT_URL`; коллекция `concepts` создаётся при отсутствии.
- Очередь: `POST /v1/construct/magic_fill/queue` возвращает `job_id` и путь для WebSocket; воркер публикует прогресс в канал `progress:{job_id}`.
- Аналитика: метрики вычисляются из текущего графа Neo4j, не требуют APOC.
- Curriculum: путь строится через `PREREQ*0..` без плагинов.
## Рекомендации по деплою
- Обновить контейнеры: установить `qdrant-client` и обеспечить доступ к Qdrant (`QDRANT_URL`).
- Запустить ARQ воркер: `arq src.tasks.worker.WorkerSettings`.
- Прокси/Traefik остаются без изменений.
## Следующее
- Консолидация монолитного `fastapi_app.py` в модульные роутеры `src/api/*`.
- Расширение аналитики: токены/cost/latency и качество (сироты/мерджи).
- Юнит‑тесты: `tests/` для ключевых модулей.

## Дополнительно выполнено
- Очистка пользовательских артефактов в графе: добавлен эндпоинт `/v1/admin/purge_users` и функция `purge_user_artifacts()` (`src/services/graph/neo4j_repo.py`, `src/api/admin.py`).
- Вьюпорт графа переработан: `/v1/graph/viewport` возвращает окрестность узла по `center_uid` и глубине (`src/api/graph.py`, `src/services/graph/neo4j_repo.py::neighbors`).
- Адаптивное планирование дорожной карты: добавлен планировщик `plan_route(...)` и эндпоинт `/v1/graph/roadmap` (`src/services/roadmap_planner.py`, `src/api/graph.py`).
- Конструктор знаний: добавлен `/v1/construct/propose` для генерации предложений (концепты/навыки) на основе текста (`src/api/construct.py`).

## Консолидация API (частично выполнена)
- Добавлен модульный роутинг под Headless:
  - `/v1/admin/curriculum*` (создание, узлы, просмотр) — `src/api/admin_curriculum.py`.
  - `/v1/admin/generate_subject*` — `src/api/admin_generate.py`.
  - `/v1/levels/*` — базовые уровни темы/навыка — `src/api/levels.py`.
  - Подключено в `src/main.py`.
- Следующий шаг: перенос оставшихся монолитных эндпоинтов из `fastapi_app.py` под `src/api/*`.

## Перенос монолитных эндпоинтов (выполнено)
- Добавлены роутеры:
  - `/v1/maintenance/*` — пересборка KB и пересчёт связей.
  - `/v1/user/*` — вычисление пользовательских весов, персональный маршрут.
  - `/v1/graphql` — базовый GraphQL слой с Neo4j и Postgres резолверами.
- Обновлён `src/main.py` для подключения роутеров.

## Визуализатор
- Режимы фильтрации по типам связей (`contains`, `has_skill`, `PREREQ`, `targets`, `linked`) и кнопка «Окрестность» для ленивой подгрузки.

## Тесты
- Добавлены базовые Pytest тесты: planner, selector, levels, импорт.
## CI: Run tests\n- Use Pytest to run unit tests.\n- Install dependencies and run: pip install -r requirements.txt && pytest -q
## Migration
- fastapi_app.py now re-exports Headless app from src/main.py.
- GraphQL expanded: TopicDetails includes examples/errors (JSONL fallback).
- Integration tests added: GraphQL, curriculum without Postgres, planner, selector, levels.

# Подготовка к рефактору (2025-12-13 04:52 UTC)

## Таблица соответствий (документы → реализация)

| Документ | Требование/идея | Статус | Где в коде / примечание |
|---|---|---:|---|
| `Vision.md` | KnowledgeBaseAI как ядро/фабрика + API для внешних систем | ✅ | `src/main.py:54-66`, роутеры `src/api/*` |
| `Vision.md` | Разделение: KB пишет структуру, внешняя LMS хранит прогресс | ✅ | Roadmap/questions принимают `progress` извне: `src/api/user.py:27-35`, `src/api/graph.py:42-71` |
| `knowledge_constructor.md` | Neo4j хранит только канонические знания (без User/Progress) | 🟡 | В целом соблюдено, но есть legacy: `src/services/graph/utils.py:83-84` (`MERGE (:User ...)`) |
| `knowledge_constructor.md` | Stateless API: roadmap + adaptive questions на входных весах | ✅ | Roadmap: `src/api/user.py:32-35`, `src/api/graph.py:47-50`; Questions: `src/api/graph.py:60-71` |
| `knowledge_constructor.md` | Questions/examples выдаются из KB (не генерируются “из воздуха”) | ✅ | `src/services/questions.py` (JSONL fallback + Neo4j при наличии) |
| `knowledge_constructor.md` | Curriculum слой в Postgres, не мутирует канон | ✅ | `src/services/curriculum/repo.py`, `src/api/admin_curriculum.py` |
| `knowledge_constructor.md` | Async, verifiable KB pipeline (LLM → validate → review → publish) | 🟡 | Есть rebuild pipeline (thread-based): `src/services/jobs/rebuild.py`, `src/api/maintenance.py`; стадий review/publish нет |
| `knowledge_constructor.md` | Validators: проверка инвариантов перед publish | ❌ | `src/services/validation.py` — заглушка |
| `knowledge_model.md` / `base_concept.md` | Формальная модель Subject/Section/Topic/Skill/Method/Goal/Objective | 🟡 | Загрузка в Neo4j есть: `src/services/graph/utils.py:86+`, но не все поля/enum из доков отражены |
| `knowledge_model.md` | Example/Question как сущность графа + связи Example↔Skill/Error | 🟡 | API работает через JSONL; Neo4j-ветка селектора ожидает `HAS_QUESTION`, но `sync_from_jsonl()` не грузит `Question` |
| `knowledge_model.md` | difficulty в диапазоне [0..1] | 🟡 | В JSONL/README 1..5, но нормализация в [0..1] есть: `src/services/questions.py:57-63,76-82` |
| `base_concept.md` | Neo4j constraints/indexes | ✅ | `src/services/graph/utils.py:49-70` |
| `Vision.md` | Redis/Arq для очередей/фоновых задач | 🟡 | Очередь есть для `magic_fill`: `src/api/construct.py:47-54`, `src/tasks/worker.py`; rebuild KB не в очереди |
| `Vision.md` | GraphQL слой | 🟡 | Опционально подключается: `src/main.py:15-18,64-65`; есть устаревший импорт: `src/api/graphql.py:5` |

## TODO

- [x] Удалить остатки user-логики в графовом слое (в т.ч. `ensure_user_profile` с `(:User)`): `src/services/graph/utils.py`.
- [x] Реализовать реальную валидацию снапшота канонического графа (инварианты, DAG для `PREREQ`, orphan-узлы): `src/services/validation.py`, `src/api/validation.py`.
- [x] Привести GraphQL к актуальным импортам и сервисам (`services.curriculum_repo` → `src.services.curriculum.repo`): `src/api/graphql.py:5`.
- [x] Определить единый источник “вопросов/примеров” как JSONL (SSOT) и исправить пути к KB: `src/services/kb/jsonl_io.py`, `src/services/questions.py`, `src/api/graphql.py`.
- [x] Выровнять обработку сложности: устойчивый парсинг difficulty + нормализация в [0..1] на выдаче: `src/services/questions.py`.
- [ ] Если нужен “verifiable pipeline”: добавить стадии staging/review/publish и блокировку publish при ошибках валидаторов (сейчас rebuild — упрощённый).
- [x] Перевести rebuild KB на очередь (Redis/Arq) для соответствия инфраструктурной модели из Vision.

## Отчет по проделанной работе (2025-12-13 05:07 UTC)

- Удален остаток user-логики из графового слоя: убрана функция, создававшая `(:User ...)` (`src/services/graph/utils.py`).
- Реализована базовая валидация снапшота канонического графа: структура nodes/edges, ссылочная целостность, запрет user-узлов, детект циклов `PREREQ`, предупреждения по orphan-узлам (`src/services/validation.py`).
- GraphQL приведен к актуальным импортам curriculum repo (`src/api/graphql.py`).
- Зафиксирован источник вопросов/примеров как JSONL (SSOT) и исправлены пути к папке `kb/` для JSONL IO/селекторов.
- Стандартизирована обработка difficulty в селекторе вопросов: устойчивый парсинг и нормализация в [0..1] (`src/services/questions.py`).
- Добавлен endpoint `/v1/maintenance/kb/pipeline_async` для запуска rebuild+validate (validate запускается автоматически после rebuild).
- Добавлен опциональный auto-publish: при `auto_publish=true` в `/v1/maintenance/kb/pipeline_async` и при `validate.ok == true` автоматически обновляется `kb:published:current`.

