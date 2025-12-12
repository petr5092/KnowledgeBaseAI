# KnowledgeBaseAI Core Architecture

## Храним в Neo4j
- `Subject`, `Section`, `Topic`, `Skill`, `Method`, `Goal`, `Objective`, `ContentUnit`
- Связи: `CONTAINS`, `HAS_SKILL`, `USES_SKILL`, `LINKED`, `TARGETS`, `PREREQ`
- Веса: `static_weight`, `dynamic_weight` на узлах; `adaptive_weight` на связях `LINKED`

## Храним в JSONL
- Каталог `kb/`: `subjects.jsonl`, `sections.jsonl`, `topics.jsonl`, `skills.jsonl`, `methods.jsonl`
- Связи: `skill_methods.jsonl`, `topic_prereqs.jsonl`, цели/задачи: `topic_goals.jsonl`, `topic_objectives.jsonl`
- Примеры/вопросы: `examples.jsonl`, метаданные примеров: `example_skills.jsonl`

## Не храним в ядре
- Пользователи, прогресс, результаты тестов
- Персональные веса — рассчитываются на лету и передаются извне

## API (stateless)
- `/test_result`: считает пользовательский вес темы без записи
- `/skill_test_result`: считает пользовательский вес навыка без записи
- `/user/roadmap`: принимает веса от ЛМС и возвращает дорожную карту
- `/adaptive/questions`: выбирает вопросы по темам из KB
- `/user/topic_level`, `/user/skill_level`: возвращают уровень по переданному весу

## Взаимодействие ЛМС ↔ ядро
- ЛМС хранит пользователей, историю, свои веса
- Ядро принимает веса и по графу знаний строит рекомендации и подбор вопросов
