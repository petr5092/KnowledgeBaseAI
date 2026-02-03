# Техническая спецификация: Улучшение LMS интеграции KnowledgeBaseAI + StudyNinja

**Дата:** 2026-02-03
**Версия:** 1.0
**Статус:** Implementation Ready

---

## Архитектура системы

### KnowledgeBaseAI (`/root/KnowledgeBaseAI`)
- **Роль**: Stateless-сервис работы с графом знаний Neo4j
- **Функции**: Генерация вопросов, адаптивное тестирование, дорожные карты, аналитика
- **API**: REST endpoints для внешних LMS
- **Развертывание**: Текущий продакшн сервер, ветка `feat-lms-integration`

### StudyNinja (`/root/StudyNinja-API`)
- **Роль**: LMS система, клиент KnowledgeBaseAI
- **Функции**: Генерация микро-уроков, управление прогрессом, UI/UX обучения
- **API Client**: `kb_integration/client.py` для взаимодействия с KB
- **Развертывание**: Отдельный сервер, ветка `latest`

---

## Задача 1: Синхронизация генерации вопросов и визуализации

### Текущая проблема

**KnowledgeBaseAI (`engine.py:851-1222`)**:
- Генерация вопроса и визуализации происходит в одном LLM вызове
- Проверка консистентности через regex после генерации
- Retry-логика (2 попытки) не всегда помогает
- Нет гарантии соответствия меток в тексте и визуализации

### Решение: Двухэтапная генерация с предварительным планированием

#### Изменения в KnowledgeBaseAI

**Файл 1: `backend/app/services/question_visual_sync.py` (создать новый)**

