# Руководство разработчика

## Стек и зависимости
- Backend: FastAPI, Pydantic v2, Neo4j Python Driver, psycopg2, Redis, arq, Qdrant Client
- Frontend: React + TypeScript + Vite
- Тесты: PyTest (`backend/tests`)

## Структура проекта
- `backend/app` — основное приложение (см. [ARCHITECTURE.md](file:///c:/Users/freak/TRAE/KnowledgeBaseAI/docs/ARCHITECTURE.md))
- `backend/scripts` — утилиты импорта/миграции
- `frontend` — клиентская часть
- `docs` — документация

## Конвенции кода
- API слои не содержат бизнес‑логики — только оркестрация сервисов.
- Все записи в граф — строго через Proposals.
- Ответы API: `items` и `meta`, ошибки — унифицированные.

## Локальная разработка
```bash
python -m pip install -r backend/requirements.txt
uvicorn app.main:app --app-dir backend --reload
```

## Тестирование
- Запуск:
```bash
$env:PYTHONPATH="backend"; python -m pytest backend/tests
```
- Юнит‑тесты целостности: [test_integrity.py](file:///c:/Users/freak/TRAE/KnowledgeBaseAI/backend/tests/unit/test_integrity.py)
- Интеграционные тесты Outbox/Events: [tests/integration](file:///c:/Users/freak/TRAE/KnowledgeBaseAI/backend/tests/integration)

## Логирование и метрики
- Инициализация — [main.py](file:///c:/Users/freak/TRAE/KnowledgeBaseAI/backend/app/main.py)
- Метрики Prometheus: `/metrics`
- Корреляция: `X-Correlation-ID` в запросах и ответах

## Безопасность
- JWT, роли (`require_admin`), мульти‑тенантность.
- `X-Tenant-ID` обязателен для записи.

## Векторный поиск
- Индексация сущностей по событию `graph_committed`.
- Воркеры: [vector_sync.py](file:///c:/Users/freak/TRAE/KnowledgeBaseAI/backend/app/workers/vector_sync.py)

