# Загрузка данных и индексирование

Ниже — минимальная процедура загрузки сидов из `kb/` в PostgreSQL и индексацию в Elasticsearch.

## 1) PostgreSQL

1. Создайте БД и выполните `schemas/postgres.sql`.
2. Сопоставьте `uid` → `id` через временные таблицы или INSERT с возвратом `id`.

Пример загрузки (упрощено, без полноценных UPSERT/конфликта uid):

```sql
-- Subjects
INSERT INTO subjects(uid, title, description)
VALUES ('SUB-MATH','Математика','Базовые и продвинутые математические компетенции.')
RETURNING id;

-- Sections (требуется subject_id)
WITH s AS (
  SELECT id FROM subjects WHERE uid='SUB-MATH'
)
INSERT INTO sections(uid, subject_id, title, description)
SELECT 'SEC-ALG', s.id, 'Алгебра','Уравнения, функции, выражения.' FROM s;

-- Topics (требуется section_id)
WITH sec AS (
  SELECT id FROM sections WHERE uid='SEC-ALG'
)
INSERT INTO topics(uid, section_id, title, description, accuracy_threshold, critical_errors_max, median_time_threshold_seconds)
SELECT 'TOP-LIN-EQ', sec.id, 'Линейные уравнения', 'Решение уравнений вида ax + b = c.', 0.9, 0, 480 FROM sec;

-- Skills (привязка к предмету)
WITH subj AS (
  SELECT id FROM subjects WHERE uid='SUB-MATH'
)
INSERT INTO skills(uid, subject_id, title, definition)
SELECT 'SKL-SIMPLIFY', subj.id, 'Приведение подобных', 'Суммировать/вычитать подобные члены выражения.' FROM subj;

WITH subj AS (
  SELECT id FROM subjects WHERE uid='SUB-MATH'
)
INSERT INTO skills(uid, subject_id, title, definition)
SELECT 'SKL-SOLVE-LIN', subj.id, 'Решение линейного уравнения', 'Изолировать переменную и находить её значение.' FROM subj;

-- Methods
INSERT INTO methods(uid, title, method_text, applicability_types)
VALUES ('MTH-ISOLATE','Изоляция переменной','Переносим все члены с x в одну сторону, остальное — в другую.', ARRAY['algebra','linear']);

INSERT INTO methods(uid, title, method_text, applicability_types)
VALUES ('MTH-SIMPLIFY','Сведение подобных','Группируем и суммируем коэффициенты при одинаковых степенях переменной.', ARRAY['algebra']);

-- Связи: skill ↔ method
WITH skl AS (
  SELECT id FROM skills WHERE uid='SKL-SOLVE-LIN'
), m AS (
  SELECT id FROM methods WHERE uid='MTH-ISOLATE'
)
INSERT INTO skill_methods(skill_id, method_id)
SELECT skl.id, m.id FROM skl, m;

WITH skl AS (
  SELECT id FROM skills WHERE uid='SKL-SIMPLIFY'
), m AS (
  SELECT id FROM methods WHERE uid='MTH-SIMPLIFY'
)
INSERT INTO skill_methods(skill_id, method_id)
SELECT skl.id, m.id FROM skl, m;

-- Examples (нужен subject_id и topic_id)
WITH subj AS (
  SELECT id FROM subjects WHERE uid='SUB-MATH'
), t AS (
  SELECT id FROM topics WHERE uid='TOP-LIN-EQ'
)
INSERT INTO examples(uid, subject_id, topic_id, title, statement, difficulty)
SELECT 'EX-ALG-001', subj.id, t.id, 'Решить: 2x + 5 = 11', 'Найдите x из 2x + 5 = 11.', 2 FROM subj, t;

WITH subj AS (
  SELECT id FROM subjects WHERE uid='SUB-MATH'
), t AS (
  SELECT id FROM topics WHERE uid='TOP-LIN-EQ'
)
INSERT INTO examples(uid, subject_id, topic_id, title, statement, difficulty)
SELECT 'EX-ALG-002', subj.id, t.id, 'Решить: 3x - 4 = 2x + 7', 'Найдите x из 3x - 4 = 2x + 7.', 3 FROM subj, t;

-- Example ↔ Skill + role
WITH ex AS (SELECT id FROM examples WHERE uid='EX-ALG-001'),
     sk AS (SELECT id FROM skills WHERE uid='SKL-SOLVE-LIN')
INSERT INTO example_skills(example_id, skill_id, role)
SELECT ex.id, sk.id, 'target' FROM ex, sk;

WITH ex AS (SELECT id FROM examples WHERE uid='EX-ALG-001'),
     sk AS (SELECT id FROM skills WHERE uid='SKL-SIMPLIFY')
INSERT INTO example_skills(example_id, skill_id, role)
SELECT ex.id, sk.id, 'auxiliary' FROM ex, sk;

-- Errors
INSERT INTO errors(uid, title, error_text)
VALUES ('ERR-ADD-SIGN','Неверный знак при переносе','При переносе через знак равенства меняют знак — ошибка допущена.'),
       ('ERR-SUM-COEF','Ошибочная сумма коэффициентов','Сложение или вычитание коэффициентов выполнено неверно.');

-- Привязка ошибок к навыкам
WITH e AS (SELECT id FROM errors WHERE uid='ERR-ADD-SIGN'),
     sk AS (SELECT id FROM skills WHERE uid='SKL-SOLVE-LIN')
INSERT INTO error_skills(error_id, skill_id)
SELECT e.id, sk.id FROM e, sk;
```

### Проверка DAG

Добавление записи в `skill_prerequisites` автоматически проверяется триггером:

```sql
WITH subj AS (SELECT id FROM subjects WHERE uid='SUB-MATH'),
     skl AS (SELECT id FROM skills WHERE uid='SKL-SOLVE-LIN'),
     dep AS (SELECT id FROM skills WHERE uid='SKL-SIMPLIFY')
INSERT INTO skill_prerequisites(subject_id, skill_id, depends_on_skill_id)
SELECT subj.id, skl.id, dep.id FROM subj, skl, dep;
```

Если образуется цикл, вставка будет отклонена с ошибкой.

## 2) Elasticsearch

1. Создайте индексы:

```sh
curl -X PUT localhost:9200/subjects -H 'Content-Type: application/json' --data-binary @elastic/subjects.json
curl -X PUT localhost:9200/sections  -H 'Content-Type: application/json' --data-binary @elastic/sections.json
curl -X PUT localhost:9200/topics    -H 'Content-Type: application/json' --data-binary @elastic/topics.json
curl -X PUT localhost:9200/skills    -H 'Content-Type: application/json' --data-binary @elastic/skills.json
curl -X PUT localhost:9200/methods   -H 'Content-Type: application/json' --data-binary @elastic/methods.json
curl -X PUT localhost:9200/examples  -H 'Content-Type: application/json' --data-binary @elastic/examples.json
curl -X PUT localhost:9200/errors    -H 'Content-Type: application/json' --data-binary @elastic/errors.json
```

2. Загрузите сиды через Bulk API (UID как документ ID):

```sh
# Пример для subjects
{
  "index": {"_index":"subjects","_id":"SUB-MATH"}
}
{"uid":"SUB-MATH","title":"Математика","description":"Базовые и продвинутые математические компетенции."}
```

3. Векторные поля (`*_vector`) заполняются отдельно по пайплайну эмбеддингов (не входит в минимальный пример).

## 3) Персонализация

- На уровне выборки применяйте фильтры по `difficulty`, роли `example_skills.role` и целевым навыкам темы.
- Весовые схемы и психотипы — вне данной спецификации данных; реализуются в сервисном слое.