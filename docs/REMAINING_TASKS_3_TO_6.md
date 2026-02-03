# Технические инструкции: Задачи 3-6

## Задача 3: Повышение релевантности дорожной карты

### Текущая проблема

**KnowledgeBaseAI (`engine.py:155-348`)**:
- Roadmap генерируется на основе PREREQ связей из Neo4j
- Недостаточный датасет связей между темами
- Простое расстояние в графе не учитывает семантику
- LLM выбирает 5-8 тем одноразово без адаптации

**StudyNinja (`service.py`, `router.py`)**:
- Получает roadmap и сохраняет как есть
- Не использует embeddings для похожести тем
- Нет учета реальных навыков пользователя

### Решение: Гибридная система (Graph + Embeddings + Skill Matching)

#### Изменения в KnowledgeBaseAI

**Файл 1: `backend/app/services/hybrid_roadmap.py` (создать новый)**

```python
"""
Гибридная рекомендательная система для дорожных карт
Использует: Graph structure + Semantic embeddings + Skill matching
"""

from typing import List, Dict, Optional
import numpy as np
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)


class RoadmapRecommendation(BaseModel):
    """Рекомендация темы с объяснением"""
    topic_uid: str
    title: str
    description: str
    score: float  # Композитный скор (0-1)
    reasons: List[str]  # Почему рекомендована
    component_scores: Dict[str, float]  # Детали скоринга


class HybridRoadmapEngine:
    """Движок гибридных рекомендаций"""

    # Веса компонентов скоринга
    W_GRAPH = 0.3      # Структура графа (prereqs, importance)
    W_SEMANTIC = 0.35  # Семантическая близость (embeddings)
    W_SKILL = 0.25     # Соответствие навыкам пользователя
    W_DIFFICULTY = 0.1 # Оптимальная сложность (ZPD)

    @staticmethod
    async def generate_personalized_roadmap(
        subject_uid: str,
        user_progress: Dict[str, float],  # {topic_uid: mastery 0-1}
        user_skills: Dict[str, float],    # {skill_uid: priority 0-1}
        focus_topic_uid: Optional[str] = None,
        user_theta: float = 0.0,
        limit: int = 8
    ) -> List[RoadmapRecommendation]:
        """
        Генерация персонализированной дорожной карты

        Алгоритм:
        1. Загрузить все темы предмета с метаданными
        2. Фильтровать по доступности (пререквизиты освоены)
        3. Для каждой темы: вычислить композитный скор из 4 компонентов
        4. Ранжировать и выбрать топ-N
        5. Обогатить через LLM (описания, связи)
        """

        # ШАГ 1: Загрузка кандидатов из Neo4j
        candidates = await HybridRoadmapEngine._load_topic_candidates(
            subject_uid, user_progress
        )

        # ШАГ 2: Фильтрация доступных
        available = HybridRoadmapEngine._filter_available_topics(
            candidates, user_progress
        )

        if not available:
            logger.warning(f"No available topics for subject {subject_uid}")
            return []

        # ШАГ 3: Получить focus embedding
        if focus_topic_uid:
            focus_embedding = await HybridRoadmapEngine._get_topic_embedding(
                focus_topic_uid
            )
        else:
            # Среднее по целевым навыкам
            focus_embedding = await HybridRoadmapEngine._compute_goal_embedding(
                user_skills
            )

        # ШАГ 4: Скоринг каждой темы
        scored = []
        for topic in available:
            score, components, reasons = await HybridRoadmapEngine._score_topic(
                topic=topic,
                focus_embedding=focus_embedding,
                user_progress=user_progress,
                user_skills=user_skills,
                user_theta=user_theta
            )

            scored.append(RoadmapRecommendation(
                topic_uid=topic['uid'],
                title=topic['title'],
                description=topic.get('description', ''),
                score=score,
                component_scores=components,
                reasons=reasons
            ))

        # ШАГ 5: Ранжирование и отбор
        scored.sort(key=lambda x: x.score, reverse=True)
        top_recommendations = scored[:limit]

        # ШАГ 6: Обогащение через LLM
        enriched = await HybridRoadmapEngine._enrich_descriptions(
            top_recommendations, user_progress, user_skills
        )

        return enriched

    @staticmethod
    async def _load_topic_candidates(
        subject_uid: str,
        user_progress: Dict[str, float]
    ) -> List[Dict]:
        """
        Загрузка тем предмета с метаданными

        Возвращает для каждой темы:
        - uid, title, description
        - irt_difficulty (средняя сложность вопросов)
        - graph_importance (in-degree)
        - unlock_count (количество зависимых тем)
        - required_skills (список UID навыков)
        - prerequisites (список UID пререквизитов)
        """

        from app.services.graph.neo4j_repo import get_driver

        query = """
        MATCH (t:Topic)-[:BELONGS_TO*]->(subj:Subject {uid: $subject_uid})

        // Средняя IRT сложность вопросов темы
        OPTIONAL MATCH (t)-[:HAS_QUESTION]->(q:Question)
        WITH t, subj, AVG(COALESCE(q.irt_difficulty, 0.0)) as avg_difficulty

        // Graph metrics
        OPTIONAL MATCH (other:Topic)-[:PREREQ]->(t)
        WITH t, subj, avg_difficulty, COUNT(DISTINCT other) as importance

        OPTIONAL MATCH (t)-[:PREREQ*]->(descendant:Topic)
        WITH t, subj, avg_difficulty, importance, COUNT(DISTINCT descendant) as unlock_count

        // Навыки и пререквизиты
        OPTIONAL MATCH (t)-[:REQUIRES_SKILL]->(skill:Skill)
        OPTIONAL MATCH (t)<-[:PREREQ]-(prereq:Topic)

        RETURN
            t.uid as uid,
            t.title as title,
            t.description as description,
            t.user_class_min as class_min,
            t.user_class_max as class_max,
            avg_difficulty as irt_difficulty,
            importance,
            unlock_count,
            COLLECT(DISTINCT skill.uid) as required_skills,
            COLLECT(DISTINCT prereq.uid) as prerequisites
        ORDER BY importance DESC, unlock_count DESC
        LIMIT 100
        """

        async with get_driver().session() as session:
            result = await session.run(query, {"subject_uid": subject_uid})
            records = await result.data()

        # Добавить текущее мастерство
        for rec in records:
            rec['current_mastery'] = user_progress.get(rec['uid'], 0.0)

        return records

    @staticmethod
    def _filter_available_topics(
        candidates: List[Dict],
        user_progress: Dict[str, float],
        prereq_threshold: float = 0.7,
        mastery_threshold: float = 0.85
    ) -> List[Dict]:
        """
        Фильтрация доступных тем

        Условия:
        1. Все пререквизиты освоены >= prereq_threshold
        2. Тема сама не освоена >= mastery_threshold
        """

        available = []
        for topic in candidates:
            # Исключить полностью освоенные
            if topic['current_mastery'] >= mastery_threshold:
                continue

            # Проверить пререквизиты
            prereqs = topic.get('prerequisites', [])
            if all(user_progress.get(p, 0.0) >= prereq_threshold for p in prereqs):
                available.append(topic)

        return available

    @staticmethod
    async def _get_topic_embedding(topic_uid: str) -> np.ndarray:
        """
        Получение эмбеддинга темы (с кэшированием в Redis)
        """

        from app.config import redis_client
        from app.services.graph.neo4j_repo import get_driver
        import openai
        import json

        # Проверить кэш
        cache_key = f"embedding:topic:{topic_uid}"
        cached = await redis_client.get(cache_key)
        if cached:
            return np.array(json.loads(cached))

        # Загрузить текст темы
        query = """
        MATCH (t:Topic {uid: $topic_uid})
        OPTIONAL MATCH (t)-[:REQUIRES_SKILL]->(s:Skill)
        RETURN t.title as title, t.description as description,
               COLLECT(s.title) as skills
        """

        async with get_driver().session() as session:
            result = await session.run(query, {"topic_uid": topic_uid})
            record = await result.single()

        if not record:
            return np.zeros(1536)

        # Составить текст для эмбеддинга
        text_parts = [record['title']]
        if record.get('description'):
            text_parts.append(record['description'])
        if record.get('skills'):
            text_parts.append(f"Навыки: {', '.join(record['skills'])}")

        text = ". ".join(text_parts)

        # Генерация эмбеддинга
        response = await openai.Embedding.acreate(
            input=text,
            model="text-embedding-3-small"
        )
        embedding = response['data'][0]['embedding']

        # Кэш на 7 дней
        await redis_client.setex(cache_key, 604800, json.dumps(embedding))

        return np.array(embedding)

    @staticmethod
    async def _compute_goal_embedding(user_skills: Dict[str, float]) -> np.ndarray:
        """
        Вычисление эмбеддинга цели пользователя из приоритетных навыков
        """

        if not user_skills:
            return np.zeros(1536)

        # Топ-5 навыков
        sorted_skills = sorted(user_skills.items(), key=lambda x: x[1], reverse=True)[:5]

        embeddings = []
        weights = []

        for skill_uid, weight in sorted_skills:
            emb = await HybridRoadmapEngine._get_topic_embedding(skill_uid)
            embeddings.append(emb)
            weights.append(weight)

        # Взвешенное среднее
        weights = np.array(weights)
        weights = weights / weights.sum()

        return np.average(embeddings, axis=0, weights=weights)

    @staticmethod
    async def _score_topic(
        topic: Dict,
        focus_embedding: np.ndarray,
        user_progress: Dict[str, float],
        user_skills: Dict[str, float],
        user_theta: float
    ) -> tuple:
        """
        Композитный скоринг темы по 4 компонентам

        Возвращает: (total_score, component_scores, reasons)
        """

        reasons = []
        components = {}

        # === КОМПОНЕНТ 1: Graph structure (30%) ===
        importance = topic.get('importance', 0)
        unlock_count = topic.get('unlock_count', 0)

        # Нормализация
        importance_norm = min(importance / 10.0, 1.0)
        unlock_norm = min(unlock_count / 20.0, 1.0)

        graph_score = 0.5 * importance_norm + 0.5 * unlock_norm
        components['graph'] = graph_score

        if importance >= 3:
            reasons.append(f"Важная тема ({importance} тем зависят от неё)")
        if unlock_count >= 5:
            reasons.append(f"Откроет {unlock_count} новых тем")

        # === КОМПОНЕНТ 2: Semantic similarity (35%) ===
        topic_embedding = await HybridRoadmapEngine._get_topic_embedding(topic['uid'])

        cosine_sim = np.dot(focus_embedding, topic_embedding) / (
            np.linalg.norm(focus_embedding) * np.linalg.norm(topic_embedding) + 1e-8
        )
        semantic_score = (cosine_sim + 1) / 2  # [-1, 1] → [0, 1]
        components['semantic'] = semantic_score

        if semantic_score > 0.7:
            reasons.append("Тематически близка к вашим целям")

        # === КОМПОНЕНТ 3: Skill matching (25%) ===
        required_skills = set(topic.get('required_skills', []))
        user_skill_set = set(user_skills.keys())

        if not required_skills:
            skill_score = 0.5
        else:
            overlap = len(required_skills & user_skill_set)
            skill_score = overlap / len(required_skills)

            if skill_score > 0.5:
                reasons.append("Развивает приоритетные навыки")

        components['skill'] = skill_score

        # === КОМПОНЕНТ 4: Optimal difficulty (10%) ===
        topic_difficulty = topic.get('irt_difficulty', 0.0)
        difficulty_gap = abs(topic_difficulty - user_theta)

        if difficulty_gap <= 0.5:
            difficulty_score = 1.0
            reasons.append("Оптимальная сложность")
        elif difficulty_gap <= 1.0:
            difficulty_score = 0.7
        elif difficulty_gap <= 1.5:
            difficulty_score = 0.4
        else:
            difficulty_score = 0.2
            if topic_difficulty > user_theta + 1.0:
                reasons.append("Может быть сложной")

        components['difficulty'] = difficulty_score

        # === ИТОГОВЫЙ СКОР ===
        total_score = (
            HybridRoadmapEngine.W_GRAPH * graph_score +
            HybridRoadmapEngine.W_SEMANTIC * semantic_score +
            HybridRoadmapEngine.W_SKILL * skill_score +
            HybridRoadmapEngine.W_DIFFICULTY * difficulty_score
        )

        return total_score, components, reasons

    @staticmethod
    async def _enrich_descriptions(
        recommendations: List[RoadmapRecommendation],
        user_progress: Dict[str, float],
        user_skills: Dict[str, float]
    ) -> List[RoadmapRecommendation]:
        """
        Обогащение описаний через LLM для тем с пустыми полями
        """

        needs_description = [r for r in recommendations if not r.description]

        if not needs_description:
            return recommendations

        # Генерация описаний батчем
        titles = [r.title for r in needs_description]

        prompt = f"""Создай краткие описания (1-2 предложения) для учебных тем.

Темы: {', '.join(titles)}

Контекст: Пользователь изучает математику, освоено {len([m for m in user_progress.values() if m > 0.5])} тем.

JSON формат:
{{
    "descriptions": [
        {{"title": "...", "description": "..."}},
        ...
    ]
}}
"""

        from app.services.openai_helpers import openai_chat_async
        import json

        response = await openai_chat_async(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            model="gpt-4o-mini",
            response_format={"type": "json_object"}
        )

        descriptions_data = json.loads(response)['descriptions']

        # Обновить описания
        desc_map = {d['title']: d['description'] for d in descriptions_data}

        for rec in recommendations:
            if not rec.description and rec.title in desc_map:
                rec.description = desc_map[rec.title]

        return recommendations
```

