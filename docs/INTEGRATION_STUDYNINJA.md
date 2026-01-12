# Интеграция StudyNinja: публичный API и события

## Формат ответов
- Все эндпоинты возвращают объект: { "items": [...], "meta": {...} }

## Эндпоинты
- POST /v1/reasoning/gaps
  - Вход: { subject_uid, progress{topic_uid: mastery}, goals?, prereq_threshold? }
  - Выход: { items: [], meta: { blocking_gaps[], latent_gaps[] } }
- POST /v1/reasoning/next-best-topic
  - Вход: { subject_uid, progress{topic_uid: mastery}, prereq_threshold?, top_k?, alpha?, beta? }
  - Выход: { items: [{topic_uid,title,mastery,score,reasoning{need,importance,unlock_impact,prereqs}}], meta: {} }
- POST /v1/reasoning/roadmap
  - Вход: { subject_uid, progress{topic_uid: mastery}, goals?, prereq_threshold?, top_k? }
  - Выход: { items: [{topic_uid,title,mastery,missing_prereqs,priority,reasoning}], meta: { blocking_gaps[], latent_gaps[] } }
- POST /v1/reasoning/mastery/update
  - Вход: { entity_uid, kind: Topic|Skill, score, prior_mastery, confidence? }
  - Выход: { items: [{uid,kind,new_mastery,delta,confidence}], meta: {} }
- GET /v1/graph/viewport, /v1/graph/node — без изменений, формат привести к {items,meta} по мере унификации
- POST /v1/assessment/* — адаптивные вопросы, stateless: состояние сеанса возвращается клиенту или в Postgres (не Neo4j)
- POST /v1/proposals/* — админ-операции создания/коммита предложений

## События (Outbox)
- graph_committed — при транзакционном коммите предложения
- roadmap_generated — при успешной генерации дорожной карты reasoning/roadmap
- assessment_completed — завершение сессии тестирования (если хранится в Postgres)

## Без состояния пользователя (stateless)
- KnowledgeBaseAI не хранит мастерство в графе. Mastery приходит из LMS и возвращается в ответы reasoning.

