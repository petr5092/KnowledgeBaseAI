# Рефактор KnowledgeBaseAI Core

- [x] Пометить user-функции в `neo4j_repo.py` как deprecated
- [x] Переписать `neo4j_utils.py` на stateless-логику весов/дорожной карты
- [x] Добавить `services/question_selector.py` и выбор вопросов из KB
- [x] Переработать `fastapi_app.py` под stateless API
- [x] Обновить `sync_from_jsonl()` для PREREQ и веса
- [x] Добавить `analyze_prereqs()` и монотонность статических весов
- [x] Создать `docs/core_architecture.md` с описанием ядра
- [x] Обновлять этот файл и отмечать выполнение