**Файл 2: Модификация `backend/app/api/engine.py` (roadmap endpoint)**

```python
# backend/app/api/engine.py

from app.services.hybrid_roadmap import HybridRoadmapEngine

@app.post("/v1/engine/roadmap")
async def generate_hybrid_roadmap(request: RoadmapRequest):
    """
    ОБНОВЛЕНО: Генерация roadmap с гибридной системой рекомендаций
    """

    # Получить theta пользователя из истории
    user_theta = await _get_user_theta(request.user_id, request.subject_uid)

    # Генерация персонализированной roadmap
    recommendations = await HybridRoadmapEngine.generate_personalized_roadmap(
        subject_uid=request.subject_uid,
        user_progress=request.current_progress,
        user_skills=request.user_skills or {},
        focus_topic_uid=request.focus_topic_uid,
        user_theta=user_theta,
        limit=request.limit or 8
    )

    # Преобразовать в формат API ответа
    roadmap_nodes = []
    for rec in recommendations:
        roadmap_nodes.append({
            "topic_uid": rec.topic_uid,
            "title": rec.title,
            "description": rec.description,
            "status": _determine_status(rec.topic_uid, request.current_progress),
            "progress_percentage": request.current_progress.get(rec.topic_uid, 0.0) * 100,
            "recommendation_score": rec.score,
            "reasons": rec.reasons,
            "score_breakdown": rec.component_scores
        })

    return {"nodes": roadmap_nodes}
```

