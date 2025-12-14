**TASK TITLE:** Refactor KnowledgeBaseAI into Stateless Canonical-KB Kernel + Async LLM KB Constructor + Postgres Curriculum

**GOALS:**

1. Make Neo4j store only canonical subject knowledge (no user data).
2. Provide stateless APIs: roadmap + adaptive questions driven by user weights coming from external LMS.
3. Add Postgres curriculum layer to map standards/grades/programs to canonical topics/skills.
4. Implement async, verifiable KB generation pipeline (LLM → validate → review → publish).

**CONSTRAINTS:**

* Do not create `User` nodes or `PROGRESS_*` edges in Neo4j (stateless core). This is aligned with README latest.
* Questions/examples must be served from KB.
* Curriculums/grade ordering must not mutate canonical KB.

**DELIVERABLES:**

* Code changes (services/ layering, cleaned FastAPI).
* Neo4j constraints & indexes.
* Postgres schema + repo layer + admin endpoints.
* Async kb_jobs pipeline + staging + validators.
* Updated README and OpenAPI docs reflecting the real behavior.


## 0) Контекст проекта 

Согласно README:

* Проект держит **единый граф БЗ в Neo4j** + UI (Flask) + API (FastAPI). 
* В `latest` заявлено, что ядро **stateless** и **не хранит пользователей и прогресс**. 
* FastAPI уже описан как “stateless эндпоинты тестов/весов/дорожных карт/вопросов” и принимает веса снаружи:

  * `/user/roadmap { … topic_weights{}, skill_weights{} … }` 
  * `/adaptive/questions { … topic_weights{}, skill_weights{} … }` 
* Есть утилиты “compute_static_weights()” и “add_prereqs_heuristic()” (сейчас эвристические)
* Ветка `latest` добавила `kb_jobs.py` и папку `services/` ( важно встроить туда асинхронный пайплайн генерации/проверки).
---

## 1) Цель рефакторинга (Definition of Done)

### 1.1. Canonical Knowledge Graph (Neo4j) — только предметная истина

* Граф хранит **только канонические сущности предметной области** (subject/section/topic/skill/method/example/error + связи prerequisite/targets/links).
* **Никаких `User` узлов, `PROGRESS_*` связей, персональных полей** в Neo4j.

### 1.2. Персонализация — вычислительный слой “поверх”

* FastAPI принимает **словарь динамических весов** пользователя извне:

  * `topic_weights: {topic_uid: float}`
  * `skill_weights: {skill_uid: float}`
* Возвращает:

  * “персональную карту” = подграф + рассчитанные `effective_weight` (и причины: prerequisite penalty, coverage gaps, difficulty targeting).

### 1.3. Вопросы и задания — из базы знаний

* Questions/Examples — это сущности БЗ. Выдача вопросов (`/adaptive/questions`) должна брать их **из Neo4j**, а не генерировать “из воздуха”.

### 1.4. Куррикулумы/программы/классы — вне графа (Postgres)

* “Математика не меняется”, меняется **представление и порядок** (план/стандарт/класс).
* Это отдельный слой: **Curriculum Service (Postgres)** + маппинг на канонические темы/навыки.

### 1.5. Генерация БЗ — асинхронная и “проверяемая на истинность”

* Встроить **асинхронный пайплайн**: LLM предлагает сущности/связи → валидаторы проверяют инварианты + фактологическую “правдоподобность” → только затем коммит в Neo4j.

---

## 2) Изменения в API (FastAPI) — привести к реальному stateless

> В README уже описаны stateless-эндпоинты и формат payload’ов — нужно привести код к этой спецификации и вычистить все следы “User в Neo4j”.

### 2.1. Удалить / запретить любые операции записи персонального прогресса в Neo4j

* Если в коде есть функции вида `update_user_*`, `get_user_*`, `PROGRESS_*` — **удалить/отключить**.
* Любая персонализация только через входные `topic_weights/skill_weights`.

### 2.2. Обязательные stateless-эндпоинты

1. `POST /user/roadmap`

* In: `{ subject_uid?, topic_weights{}, skill_weights{}, limit?, penalty_factor? }`
* Out: список `RoadmapItem` (topic/skill/method) с:

  * `effective_weight`
  * `base_static_weight`
  * `global_dynamic_weight` (если есть)
  * `user_weight` (из payload)
  * `blocked_by_prereqs: [topic_uid]`
  * `why: {components}`

2. `POST /adaptive/questions`

