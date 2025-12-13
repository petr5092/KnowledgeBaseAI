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
## Migration\n- fastapi_app.py now re-exports Headless app from src/main.py.\n- GraphQL expanded: TopicDetails includes examples/errors (JSONL fallback).\n- Integration tests added: GraphQL, curriculum without Postgres, planner, selector, levels.\n