#### Интеграция в StudyNinja

**Изменения минимальны** - StudyNinja просто получает обогащенный roadmap с дополнительными полями `reasons` и `score_breakdown`, которые можно показать в UI.

---

## Задача 4: Генерация координат для микро-уроков (визуализация фаз)

### Текущая реализация

**StudyNinja (`adaptive_engine.py`)**:
- Генерирует микро-уроки с фазами I Do / We Do / You Do
- НЕ генерирует визуализацию для интерактивных фаз
- Payload микро-урока содержит только текст

### Решение: Расширить генерацию микро-уроков визуализацией

#### Изменения в StudyNinja

**Файл: `backend/app/domain/services/ai_services/adaptive_engine.py` (модификация)**

```python
# Добавить в класс AdaptiveLessonGenerator

async def _generate_lesson_with_visual(
    self,
    topic_context: dict,
    node_data: dict
) -> dict:
    """
    Генерация микро-урока с визуализацией для фаз We Do / You Do

    Вызывает KB API для генерации визуализации если нужна
    """

    # Определить необходимость визуализации
    needs_visual = self._should_use_visualization(topic_context)

    # Генерация контента урока
    lesson_content = await self._generate_lesson_content(topic_context, node_data)

    # Если нужна визуализация - запросить из KB
    if needs_visual:
        visual_data = await self._request_visual_from_kb(
            topic_context,
            lesson_content
        )

        # Добавить визуализацию в фазы
        if 'we_do' in lesson_content:
            lesson_content['we_do']['visualization'] = visual_data

        if 'you_do' in lesson_content:
            lesson_content['you_do']['visualization'] = visual_data

    return lesson_content


def _should_use_visualization(self, topic_context: dict) -> bool:
    """Определение необходимости визуализации"""

    visual_keywords = [
        'геометр', 'график', 'функц', 'треугольн', 'окружн',
        'координат', 'вектор', 'угол', 'прямая', 'отрезок'
    ]

    text = (topic_context.get('title', '') + ' ' +
            topic_context.get('description', '')).lower()

    return any(kw in text for kw in visual_keywords)


async def _request_visual_from_kb(
    self,
    topic_context: dict,
    lesson_content: dict
) -> dict:
    """
    Запрос визуализации из KnowledgeBaseAI

    Использует существующий endpoint для генерации визуализации
    """

    from app.api.kb_integration.client import KnowledgeBaseClient

    kb_client = KnowledgeBaseClient()

    # Запрос в KB для генерации визуализации
    response = await kb_client.post(
        "/v1/graph/generate_visualization",
        json={
            "topic_uid": topic_context['uid'],
            "context_text": lesson_content.get('we_do', {}).get('problem', {}).get('text', ''),
            "visualization_type": "geometry"  # или "graph", "chart"
        }
    )

    return response.get('visualization_data', {})
```