* In: `{ subject_uid?, topic_weights{}, skill_weights{}, question_count, difficulty_min?, difficulty_max?, exclude_question_uids? }`
* Out: массив `Question` из БЗ:

  * `question_uid`
  * `topic_uid`
  * `skills[] (with role)`
  * `difficulty ∈ [0..1]` (Глубокий градиент)
  * `statement`, `answer_schema`, `rubric`, `common_errors[]`, `method_hints[]`

3. `POST /recompute_links`

* Пересчёт `adaptive_weight` на `Skill-[:LINKED]->Method` (но **без user**), как служебная операция

---

## 3) Формальная модель БЗ (Neo4j) — сущности, свойства, enum, связи, инварианты

Ниже — **каноническая модель**, совместимая с тем, что уже заявлено в README (Subject/Section/Topic/Skill/Method/Goal/Objective + PREREQ + LINKED), но расширенная под “истинность” и “вопросы из БЗ”.

### 3.1. Node Labels и ключевые поля

#### `Subject`

* `uid: "SUB-<ULID>"` (unique)
* `title`
* `description`
* `domain: enum Domain` (например: `MATH`, `PHYSICS`, …)
* `lang: "ru"|"en"|...`
* `version: string` (версия канона)

#### `Section`

* `uid: "SEC-<ULID>"`
* `title`, `description`

#### `Topic`

* `uid: "TOP-<ULID>"`
* `title`, `description`
* `canonical_scope_note: string` (что именно входит/не входит)
* `static_weight: float` (сложность/значимость канона, **не пользователь**)
* `dynamic_weight: float` (глобальная динамика графа, допускается)
* `mastery_threshold: float` (порог “освоено” в терминах диагностики, не персональный)

#### `Skill`

* `uid: "SKL-<ULID>"`
* `title`
* `definition`
* `skill_type: enum SkillType`
* `status: enum SkillStatus`
* `static_weight: float`
* `dynamic_weight: float`

**SkillStatus (как это работает)**

* `ACTIVE` — участвует в планировании/диагностике/вопросах
* `DEPRECATED` — оставляем для совместимости, но:

  * новые куррикулумы не должны ссылаться
  * вопросы не должны выдавать
  * возможен маппинг “заменён на …”
* `ARCHIVED` — скрыт от всего, кроме админ-аудита

#### `Method`

* `uid: "MTH-<ULID>"`
* `title`
* `method_text` (инструкция/алгоритм)
* `applicability: SkillType[]` (к каким типам навыков применим)
* `status: enum MethodStatus` (`ACTIVE|DEPRECATED|ARCHIVED`)

#### `Example` (это же “Question”/“Task” банка)

* `uid: "EXM-<ULID>"`
* `title`
* `statement`
* `difficulty: float` **в диапазоне [0.0 … 1.0]** (глубокий градиент)
* `format: enum ExampleFormat` (`MCQ|SHORT|LONG|PROOF|INTERACTIVE|…`)
* `answer_schema: json` (формат ответа)
* `rubric: json` (критерии)
* `source: enum ExampleSource` (`CANONICAL|FIPI|AUTHOR|GENERATED_VERIFIED`)
* `quality_score: float [0..1]` (качество/доверие)
* `verified: bool`
* `verified_by: string|null` (методист/пайплайн)

#### `Error`

* `uid: "ERR-<ULID>"`
* `title`
* `error_text`
* `triggers: string[]`
* `severity: enum ErrorSeverity` (`MINOR|MAJOR|CRITICAL`)
* `remediation: json` 

#### `Goal` / `Objective`

* `uid: "GOL-<ULID>" | "OBJ-<ULID>"`
* `title`, `description`

---

### 3.2. Relationships (типы, свойства, инварианты)

#### Иерархия адресации

* `(Subject)-[:CONTAINS]->(Section)` 
* `(Section)-[:CONTAINS]->(Topic)` 
  **Инварианты:**
* Section принадлежит ровно одному Subject
* Topic принадлежит ровно одному Section

#### Topic ↔ Skill (M:N)

* `(Topic)-[:USES {role: TopicSkillRole, weight: float}]->(Skill)`
* `TopicSkillRole: enum`

  * `CORE` (ядро темы)
  * `SUPPORT` (вспомогательный)
  * `CONTEXT` (контекстный)
    `weight` здесь — **позиционная важность** (не сложность и не персональный вес).

**Как работает “позиционная важность (enum weight)”**

