# KnowledgeBaseAI — ядро графа знаний (Neo4j + Flask + FastAPI)

Единый граф базы знаний в Neo4j, веб‑интерфейс для визуализации, API для синхронизации данных, аналитики и построения адаптивных дорожных карт. Ядро статлес: оно не хранит пользователей и их прогресс; персональные веса приходят извне (из ЛМС) и используются только для вычислений.

## Структура проекта

```
web_app.py              # Flask UI и REST для графа/синхронизации/аналитики
static/js/knowledge.js  # Визуализация графа (Cytoscape)
src/services/graph/utils.py    # Клиент Neo4j, синхронизация, аналитика, веса, пререквизиты, stateless вычисления
src/main.py                    # FastAPI: эндпоинты графа/синхронизации/аналитики/роадмапов/вопросов
src/services/kb/builder.py     # Автогенерация целей/задач и автосвязи навыков-методов
scripts/clear_neo4j.py  # Полная очистка Neo4j (узлы/связи/индексы/констрейнты)
kb/*.jsonl              # Источники данных (JSONL сиды)
requirements.txt        # Зависимости (Flask, FastAPI, Neo4j и др.)
```

## Модель графа

- Узлы: `Subject`, `Section`, `Topic`, `Skill`, `Method`, `Goal`, `Objective`
- Связи:
  - `Subject-[:CONTAINS]->Section`
  - `Section-[:CONTAINS]->Topic`
  - `Subject-[:HAS_SKILL]->Skill`
  - `Skill-[:LINKED]->Method` (свойства `weight`, `confidence`, `adaptive_weight`)
  - `Topic-[:TARGETS]->(Goal|Objective)`
  - `Topic-[:PREREQ]->Topic` (пререквизиты)
- Веса:
  - `static_weight` — базовая сложность (эвристика по содержимому)
  - `dynamic_weight` — глобальная динамика графа
  - `adaptive_weight` — на `LINKED` (пересчитывается из динамичного веса навыка)

## Быстрый старт (локально)

- Установка зависимостей:

  ```
  pip install -r requirements.txt
  ```

- Переменные окружения (Neo4j):

  ```
  export NEO4J_URI="REDACTED_NEO4J_URI"
  export NEO4J_USER="neo4j"
  export NEO4J_PASSWORD="<пароль>"
  ```

- Запуск Flask UI:

  ```
  python web_app.py
  ```

  Откройте `http://localhost:5000/knowledge`.

- Запуск FastAPI:

  ```
  uvicorn src.main:app --host 0.0.0.0 --port 8000
  ```

  Документация: `http://localhost:8000/docs`.

## Данные и синхронизация

- Сиды JSONL: `kb/subjects.jsonl`, `kb/sections.jsonl`, `kb/topics.jsonl`, `kb/skills.jsonl`, `kb/methods.jsonl`, `kb/skill_methods.jsonl`, `kb/topic_goals.jsonl`, `kb/topic_objectives.jsonl`.
- Синхронизация в Neo4j:
  - REST: `POST /api/neo4j_sync` (Flask)
  - Python: `from src.services.graph.utils import sync_from_jsonl`
- Автогенерация:
  - Цели/задачи: `from src.services.kb.builder import generate_goals_and_objectives`
  - Автосвязи навыков-методов: `from src.services.kb.builder import autolink_skills_methods`

## Аналитика (качество графа)

- `GET /api/analysis` — возвращает агрегаты и проблемные списки:
  - `topics_without_targets`, `skills_without_methods`, `methods_without_links`, `orphan_sections`
  - покрытия: `topic_targets_coverage`, `skill_linkage_coverage`

## Визуализация (Flask UI)

- `GET /knowledge` — страница визуализации графа
- `GET /api/graph?subject_uid=...` — данные для визуализации (из Neo4j при наличии ENV)
- CRUD для ввода через UI‑формы:
  - `POST /api/subjects`, `/api/sections`, `/api/topics`, `/api/skills`, `/api/methods`
  - `POST /api/topic_goals`, `/api/topic_objectives`, `/api/skill_methods`

## FastAPI (stateless ядро)

- Основные маршруты:
  - `POST /v1/admin/generate_subject` — генерация предмета (разделы/темы/навыки/методы/примеры)
  - `POST /v1/admin/generate_subject_import` — генерация + импорт в Neo4j + аналитика
  - `POST /v1/maintenance/kb/rebuild_async` — асинхронная пересборка KB (импорт, веса, пререквизиты, аналитика)
  - `GET  /v1/maintenance/kb/rebuild_status?job_id=...` — статус джобы пересборки
  - `POST /v1/maintenance/recompute_links` — пересчёт `adaptive_weight` на `LINKED`
  - `GET  /v1/levels/topic/{uid}` — уровень темы (на основе глобальных весов)
  - `GET  /v1/levels/skill/{uid}` — уровень навыка (на основе глобальных весов)
  - `POST /v1/user/roadmap` — статическая персональная дорожная карта
  - `POST /v1/graph/roadmap` — roadmap (алиас, проксирует в `src.api.user`)
  - `GET  /v1/graph/viewport?center_uid=...&depth=1` — окрестность узла
  - `POST /v1/graph/chat` — объяснение связи (требует OpenAI)
  - `POST /v1/graph/adaptive_questions` — подбор вопросов/примеров по темам
  - `POST /v1/validation/graph_snapshot` — проверка снапшота графа
  - `POST /v1/construct/magic_fill` — дополнение концептов/навыков по теме (OpenAI+Qdrant)
  - `POST /v1/construct/magic_fill/queue` — постановка задачи в очередь (Redis/Arq)
  - `POST /v1/construct/propose` — предложить набор концептов/навыков
  - `POST /v1/curriculum/pathfind` — поиск пути в учебном графе
  - `GET  /v1/analytics/stats` — агрегаты/метрики по графу
  - `POST /v1/admin/purge_users` — очистка пользовательских артефактов в Neo4j
  - `POST /v1/admin/curriculum` — создать curriculum
  - `POST /v1/admin/curriculum/nodes` — добавить узлы curriculum
  - `GET  /v1/admin/curriculum/graph_view` — получить graph view curriculum
  - `GET  /v1/graphql` — GraphQL (если установлен `strawberry`)