**Структура payload микро-урока с визуализацией:**

```json
{
    "i_do": {
        "theory": {"text": "...", "steps": [...]},
        "content": "..."
    },
    "we_do": {
        "problem": {
            "text": "На координатной плоскости даны точки A(2,3) и B(5,7)...",
            "correctAnswer": "...",
            "hints": [...]
        },
        "visualization": {
            "shapes": [
                {"type": "point", "label": "A", "points": [{"x": 2, "y": 3}]},
                {"type": "point", "label": "B", "points": [{"x": 5, "y": 7}]}
            ],
            "labels": ["A", "B"],
            "coordinate_system": "cartesian"
        },
        "content": "..."
    },
    "you_do": {
        "title": "...",
        "content": "...",
        "correctAnswers": [...],
        "visualization": {
            // Аналогично
        }
    }
}
```

---

## Задача 5: Тестирование и доработка системы прогресса

### Текущая система прогресса

**StudyNinja**:
- `RoadmapNode.current_score` / `max_score`
- `MicroLesson.is_completed`
- `SkillMastery.mastery_level`

### План тестирования

**Файл: `tests/test_progress_system.py` (создать новый)**

```python
import pytest
from app.domain.services.api_services.lesson_service import complete_micro_lesson


@pytest.mark.asyncio
async def test_progress_micro_lesson_completion(db_session):
    """
    Тест: Завершение микро-урока обновляет прогресс узла
    """

    # 1. Создать roadmap с узлом и 3 микро-уроками
    # 2. Завершить 1-й урок → node.current_score должно быть 33%
    # 3. Завершить 2-й урок → node.current_score должно быть 66%
    # 4. Завершить 3-й урок → node.current_score = 100%, node.status = 'completed'


@pytest.mark.asyncio
async def test_progress_node_unlock(db_session):
    """
    Тест: Завершение узла разблокирует следующий
    """

    # 1. Создать roadmap с 3 узлами (статусы: available, locked, locked)
    # 2. Завершить все уроки узла 1 → узел 2 должен стать available


@pytest.mark.asyncio
async def test_progress_remediation_lesson(db_session):
    """
    Тест: Провал теста создает remediation_lesson и НЕ разблокирует следующий узел
    """

    # 1. Создать узел с lesson_test
    # 2. Провалить тест (errors > allowed_errors)
    # 3. Проверить: is_completed=True, но следующий узел locked
    # 4. Проверить: создан remediation_lesson


@pytest.mark.asyncio
async def test_progress_roadmap_total_score(db_session):
    """
    Тест: Roadmap.total_score = сумма node.current_score
    """

    # 1. Создать roadmap с 3 узлами (max_score = 20 каждый)
    # 2. Обновить прогресс узлов: 10, 15, 20
    # 3. Проверить: roadmap.total_score = 45, max_score = 60
```

