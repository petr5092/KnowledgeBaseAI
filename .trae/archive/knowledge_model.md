# Полный отчёт по рефакторингу KnowledgeBaseAI Core

## 1. Резюме

* Ядро переведено на stateless‑архитектуру: данные пользователя (веса, прогресс, ответы) не хранятся в графе и не модифицируются сервисом.

* Обновлены API и документация: все пользовательские операции получают веса извне и рассчитывают рекомендации без записи в Neo4j.

* Удалены/задепрекейтены все упоминания `User`, `PROGRESS_TOPIC`, `PROGRESS_SKILL`, `COMPLETED` в коде; функции переведены на вычислительный режим.

* Реализован модуль выбора вопросов по KB с Neo4j и JSONL‑фоллбеком; документирован формат вопросов.

* Оформлен асинхронный пайплайн сборки KB с этапами, статусами и анализом валидности.

* Сервисы контейнеризированы и перезапущены; проверены логи и доступность.

## 2. Соответствие рефактор‑плану

План: `.trae/documents/refactor_plan.md`. Ниже — выполнение по разделам.

### 2.1. Общие принципы ядра (LMS‑agnostic)

* Ядро не является ЛМС, не хранит пользователей/прогресс, работает как универсальный сервис предметного графа.

* Внешняя ЛМС хранит все пользовательские данные и передаёт веса в API.

### 2.2. Пользовательская модель удалена/задепрекейтена

* В `neo4j_repo.py` методы, связанные с `(:User)`, `:PROGRESS_TOPIC`, `:PROGRESS_SKILL`, `:COMPLETED`, отмечены как LEGACY и не используются.

* В `neo4j_utils.py` пользовательские функции переписаны в stateless‑вычислители: не модифицируют граф, возвращают рекомендации.

### 2.3. Дорожная карта (stateless)

* Реализован `build_user_roadmap_stateless(subject_uid, user_topic_weights, user_skill_weights?, limit, penalty_factor)`.

* Считывание тем из графа, учёт пререквизитов, сортировка по `effective_weight` и ограничение топ‑N.

### 2.4. Вопросы тестирования из KB

* Источник: `kb/examples.jsonl` (+ при необходимости метаданные `kb/example_skills.jsonl`).

* Формат вопроса документирован: `uid`, `title`, `statement`, `topic_uid`, `difficulty`.

* Модуль `services/question_selector.py`: попытка выборки из Neo4j, при отсутствии ENV фоллбек на JSONL.

### 2.5. Новый API для адаптивного тестирования

* Эндпоинт `/adaptive/questions`: строит stateless‑дорожную карту, выбирает вопросы для релевантных тем.

* Эндпоинты `/test_result`, `/skill_test_result`, `/user/roadmap`, `/user/topic_level`, `/user/skill_level` — все stateless, без записи в граф.

### 2.6. Асинхронная сборка KB

* Модуль `kb_jobs.py`: стадии импорта JSONL, расчёт статических весов, эвристические пререквизиты, анализ графа, возврат статуса `ok/warnings/errors`.

* API: `POST /kb/rebuild_async`, `GET /kb/rebuild_status?job_id=...`.

### 2.7. Пререквизиты и статические веса

* `sync_from_jsonl()` включает `topic_prereqs.jsonl` и создаёт `[:PREREQ {weight, confidence}]`.

* Функция `analyze_prereqs(subject_uid?)` проверяет циклы, межпредметные связи, аномальные веса.

* `compute_static_weights()` нормирует диапазоны и проверяет монотонность по пререквизитам.

### 2.8. Документация

* Обновлён `README.md`: убраны `User` из типовых узлов и связей, описана stateless‑логика, раздел FastAPI, формат вопросов, KB‑пайплайн.

* Документирована схема взаимодействия: внешняя ЛМС ↔ ядро.

## 3. Изменения по файлам

* `README.md`: обновлён раздел архитектуры и API; явно указано хранение пользовательских данных во внешней ЛМС; раздел о stateless FastAPI; формат вопросов; KB‑пайплайн.

* `neo4j_repo.py`: добавлены LEGACY‑пометки для любых функций, связанных с `User`; такие функции больше не вызываются; оставлена поддержка только глобальных весов и системных связей (`static_weight`, `dynamic_weight`, `adaptive_weight`, `PREREQ`).