* Это не “вес ученика”, а **канонический приоритет** влияния навыка на тему:

  * в диагностике `CORE` влияет сильнее на вывод по теме
  * в планировании `CORE` закрывается раньше
* Реализация: в scoring/roadmap используйте коэффициенты:

  * `CORE=1.0`, `SUPPORT=0.6`, `CONTEXT=0.25` (значения — константы сервиса)

#### Skill ↔ Method (M:N)

* `(Skill)-[:LINKED {weight: float, confidence: float, adaptive_weight: float}]->(Method)`
  `adaptive_weight` пересчитывается сервисом, но **без user**.

#### Topic prerequisites (DAG)

* `(Topic)-[:PREREQ {reason: string, strength: float}]->(Topic)`reboot
  **Инвариант:** граф prerequisites внутри предмета **ацикличен**.

#### Topic targets

* `(Topic)-[:TARGETS]->(Goal|Objective)`

#### Example ↔ Topic, Example ↔ Skill

* `(Example)-[:IN_TOPIC]->(Topic)`
* `(Example)-[:CHECKS {role: ExampleSkillRole}]->(Skill)` (M:N)

  * `ExampleSkillRole: TARGET|AUX|CONTEXT`

#### Error ↔ Skill / Example

* `(Error)-[:RELATED_TO]->(Skill)` (M:N, минимум 1)
* `(Error)-[:TRIGGERED_BY]->(Example)` (M:N)

---

### 3.3. Что такое “ремедиация”

**Ремедиация** = “корректирующая интервенция” после ошибки: короткий адресный блок, который:

* объясняет, *почему* ошибка возникла,
* даёт *минимальный набор* упражнений/примеров для исправления,
* возвращает ученика в основной маршрут.

В модели это хранится в `Error.remediation` (json), например:

* `strategy: enum RemediationStrategy` (`MICRO_EXPLANATION|COUNTEREXAMPLE|DRILL|HINT_SEQUENCE|METHOD_SWITCH`)
* `recommended_method_uids[]`
* `example_uids[]`
* `stop_condition` (когда ремедиацию считать пройденной)

---

## 4) Curriculum слой (Postgres) — программы/стандарты/классы/порядок тем вне графа

> Вы хотите “не привязывать разделы к классам/программам”, но уметь получать *разные представления* и порядок.

### 4.1. Таблицы

**`curriculum`**

* `id (uuid)`
* `code` (например `RU_FGOS_2021_MATH_5`)
* `title`
* `standard_body` (минобр/кем утверждено)
* `meta jsonb`

**`curriculum_node`** (плановая “единица”)

* `id`
* `curriculum_id`
* `kind enum` (`TOPIC|SKILL`)
* `canonical_uid` (TOP-… или SKL-…)
* `grade_range int4range|null`
* `order_index int`
* `hours float|null`
* `is_required bool`
* `constraints jsonb` (например: “до контрольной”, “перед модулем X”)

**`curriculum_edge`** (доп. зависимости плана, если нужно)

* `id`
* `curriculum_id`
* `from_node_id`
* `to_node_id`
* `edge_type enum` (`RECOMMENDS_BEFORE|MUST_BEFORE|ASSESS_AFTER`)
* `strength float`

**`admin_user`**, **`methodist_profile`**, **`review_task`**

* хранение админов/методистов
* хранение задач на проверку/верификацию, статусов, комментариев

### 4.2. Как получать “граф для программы”

Алгоритм:

1. Берём curriculum (Postgres) → список canonical_uid тем/навыков.
2. В Neo4j делаем запрос на **индуцированный подграф**: все выбранные темы + их `PREREQ` (замыкание по пререквизитам).
3. Возвращаем как “curriculum graph view”, сохранив `order_index` из Postgres.

---

## 5) Асинхронный LLM-конструктор БЗ (проверяемая генерация)

В README сейчас есть эвристики `compute_static_weights()` и `add_prereqs_heuristic()`
Нужно поднять это на уровень “канонического конструктора”.

### 5.1. Пайплайн Job’ов (kb_jobs.py / services/)

Сделать очередь “build jobs”:

**Job types**

* `CANON_BUILD_SUBJECT`
* `CANON_BUILD_SECTIONS`
* `CANON_BUILD_TOPICS`
* `CANON_BUILD_SKILLS`
* `CANON_BUILD_METHODS`
* `CANON_BUILD_EXAMPLES`
* `CANON_BUILD_ERRORS`
* `CANON_LINK_TOPIC_SKILLS`
* `CANON_LINK_SKILL_METHODS`
* `CANON_BUILD_PREREQS`
* `CANON_VALIDATE_ALL`
* `CANON_PUBLISH`

