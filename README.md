# KnowledgeBaseAI — граф знаний с персонализацией (Neo4j + Flask + FastAPI)

Единый граф базы знаний в Neo4j, веб‑интерфейс для визуализации, API для синхронизации данных, аналитики и построения персонализированных дорожных карт обучения. Глобальные статичные веса задают сложность материала, а динамичные веса обновляются по прогрессу учащихся (персонально на пользователя).

## Структура проекта

```
web_app.py              # Flask UI и REST для графа/синхронизации/аналитики
static/js/knowledge.js  # Визуализация графа (Cytoscape)
neo4j_utils.py          # Клиент Neo4j, синхронизация, аналитика, веса, пререквизиты, персонализация
fastapi_app.py          # FastAPI: тесты, обновление весов, дорожные карты, пользовательские API
kb_builder.py           # Автогенерация целей/задач и автосвязи навыков-методов
scripts/clear_neo4j.py  # Полная очистка Neo4j (узлы/связи/индексы/констрейнты)
kb/*.jsonl              # Источники данных (JSONL сиды)
requirements.txt        # Зависимости (Flask, FastAPI, Neo4j и др.)
```

## Модель графа

- Узлы: `Subject`, `Section`, `Topic`, `Skill`, `Method`, `Goal`, `Objective`, `User`
- Связи:
  - `Subject-[:CONTAINS]->Section`
  - `Section-[:CONTAINS]->Topic`
  - `Subject-[:HAS_SKILL]->Skill`
  - `Skill-[:LINKED]->Method` (свойства `weight`, `confidence`, `adaptive_weight`)
  - `Topic-[:TARGETS]->(Goal|Objective)`
  - `Topic-[:PREREQ]->Topic` (пререквизиты)
  - `User-[:PROGRESS_TOPIC]->Topic` (персональные динамичные веса темы)
  - `User-[:PROGRESS_SKILL]->Skill` (персональные динамичные веса навыка)
- Веса:
  - `static_weight` — базовая сложность (эвристика от текста/терминов)
  - `dynamic_weight` — глобальная динамика (если пользователь не задан)
  - пользовательские `dynamic_weight` — на связях `PROGRESS_*`
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
  uvicorn fastapi_app:app --host 0.0.0.0 --port 8000
  ```

  Документация: `http://localhost:8000/docs`.

## Данные и синхронизация

- Сиды JSONL: `kb/subjects.jsonl`, `kb/sections.jsonl`, `kb/topics.jsonl`, `kb/skills.jsonl`, `kb/methods.jsonl`, `kb/skill_methods.jsonl`, `kb/topic_goals.jsonl`, `kb/topic_objectives.jsonl`.
- Синхронизация в Neo4j:
  - REST: `POST /api/neo4j_sync` (Flask)
  - Python: `from neo4j_utils import sync_from_jsonl`
- Автогенерация:
  - Цели/задачи: `from kb_builder import generate_goals_and_objectives`
  - Автосвязи навыков-методов: `from kb_builder import autolink_skills_methods`

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

## FastAPI (тесты, веса, дорожные карты)

- Глобальные обновления (без пользователя):
  - `POST /test_result` — обновляет `dynamic_weight` темы и пересчитывает `adaptive_weight`
  - `POST /skill_test_result` — обновляет `dynamic_weight` навыка и пересчитывает `adaptive_weight`
- Пользовательские обновления/просмотр:
  - `POST /test_result` с `user_id` — обновляет `User-[:PROGRESS_TOPIC]->Topic`
  - `POST /skill_test_result` с `user_id` — обновляет `User-[:PROGRESS_SKILL]->Skill`
  - `GET /user/knowledge_level/{user_id}/{topic_uid}`
  - `GET /user/skill_level/{user_id}/{skill_uid}`
- Дорожные карты:
  - Глобальная: `POST /roadmap {subject_uid?, limit}`
  - Персональная: `POST /user/roadmap {user_id, subject_uid?, limit}`
- Перерасчёт связей:
  - `POST /recompute_links` — обновляет `adaptive_weight` на `LINKED`

## Пререквизиты и статичные веса

- `compute_static_weights()` — устанавливает `static_weight` для `Topic`/`Skill` по эвристике (длина текста, продвинутые термины), инициализирует `dynamic_weight` при необходимости.
- `add_prereqs_heuristic()` — добавляет базовые `PREREQ` связи для ключевых тем.

## Служебные утилиты

- Очистка графа: `python scripts/clear_neo4j.py` (удаляет узлы/связи/индексы/констрейнты)

## Переменные окружения

- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` — доступ к Neo4j (обязательные)

## Развертывание

- Запуск в Docker/оркестрации возможен через любой стандартный образ Python. Пробросьте `NEO4J_*` ENV и поднимите два процесса:
  - Flask (`python web_app.py`)
  - FastAPI (`uvicorn fastapi_app:app --host 0.0.0.0 --port 8000`)
- Traefik/Nginx — по желанию, для маршрутизации HTTP‑трафика на порты 5000/8000. Секреты передавайте только через переменные окружения. 

## Примеры

- Синхронизация:

  ```
  curl -X POST http://localhost:5000/api/neo4j_sync
  ```

- Аналитика:

  ```
  curl http://localhost:5000/api/analysis
  ```

- Тест пользователя (персонализация):

  ```
  curl -X POST http://localhost:8000/test_result \
    -H 'Content-Type: application/json' \
    -d '{"topic_uid":"TOP-ALG-QUAD-EQ","score":42,"user_id":"user-001"}'
  ```

## Примечания безопасности

- Не храните пароли/URI в коде и файлах репозитория. Используйте только переменные окружения.
- Глобальные данные графа отделены от пользовательских весов: персональные динамичные веса хранятся на связях с `User` и не изменяют первичные сущности.