### Доработки

**Файл: `backend/app/domain/services/api_services/lesson_service.py` (доработка)**

```python
async def complete_micro_lesson(
    db_session,
    user_id: UUID,
    micro_lesson_kb_uid: str,
    test_score: Optional[int] = None,
    user_answers: Optional[Dict] = None
) -> RoadmapNodeResponse | None:
    """
    ДОРАБОТКА: Улучшенная логика обновления прогресса
    """

    # ... существующий код ...

    # НОВОЕ: Атомарное обновление прогресса узла
    await _update_node_progress_atomic(db_session, node.id)

    # НОВОЕ: Обновить прогресс roadmap
    await _update_roadmap_progress(db_session, node.roadmap_id)

    # НОВОЕ: Логировать событие прогресса
    await _log_progress_event(
        db_session,
        user_id=user_id,
        node_id=node.id,
        lesson_uid=micro_lesson_kb_uid,
        event_type="lesson_completed",
        metadata={"test_score": test_score}
    )

    return node


async def _update_node_progress_atomic(db_session, node_id: UUID):
    """
    Атомарное обновление прогресса узла

    Вычисляет: current_score = (completed_units / total_units) * max_score
    """

    query = """
    WITH node_progress AS (
        SELECT
            rn.id,
            rn.max_score,
            COUNT(ml.id) as total_units,
            SUM(CASE WHEN ml.is_completed THEN 1 ELSE 0 END) as completed_units
        FROM roadmap_nodes rn
        LEFT JOIN micro_lessons ml ON ml.roadmap_node_id = rn.id
        WHERE rn.id = :node_id
        GROUP BY rn.id, rn.max_score
    )
    UPDATE roadmap_nodes rn
    SET
        current_score = CASE
            WHEN np.total_units > 0
            THEN (np.completed_units::float / np.total_units) * np.max_score
            ELSE 0
        END,
        status = CASE
            WHEN np.completed_units = np.total_units THEN 'completed'
            WHEN np.completed_units > 0 THEN 'in_progress'
            ELSE rn.status
        END,
        updated_at = NOW()
    FROM node_progress np
    WHERE rn.id = np.id
    RETURNING rn.current_score, rn.status
    """

    result = await db_session.execute(query, {"node_id": node_id})
    return result.fetchone()


async def _update_roadmap_progress(db_session, roadmap_id: UUID):
    """
    Обновление общего прогресса roadmap
    """

    query = """
    UPDATE roadmaps r
    SET
        total_score = (
            SELECT COALESCE(SUM(current_score), 0)
            FROM roadmap_nodes
            WHERE roadmap_id = :roadmap_id
        ),
        updated_at = NOW()
    WHERE id = :roadmap_id
    RETURNING total_score, max_score
    """

    result = await db_session.execute(query, {"roadmap_id": roadmap_id})
    return result.fetchone()
```

