# Руководство по деплою

## Предпосылки
- Docker и Docker Compose
- Настроенные переменные окружения (см. `.env.example` и `backend/requirements.txt`)
- Зависимости: Neo4j, Postgres, Redis, Qdrant

## Быстрый старт (Docker Compose)

```bash
cp .env.example .env.prod
# Проверьте/заполните ключи: NEO4J_*, PG_DSN, REDIS_URL, QDRANT_URL, OPENAI_API_KEY

docker-compose up -d --build
```

Сервисы:
- Backend API: `http://localhost:8000`
- Frontend: `http://localhost:5173`
- Neo4j Browser: `http://localhost:7474`

## Инициализация данных
- Импорт файловой базы знаний и синхронизация в Neo4j: см. [scripts](file:///c:/Users/freak/TRAE/KnowledgeBaseAI/backend/scripts)
- Векторная индексация запускается по событию `graph_committed`.

## Среда
Ключевые переменные (пример):
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
- `PG_DSN` (например, `postgres://user:pass@localhost:5432/kb`)
- `REDIS_URL` (например, `redis://localhost:6379/0`)
- `QDRANT_URL`, `QDRANT_COLLECTION_NAME`
- `OPENAI_API_KEY`
- `CORS_ALLOW_ORIGINS`

## Запуск вручную (без Docker)

```bash
python -m pip install -r backend/requirements.txt
# Запуск FastAPI
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --app-dir backend
```

## Воркеры
- Планировщик `arq` конфигурируется в [worker.py](file:///c:/Users/freak/TRAE/KnowledgeBaseAI/backend/app/tasks/worker.py)
- Cron‑задачи:
  - публикация Outbox → Redis
  - индексация в Qdrant