```python
"""
Сервис синхронизированной генерации вопросов и визуализации
"""

from typing import Optional, List, Tuple
from pydantic import BaseModel, Field
import re
import logging
from app.services.openai_helpers import openai_chat_async
from app.services.visualization.geometry import GeometryEngine

logger = logging.getLogger(__name__)


class VisualizationSpec(BaseModel):
    """Спецификация визуализации, созданная ДО генерации вопроса"""
    required: bool
    shapes: List[dict] = Field(default_factory=list)
    labels: List[str] = Field(default_factory=list)
    coordinate_system: str = "cartesian"
    canvas_bounds: Tuple[float, float, float, float] = (0.0, 0.0, 10.0, 10.0)


class SyncedQuestion(BaseModel):
    """Вопрос с синхронизированной визуализацией"""
    question_uid: str
    topic_uid: str
    question_text: str
    question_type: str  # single_choice, numeric, free_text, boolean
    options: List[dict] = Field(default_factory=list)
    correct_answer: any
    difficulty: int = 5
    is_visual: bool = False
    visualization_data: Optional[dict] = None
    visual_references: List[str] = Field(default_factory=list)


class QuestionVisualSyncService:
    """Сервис двухэтапной генерации вопросов с визуализацией"""

    # Ключевые слова для определения визуальных тем
    VISUAL_KEYWORDS_RU = [
        'геометр', 'треугольн', 'график', 'функц', 'окружн',
        'угл', 'шар', 'конус', 'цилиндр', 'вектор', 'координат',
        'ось', 'плоскост', 'прямая', 'отрезок', 'площад', 'диаграмм'
    ]

    VISUAL_KEYWORDS_EN = [
        'geometry', 'triangle', 'circle', 'graph', 'function',
        'chart', 'angle', 'sphere', 'cone', 'cylinder', 'vector',
        'coordinate', 'axis', 'plane', 'line', 'segment', 'area', 'diagram'
    ]

    @staticmethod
    async def generate_synced_question(
        topic_context: dict,
        difficulty: int = 5,
        force_visual: bool = False
    ) -> SyncedQuestion:
        """
        Основной метод двухэтапной генерации

        Алгоритм:
        1. Анализ темы и решение о необходимости визуализации
        2. ЭТАП 1: Генерация структуры визуализации (если нужна)
        3. ЭТАП 2: Генерация вопроса с привязкой к визуализации
        4. Валидация синхронизации
        5. Retry с явными исправлениями (если нужно)
        """

        # Определить необходимость визуализации
        needs_visual = force_visual or QuestionVisualSyncService._should_use_visualization(
            topic_context
        )

        # ЭТАП 1: Планирование визуализации
        visual_spec = None
        if needs_visual:
            visual_spec = await QuestionVisualSyncService._plan_visualization(
                topic_context
            )

        # ЭТАП 2: Генерация вопроса с учетом визуализации
        question = await QuestionVisualSyncService._generate_question_with_visual(
            topic_context=topic_context,
            visual_spec=visual_spec,
            difficulty=difficulty
        )

        # Валидация синхронизации
        validation = QuestionVisualSyncService._validate_sync(question, visual_spec)

        if not validation['is_valid']:
            logger.warning(f"Question-visual sync validation failed: {validation['errors']}")

            # Одна попытка исправления
            question = await QuestionVisualSyncService._regenerate_with_fixes(
                topic_context, visual_spec, validation['errors'], difficulty
            )

            # Финальная проверка
            final_validation = QuestionVisualSyncService._validate_sync(question, visual_spec)
            if not final_validation['is_valid']:
                logger.error(f"Failed to fix sync issues: {final_validation['errors']}")

        return question

    @staticmethod
    def _should_use_visualization(topic_context: dict) -> bool:
        """Определение необходимости визуализации на основе контекста темы"""

        text = (
            topic_context.get('title', '') + ' ' +
            topic_context.get('description', '') + ' ' +
            ' '.join(topic_context.get('prerequisites', []))
        ).lower()

        return any(
            kw in text
            for kw in (QuestionVisualSyncService.VISUAL_KEYWORDS_RU +
                      QuestionVisualSyncService.VISUAL_KEYWORDS_EN)
        )

    @staticmethod
    async def _plan_visualization(topic_context: dict) -> VisualizationSpec:
        """
        ЭТАП 1: Планирование визуализации ДО генерации вопроса

        Создает структуру визуализации с метками, которые будут
        использованы в тексте вопроса
        """

        prompt = f"""Создай структуру визуализации для математической темы.

ТЕМА: {topic_context['title']}
ОПИСАНИЕ: {topic_context.get('description', '')}

ТРЕБОВАНИЯ:
1. Определи тип визуализации (график, геометрическая фигура, диаграмма)
2. Создай 1-3 объекта с уникальными метками
3. Метки должны быть простыми: A, B, C или "точка1", "прямая1"
4. Координаты в диапазоне [0, 10]
5. Система координат: cartesian (x,y) или polar (r,θ)

ФОРМАТ JSON:
{{
    "coordinate_system": "cartesian",
    "shapes": [
        {{
            "type": "point|line|circle|polygon|curve",
            "label": "A",
            "points": [{{"x": 2.5, "y": 3.0}}],
            "style": {{"color": "blue", "width": 2}}
        }}
    ],
    "labels": ["A", "B", "C"]
}}

ВАЖНО: Каждый объект ОБЯЗАТЕЛЬНО должен иметь уникальную метку!
"""

        response = await openai_chat_async(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            model="gpt-4o-mini",
            response_format={"type": "json_object"}
        )

        import json
        visual_data = json.loads(response)

        # Нормализация координат сразу через GeometryEngine
        normalized_shapes = GeometryEngine.normalize(visual_data['shapes'])

        return VisualizationSpec(
            required=True,
            shapes=normalized_shapes,
            labels=visual_data.get('labels', []),
            coordinate_system=visual_data.get('coordinate_system', 'cartesian')
        )

    @staticmethod
    async def _generate_question_with_visual(
        topic_context: dict,
        visual_spec: Optional[VisualizationSpec],
        difficulty: int
    ) -> SyncedQuestion:
        """
        ЭТАП 2: Генерация вопроса с привязкой к существующей визуализации

        LLM получает ГОТОВУЮ структуру визуализации и должен использовать
        только существующие метки
        """

        # Подготовка контекста визуализации для LLM
        visual_context = ""
        if visual_spec and visual_spec.required:
            labels_str = ', '.join(visual_spec.labels)
            shapes_desc = '\n'.join([
                f"- {s.get('label', '?')}: {s.get('type', 'объект')}"
                for s in visual_spec.shapes
            ])

            visual_context = f"""
ВИЗУАЛИЗАЦИЯ СОЗДАНА:
- Доступные метки: {labels_str}
- Объекты:
{shapes_desc}

ОБЯЗАТЕЛЬНО:
- Используй ТОЛЬКО эти метки: {labels_str}
- НЕ создавай новые метки
- Ссылайся на объекты визуализации в тексте вопроса
"""

        difficulty_desc = {
            1: "очень простой",
            2: "простой",
            3: "базовый",
            4: "средний",
            5: "стандартный",
            6: "повышенный",
            7: "сложный",
            8: "высокий",
            9: "очень сложный",
            10: "экспертный"
        }.get(difficulty, "стандартный")

        prompt = f"""Сгенерируй вопрос по теме: {topic_context['title']}

КОНТЕКСТ:
{topic_context.get('description', '')}

СЛОЖНОСТЬ: {difficulty}/10 ({difficulty_desc})

{visual_context}

ТРЕБОВАНИЯ:
1. Тип вопроса: single_choice (4 варианта), numeric, free_text, или boolean
2. {"ОБЯЗАТЕЛЬНО используй метки визуализации в тексте" if visual_spec else "НЕ используй визуализацию"}
3. Точный правильный ответ
4. Соответствие сложности {difficulty}/10

ФОРМАТ JSON:
{{
    "question_text": "Текст вопроса...",
    "question_type": "single_choice",
    "options": [
        {{"uid": "opt1", "text": "Вариант 1"}},
        {{"uid": "opt2", "text": "Вариант 2"}},
        {{"uid": "opt3", "text": "Вариант 3"}},
        {{"uid": "opt4", "text": "Вариант 4"}}
    ],
    "correct_answer": "opt1",
    "visual_references": ["A", "B"]
}}

Для numeric/free_text/boolean: поле options должно быть пустым массивом []
"""

        response = await openai_chat_async(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            model="gpt-4o-mini",
            response_format={"type": "json_object"}
        )

        import json
        import uuid
        question_data = json.loads(response)

        return SyncedQuestion(
            question_uid=f"Q-{topic_context['uid']}-{uuid.uuid4().hex[:8]}",
            topic_uid=topic_context['uid'],
            question_text=question_data['question_text'],
            question_type=question_data['question_type'],
            options=question_data.get('options', []),
            correct_answer=question_data['correct_answer'],
            difficulty=difficulty,
            is_visual=visual_spec is not None,
            visualization_data={
                "shapes": visual_spec.shapes,
                "labels": visual_spec.labels,
                "coordinate_system": visual_spec.coordinate_system
            } if visual_spec else None,
            visual_references=question_data.get('visual_references', [])
        )

    @staticmethod
    def _validate_sync(
        question: SyncedQuestion,
        visual_spec: Optional[VisualizationSpec]
    ) -> dict:
        """
        Валидация синхронизации вопроса и визуализации

        Проверки:
        1. Если визуализация есть - текст должен содержать ссылки
        2. Если визуализации нет - текст НЕ должен упоминать визуальные элементы
        3. Все упомянутые метки должны существовать
        """

        errors = []
        text = question.question_text.lower()

        # Паттерны для поиска визуальных ссылок
        visual_ref_patterns = [
            r'\b(точк[аеуи]|отрезо[кмв]|прям[аяую]|окружност[ьию])\s+([A-ZА-Я])\b',
            r'\b(на\s+рисунк|на\s+граф|на\s+черт|изображен|показан)',
            r'\b(triangle|circle|point|line)\s+([A-Z])\b',
        ]

        has_visual_refs = any(
            re.search(pattern, text, re.IGNORECASE | re.UNICODE)
            for pattern in visual_ref_patterns
        )

        # Проверка 1: Визуализация создана, но не используется
        if visual_spec and visual_spec.required and not has_visual_refs:
            errors.append("Визуализация создана, но вопрос не ссылается на объекты")

        # Проверка 2: Визуализации нет, но текст ссылается
        if not visual_spec and has_visual_refs:
            errors.append("Вопрос содержит визуальные ссылки без визуализации")

        # Проверка 3: Все метки существуют
        if visual_spec and visual_spec.required:
            mentioned = set(question.visual_references)
            available = set(visual_spec.labels)

            invalid = mentioned - available
            if invalid:
                errors.append(f"Упомянуты несуществующие метки: {invalid}")

        return {
            'is_valid': len(errors) == 0,
            'errors': errors
        }

    @staticmethod
    async def _regenerate_with_fixes(
        topic_context: dict,
        visual_spec: Optional[VisualizationSpec],
        errors: List[str],
        difficulty: int
    ) -> SyncedQuestion:
        """Регенерация вопроса с явным указанием на ошибки"""

        errors_text = '\n'.join([f"- {err}" for err in errors])

        prompt = f"""ИСПРАВЛЕНИЕ ВОПРОСА - предыдущая версия содержала ошибки:

ОШИБКИ:
{errors_text}

Сгенерируй вопрос заново с учетом этих ошибок.

ТЕМА: {topic_context['title']}
{topic_context.get('description', '')}

{"ИСПОЛЬЗУЙ ТОЛЬКО эти метки: " + ', '.join(visual_spec.labels) if visual_spec else "НЕ используй визуализацию"}

ФОРМАТ JSON: (такой же как раньше)
{{
    "question_text": "...",
    "question_type": "single_choice",
    "options": [...],
    "correct_answer": "...",
    "visual_references": [...]
}}
"""

        response = await openai_chat_async(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            model="gpt-4o-mini",
            response_format={"type": "json_object"}
        )

        import json
        import uuid
        question_data = json.loads(response)

        return SyncedQuestion(
            question_uid=f"Q-{topic_context['uid']}-{uuid.uuid4().hex[:8]}",
            topic_uid=topic_context['uid'],
            question_text=question_data['question_text'],
            question_type=question_data['question_type'],
            options=question_data.get('options', []),
            correct_answer=question_data['correct_answer'],
            difficulty=difficulty,
            is_visual=visual_spec is not None,
            visualization_data={
                "shapes": visual_spec.shapes,
                "labels": visual_spec.labels,
                "coordinate_system": visual_spec.coordinate_system
            } if visual_spec else None,
            visual_references=question_data.get('visual_references', [])
        )
```

