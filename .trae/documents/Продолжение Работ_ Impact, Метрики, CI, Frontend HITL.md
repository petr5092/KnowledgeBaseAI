## Цели Итерации
- Усилить визуализацию impact subgraph на фронтенде и связать её с ReviewDiff.
- Расширить метрики (integrity, outbox, latency) и обеспечить удобный сбор.
- Укрепить CI: стабильный запуск docker compose, прогон unit+integration, базовый артефакт‑логгинг.
- Завершить API/DB штрихи: фильтры и индексы, типизация изменений, кэширование.

## Frontend: Impact и ReviewDiff
- Компонент ImpactGraph: добавить интерактивность (выбор depth, подсветка узлов/рёбер) без внешних тяжёлых библиотек; при согласии — подключить лёгкую библиотеку визуализации графов.
- ReviewDiff: объединить с ImpactGraph (быстрый переход от diff‑элемента к соответствующему узлу/ребру в impact).
- txLog: завести утилиты для привязки txId к откатам inversePatch при ошибке запроса и визуальный статус.

## Backend: Impact и производительность
- API `/v1/proposals/{id}/impact`: добавить опциональные параметры (фильтрация типов рёбер, max_nodes, max_edges), ввод элементарного rate limit.
- neighbors: добавить простейшее кэширование (в памяти) на короткий TTL по `(uid, depth)` для снижения нагрузки.
- Graph changes: дополнить `change_type` значением `PROPERTY` для операций замены свойств и фильтрацию по типу в выборках.

## Метрики и Observability
- Integrity: расширить histogram buckets для `integrity_check_latency_ms`, добавить `integrity_base_rule_violation_total{kind}` в /metrics проверку.
- Outbox: добавить отдельные counters по типам событий и latencies публикации, экспорт в `/metrics` (уже собирается) — протоколировать в CI.
- HTTP: включить CORS на нужные домены (включено), добавить доп. лейблы/багреты при необходимости.

## Tests
- Integration: добавить тесты для `/impact` (разные depth и фильтры), для outbox retry‑сценариев с искусственной ошибкой публикации.
- Unit: добавить тест для `change_type=PROPERTY` и фильтрации `get_changed_targets_since(..., change_type)`.
- Frontend: минимальные smoke‑тесты для ImpactGraph и ReviewDiff (рендер, обработка ошибок).

## CI
- Workflow: стабилизировать docker compose up — добавить healthcheck ожидание Neo4j/Postgres/Redis до pytest.
- Параллелизация: разбить unit и integration в отдельные job‑ы; добавить артефакты логов контейнеров при падении.
- Кэширование: включить Python/pytest кэш где возможно.

## Документация (MasterFile)
- После выполнения каждой из задач: отметить статус и краткий changelog.

Если подтверждаете план — приступаю к реализации по пунктам, с коммитом, push и merge в `latest` после каждого завершённого шага.