---

## Задача 6: Адаптивная дорожная карта (регенерация после узла)

### Концепция

После завершения узла roadmap:
1. Получить обновленный прогресс пользователя (новый mastery, theta)
2. Запустить регенерацию следующих 2-3 узлов
3. Заменить или дополнить существующие узлы

### Реализация

#### Изменения в StudyNinja

**Файл: `backend/app/domain/services/api_services/lesson_service.py` (расширение)**

```python
async def complete_micro_lesson(
    # ... параметры ...
) -> RoadmapNodeResponse | None:
    """
    РАСШИРЕНИЕ: Триггер адаптивной регенерации после завершения узла
    """

    # ... существующий код завершения урока ...

    # НОВОЕ: Если узел полностью завершен
    if node.status == 'completed':
        # Запустить фоновую задачу регенерации следующих узлов
        from app.tasks.adaptive_roadmap import regenerate_next_nodes

        asyncio.create_task(
            regenerate_next_nodes.delay(
                roadmap_id=str(node.roadmap_id),
                completed_node_id=str(node.id),
                user_id=str(user_id)
            )
        )

    return node
```

**Файл: `backend/app/tasks/adaptive_roadmap.py` (создать новый)**

```python
"""
Фоновая задача регенерации адаптивной дорожной карты
"""

from celery import shared_task
from app.api.kb_integration.client import KnowledgeBaseClient
from app.core.postgres.db import get_db_session
from app.core.postgres.models import Roadmap, RoadmapNode
import logging

logger = logging.getLogger(__name__)


@shared_task
async def regenerate_next_nodes(
    roadmap_id: str,
    completed_node_id: str,
    user_id: str
):
    """
    Регенерация следующих узлов roadmap после завершения текущего

    Алгоритм:
    1. Получить обновленный прогресс пользователя
    2. Запросить новые рекомендации из KB API
    3. Сравнить с существующими узлами
    4. Обновить или добавить узлы
    """

    async with get_db_session() as db:
        # 1. Загрузить roadmap и завершенный узел
        roadmap = await db.get(Roadmap, roadmap_id)
        completed_node = await db.get(RoadmapNode, completed_node_id)

        if not roadmap or not completed_node:
            logger.error(f"Roadmap {roadmap_id} or node {completed_node_id} not found")
            return

        # 2. Получить обновленный прогресс из SkillMastery
        user_progress = await _get_updated_user_progress(db, user_id, roadmap.user_goal_id)

        # 3. Получить user_theta из последнего assessment
        user_theta = await _get_user_theta(db, user_id, roadmap.kb_subject_uid)

        # 4. Запросить новые рекомендации из KB
        kb_client = KnowledgeBaseClient()

        response = await kb_client.post(
            "/v1/engine/roadmap",
            json={
                "subject_uid": roadmap.kb_subject_uid,
                "current_progress": user_progress,
                "user_skills": await _get_user_skills(db, user_id),
                "focus_topic_uid": completed_node.kb_topic_uid,  # Фокус на завершенной теме
                "user_theta": user_theta,
                "limit": 5  # Запросить 5 новых рекомендаций
            }
        )

        new_recommendations = response.get('nodes', [])

        # 5. Стратегия обновления:
        #    - Первый узел после completed должен быть available
        #    - Остальные locked
        #    - Если узел уже существует - обновить description и reasons
        #    - Если новый - создать

        next_order = completed_node.order_index + 1

        for i, rec in enumerate(new_recommendations[:3]):  # Обновить только 3 следующих
            target_order = next_order + i

            # Найти существующий узел с этим order_index
            existing_node = await db.query(RoadmapNode).filter(
                RoadmapNode.roadmap_id == roadmap_id,
                RoadmapNode.order_index == target_order
            ).first()

            if existing_node:
                # Обновить существующий узел
                existing_node.title = rec['title']
                existing_node.description = rec['description']
                existing_node.kb_topic_uid = rec['topic_uid']

                # Первый узел после completed → available
                if i == 0:
                    existing_node.status = 'available'

                await db.commit()
                logger.info(f"Updated node {existing_node.id} at order {target_order}")

            else:
                # Создать новый узел
                new_node = RoadmapNode(
                    roadmap_id=roadmap.id,
                    order_index=target_order,
                    kb_topic_uid=rec['topic_uid'],
                    title=rec['title'],
                    description=rec['description'],
                    status='available' if i == 0 else 'locked',
                    max_score=20,
                    current_score=0
                )

                db.add(new_node)
                await db.commit()
                logger.info(f"Created new node {new_node.id} at order {target_order}")

        logger.info(f"Regenerated next nodes for roadmap {roadmap_id}")


async def _get_updated_user_progress(db, user_id: str, user_goal_id: str) -> dict:
    """Получить актуальный прогресс пользователя из SkillMastery"""

    from app.api.kb_integration.models import SkillMastery

    masteries = await db.query(SkillMastery).filter(
        SkillMastery.user_id == user_id,
        SkillMastery.user_goal_id == user_goal_id
    ).all()

    return {
        m.kb_skill_uid: m.mastery_level / 100.0
        for m in masteries
    }


async def _get_user_theta(db, user_id: str, subject_uid: str) -> float:
    """Получить последний theta пользователя из AssessmentAttempt"""

    from app.core.postgres.models import AssessmentAttempt

    latest = await db.query(AssessmentAttempt).filter(
        AssessmentAttempt.user_id == user_id,
        AssessmentAttempt.status == 'completed'
    ).order_by(AssessmentAttempt.submitted_at.desc()).first()

    if latest and latest.analytics:
        return latest.analytics.get('theta', 0.0)

    return 0.0


async def _get_user_skills(db, user_id: str) -> dict:
    """Получить приоритетные навыки пользователя"""

    # Из UserGoal.target_skills или из SkillMastery
    # Для простоты - вернуть пустой dict
    return {}
```