**Файл 2: Модификация `backend/app/api/engine.py` (строки 851-1222)**

```python
# backend/app/api/engine.py

from app.services.question_visual_sync import QuestionVisualSyncService, SyncedQuestion

async def _generate_question_llm(
    topic_uid: str,
    neo4j_repo,
    difficulty: Optional[int] = None,
    force_visual: bool = False
) -> dict:
    """
    ОБНОВЛЕНО: Использование нового сервиса синхронизации
    """

    # Получить контекст темы из Neo4j
    topic_context = await _get_topic_context_from_neo4j(topic_uid, neo4j_repo)

    if not topic_context:
        raise ValueError(f"Topic {topic_uid} not found")

    # НОВОЕ: Синхронизированная генерация через сервис
    synced_question = await QuestionVisualSyncService.generate_synced_question(
        topic_context=topic_context,
        difficulty=difficulty or 5,
        force_visual=force_visual
    )

    # Преобразовать в формат API ответа (для обратной совместимости)
    return {
        "question_uid": synced_question.question_uid,
        "topic_uid": synced_question.topic_uid,
        "question_text": synced_question.question_text,
        "question_type": synced_question.question_type,
        "options": synced_question.options,
        "correct_answer": synced_question.correct_answer,
        "difficulty": synced_question.difficulty,
        "is_visual": synced_question.is_visual,
        "visualization_data": synced_question.visualization_data
    }


async def _get_topic_context_from_neo4j(topic_uid: str, neo4j_repo) -> dict:
    """
    Загрузка контекста темы для генерации вопроса

    Возвращает:
    {
        "uid": "TOPIC-...",
        "title": "Название темы",
        "description": "Описание",
        "prerequisites": ["TOPIC-1", "TOPIC-2"],
        "subject": "Математика",
        "skills": ["SKILL-1", "SKILL-2"]
    }
    """

    query = """
    MATCH (t:Topic {uid: $topic_uid})
    OPTIONAL MATCH (t)-[:BELONGS_TO*]->(subj:Subject)
    OPTIONAL MATCH (t)<-[:PREREQ]-(prereq:Topic)
    OPTIONAL MATCH (t)-[:REQUIRES_SKILL]->(skill:Skill)
    RETURN
        t.uid as uid,
        t.title as title,
        t.description as description,
        subj.title as subject,
        COLLECT(DISTINCT prereq.title) as prerequisites,
        COLLECT(DISTINCT skill.title) as skills
    """

    result = await neo4j_repo.run_query(query, {"topic_uid": topic_uid})

    if not result:
        return None

    record = result[0]
    return {
        "uid": record['uid'],
        "title": record['title'],
        "description": record.get('description', ''),
        "subject": record.get('subject', ''),
        "prerequisites": record.get('prerequisites', []),
        "skills": record.get('skills', [])
    }
```

