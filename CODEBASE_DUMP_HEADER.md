# Полный дамп кодовой базы (Codebase Dump)

Этот файл содержит исходный код ключевых компонентов системы для детального анализа и отладки.
Собранные файлы охватывают логику Ingestion, валидации целостности (Integrity), работу с графом (Neo4j) и систему пропозалов.

**Содержание:**
1.  `backend/app/services/ingestion/academic.py` — Логика парсинга (подтверждает иерархию Subject -> Section -> Subsection -> Topic).
2.  `backend/app/services/ingestion/corporate.py` — Альтернативная стратегия ingestion.
3.  `backend/app/services/kb/builder.py` — Низкоуровневый билдер графа.
4.  `backend/app/services/graph/neo4j_repo.py` — Взаимодействие с БД Neo4j.
5.  `backend/app/services/proposal_service.py` — Логика обработки изменений (Proposals).
6.  `backend/app/schemas/proposal.py` — Pydantic модели операций.
7.  `backend/app/services/integrity.py` — Правила валидации графа (включая проверку иерархии).
8.  `backend/app/api/ingestion.py` — API эндпоинт генерации.
9.  `backend/app/api/admin_graph.py` — API администратора.
10. `backend/app/core/canonical.py` — Канонические константы (ALLOWED_LABELS).
11. `backend/app/services/kb/jsonl_io.py` — Работа с JSONL файлами и генерация UID.

---
