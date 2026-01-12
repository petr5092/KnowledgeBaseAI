# CANON: Единая спецификация графа и прогресса

## ДОЛЖНО
- Labels: Subject, Section, Subsection, Topic, Skill, Method, Error, Example, Concept, Formula, TaskType, ContentUnit, Goal, Objective
- Единственные разрешённые отношения:
  - (Subject)-[:CONTAINS]->(Section)
  - (Section)-[:CONTAINS]->(Subsection)
  - (Subsection)-[:CONTAINS]->(Topic)
  - (Topic)-[:PREREQ]->(Topic)
  - (Topic)-[:USES_SKILL]->(Skill)
  - (Skill)-[:LINKED]->(Method)
  - (Topic)-[:HAS_ERROR]->(Error)
  - (Topic)-[:HAS_EXAMPLE]->(Example)
  - (Topic)-[:HAS_CONCEPT]->(Concept)
  - (Topic)-[:HAS_FORMULA]->(Formula)
  - (Topic)-[:HAS_TASK_TYPE]->(TaskType)
  - (Topic)-[:HAS_UNIT]->(ContentUnit)
  - (Goal)-[:TARGETS]->(Topic)
  - (Objective)-[:MEASURES]->(Skill)
- Единственная метрика знания: mastery ∈ [0..1], 1 — освоено, 0 — не освоено.
- Любая генерация/изменения графа проходят конвейер: Proposal → Integrity Gate → Commit → Outbox Event (`graph_committed`). Прямых записей для не-админских операций нет.
- Ядро KnowledgeBaseAI — stateless относительно пользователя: состояние пользователя (mastery по темам/навыкам) приходит из LMS и возвращается наружу.
- Векторинг: индексируются только Concept, Method, ContentUnit, Example; Topic/Skill — только если есть текстовое описание. Индексация подписана на событие `graph_committed`.

## ЗАПРЕЩЕНО
- Любые другие отношения помимо перечисленных: HAS_SECTION, HAS_TOPIC, REQUIRES_SKILL, HAS_SKILL, HAS_QUESTION, HAS_LEARNING_PATH/HAS_PRACTICE_PATH/HAS_MASTERY_PATH, EVIDENCED_BY, и т.п.
- Пользовательские узлы/ребра в Neo4j (например, (:User) и прогресс-ребра).
- Хранение user state внутри ядра KnowledgeBaseAI.
- Параллельные/альтернативные пути записи в граф (обход Proposal/Integrity Gate).
- Расширение схемы без обновления миграций и валидаторов канона.

## Нормативы прогресса
- Все поля, трактуемые как знание (weight/dynamic_weight), приводятся к `mastery` или переименовываются в `need`, если означают нуждаемость.
- Обновление `mastery` выполняется через единый endpoint. Вход: идентификатор темы/скилла, результат/оценка, prior_mastery; выход: new_mastery, delta, confidence (опционально). Алгоритм фиксирован и документирован.

## Админские загрузки
- Bulk import JSONL: либо создаёт Proposal и коммитит, либо работает в режиме MAINTENANCE с теми же проверками, что и commit, и завершает ошибкой при нарушении канона. Допустим только один путь.
