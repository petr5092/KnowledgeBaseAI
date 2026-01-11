# Карта API KnowledgeBaseAI

Базовый URL: http://localhost:8000  
Требуемые заголовки для защищённых маршрутов:
- Authorization: Bearer <access_token>
- X-Tenant-ID: <tenant_id> (для мульти‑тенантных операций в админ/заявках/обслуживании)

## Аутентификация
Источник: [auth.py](file:///root/KnowledgeBaseAI/backend/src/api/auth.py)

### Регистрация
POST /v1/auth/register

Пример запроса:

```bash
curl -X POST http://localhost:8000/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"secret"}'
```

Пример ответа:

```json
{"ok":true,"id":42,"email":"user@example.com"}
```

### Вход
POST /v1/auth/login

```bash
curl -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"secret"}'
```

```json
{"access_token":"eyJ...","refresh_token":"eyJ...","token_type":"bearer"}
```

### Обновление токена
POST /v1/auth/refresh

```bash
curl -X POST http://localhost:8000/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"eyJ..."}'
```

```json
{"access_token":"eyJ...","refresh_token":"eyJ...","token_type":"bearer"}
```

### Текущий пользователь
GET /v1/auth/me

```bash
curl http://localhost:8000/v1/auth/me \
  -H "Authorization: Bearer ${ACCESS}"
```

```json
{"id":42,"email":"user@example.com","role":"admin"}
```

## Граф
Источник: [graph.py](file:///root/KnowledgeBaseAI/backend/src/api/graph.py)

### Детали узла
GET /v1/graph/node/{uid}

```bash
curl http://localhost:8000/v1/graph/node/TOP-DEMO
```

Пример ответа (вариативно):

```json
{"uid":"TOP-DEMO","labels":["Topic"],"props":{"title":"Демо тема"}}
```

### Окрестность узла
GET /v1/graph/viewport?center_uid=TOP-DEMO&depth=1

```bash
curl "http://localhost:8000/v1/graph/viewport?center_uid=TOP-DEMO&depth=1"
```

```json
{
  "nodes":[{"id":1,"uid":"TOP-DEMO","labels":["Topic"]}],
  "edges":[{"from":1,"to":2,"type":"PREREQ"}],
  "center_uid":"TOP-DEMO","depth":1
}
```

### Объяснение связи (LLM)
POST /v1/graph/chat

```bash
curl -X POST http://localhost:8000/v1/graph/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"Почему A зависит от B?","from_uid":"TOP-A","to_uid":"TOP-B"}'
```

```json
{
  "answer":"Тема B опирается на базовые понятия из темы A...",
  "usage":{"prompt_tokens":120,"completion_tokens":56,"total_tokens":176},
  "context":{"rel":"PREREQ","props":{"weight":0.7},"from_title":"Тема A","to_title":"Тема B"}
}
```

### Адаптивная дорожная карта
POST /v1/graph/roadmap

```bash
curl -X POST http://localhost:8000/v1/graph/roadmap \
  -H "Content-Type: application/json" \
  -d '{"subject_uid":"MATH","progress":{"TOP-ALG-1":0.2},"limit":30}'
```

```json
{"items":[{"uid":"TOP-ALG-1","title":"Алгебра: основы","mastered":0.2,"missing_prereqs":1,"priority":0.91}]}
```

### Адаптивные вопросы
POST /v1/graph/adaptive_questions

```bash
curl -X POST http://localhost:8000/v1/graph/adaptive_questions \
  -H "Content-Type: application/json" \
  -d '{"subject_uid":"MATH","progress":{"TOP-ALG-1":0.2},"count":2,"difficulty_min":1,"difficulty_max":5,"exclude":[]}'
```

```json
{"questions":[{"uid":"Q-123","title":"Решите уравнение","statement":"2x+3=7","difficulty":0.4,"topic_uid":"TOP-ALG-2"}]}
```

## ИИ‑ассистент
Источник: [assistant.py](file:///root/KnowledgeBaseAI/backend/src/api/assistant.py)

### Список инструментов
GET /v1/assistant/tools

```bash
curl http://localhost:8000/v1/assistant/tools
```

```json
{"tools":[{"name":"explain_relation","description":"Объяснить связь между двумя узлами"}]}
```

### Чат/действия
POST /v1/assistant/chat

Объяснение связи:

```bash
curl -X POST http://localhost:8000/v1/assistant/chat \
  -H "Content-Type: application/json" \
  -d '{"action":"explain_relation","message":"Почему?","from_uid":"TOP-A","to_uid":"TOP-B"}'
```

Свободный ответ:

```bash
curl -X POST http://localhost:8000/v1/assistant/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Привет! Расскажи про граф."}'
```

## Учебные планы
Источник: [curriculum.py](file:///root/KnowledgeBaseAI/backend/src/api/curriculum.py)

### Порядок темы
POST /v1/curriculum/pathfind

```bash
curl -X POST http://localhost:8000/v1/curriculum/pathfind \
  -H "Content-Type: application/json" \
  -d '{"target_uid":"TOP-ALG-2"}'
```

```json
{"target":"TOP-ALG-2","path":["TOP-ALG-1","TOP-ALG-2"]}
```

### Учебный маршрут
POST /v1/curriculum/roadmap

```bash
curl -X POST http://localhost:8000/v1/curriculum/roadmap \
  -H "Content-Type: application/json" \
  -d '{"subject_uid":"MATH","progress":{"TOP-ALG-1":0.3},"limit":30,"penalty_factor":0.15}'
```

```json
{"items":[{"uid":"TOP-ALG-1","title":"Алгебра: основы","mastered":0.3,"missing_prereqs":1,"priority":0.91}]}
```

## Оценивание
Источник: [assessment.py](file:///root/KnowledgeBaseAI/backend/src/api/assessment.py)

### Начать сессию
POST /v1/assessment/start

```bash
curl -X POST http://localhost:8000/v1/assessment/start \
  -H "Content-Type: application/json" \
  -d '{"subject_uid":"MATH","topic_uid":"TOP-ALG-1","user_context":{"age":12}}'
```

```json
{"assessment_session_id":"abc123","question":{"question_uid":"Q-STUB-TOP-ALG-1-1","type":"free_text","prompt":"..." }}
```

### Следующий вопрос (SSE)
POST /v1/assessment/next (text/event-stream)

```bash
curl -N -X POST http://localhost:8000/v1/assessment/next \
  -H "Content-Type: application/json" \
  -d '{"assessment_session_id":"abc123","question_uid":"Q-STUB-TOP-ALG-1-1","answer":{"text":"мой ответ"}}'
```

События:

```
event: ack
data: {"accepted":true}

event: question
data: {"question_uid":"Q-...","prompt":"..."}
```

## Знание
Источник: [knowledge.py](file:///root/KnowledgeBaseAI/backend/src/api/knowledge.py)

### Доступные темы
POST /v1/knowledge/topics/available

```bash
curl -X POST http://localhost:8000/v1/knowledge/topics/available \
  -H "Content-Type: application/json" \
  -d '{"subject_uid":"MATH","user_context":{"age":12}}'
```

```json
{"subject_uid":"MATH","resolved_user_class":6,"topics":[{"topic_uid":"TOP-ALG-1","title":"Алгебра: основы","prereq_topic_uids":[]}]}
```

## Уровни
Источник: [levels.py](file:///root/KnowledgeBaseAI/backend/src/api/levels.py)

GET /v1/levels/topic/{uid}

```bash
curl http://localhost:8000/v1/levels/topic/TOP-ALG-1
```

GET /v1/levels/skill/{uid}

```bash
curl http://localhost:8000/v1/levels/skill/SK-ALG-1
```

## Конструирование (LLM + Qdrant)
Источник: [construct.py](file:///root/KnowledgeBaseAI/backend/src/api/construct.py)

### Magic Fill
POST /v1/construct/magic_fill

```bash
curl -X POST http://localhost:8000/v1/construct/magic_fill \
  -H "Content-Type: application/json" \
  -d '{"topic_uid":"TOP-ALG-1","topic_title":"Алгебра: основы","language":"ru"}'
```

```json
{"ok":true,"results":[{"created":"CN-TOP-ALG-1-12345","title":"Понятие X"}]}
```

### Magic Fill (очередь)
POST /v1/construct/magic_fill/queue

```bash
curl -X POST http://localhost:8000/v1/construct/magic_fill/queue \
  -H "Content-Type: application/json" \
  -d '{"topic_uid":"TOP-ALG-1","topic_title":"Алгебра: основы"}'
```

```json
{"job_id":"abcd1234efgh","ws":"/ws/progress?job_id=abcd1234efgh"}
```

### Предложения
POST /v1/construct/propose

```bash
curl -X POST http://localhost:8000/v1/construct/propose \
  -H "Content-Type: application/json" \
  -d '{"text":"Определение производной и базовые свойства...","language":"ru"}'
```

```json
{"concepts":[{"uid":"...","title":"..."}],"skills":[{"uid":"...","title":"..."}]}
```

## Заявки (Proposals)
Источник: [proposals.py](file:///root/KnowledgeBaseAI/backend/src/api/proposals.py)  
Требует: Authorization Bearer и заголовок X-Tenant-ID

### Создать черновик
POST /v1/proposals

```bash
curl -X POST http://localhost:8000/v1/proposals \
  -H "Authorization: Bearer ${ACCESS}" \
  -H "X-Tenant-ID: tenant-1" \
  -H "Content-Type: application/json" \
  -d '{"base_graph_version":1,"operations":[{"op_id":"1","op_type":"CREATE_NODE","target_id":"TOP-NEW","properties_delta":{"title":"Новая тема"}}]}'
```

```json
{"proposal_id":"p-123","proposal_checksum":"sha256:...","status":"DRAFT"}
```

### Commit
POST /v1/proposals/{proposal_id}/commit

```bash
curl -X POST http://localhost:8000/v1/proposals/p-123/commit \
  -H "Authorization: Bearer ${ACCESS}" \
  -H "X-Tenant-ID: tenant-1"
```

```json
{"ok":true,"status":"DONE","graph_version":7}
```

### Approve/Reject, Get/List/Diff/Impact
Аналогично, с заголовками Authorization и X-Tenant-ID.

## Админ: Граф
Источник: [admin_graph.py](file:///root/KnowledgeBaseAI/backend/src/api/admin_graph.py)  
Требует: роль admin, Authorization, X-Tenant-ID

### Создать узел
POST /v1/admin/graph/nodes

```bash
curl -X POST http://localhost:8000/v1/admin/graph/nodes \
  -H "Authorization: Bearer ${ADMIN}" \
  -H "X-Tenant-ID: tenant-1" \
  -H "Content-Type: application/json" \
  -d '{"uid":"TOP-ALG-1","labels":["Topic"],"props":{"title":"Алгебра: основы"}}'
```

```json
{"uid":"TOP-ALG-1"}
```

### Создать связь
POST /v1/admin/graph/edges

```bash
curl -X POST http://localhost:8000/v1/admin/graph/edges \
  -H "Authorization: Bearer ${ADMIN}" \
  -H "X-Tenant-ID: tenant-1" \
  -H "Content-Type: application/json" \
  -d '{"from_uid":"TOP-ALG-1","to_uid":"TOP-ALG-2","type":"PREREQ","props":{"weight":0.7}}'
```

```json
{"edge_uid":"E-abcdef1234567890"}
```

Другие операции: get/patch/delete для узлов и связей.

## Админ: Генерация предмета (LLM)
Источник: [admin_generate.py](file:///root/KnowledgeBaseAI/backend/src/api/admin_generate.py)  
Требует: роль admin, Authorization

### Генерация
POST /v1/admin/generate_subject

```bash
curl -X POST http://localhost:8000/v1/admin/generate_subject \
  -H "Authorization: Bearer ${ADMIN}" \
  -H "Content-Type: application/json" \
  -d '{"subject_uid":"MATH","subject_title":"Математика","language":"ru","topics_per_section":4}'
```

```json
{"sections":[...],"topics":[...],"skills":[...]}
```

### Генерация + импорт
POST /v1/admin/generate_subject_import

```bash
curl -X POST http://localhost:8000/v1/admin/generate_subject_import \
  -H "Authorization: Bearer ${ADMIN}" \
  -H "Content-Type: application/json" \
  -d '{"subject_uid":"MATH","subject_title":"Математика"}'
```

```json
{"generated":{...},"sync":{"created":100},"weights":{"updated":true},"metrics":{"ok":true}}
```

## Админ: Учебные планы
Источник: [admin_curriculum.py](file:///root/KnowledgeBaseAI/backend/src/api/admin_curriculum.py)

### Создать план
POST /v1/admin/curriculum

```bash
curl -X POST http://localhost:8000/v1/admin/curriculum \
  -H "Authorization: Bearer ${ADMIN}" \
  -H "X-Tenant-ID: tenant-1" \
  -H "Content-Type: application/json" \
  -d '{"code":"MATH-6","title":"Математика (6 класс)","standard":"FGOS","language":"ru"}'
```

```json
{"ok":true,"id":123}
```

### Добавить узлы
POST /v1/admin/curriculum/nodes

```bash
curl -X POST http://localhost:8000/v1/admin/curriculum/nodes \
  -H "Authorization: Bearer ${ADMIN}" \
  -H "X-Tenant-ID: tenant-1" \
  -H "Content-Type: application/json" \
  -d '{"code":"MATH-6","nodes":[{"kind":"Topic","canonical_uid":"TOP-ALG-1","order_index":1,"is_required":true}]}'
```

```json
{"ok":true}
```

### Просмотр плана
GET /v1/admin/curriculum/graph_view?code=MATH-6

```bash
curl "http://localhost:8000/v1/admin/curriculum/graph_view?code=MATH-6"
```

```json
{"ok":true,"nodes":[{"kind":"Topic","canonical_uid":"TOP-ALG-1","order_index":1}]}
```

## Обслуживание
Источник: [maintenance.py](file:///root/KnowledgeBaseAI/backend/src/api/maintenance.py)  
Требует: Authorization, X-Tenant-ID

### Пересборка KB (async)
POST /v1/maintenance/kb/rebuild_async

```bash
curl -X POST http://localhost:8000/v1/maintenance/kb/rebuild_async \
  -H "Authorization: Bearer ${ACCESS}" \
  -H "X-Tenant-ID: tenant-1"
```

```json
{"job_id":"1736530000000","queued":true,"ws":"/ws/progress?job_id=1736530000000"}
```

### Валидация/Публикация
POST /v1/maintenance/kb/validate_async  
POST /v1/maintenance/kb/publish  
GET /v1/maintenance/kb/published

### Пересчёт весов
POST /v1/maintenance/recompute_links

```bash
curl -X POST http://localhost:8000/v1/maintenance/recompute_links \
  -H "Authorization: Bearer ${ACCESS}" \
  -H "X-Tenant-ID: tenant-1"
```

```json
{"ok":true,"stats":{"updated_edges":123}}
```

### Заявки: целостность и Outbox
POST /v1/maintenance/proposals/run_integrity_async  
POST /v1/maintenance/events/publish_outbox

## Валидация графа
Источник: [validation.py](file:///root/KnowledgeBaseAI/backend/src/api/validation.py)

POST /v1/validation/graph_snapshot

```bash
curl -X POST http://localhost:8000/v1/validation/graph_snapshot \
  -H "Content-Type: application/json" \
  -d '{"snapshot":{"nodes":[],"edges":[]}}'
```

```json
{"ok":true,"errors":[],"warnings":[]}
```

## Пользовательские веса/маршрут
Источник: [user.py](file:///root/KnowledgeBaseAI/backend/src/api/user.py)

POST /v1/user/compute_topic_weight  
POST /v1/user/compute_skill_weight  
POST /v1/user/roadmap

## WebSocket: прогресс задач
Источник: [ws.py](file:///root/KnowledgeBaseAI/backend/src/api/ws.py)

WS /ws/progress?job_id=<id>

Пример (wscat):

```bash
wscat -c "ws://localhost:8000/ws/progress?job_id=1736530000000"
```

Получаем поток JSON-сообщений о прогрессе:

```json
{"percent":10,"stage":"embedding"}
```

