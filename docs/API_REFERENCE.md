# API справочник (v1)

Все ответы имеют унифицированный формат `StandardResponse`:

```json
{
  "items": [ ... ],
  "meta": { ... }
}
```

Заголовки:
- `X-Tenant-ID`: идентификатор арендатора (обязателен для записей; рекомендуется для чтения).
- `X-Correlation-ID`: трекинг запроса.

## Аутентификация
- JWT Bearer для защищенных маршрутов админки.
- Генерация токена: см. [auth.py](file:///c:/Users/freak/TRAE/KnowledgeBaseAI/backend/app/api/auth.py).

## Раздел: Граф для LMS (`/v1/graph`)
- GET `/v1/graph/node/{uid}` — получить узел.
- GET `/v1/graph/viewport?center_uid=...&depth=1..3` — окрестность узла (узлы/связи) с фильтрацией по `tenant_id`.
- POST `/v1/graph/chat` — объяснение связи (LLM), вход: `{question, from_uid, to_uid}`.
- POST `/v1/graph/roadmap` — построить дорожную карту; вход: `{subject_uid?, progress, limit?}`.
- POST `/v1/graph/adaptive_questions` — подбор вопросов; вход: `{subject_uid?, progress, count, difficulty_min, difficulty_max, exclude}`.

## Раздел: Заявки (`/v1/proposals`)
- POST `/v1/proposals` — создать черновик заявки.
  - Вход: `{base_graph_version, operations}`
  - `operations[]`: объекты [Operation](file:///c:/Users/freak/TRAE/KnowledgeBaseAI/backend/app/schemas/proposal.py).
- POST `/v1/proposals/{proposal_id}/commit` — применить заявку.
- GET `/v1/proposals/{proposal_id}` — получить заявку.
- GET `/v1/proposals?status=...` — список заявок с пагинацией.
- POST `/v1/proposals/{proposal_id}/approve` — одобрить и закоммитить.
- POST `/v1/proposals/{proposal_id}/reject` — отклонить.
- GET `/v1/proposals/{proposal_id}/diff` — diff заявок.
- GET `/v1/proposals/{proposal_id}/impact` — анализ влияния заявок.

## Раздел: Админка графа (`/v1/admin/graph`)
Маршруты создают **заявки** и коммитят через конвейер.
- POST `/v1/admin/graph/nodes`
  - Вход: `{uid, labels[], props{}}` → операция `CREATE_NODE`.
- PATCH `/v1/admin/graph/nodes/{uid}`
  - Вход: `{set{}, unset[]}` → операция `UPDATE_NODE`.
- DELETE `/v1/admin/graph/nodes/{uid}?detach=true|false`
  - Операция `DELETE_NODE`.
- POST `/v1/admin/graph/edges`
  - Вход: `{edge_uid?, from_uid, to_uid, type, props{}}` → `CREATE_REL`.
- PATCH `/v1/admin/graph/edges/{edge_uid}`
  - Вход: `{set{}, unset[]}` → `UPDATE_REL`.
- DELETE `/v1/admin/graph/edges/{edge_uid}`
  - Операция `DELETE_REL`.

## Валидаторы и ошибки
- Все ошибки унифицированы: см. [main.py](file:///c:/Users/freak/TRAE/KnowledgeBaseAI/backend/app/main.py).
  - `code`: `validation_error`, `unauthorized`, `forbidden`, `not_found`, `conflict`, `internal_error` и др.
  - `request_id`, `correlation_id` присутствуют в ответах.

## Примеры

Получение окрестности узла:
```bash
curl -H "X-Tenant-ID: acme" "http://localhost:8000/v1/graph/viewport?center_uid=TOP-ALG-1&depth=2"
```

Создание узла через админку:
```bash
curl -X POST -H "Authorization: Bearer <JWT>" -H "X-Tenant-ID: acme" \
  -H "Content-Type: application/json" \
  -d '{"uid":"TOP-LIN-1","labels":["Topic"],"props":{"title":"Линейные уравнения"}}' \
  http://localhost:8000/v1/admin/graph/nodes
```