#### Тестирование

**Файл: `backend/tests/test_question_visual_sync.py` (создать новый)**

```python
import pytest
from app.services.question_visual_sync import QuestionVisualSyncService, VisualizationSpec


@pytest.mark.asyncio
async def test_visual_detection():
    """Тест определения необходимости визуализации"""

    # Геометрическая тема - должна требовать визуализацию
    context_geo = {
        "uid": "TOPIC-1",
        "title": "Треугольники и их свойства",
        "description": "Изучение углов треугольника"
    }
    assert QuestionVisualSyncService._should_use_visualization(context_geo) == True

    # Алгебраическая тема - не должна требовать
    context_alg = {
        "uid": "TOPIC-2",
        "title": "Решение линейных уравнений",
        "description": "Методы решения уравнений первой степени"
    }
    assert QuestionVisualSyncService._should_use_visualization(context_alg) == False


@pytest.mark.asyncio
async def test_synced_generation_without_visual():
    """Тест генерации вопроса без визуализации"""

    context = {
        "uid": "TOPIC-ALGEBRA-001",
        "title": "Квадратные уравнения",
        "description": "Решение уравнений вида ax²+bx+c=0",
        "prerequisites": [],
        "subject": "Алгебра",
        "skills": []
    }

    question = await QuestionVisualSyncService.generate_synced_question(
        topic_context=context,
        difficulty=5,
        force_visual=False
    )

    assert question.is_visual == False
    assert question.visualization_data is None
    assert len(question.question_text) > 10


@pytest.mark.asyncio
async def test_synced_generation_with_visual():
    """Тест генерации вопроса с визуализацией"""

    context = {
        "uid": "TOPIC-GEOMETRY-001",
        "title": "Прямоугольный треугольник",
        "description": "Свойства прямоугольного треугольника",
        "prerequisites": [],
        "subject": "Геометрия",
        "skills": []
    }

    question = await QuestionVisualSyncService.generate_synced_question(
        topic_context=context,
        difficulty=5,
        force_visual=True
    )

    assert question.is_visual == True
    assert question.visualization_data is not None
    assert len(question.visualization_data['labels']) > 0

    # Проверка, что визуализация упоминается в тексте
    validation = QuestionVisualSyncService._validate_sync(
        question,
        VisualizationSpec(
            required=True,
            shapes=question.visualization_data['shapes'],
            labels=question.visualization_data['labels']
        )
    )

    assert validation['is_valid'] == True


@pytest.mark.asyncio
async def test_validation_catches_invalid_labels():
    """Тест валидации несуществующих меток"""

    from app.services.question_visual_sync import SyncedQuestion

    # Вопрос упоминает метку D, которой нет в визуализации
    question = SyncedQuestion(
        question_uid="Q-TEST-001",
        topic_uid="TOPIC-1",
        question_text="Найдите длину отрезка D",
        question_type="numeric",
        correct_answer=5.0,
        is_visual=True,
        visual_references=["A", "D"]  # D не существует
    )

    visual_spec = VisualizationSpec(
        required=True,
        labels=["A", "B", "C"]  # Только A, B, C
    )

    validation = QuestionVisualSyncService._validate_sync(question, visual_spec)

    assert validation['is_valid'] == False
    assert any('D' in err for err in validation['errors'])
```

#### Миграция и развертывание

**План действий:**

1. **Создать новый сервис** `question_visual_sync.py` в KnowledgeBaseAI
2. **Добавить unit-тесты** и прогнать: `pytest backend/tests/test_question_visual_sync.py`
3. **Обновить** `engine.py` для использования нового сервиса
4. **Feature flag**: Добавить env переменную `USE_SYNCED_VISUAL_GENERATION=true/false`
5. **A/B тестирование**:
   - 20% трафика через новую систему (1 неделя)
   - Метрики: sync_errors_rate, generation_latency, user_satisfaction
   - Если успешно: увеличить до 50% (1 неделя), затем 100%
6. **Мониторинг**: Логировать все sync validation errors

**Метрики успеха:**
- Sync validation error rate < 2% (текущий ~15-20%)
- Generation latency < 4 сек (2 LLM вызова)
- User complaint rate по "несоответствующей визуализации" → 0

---

## Задача 2: Адаптивное тестирование с объективной оценкой освоенности

### Текущая проблема

**KnowledgeBaseAI (`engine.py:1272-1691`)**:
- Простая линейная адаптация сложности: +1 если правильно, -1 если нет
- Критерий завершения: 85% confidence ИЛИ 20 вопросов
- Финальный скор: простое взвешенное среднее по сложности
- Нет статистической оценки надежности результата