#### Конфигурация Celery

**Файл: `backend/app/core/celery_app.py` (если нет - создать)**

```python
from celery import Celery

celery_app = Celery(
    'studyninja',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

celery_app.autodiscover_tasks(['app.tasks'])
```

---

## Итоговый чеклист реализации

### Задача 1: Синхронизация вопросов и визуализации
- [ ] Создать `question_visual_sync.py` в KnowledgeBaseAI
- [ ] Добавить unit-тесты
- [ ] Обновить `engine.py`
- [ ] Feature flag для A/B тестирования
- [ ] Мониторинг sync validation errors

### Задача 2: IRT адаптивное тестирование
- [ ] Создать `irt_assessment.py` в KnowledgeBaseAI
- [ ] Обновить assessment endpoints
- [ ] Добавить `scipy` в requirements
- [ ] Калибровка IRT параметров на пилотных данных
- [ ] A/B тестирование (старая vs IRT система)

### Задача 3: Гибридные рекомендации roadmap
- [ ] Создать `hybrid_roadmap.py` в KnowledgeBaseAI
- [ ] Интеграция embeddings (OpenAI API)
- [ ] Обновить roadmap endpoint
- [ ] Настроить Redis кэширование embeddings
- [ ] Тестирование качества рекомендаций

### Задача 4: Визуализация микро-уроков
- [ ] Расширить `adaptive_engine.py` в StudyNinja
- [ ] Создать endpoint `/v1/graph/generate_visualization` в KB
- [ ] Обновить структуру payload микро-урока
- [ ] Тестирование генерации визуализации

### Задача 5: Система прогресса
- [ ] Создать `test_progress_system.py`
- [ ] Реализовать атомарные обновления прогресса
- [ ] Добавить логирование событий прогресса
- [ ] End-to-end тестирование flow

### Задача 6: Адаптивная roadmap
- [ ] Создать `adaptive_roadmap.py` task в StudyNinja
- [ ] Настроить Celery для фоновых задач
- [ ] Интеграция с lesson completion flow
- [ ] Мониторинг регенераций roadmap

---

## Метрики успеха

| Задача | Метрика | Целевое значение |
|--------|---------|------------------|
| 1. Синхронизация | Sync validation error rate | < 2% |
| 2. IRT тестирование | Средняя длина теста | < 12 вопросов |
| 2. IRT тестирование | Reliability (avg) | > 0.80 |
| 3. Roadmap релевантность | User satisfaction rating | > 4.0/5.0 |
| 3. Roadmap релевантность | Completion rate узлов | > 70% |
| 4. Визуализация уроков | Visual generation success rate | > 95% |
| 5. Система прогресса | Progress calculation accuracy | 100% |
| 6. Адаптивная roadmap | Regeneration latency | < 5 сек |

