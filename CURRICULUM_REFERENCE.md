# Справочник по API и Внутренним Механизмам Учебных Программ

**Версия:** 1.0
**Цель документа:** Детальное техническое описание функций, методов и конечных точек для реализации функционала учебных программ (Curriculum).

---

## 1. Модель Данных (Data Layer)

Система использует гибридное хранение данных. Метаданные плана хранятся в PostgreSQL, а связи контента — в Neo4j.

### 1.1 PostgreSQL (Таблицы)

**`curricula`** — Определения учебных планов.
| Поле | Тип | Описание |
| :--- | :--- | :--- |
| `id` | SERIAL PK | Внутренний идентификатор. |
| `code` | VARCHAR(64) | Уникальный бизнес-код (Slug), например `MATH-5-FGOS`. Используется в API. |
| `title` | VARCHAR(255) | Название программы. |
| `standard` | VARCHAR(64) | Образовательный стандарт (FGOS, CC, CORPORATE). |
| `language` | VARCHAR(2) | Язык контента (`ru`, `en`). |
| `status` | VARCHAR(16) | `draft`, `active`, `archived`. |

**`curriculum_nodes`** — Состав программы (явные узлы).
| Поле | Тип | Описание |
| :--- | :--- | :--- |
| `id` | SERIAL PK | Внутренний идентификатор. |
| `curriculum_id` | INT FK | Ссылка на таблицу `curricula`. |
| `canonical_uid` | VARCHAR(128) | UID узла в Графе Знаний (Neo4j). |
| `kind` | VARCHAR(16) | Тип узла (`topic`, `skill`). |
| `order_index` | INT | Порядковый номер для сортировки (опционально). |
| `is_required` | BOOLEAN | Флаг обязательности (в текущей версии `true`). |

### 1.2 Neo4j (Граф)

Учебный план не создает новых сущностей в графе, а ссылается на существующие.
*   **Topic**: Узел темы.
*   **PREREQ**: Связь пререквизита. Планировщик использует эти связи для *неявного* включения тем в план.

---

## 2. API Endpoints (`backend/app/api/admin_curriculum.py`)

Все эндпоинты находятся в пространстве `/v1/admin` и требуют прав администратора (`require_admin`).

### 2.1 Создание Учебного Плана
**Endpoint:** `POST /v1/admin/curriculum`
**Function:** `admin_create_curriculum`

Создает запись в таблице `curricula`.

**Request Body (`CreateCurriculumInput`):**
```json
{
  "code": "PYTHON-BASIC-V1",
  "title": "Основы Python",
  "standard": "CORPORATE",
  "language": "ru"
}
```

**Response (`CurriculumResponse`):**
```json
{
  "ok": true,
  "id": 42
}
```

### 2.2 Добавление Узлов в План
**Endpoint:** `POST /v1/admin/curriculum/nodes`
**Function:** `admin_add_curriculum_nodes`

Массово добавляет ссылки на узлы графа в план. Позволяет "наполнить" программу темами.

**Request Body (`CurriculumNodeInput`):**
```json
{
  "code": "PYTHON-BASIC-V1",
  "nodes": [
    {
      "kind": "topic",
      "canonical_uid": "TOP-variables-123",
      "order_index": 1,
      "is_required": true
    },
    {
      "canonical_uid": "TOP-loops-456",
      "kind": "topic",
      "order_index": 2
    }
  ]
}
```

**Response:**
```json
{
  "ok": true
}
```

### 2.3 Просмотр Состава Плана
**Endpoint:** `GET /v1/admin/curriculum/graph_view`
**Function:** `admin_curriculum_graph_view`

Возвращает "плоский" список узлов, явно включенных в план.

**Query Parameters:**
*   `code`: Код учебного плана (например, `PYTHON-BASIC-V1`).

**Response:**
```json
{
  "ok": true,
  "nodes": [
    { "canonical_uid": "TOP-variables-123", "kind": "topic", ... },
    ...
  ],
  "meta": { "title": "Основы Python" }
}
```

---

## 3. Сервисный Слой (`backend/app/services`)

### 3.1 Repository (`curriculum/repo.py`)

Модуль прямого доступа к PostgreSQL.

*   **`create_curriculum(code, title, standard, language)`**
    *   Выполняет `INSERT INTO curricula`.
    *   Возвращает `id` созданной записи.
*   **`add_curriculum_nodes(code, nodes)`**
    *   Сначала ищет `id` плана по `code`.
    *   В транзакции выполняет массовые `INSERT INTO curriculum_nodes`.
*   **`get_graph_view(code)`**
    *   Извлекает данные плана и список связанных узлов.
    *   Возвращает структуру, готовую для использования в планировщике.

### 3.2 Roadmap Planner (`roadmap_planner.py`)

Ключевой модуль, реализующий логику "Призмы" (фильтрации графа).

**Функция:** `plan_route(...)`
**Аргумент:** `curriculum_code: str | None`

**Алгоритм работы:**

1.  **Проверка наличия плана:**
    Если `curriculum_code` передан, вызывается `get_graph_view(code)`.

2.  **Развертывание Графа (Graph Expansion):**
    Планировщик берет список `canonical_uid` из плана (явные цели) и делает запрос в Neo4j, чтобы найти **все** пререквизиты этих тем (неявные цели).
    ```cypher
    UNWIND $roots AS root 
    MATCH (t:Topic {uid:root})-[:PREREQ*0..]->(p:Topic) 
    RETURN collect(DISTINCT p.uid) AS uids
    ```
    Результат сохраняется в множество `allowed_topics`.

3.  **Фильтрация (Prism Filter):**
    При переборе всех доступных тем графа (из `MATCH (t:Topic)...`), применяется жесткий фильтр:
    ```python
    if curriculum_code and tuid not in allowed_topics:
        continue
    ```
    Это отсекает любые темы, которые не ведут к целям, заданным в учебном плане.

4.  **Приоритизация:**
    Среди оставшихся (`allowed`) тем выбираются те, у которых выполнены пререквизиты (`missing_prereqs == 0`), и они сортируются по приоритету для выдачи студенту.

---

## 4. Сценарии Использования (Integration Flows)

### Сценарий А: Создание Программы (Автор контента)
1.  Автор создает структуру в Neo4j (Темы, Связи).
2.  Автор вызывает `POST /curriculum` для создания "Физика 7 класс".
3.  Автор выбирает ключевые темы (например, "Законы Ньютона", "Работа и Энергия") и вызывает `POST /curriculum/nodes` с их UID. Не обязательно добавлять "Векторы", если "Законы Ньютона" зависят от них — система подтянет их сама.

### Сценарий Б: Обучение (Студент)
1.  Фронтенд вызывает `POST /roadmap` с параметром `curriculum_code="PHYSICS-7"`.
2.  Бэкенд загружает "Физику 7 класс", разворачивает дерево зависимостей.
3.  Бэкенд исключает темы, которые не относятся к физике 7 класса (например, квантовую механику, даже если она есть в базе).
4.  Студент получает список только тех тем, которые ведут к освоению программы 7 класса.