**StudyNinja (`service.py`, `models.py`)**:
- Использует `percentage` из KB API как есть
- Не хватает детальной аналитики по пробелам знаний
- Нет измерения confidence interval

### Решение: Item Response Theory (IRT) для точной оценки знаний

#### Изменения в KnowledgeBaseAI

**Файл 1: `backend/app/services/irt_assessment.py` (создать новый)**

```python
"""
Адаптивное тестирование на основе Item Response Theory (IRT)
Использует 2-параметрическую модель (2PL) для оценки знаний
"""

from typing import List, Optional, Dict, Tuple
from pydantic import BaseModel, Field
import math
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class IRTParameters:
    """IRT параметры вопроса"""
    difficulty: float  # b: сложность (-3 to +3, среднее = 0)
    discrimination: float  # a: различительная способность (0.5 to 2.5)
    guessing: float = 0.0  # c: для 2PL модели всегда 0


class KnowledgeState(BaseModel):
    """Состояние знаний учащегося"""
    theta: float  # Уровень способностей (-3 to +3)
    theta_se: float  # Стандартная ошибка оценки
    confidence: float  # Уверенность в оценке (0-1)
    mastery_probability: float  # Вероятность освоения темы (0-1)


class ResponseRecord(BaseModel):
    """Запись ответа на вопрос"""
    question_uid: str
    is_correct: bool
    difficulty: float
    discrimination: float
    response_time_ms: Optional[int] = None


class AssessmentSession(BaseModel):
    """Сессия адаптивного тестирования с IRT"""
    topic_uid: str
    user_id: str
    responses: List[ResponseRecord] = Field(default_factory=list)
    knowledge_state: KnowledgeState
    questions_asked: int = 0
    is_terminated: bool = False
    termination_reason: Optional[str] = None


class IRTAssessmentEngine:
    """Движок адаптивного тестирования на основе IRT"""

    # Константы
    D = 1.702  # Scaling factor для логистической функции

    # Критерии завершения
    MIN_QUESTIONS = 6
    MAX_QUESTIONS = 20
    TARGET_SE = 0.35  # Целевая стандартная ошибка
    MIN_INFORMATION = 12.0  # Минимальная накопленная информация

    @staticmethod
    def initialize_session(topic_uid: str, user_id: str, prior_theta: float = 0.0) -> AssessmentSession:
        """
        Инициализация сессии тестирования

        Args:
            prior_theta: Априорная оценка theta (из предыдущих тестов)
        """
        return AssessmentSession(
            topic_uid=topic_uid,
            user_id=user_id,
            knowledge_state=KnowledgeState(
                theta=prior_theta,
                theta_se=1.0,  # Начальная высокая неопределенность
                confidence=0.0,
                mastery_probability=0.5
            )
        )

    @staticmethod
    def probability_correct(
        theta: float,
        difficulty: float,
        discrimination: float
    ) -> float:
        """
        2-параметрическая логистическая модель (2PL)

        P(correct | theta, b, a) = 1 / (1 + exp(-D * a * (theta - b)))

        где:
        - theta: способности учащегося
        - b: сложность вопроса
        - a: различительная способность
        - D: константа 1.702
        """
        exponent = -IRTAssessmentEngine.D * discrimination * (theta - difficulty)
        return 1.0 / (1.0 + math.exp(exponent))

    @staticmethod
    def fisher_information(
        theta: float,
        difficulty: float,
        discrimination: float
    ) -> float:
        """
        Информация Фишера для 2PL модели

        I(theta) = D² * a² * P(theta) * (1 - P(theta))

        Максимум информации достигается когда theta = b (сложность вопроса)
        """
        P = IRTAssessmentEngine.probability_correct(theta, difficulty, discrimination)
        return (IRTAssessmentEngine.D ** 2) * (discrimination ** 2) * P * (1 - P)

    @staticmethod
    def select_next_question(
        session: AssessmentSession,
        available_questions: List[Dict]
    ) -> Optional[Dict]:
        """
        Выбор следующего вопроса методом Maximum Information

        Алгоритм:
        1. Исключить уже использованные вопросы
        2. Для каждого вопроса вычислить информацию Фишера при текущем theta
        3. Выбрать вопрос с максимальной информацией
        """

        theta = session.knowledge_state.theta
        asked_uids = {r.question_uid for r in session.responses}

        best_question = None
        max_info = -1.0

        for q in available_questions:
            if q['question_uid'] in asked_uids:
                continue

            # Получить/оценить IRT параметры
            irt_params = IRTAssessmentEngine._estimate_irt_parameters(q)

            # Вычислить информацию при текущем theta
            info = IRTAssessmentEngine.fisher_information(
                theta,
                irt_params.difficulty,
                irt_params.discrimination
            )

            if info > max_info:
                max_info = info
                best_question = q

        return best_question

    @staticmethod
    def _estimate_irt_parameters(question: Dict) -> IRTParameters:
        """
        Оценка IRT параметров из метаданных вопроса

        Если параметры откалиброваны - используем их,
        иначе оцениваем из difficulty и типа вопроса
        """

        # Если есть откалиброванные параметры
        if 'irt_difficulty' in question and 'irt_discrimination' in question:
            return IRTParameters(
                difficulty=question['irt_difficulty'],
                discrimination=question['irt_discrimination']
            )

        # Оценка из difficulty (1-10) → IRT scale (-3 to +3)
        raw_diff = question.get('difficulty', 5)
        difficulty = ((raw_diff - 5.5) / 2.0)  # 1→-2.25, 5→-0.25, 10→2.25

        # Оценка discrimination по типу вопроса
        question_type = question.get('question_type', 'single_choice')
        discrimination_map = {
            'single_choice': 1.0,
            'numeric': 1.5,  # Более различительные
            'free_text': 1.2,
            'boolean': 0.7   # Менее различительные
        }
        discrimination = discrimination_map.get(question_type, 1.0)

        return IRTParameters(
            difficulty=difficulty,
            discrimination=discrimination
        )

    @staticmethod
    def update_theta(
        session: AssessmentSession,
        question: Dict,
        is_correct: bool,
        response_time_ms: Optional[int] = None
    ) -> KnowledgeState:
        """
        Обновление оценки theta методом Maximum Likelihood (MLE)

        Использует метод Ньютона-Рафсона для численной оптимизации
        """

        # Добавить ответ в историю
        irt_params = IRTAssessmentEngine._estimate_irt_parameters(question)
        session.responses.append(ResponseRecord(
            question_uid=question['question_uid'],
            is_correct=is_correct,
            difficulty=irt_params.difficulty,
            discrimination=irt_params.discrimination,
            response_time_ms=response_time_ms
        ))

        # MLE оценка theta
        theta_new = IRTAssessmentEngine._estimate_theta_mle(session.responses)

        # Стандартная ошибка = 1 / sqrt(сумма информации)
        total_info = sum(
            IRTAssessmentEngine.fisher_information(
                theta_new,
                r.difficulty,
                r.discrimination
            )
            for r in session.responses
        )

        theta_se = 1.0 / math.sqrt(total_info) if total_info > 0 else 1.0

        # Уверенность: нормализованная обратная SE
        # SE: 1.0 (низкая) → 0.2 (высокая) => confidence: 0 → 1
        confidence = max(0.0, min(1.0, 1.0 - (theta_se / 1.0)))

        # Вероятность освоения: P(theta > threshold)
        # Используем нормальное распределение N(theta, SE)
        # Threshold = 0.5 (выше среднего = освоено)
        mastery_threshold = 0.5
        z_score = (theta_new - mastery_threshold) / theta_se if theta_se > 0 else 0
        mastery_probability = IRTAssessmentEngine._normal_cdf(z_score)

        return KnowledgeState(
            theta=theta_new,
            theta_se=theta_se,
            confidence=confidence,
            mastery_probability=mastery_probability
        )

    @staticmethod
    def _estimate_theta_mle(responses: List[ResponseRecord], max_iter: int = 20) -> float:
        """
        Maximum Likelihood Estimation theta методом Ньютона-Рафсона

        Итеративно максимизируем log-likelihood:
        theta_new = theta_old - L'(theta) / L''(theta)
        """

        theta = 0.0  # Начальная оценка

        for iteration in range(max_iter):
            first_deriv = 0.0  # L'(theta)
            second_deriv = 0.0  # L''(theta)

            for r in responses:
                P = IRTAssessmentEngine.probability_correct(
                    theta, r.difficulty, r.discrimination
                )

                # Защита от численных проблем
                P = max(0.0001, min(0.9999, P))

                # Производные логарифмической правдоподобности
                D_a = IRTAssessmentEngine.D * r.discrimination

                if r.is_correct:
                    first_deriv += D_a * (1 - P)
                    second_deriv -= D_a * D_a * P * (1 - P)
                else:
                    first_deriv -= D_a * P
                    second_deriv -= D_a * D_a * P * (1 - P)

            # Шаг Ньютона-Рафсона
            if abs(second_deriv) > 1e-6:
                theta_new = theta - (first_deriv / second_deriv)
            else:
                break

            # Проверка сходимости
            if abs(theta_new - theta) < 0.001:
                theta = theta_new
                break

            theta = theta_new

        # Зажать в разумных пределах
        return max(-3.0, min(3.0, theta))

    @staticmethod
    def _normal_cdf(z: float) -> float:
        """Кумулятивная функция распределения стандартного нормального распределения"""
        # Приближение через функцию ошибок
        return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))

    @staticmethod
    def check_termination(session: AssessmentSession) -> Tuple[bool, Optional[str]]:
        """
        Проверка критериев завершения

        Критерии (OR логика):
        1. SE <= TARGET_SE (достаточная точность)
        2. MIN_QUESTIONS пройдено И накопленная информация >= MIN_INFORMATION
        3. MAX_QUESTIONS достигнут (жесткий лимит)
        """

        n = len(session.responses)
        se = session.knowledge_state.theta_se

        # Критерий 3: Максимум вопросов
        if n >= IRTAssessmentEngine.MAX_QUESTIONS:
            return True, f"max_questions ({n})"

        # Критерий 1: Достаточная точность
        if se <= IRTAssessmentEngine.TARGET_SE and n >= IRTAssessmentEngine.MIN_QUESTIONS:
            return True, f"target_precision (SE={se:.3f})"

        # Критерий 2: Минимум вопросов + достаточная информация
        if n >= IRTAssessmentEngine.MIN_QUESTIONS:
            total_info = 1.0 / (se ** 2) if se > 0 else 0.0
            if total_info >= IRTAssessmentEngine.MIN_INFORMATION:
                return True, f"sufficient_info (I={total_info:.1f})"

        return False, None

    @staticmethod
    def compute_final_report(session: AssessmentSession) -> Dict:
        """
        Финальный отчет с объективными метриками

        Возвращает:
        - theta_score: 0-100 (нормализованный theta)
        - mastery_level: 0-100 (вероятность освоения)
        - reliability: 0-1 (надежность оценки)
        - confidence_interval_95: (lower, upper) в шкале 0-100
        - achievement_band: категория достижения
        - detailed_analytics: детальная аналитика
        """

        theta = session.knowledge_state.theta
        se = session.knowledge_state.theta_se
        mastery = session.knowledge_state.mastery_probability

        # 1. Нормализация theta (-3, +3) → (0, 100)
        theta_score = ((theta + 3.0) / 6.0) * 100.0
        theta_score = max(0.0, min(100.0, theta_score))

        # 2. Mastery level (процент освоения)
        mastery_level = mastery * 100.0

        # 3. Reliability (надежность)
        max_se = 1.0
        reliability = max(0.0, 1.0 - (se / max_se))

        # 4. 95% confidence interval
        z_95 = 1.96
        ci_lower_theta = theta - z_95 * se
        ci_upper_theta = theta + z_95 * se

        ci_lower = ((ci_lower_theta + 3.0) / 6.0) * 100.0
        ci_upper = ((ci_upper_theta + 3.0) / 6.0) * 100.0

        # 5. Achievement band
        if theta >= 1.5:
            band = "excellent"
        elif theta >= 0.5:
            band = "good"
        elif theta >= -0.5:
            band = "satisfactory"
        else:
            band = "needs_improvement"

        # 6. Детальная аналитика
        correct_count = sum(1 for r in session.responses if r.is_correct)
        total_count = len(session.responses)

        # Анализ по сложности
        difficulty_analysis = {
            "easy": {"correct": 0, "total": 0},
            "medium": {"correct": 0, "total": 0},
            "hard": {"correct": 0, "total": 0}
        }

        for r in session.responses:
            if r.difficulty < -0.5:
                category = "easy"
            elif r.difficulty < 0.5:
                category = "medium"
            else:
                category = "hard"

            difficulty_analysis[category]["total"] += 1
            if r.is_correct:
                difficulty_analysis[category]["correct"] += 1

        return {
            "theta": round(theta, 3),
            "theta_se": round(se, 3),
            "theta_score": round(theta_score, 1),
            "mastery_level": round(mastery_level, 1),
            "reliability": round(reliability, 3),
            "confidence_interval_95": {
                "lower": round(max(0, ci_lower), 1),
                "upper": round(min(100, ci_upper), 1)
            },
            "achievement_band": band,
            "total_questions": total_count,
            "correct_count": correct_count,
            "accuracy_percentage": round((correct_count / total_count * 100), 1) if total_count > 0 else 0,
            "termination_reason": session.termination_reason,
            "difficulty_breakdown": difficulty_analysis,
            "measurement_quality": {
                "standard_error": round(se, 3),
                "information": round(1.0 / (se ** 2), 1) if se > 0 else 0,
                "reliability": round(reliability, 3)
            }
        }
```