**Статусы**

* `PENDING|RUNNING|NEEDS_REVIEW|FAILED|DONE`

### 5.2. “Проверка истинности” 

Нужна не абсолютная “истина”, а **детерминированные проверки качества**:

**Валидаторы (обязательные)**

* Schema/типизация: все uid/enum/поля
* Инварианты графа: уникальности, обязательные связи, DAG prerequisites
* Coverage: у темы есть `CORE` навыки; у навыка есть методы; у темы есть примеры
* Consistency: пример ссылается на навыки темы; error связан с skill
* Quality gates:

  * `Example.verified=true` только после review (методист или автоматический чек + доверие)

**LLM-проверка (ограниченная, но полезная)**

* LLM выдаёт “обоснование связи prerequisite” и “почему skill относится к topic”
* второй LLM-проход (или другой промпт) пытается опровергнуть
* итог: `confidence` + `needs_review`

### 5.3. Коммит-политика

* Всё, что ниже порога `confidence`, идёт в `review_task` (Postgres) и **не попадает в Neo4j как канон**.

---

## 6) Что именно сделать в коде (пошаговый план рефакторинга)

### Шаг A — Привести FastAPI к спецификации (stateless)

1. Найти и удалить/отключить:

   * любые импорты/функции “user progress writes to neo4j”
2. Ввести Pydantic-модели:

   * `RoadmapStatelessRequest`
   * `AdaptiveQuestionsRequest`
   * `WeightMap = Dict[str, float]`
3. Убедиться, что **все вычисления принимают веса из payload**, а Neo4j читается только как канон.

### Шаг B — Упорядочить слои (services/)

1. `services/neo4j_kb.py` — чтение/запросы к канону (репозиторий)
2. `services/roadmap.py` — вычисление roadmap (stateless)
3. `services/questions.py` — выбор примеров по весам/сложности/покрытию навыков
4. `services/weights.py` — формулы effective_weight, penalty prerequisites
5. `services/validation.py` — инварианты, DAG check, coverage
6. `kb_jobs.py` — orchestration для async generation

### Шаг C — Neo4j schema constraints/indexes

* Добавить constraints:

  * uniqueness `uid` для всех label’ов
  * existence constraints
* Добавить индексы на:

  * `uid`, `title`, `difficulty`

### Шаг D — Example difficulty: [0..1]

* Миграция:

  * пересчитать/нормализовать существующие difficulty
  * в запросах `/adaptive/questions` фильтровать `difficulty_min/max` в [0..1]

### Шаг E — Curriculum (Postgres)

* Добавить `services/curriculum_repo.py` (SQLAlchemy/asyncpg)
* Эндпоинты админки:

  * `POST /admin/curriculum`
  * `POST /admin/curriculum/nodes`
  * `GET /curriculum/{code}/graph_view`
* Важно: админ-эндпоинты защищать ключом, как уже принято в проекте через `ADMIN_API_KEY`

### Шаг F — LLM KB Constructor

* Встроить в `kb_builder.py` режим:

  * generate → validate → stage → publish
* Все результаты LLM класть в staging (Postgres таблицы или отдельные JSONL), прежде чем пушить в Neo4j.

---

## 7) правильная схема связей и слоёв

```text
                 (LMS / StudyNinja Core - другой репо)
         user_id, progress, attempts, personal weights storage
                          |
                          |  POST topic_weights/skill_weights
                          v
+---------------------------------------------------------------+
|        KnowledgeBaseAI (этот репо) — STATELESS KERNEL          |
|                                                               |
|  FastAPI                                                      |
|   /user/roadmap  <--- weights dict --- computes effective map |
|   /adaptive/questions <--- weights --- picks Examples          |
|                                                               |
|  services/roadmap.py  services/questions.py  services/weights.py|
|             |                    |                    |        |
|             v                    v                    v        |
|                         Neo4j (Canonical KB)                  |
|   Subject->Section->Topic ; Topic-PREREQ->Topic (DAG)         |
|   Topic-USES->Skill ; Skill-LINKED->Method                    |
|   Example-IN_TOPIC->Topic ; Example-CHECKS->Skill             |
|   Error-RELATED_TO->Skill ; Error-TRIGGERED_BY->Example        |
+---------------------------------------------------------------+
             ^
             | (metadata about plans, order, grades, standards)
             |
        Postgres (Curriculum + Admin + Methodist Review)
```