* `neo4j_utils.py`: добавлены чистые вычислители (`compute_user_weight`, `compute_topic_user_weight`, `compute_skill_user_weight`, `knowledge_level_from_weight`), реализована `build_user_roadmap_stateless`; расширен импорт и анализ пререквизитов; монотонность статических весов.

* `fastapi_app.py`: переписаны эндпоинты на stateless; `startup_event` устойчив к отсутствию ENV для Neo4j; добавлены `/adaptive/questions`, `/kb/rebuild_async`, `/kb/rebuild_status`.

* `services/question_selector.py`: выбор вопросов из Neo4j с фоллбеком на JSONL; утилиты индексации; фильтрация по сложности; исключение UID.

* `kb_jobs.py`: расширенный пайплайн задач, статусы и сбор метрик/предупреждений.

* Docker/Compose: пересборка образов, удаление сирот, запуск контейнеров (FastAPI, Flask, Neo4j, Traefik); проверка логов.

## 4. API (актуально)

* `POST /test_result {topic_uid, score, base_weight?} → {topic_uid, base_weight, user_weight}`

* `POST /skill_test_result {skill_uid, score, base_weight?} → {skill_uid, base_weight, user_weight}`

* `POST /user/roadmap {subject_uid?, topic_weights{}, skill_weights{}, limit?, penalty_factor?} → [topics]`

* `POST /adaptive/questions {subject_uid?, topic_weights{}, skill_weights?, question_count, difficulty_min?, difficulty_max?, exclude_question_uids?} → {questions: [...]}`

* `POST /user/topic_level {weight} → {level}`

* `POST /user/skill_level {weight} → {level}`

* `POST /kb/rebuild_async → {job_id}`

* `GET /kb/rebuild_status?job_id=... → {status, stages, ok, warnings, errors}`

## 5. Данные пользователя

* Все пользовательские данные (веса, прогресс, ответы) хранятся во внешней ЛМС.

* Ядро KnowledgeBaseAI получает веса через запрос и возвращает рекомендации; в граф Neo4j не записывает пользовательские состояния.

## 6. Формат «вопроса»

```json
{
  "uid": "EX-123",
  "title": "Найдите корень уравнения…",
  "statement": "2x - 5 = 11",
  "topic_uid": "TOP-LINEQ",
  "difficulty": 3
}
```

* Минимальный состав: `uid`, `title`/`statement`, `topic_uid`, `difficulty` (1–5).

* Дополнительно допускаются поля типа, вариантов ответа, связей с навыками.

## 7. Пайплайн KB

* Стадии: загрузка/генерация сидов (`kb/*.jsonl`), импорт в Neo4j, `compute_static_weights()`, `add_prereqs_heuristic()`, анализ (`analyze_knowledge`, `analyze_prereqs`), статус `ok/warnings/errors`.

* Реализация: `kb_jobs.py` с API для запуска и отслеживания.

## 8. Валидация и устойчивость

* При отсутствии ENV для Neo4j: функции `compute_*` используют дефолты (`base_weight=0.5`); дорожная карта возвращает пустой список; выбор вопросов падает на JSONL‑фоллбек.

* `startup_event` FastAPI обёрнут в `try/except` и не мешает запуску без Neo4j.

## 9. Контейнеризация и запуск

* Остановлены локальные сервисы, пересобраны образы, удалены старые/сиротские.

* Запуск: `docker compose down --remove-orphans && docker system prune -af && docker compose build --no-cache && docker compose up -d && docker compose ps`.

* Проверка логов: `docker compose logs fastapi | tail -n 50`, `docker compose logs flask | tail -n 50`.

* Контейнеры: FastAPI, Flask, Neo4j, Traefik — в состоянии `running`.

## 10. Definition of Done — выполнено

1. В графе Neo4j не создаются узлы `User` и связи `PROGRESS_*`.
2. Все функции user‑related — stateless.
3. `/adaptive/questions` работает на основе KB (Neo4j/JSONL).
4. `/user/roadmap` принимает веса извне и формирует корректную карту.
5. `/test_result` и `/skill_test_result` только считают веса, не сохраняют их.
6. Сборка KB асинхронна и проверяется через статусы.
7. Пререквизиты и статические веса синхронизируются и валидируются.
8. Документация обновлена.

## 11. Ограничения и дальнейшие шаги

* При отсутствии настроек Neo4j часть функциональности работает в ограниченном режиме (фоллбек на JSONL).

* Рекомендуется добавить интеграционные smoke‑тесты для API контейнеров и включить CI.

* По мере роста KB — расширять анализ аномалий и автоисправления.