**Файл 2: Модификация `backend/app/api/engine.py` (assessment endpoints)**

```python
# backend/app/api/engine.py

from app.services.irt_assessment import (
    IRTAssessmentEngine,
    AssessmentSession,
    IRTParameters
)
from app.config import redis_client
import json


@app.post("/v1/assessment/start")
async def start_irt_assessment(request: StartAssessmentRequest):
    """
    ОБНОВЛЕНО: Запуск IRT-based адаптивного тестирования
    """

    # Получить prior theta из истории пользователя (если есть)
    prior_theta = await _get_user_prior_theta(
        request.user_id,
        request.subject_uid
    )

    # Инициализировать IRT сессию
    session = IRTAssessmentEngine.initialize_session(
        topic_uid=request.topic_uid,
        user_id=request.user_id,
        prior_theta=prior_theta
    )

    # Получить доступные вопросы
    questions = await _load_questions_for_topic(request.topic_uid)

    if not questions:
        raise HTTPException(status_code=404, detail="No questions available")

    # Выбрать первый вопрос (максимальная информация для prior_theta)
    first_question = IRTAssessmentEngine.select_next_question(session, questions)

    # Сохранить сессию в Redis
    session_key = f"irt_session:{request.topic_uid}:{request.user_id}"
    await redis_client.setex(
        session_key,
        86400,  # 24 часа
        session.json()
    )

    return {
        "session_id": session_key,
        "question": first_question,
        "progress": {
            "current": 1,
            "min": IRTAssessmentEngine.MIN_QUESTIONS,
            "max": IRTAssessmentEngine.MAX_QUESTIONS,
            "estimated_remaining": IRTAssessmentEngine.MIN_QUESTIONS - 1
        },
        "current_estimate": {
            "theta": session.knowledge_state.theta,
            "se": session.knowledge_state.theta_se,
            "confidence": session.knowledge_state.confidence,
            "mastery_probability": session.knowledge_state.mastery_probability
        }
    }


@app.post("/v1/assessment/next")
async def next_irt_question(request: NextAssessmentRequest):
    """
    ОБНОВЛЕНО: Обработка ответа и выдача следующего вопроса с IRT
    """

    # Загрузить сессию
    session_key = f"irt_session:{request.topic_uid}:{request.user_id}"
    session_data = await redis_client.get(session_key)

    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")

    session = AssessmentSession.parse_raw(session_data)

    # Найти вопрос
    question = await _get_question_by_uid(request.question_uid)

    # Оценить ответ
    is_correct = _evaluate_answer(
        question,
        request.answer,
        request.answer_type
    )

    # Обновить theta с IRT
    new_knowledge_state = IRTAssessmentEngine.update_theta(
        session,
        question,
        is_correct,
        response_time_ms=request.response_time_ms
    )
    session.knowledge_state = new_knowledge_state
    session.questions_asked = len(session.responses)

    # Проверить критерии завершения
    should_terminate, reason = IRTAssessmentEngine.check_termination(session)

    if should_terminate:
        session.is_terminated = True
        session.termination_reason = reason

        # Финальный отчет
        final_report = IRTAssessmentEngine.compute_final_report(session)

        # Обновить прогресс пользователя
        await _update_user_mastery(
            user_id=request.user_id,
            topic_uid=request.topic_uid,
            mastery_level=final_report['mastery_level'] / 100.0,
            theta=final_report['theta'],
            reliability=final_report['reliability']
        )

        # Сохранить финальную сессию
        await redis_client.setex(session_key, 86400, session.json())

        # Генерировать аналитику через LLM (опционально)
        llm_analytics = await _generate_llm_analytics(session, final_report)

        return {
            "is_finished": True,
            "feedback": is_correct,
            "final_report": final_report,
            "analytics": llm_analytics
        }

    # Выбрать следующий вопрос
    questions = await _load_questions_for_topic(request.topic_uid)
    next_question = IRTAssessmentEngine.select_next_question(session, questions)

    if not next_question:
        # Вопросы закончились - досрочное завершение
        session.is_terminated = True
        session.termination_reason = "no_more_questions"

        final_report = IRTAssessmentEngine.compute_final_report(session)
        await redis_client.setex(session_key, 86400, session.json())

        return {
            "is_finished": True,
            "feedback": is_correct,
            "final_report": final_report
        }

    # Сохранить сессию и вернуть следующий вопрос
    await redis_client.setex(session_key, 86400, session.json())

    # Оценка оставшихся вопросов
    remaining_se = session.knowledge_state.theta_se
    estimated_remaining = max(
        0,
        IRTAssessmentEngine.MIN_QUESTIONS - session.questions_asked
    )

    # Если SE уже близка к цели - можем закончить раньше
    if remaining_se <= IRTAssessmentEngine.TARGET_SE * 1.2:
        estimated_remaining = min(estimated_remaining, 2)

    return {
        "is_finished": False,
        "feedback": is_correct,
        "question": next_question,
        "progress": {
            "current": session.questions_asked + 1,
            "min": IRTAssessmentEngine.MIN_QUESTIONS,
            "max": IRTAssessmentEngine.MAX_QUESTIONS,
            "estimated_remaining": estimated_remaining
        },
        "current_estimate": {
            "theta": session.knowledge_state.theta,
            "se": session.knowledge_state.theta_se,
            "confidence": session.knowledge_state.confidence,
            "mastery_probability": session.knowledge_state.mastery_probability
        }
    }


async def _get_user_prior_theta(user_id: str, subject_uid: str) -> float:
    """
    Получение априорной оценки theta из истории пользователя

    Ищет последний завершенный assessment для этого предмета
    """
    # Query из Neo4j или PostgreSQL истории assessments
    # Для простоты - возвращаем 0.0 (среднее)
    return 0.0


async def _update_user_mastery(
    user_id: str,
    topic_uid: str,
    mastery_level: float,
    theta: float,
    reliability: float
):
    """Обновление мастерства пользователя в Neo4j"""

    from app.services.graph.neo4j_repo import get_driver

    query = """
    MATCH (u:User {id: $user_id}), (t:Topic {uid: $topic_uid})
    MERGE (u)-[m:MASTERY]->(t)
    SET m.level = $mastery_level,
        m.theta = $theta,
        m.reliability = $reliability,
        m.updated_at = datetime()
    RETURN m
    """

    async with get_driver().session() as session:
        await session.run(query, {
            "user_id": user_id,
            "topic_uid": topic_uid,
            "mastery_level": mastery_level,
            "theta": theta,
            "reliability": reliability
        })


async def _generate_llm_analytics(session: AssessmentSession, report: dict) -> dict:
    """
    Генерация детальной аналитики через LLM

    Анализирует паттерны ответов и дает рекомендации
    """

    responses_summary = [
        {
            "difficulty": r.difficulty,
            "is_correct": r.is_correct
        }
        for r in session.responses
    ]

    prompt = f"""Проанализируй результаты тестирования студента.

РЕЗУЛЬТАТЫ:
- Theta (способности): {report['theta']} (IRT scale)
- Масте&#1088;и: {report['mastery_level']}%
- Надежность оценки: {report['reliability']}
- Пройдено вопросов: {report['total_questions']}
- Правильных: {report['correct_count']}

ДЕТАЛИ ПО СЛОЖНОСТИ:
{json.dumps(report['difficulty_breakdown'], indent=2, ensure_ascii=False)}

ПАТТЕРН ОТВЕТОВ:
{json.dumps(responses_summary[:10], indent=2)}

Создай JSON с аналитикой:
{{
    "overall_assessment": "Краткая оценка уровня (1-2 предложения)",
    "strengths": ["Сильная сторона 1", "Сильная сторона 2"],
    "weaknesses": ["Слабая сторона 1", "Слабая сторона 2"],
    "recommendations": [
        "Рекомендация 1",
        "Рекомендация 2"
    ],
    "next_topics": ["TOPIC-UID-1", "TOPIC-UID-2"]
}}
"""

    from app.services.openai_helpers import openai_chat_async

    response = await openai_chat_async(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        model="gpt-4o-mini",
        response_format={"type": "json_object"}
    )

    import json
    return json.loads(response)
```

