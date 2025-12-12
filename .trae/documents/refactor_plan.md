# 🔥 **ИНСТРУКЦИИ (KnowledgeBaseAI Core Refactor Spec)**

### **Цель:** превратить репозиторий в масштабируемое предметное ядро, которое:

* хранит **единый граф знаний** (темы, навыки, методы, примеры, цели, ошибки);
* обеспечивает сервис **адаптивного тестирования** (дорожные карты, выбор вопросов, перерасчёт весов);
* работает **без хранения пользовательских данных**;
* предоставляет API внешним ЛМС/платформам;
* позволяет асинхронно **генерировать и обновлять базу знаний** с проверкой истинности.

---

# 1. 🔧 Общие принципы ядра (Core LMS-Agnostic Architecture)

1. **Ядро НЕ является ЛМС.**
   Оно **не хранит пользователей**, **не создаёт узлы User**, **не хранит прогресс**.

2. Ядро предоставляет только:

   * единый предметный граф знаний (Neo4j → Topics, Skills, Methods, Examples, PREREQ…);
   * адаптивное тестирование по статическому графу;
   * перерасчёт динамических весов тем/навыков;
   * персональные дорожные карты **на основе переданных извне веса**.

3. Внешние ЛМС хранят:

   * users, progress, history, answers, own weights.
     Ядро принимает веса как параметры, **не сохраняет**.

---

# 2. 🔥 Удалить всю пользовательскую модель из графа Neo4j

## 2.1. В `neo4j_repo.py`

Найти и отметить как `DEPRECATED` методы, использующие:

* `(:User)`
* `:PROGRESS_TOPIC`, `:PROGRESS_SKILL`
* `:COMPLETED`

Функции:
`ensure_user`, `set_topic_user_weight`, `get_topic_user_weight`, `set_skill_user_weight`, `get_skill_user_weight`, любые Cypher с `User`.

➡ **Они не должны вызываться нигде в коде.**

Добавить в начало файла:

```python
# NOTE: User-related relations are deprecated.
# KnowledgeBaseAI core no longer stores any user data inside Neo4j.
```

---

## 2.2. В `neo4j_utils.py`

Переписать функции:

* `update_user_topic_weight`
* `update_user_skill_weight`
* `get_user_topic_level`
* `get_user_skill_level`
* `build_user_roadmap`
* `complete_user_topic`
* `complete_user_skill`

### Новая логика:

### 🔄 Эти функции становятся **stateless-вычислителями**, не пишущими в граф.

### 2.2.1. Чистая функция веса:

```python
def compute_user_weight(base_weight: float, score: float) -> float:
    delta = (50.0 - float(score)) / 100.0
    new_weight = max(0.0, min(1.0, base_weight + delta))
    return new_weight
```

### 2.2.2. Stateless API для перерасчёта веса темы:

```python
def compute_topic_user_weight(topic_uid: str, score: float, base_weight: float | None = None):
    repo = Neo4jRepo()
    if base_weight is None:
        rows = repo.read(
            "MATCH (t:Topic {uid:$uid}) "
            "RETURN coalesce(t.dynamic_weight, t.static_weight, 0.5) AS w",
            {"uid": topic_uid}
        )
        base_weight = rows[0]["w"] if rows else 0.5
    return {
        "topic_uid": topic_uid,
        "base_weight": base_weight,
        "user_weight": compute_user_weight(base_weight, score),
    }
```

Аналогично — для навыков.

### 2.2.3. Уровень знания:

```python
def knowledge_level_from_weight(weight: float) -> str:
    if weight < 0.3: return "high"
    if weight < 0.7: return "medium"
    return "low"
```

---

# 3. ⚙ Переписать адаптивную дорожную карту (stateless)

Новый интерфейс:

```python
def build_user_roadmap_stateless(
    subject_uid: str | None,
    user_topic_weights: dict[str, float],
    user_skill_weights: dict[str, float] | None = None,
    limit: int = 50,
    penalty_factor: float = 0.15,
) -> list[dict]:
```

### Алгоритм:

1. Считать из Neo4j все Topics по предмету:

```cypher
MATCH (t:Topic)
WHERE $subject_uid IS NULL OR t.subject_uid = $subject_uid
OPTIONAL MATCH (t)-[:PREREQ]->(pre:Topic)
RETURN t.uid AS uid, t.title AS title,
       coalesce(t.static_weight, 0.5) AS sw,
       coalesce(t.dynamic_weight, t.static_weight, 0.5) AS dw,
       collect(pre.uid) AS prereqs
```

2. Для каждой темы:

* base_weight = dw
* user_weight = если есть → переданный вес
* effective_weight = user_weight * penalty(prereqs)

3. Сортировать по effective_weight.

4. Вернуть топ-N тем.

---

# 4. 📚 Вопросы тестирования должны браться из базы знаний

## 4.1. Источник вопросов

Все вопросы → `kb/examples.jsonl`
Метаданные → `kb/example_skills.jsonl`

Структура:

```json
{
  "uid": "EX-123",
  "title": "Найдите корень уравнения…",
  "statement": "2x - 5 = 11",
  "topic_uid": "TOP-LINEQ",
  "difficulty": 3
}
```

---

## 4.2. Новый модуль: `services/question_selector.py`

### Индексация:

```python
@lru_cache(maxsize=1)
def get_examples_indexed():
    ex = load_jsonl("examples.jsonl")
    by_topic = {}
    for e in ex:
        by_topic.setdefault(e["topic_uid"], []).append(e)
    return {"all": ex, "by_topic": by_topic}
```

### Выбор вопросов:

```python
def select_examples_for_topics(
    topic_uids: list[str],
    limit: int,
    difficulty_min: int = 1,
    difficulty_max: int = 5,
    exclude_uids: set[str] | None = None,
):
    ...
```

---

# 5. 🔥 Новый API для адаптивных тестов

## Эндпоинт `/adaptive/questions`

```python
@app.post("/adaptive/questions")
def get_adaptive_questions(payload: AdaptiveTestRequest):
    roadmap = build_user_roadmap_stateless(
        subject_uid=payload.subject_uid,
        user_topic_weights=payload.topic_weights,
        user_skill_weights=payload.skill_weights,
        limit=payload.question_count * 3,
    )

    topic_uids = [t["topic_uid"] for t in roadmap]
    examples = select_examples_for_topics(
        topic_uids=topic_uids,
        limit=payload.question_count,
        difficulty_min=payload.difficulty_min,
        difficulty_max=payload.difficulty_max,
        exclude_uids=set(payload.exclude_question_uids),
    )
    return [...]
```

### Это ядро:

* *не хранит* вопрос,
* не хранит результаты,
* только выбирает вопросы по графу знаний.

---

# 6. ⚡ Переработать весь FastAPI под stateless-ядро

## 6.1. `/test_result` → stateless

Вместо записи в граф:

```python
@app.post("/test_result")
def test_result(payload: TopicTestInput):
    return compute_topic_user_weight(
        topic_uid=payload.topic_uid,
        score=payload.score,
        base_weight=payload.base_weight
    )
```

---

## 6.2. `/user/roadmap` — принимает веса от ЛМС

```python
class UserRoadmapRequest(BaseModel):
    subject_uid: str | None = None
    topic_weights: Dict[str, float] = {}
    skill_weights: Dict[str, float] = {}
    limit: int = 50
    penalty_factor: float = 0.15
```

---

## 6.3. `/user/topic_level` и `/user/skill_level`

Принимают `weight`, возвращают уровень:

```python
@app.post("/user/topic_level")
def level(payload: LevelRequest):
    return {"level": knowledge_level_from_weight(payload.weight)}
```

---

# 7. 🧠 Асинхронная сборка базы знаний

## Новый модуль: `kb_jobs.py`

### Поддержка:

* асинхронной генерации теории/примеров/целей (через LLM);
* нормализации KB через `normalize_jsonl_file`;
* валидации (структурной + предметной);
* `sync_from_jsonl()`;
* анализа графа: `analyze_knowledge`, `analyze_prereqs`.

### API:

```
POST /kb/rebuild_async
GET  /kb/rebuild_status?job_id=...
```

---

# 8. 🧩 Пререквизиты и статические веса должны быть валидными

## 8.1. Включить `topic_prereqs.jsonl` в `sync_from_jsonl()`

Создавать связи:

```cypher
MERGE (a:Topic {uid: r.topic_uid})
MERGE (b:Topic {uid: r.prereq_uid})
MERGE (a)-[:PREREQ {weight:r.weight, confidence:r.confidence}]->(b)
```

---

## 8.2. Добавить проверку пререквизитов:

В `neo4j_utils.py` → новая функция:

```python
def analyze_prereqs(subject_uid=None) -> dict:
    - поиск циклов PREREQ
    - ошибки межпредметных связей
    - аномальные веса
```

---

## 8.3. Статические веса тем

Переработать `compute_static_weights()`:

* младшие классы → 0.2–0.4
* средние → 0.4–0.7
* старшие → 0.6–0.9

И проверять монотонность по пререквизитам:

```
если A → B (PREREQ), то weight(A) ≤ weight(B)
```

---

# 9. 📘 Обновление документации

### Создать файл: `docs/core_architecture.md`

Описание:

* что хранится в Neo4j;
* что хранится в JSONL;
* что НЕ хранится (пользователи, прогресс);
* API сервиса (stateless);
* схема взаимодействия ЛМС ↔ ядро.

---

# 10. ✔ Определение готовности (Definition of Done)

Builder должен выполнить всё, если:

1. **В графе Neo4j нет узлов `User` и связей `PROGRESS_*`.**
2. Все функции user-related → stateless.
3. `/adaptive/questions` полностью работает на основе KB.
4. `/user/roadmap` принимает веса извне и выдаёт корректную карту.
5. `/test_result` только считает веса, не сохраняет их.
6. Сборка KB асинхронна и проверяется.
7. Пререквизиты и веса грамотно синхронизируются и валидируются.
8. Документация обновлена.