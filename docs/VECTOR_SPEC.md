# VECTOR SPEC: Qdrant индексирование

## Что индексируется
- Concept: definition/title/description
- Method: method_text/title
- ContentUnit: payload/type/description
- Example: statement/title

## Коллекции
- Основная: значение переменной `QDRANT_COLLECTION` (по умолчанию `kb_entities`)

## Payload
- tenant_id: строка
- uid: строка
- type: один из {Concept, Method, ContentUnit, Example}
- text: нормализованный текст, использованный для эмбеддинга

## Размер вектора
- QDRANT_DEFAULT_VECTOR_DIM (по умолчанию 16). При несовпадении обрезаем/дополняем нулями.

## Триггер обновления
- Событие `graph_committed` публикуется в outbox, потребитель вызывает `index_entities(tenant_id, targets)` для обновления коллекции.