- Примеры вызовов:
  - Генерация и импорт:
    ```
    curl -X POST http://localhost:8000/v1/admin/generate_subject_import \
      -H 'Content-Type: application/json' \
      -d '{"subject_uid":"SUB-MATH","subject_title":"Математика","language":"ru"}'
    ```
  - Пересборка KB:
    ```
    curl -X POST http://localhost:8000/v1/maintenance/kb/rebuild_async
    curl "http://localhost:8000/v1/maintenance/kb/rebuild_status?job_id=173..."
    ```
  - Дорожная карта:
    ```
    curl -X POST http://localhost:8000/v1/user/roadmap \
      -H 'Content-Type: application/json' \
      -d '{"subject_uid":null,"progress":{"TOP-A":0.2,"TOP-B":0.6},"limit":30}'
    ```
  - Вопросы по темам:
    ```
    curl -X POST http://localhost:8000/v1/graph/adaptive_questions \
      -H 'Content-Type: application/json' \
      -d '{"subject_uid":null,"progress":{},"count":10,"difficulty_min":1,"difficulty_max":5}'
    ```

## Пререквизиты и статичные веса

- `compute_static_weights()` — устанавливает `static_weight` для `Topic`/`Skill` по эвристике (длина текста, продвинутые термины), инициализирует `dynamic_weight` при необходимости.
- `add_prereqs_heuristic()` — добавляет базовые `PREREQ` связи для ключевых тем.

## Служебные утилиты

- Очистка графа: `python scripts/clear_neo4j.py` (удаляет узлы/связи/индексы/констрейнты)

## Данные пользователя

- Данные пользователя и его веса хранятся во внешней ЛМС, ядро KnowledgeBaseAI остаётся универсальным сервисом графа предметной области. Ядро никогда не создаёт узлы `User` и не пишет персональные связи в граф.

## Переменные окружения

- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` — доступ к Neo4j (обязательные)
- `KB_DOMAIN`, `KB_ALT_DOMAIN` — домены для UI
- `LETSENCRYPT_EMAIL` — email для Let’s Encrypt
- `ADMIN_API_KEY` — ключ для небезопасных операций API

### Настройка .env

1. Скопируйте пример:

```
cp .env.example .env
```

2. Отредактируйте `.env`, указав свои значения для доменов, email и подключения к Neo4j.

3. Убедитесь, что DNS‑записи для доменов UI и API указывают на IP сервера.

### Запуск в контейнерах

```
docker compose build --no-cache
docker compose up -d
```

Traefik выпустит сертификаты автоматически (HTTP‑challenge). Для HSTS/HTTPS убедитесь, что у поддоменов `api.*` есть корректные DNS записи.

## Развертывание

- Запуск в Docker/оркестрации возможен через любой стандартный образ Python. Пробросьте `NEO4J_*` ENV и поднимите два процесса:
  - Flask (`python web_app.py`)
  - FastAPI (`uvicorn src.main:app --host 0.0.0.0 --port 8000`)
- Traefik/Nginx — по желанию, для маршрутизации HTTP‑трафика на порты 5000/8000. Секреты передавайте только через переменные окружения. 

## Формат вопросов

- JSONL (`kb/examples.jsonl`):

```
{"uid":"EX-123","title":"Найдите корень","statement":"2x - 5 = 11","topic_uid":"TOP-LINEQ","difficulty":3}
```

## Примеры

- Синхронизация:

  ```
  curl -X POST http://localhost:5000/api/neo4j_sync
  ```

- Аналитика:

  ```
  curl http://localhost:5000/api/analysis
  ```


## Примечания безопасности

- Не храните пароли/URI в коде и файлах репозитория. Используйте только переменные окружения.
– Глобальные данные графа отделены от пользовательских весов: персональные веса не хранятся в ядре и приходят из ЛМС как параметры.
- Пайплайн создания KB (см. `/kb/rebuild_async`):
  1. Загрузка/генерация сидов (`kb/*.jsonl`)
  2. Импорт в Neo4j (`sync_from_jsonl()`)
  3. Запуск `compute_static_weights()` и `add_prereqs_heuristic()`
  4. Аналитика (`/api/analysis` или `analyze_knowledge()`): логирование проблем
  5. Возврат статуса джоба: `ok`, `warnings`, `errors`
