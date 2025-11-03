# KnowledgeBaseAI — проект базы знаний

Этот репозиторий содержит минимально жизнеспособную реализацию базы знаний, созданную по спецификации из `base_concept.md`. Включены:

- Схема PostgreSQL со всеми сущностями, связями и ограничениями.
- Триггер проверки ацикличности графа предпосылок навыков (DAG).
- Маппинги Elasticsearch для индексации сущностей.
- Примеры (JSONL) начальных данных: предмет, раздел, тема, навыки, методы, примеры, ошибки.
- Краткое руководство по загрузке и индексации.

## Структура

```
schemas/
  postgres.sql          # DDL и триггеры
elastic/
  subjects.json         # mappings
  sections.json
  topics.json
  skills.json
  methods.json
  examples.json
  errors.json
kb/
  subjects.jsonl        # сиды
  sections.jsonl
  topics.jsonl
  skills.jsonl
  methods.jsonl
  examples.jsonl
  errors.jsonl
docs/
  ingestion.md          # как загрузить и проиндексировать
```

## Быстрый старт

1. Создайте БД PostgreSQL и выполните `schemas/postgres.sql`.
2. Загрузите сиды из каталога `kb/` (см. `docs/ingestion.md`).
3. Создайте индексы в Elasticsearch по файлам из `elastic/` и загрузите те же данные.

## Соответствие `base_concept.md`

- Сущности: `subject`, `section`, `topic`, `skill`, `method`, `example`, `error`.
- Иерархия: `subject → section → topic` (строгая), навыки — DAG в рамках предмета.
- Роли связей: `example ↔ skill` имеет `role ∈ {target, auxiliary, context}`.
- Мастерство темы: пороги по точности, критическим ошибкам и времени.
- Персонализация: реализуется в слое индексации и выборке (weights/filters), не изменяя первичные данные.

## Загрузка и индексирование

Смотрите `docs/ingestion.md` для пошаговой процедуры (SQL COPY/INSERT и Bulk API для Elasticsearch).