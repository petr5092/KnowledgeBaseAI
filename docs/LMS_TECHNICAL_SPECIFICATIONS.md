# Технические спецификации LMS - Инструкции по реализации

**Дата:** 2026-02-03
**Версия:** 1.0
**Статус:** Draft

## Обзор

Данный документ содержит технические инструкции и алгоритмы для реализации 6 ключевых улучшений LMS системы KnowledgeBaseAI.

---

## Задача 1: Синхронизация генерации вопросов и визуализации

### Проблема
Текущая реализация (`engine.py:851-1222`) генерирует вопросы и визуализацию асинхронно, что приводит к:
- Несоответствию текста вопроса и визуального контента
- Ссылкам на несуществующие элементы визуализации
- Retry-логике с 2 попытками, которая не всегда помогает

### Текущая архитектура
```python
# engine.py:851-1222
async def _generate_question_llm(topic_context: dict) -> GeneratedQuestion:
    # 1. Определение необходимости визуализации (автоматически)
    # 2. Генерация вопроса с LLM
    # 3. Проверка консистентности (regex для визуальных ссылок)
    # 4. Retry при несоответствии
```

### Решение: Двухэтапная генерация с промежуточной валидацией

#### Алгоритм реализации

**Шаг 1: Создать новый сервис `backend/app/services/question_visual_sync.py`**

```python
from typing import Optional, Tuple
from pydantic import BaseModel
import re

class VisualizationSpec(BaseModel):
    """Спецификация визуализации перед генерацией вопроса"""
    required: bool
    shapes: list[dict] = []
    labels: list[str] = []
    coordinate_system: str = "cartesian"  # cartesian, polar, 3d
    canvas_size: Tuple[int, int] = (10, 10)

class SyncedQuestionVisual(BaseModel):
    """Синхронизированный вопрос с визуализацией"""
    question_text: str
    question_type: str
    options: list[dict]
    correct_answer: any
    visualization: Optional[VisualizationSpec]
    visual_references: list[str] = []  # Список меток, упомянутых в тексте

class QuestionVisualSyncService:

    @staticmethod
    async def generate_synced_question(
        topic_context: dict,
        force_visual: bool = False
    ) -> SyncedQuestionVisual:
        """
        Двухэтапная синхронизированная генерация

        Этап 1: Планирование визуализации
        Этап 2: Генерация вопроса с привязкой к визуализации
        """

        # === ЭТАП 1: Определение и генерация визуализации ===
        visual_spec = await QuestionVisualSyncService._plan_visualization(
            topic_context, force_visual
        )

        # === ЭТАП 2: Генерация вопроса с учетом визуализации ===
        question = await QuestionVisualSyncService._generate_question_with_visual(
            topic_context, visual_spec
        )

        # === ВАЛИДАЦИЯ: Проверка синхронизации ===
        validation = QuestionVisualSyncService._validate_sync(
            question, visual_spec
        )

        if not validation['is_valid']:
            # Retry с явным указанием на ошибки
            question = await QuestionVisualSyncService._regenerate_with_fixes(
                topic_context, visual_spec, validation['errors']
            )

        return question

    @staticmethod
    async def _plan_visualization(
        topic_context: dict,
        force_visual: bool
    ) -> Optional[VisualizationSpec]:
        """
        Этап 1: Планирование визуализации

        Алгоритм:
        1. Анализ темы на необходимость визуализации
        2. Если нужна - генерация структуры ПЕРЕД вопросом
        3. Нормализация координат сразу
        4. Создание меток для ссылок
        """

        # Проверка на визуальные темы
        visual_keywords_ru = [
            'геометр', 'треугольн', 'график', 'функц', 'окружн',
            'угл', 'шар', 'конус', 'цилиндр', 'вектор', 'координат',
            'ось', 'плоскост', 'прямая', 'отрезок', 'площад'
        ]
        visual_keywords_en = [
            'geometry', 'triangle', 'circle', 'graph', 'function',
            'chart', 'angle', 'sphere', 'cone', 'cylinder', 'vector'
        ]

        topic_text = (
            topic_context.get('title', '') + ' ' +
            topic_context.get('description', '')
        ).lower()

        needs_visual = force_visual or any(
            kw in topic_text for kw in (visual_keywords_ru + visual_keywords_en)
        )

        if not needs_visual:
            return None

        # Генерация структуры визуализации через LLM
        prompt = f"""Создай структуру визуализации для темы: {topic_context['title']}

Тема: {topic_context.get('description', '')}
Пререквизиты: {', '.join(topic_context.get('prerequisites', []))}

Требования:
1. Определи тип визуализации (график функции, геометрическая фигура, координатная плоскость)
2. Создай 1-3 объекта/формы
3. Присвой каждому объекту УНИКАЛЬНУЮ метку (A, B, C или "точка1", "прямая1")
4. Сгенерируй координаты в диапазоне [0, 10]
5. Используй систему координат: cartesian/polar/3d

Формат JSON:
{{
    "coordinate_system": "cartesian",
    "shapes": [
        {{
            "type": "point|line|circle|polygon",
            "label": "A",  // ОБЯЗАТЕЛЬНАЯ уникальная метка
            "points": [{{"x": 2.0, "y": 3.0}}],
            "style": {{"color": "blue", "width": 2}}
        }}
    ],
    "labels": ["A", "B", "C"]  // Список всех меток для проверки
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
        visual_data = json.loads(response)

        # Нормализация координат СРАЗУ
        from app.services.visualization.geometry import GeometryEngine
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
        visual_spec: Optional[VisualizationSpec]
    ) -> SyncedQuestionVisual:
        """
        Этап 2: Генерация вопроса с учетом визуализации

        Алгоритм:
        1. Передать в LLM структуру визуализации (если есть)
        2. Требовать использования ТОЛЬКО существующих меток
        3. Генерация вопроса с явными ссылками
        """

        visual_context = ""
        if visual_spec and visual_spec.required:
            labels_list = ', '.join(visual_spec.labels)
            visual_context = f"""
ДОСТУПНЫЕ ВИЗУАЛЬНЫЕ ЭЛЕМЕНТЫ:
- Метки: {labels_list}
- Система координат: {visual_spec.coordinate_system}
- Объекты: {len(visual_spec.shapes)} шт.

ВАЖНО: Используй ТОЛЬКО эти метки при ссылках на визуализацию!
"""

        prompt = f"""Сгенерируй вопрос по теме: {topic_context['title']}

Контекст темы:
{topic_context.get('description', '')}

{visual_context}

Требования:
1. Тип вопроса: single_choice, numeric, free_text, boolean
2. {"Обязательно используй визуальные элементы" if visual_spec else "НЕ используй визуализацию"}
3. 4 варианта ответа для single_choice
4. Точный правильный ответ
5. Если ссылаешься на визуализацию - используй ТОЛЬКО метки: {visual_spec.labels if visual_spec else "нет"}

Формат JSON:
{{
    "question_text": "...",
    "question_type": "single_choice",
    "options": [{{"uid": "opt1", "text": "..."}}],
    "correct_answer": "opt1",
    "visual_references": ["A", "B"]  // Список использованных меток
}}
"""

        from app.services.openai_helpers import openai_chat_async

        response = await openai_chat_async(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            model="gpt-4o-mini",
            response_format={"type": "json_object"}
        )

        import json
        question_data = json.loads(response)

        return SyncedQuestionVisual(
            question_text=question_data['question_text'],
            question_type=question_data['question_type'],
            options=question_data.get('options', []),
            correct_answer=question_data['correct_answer'],
            visualization=visual_spec,
            visual_references=question_data.get('visual_references', [])
        )

    @staticmethod
    def _validate_sync(
        question: SyncedQuestionVisual,
        visual_spec: Optional[VisualizationSpec]
    ) -> dict:
        """
        Валидация синхронизации вопроса и визуализации

        Проверки:
        1. Если визуализация есть - текст должен ссылаться на метки
        2. Если визуализации нет - текст НЕ должен упоминать визуальные элементы
        3. Все ссылки в тексте должны существовать в визуализации
        """

        errors = []

        # Regex для поиска визуальных ссылок
        visual_ref_patterns = [
            r'\b(точк[аеуи]|triangle|circle|line)\s+([A-Z]|[А-Я])\b',
            r'\b(на\s+рисунк|на\s+граф|на\s+черт|in\s+figure|in\s+diagram)',
            r'\b(изображен|показан|нарисован|depicted|shown)\b'
        ]

        text = question.question_text.lower()
        has_visual_refs = any(
            re.search(pattern, text, re.IGNORECASE)
            for pattern in visual_ref_patterns
        )

        # Проверка 1: Визуализация есть, но текст не ссылается
        if visual_spec and visual_spec.required and not has_visual_refs:
            errors.append("Визуализация создана, но вопрос не ссылается на неё")

        # Проверка 2: Визуализации нет, но текст ссылается
        if not visual_spec and has_visual_refs:
            errors.append("Вопрос ссылается на визуализацию, которой нет")

        # Проверка 3: Все упомянутые метки существуют
        if visual_spec and visual_spec.required:
            mentioned_labels = set(question.visual_references)
            available_labels = set(visual_spec.labels)

            invalid_labels = mentioned_labels - available_labels
            if invalid_labels:
                errors.append(
                    f"Упомянуты несуществующие метки: {invalid_labels}"
                )

        return {
            'is_valid': len(errors) == 0,
            'errors': errors
        }

    @staticmethod
    async def _regenerate_with_fixes(
        topic_context: dict,
        visual_spec: Optional[VisualizationSpec],
        errors: list[str]
    ) -> SyncedQuestionVisual:
        """
        Регенерация вопроса с исправлением ошибок

        Алгоритм:
        1. Создать prompt с явным указанием ошибок
        2. Одна попытка исправления
        3. Если снова ошибка - логировать и вернуть как есть
        """

        error_context = "\n".join([f"- {err}" for err in errors])

        prompt = f"""ИСПРАВЛЕНИЕ: Предыдущая генерация содержала ошибки:
{error_context}

Сгенерируй вопрос заново с учетом требований:

Тема: {topic_context['title']}
{topic_context.get('description', '')}

{"ОБЯЗАТЕЛЬНО используй метки: " + ', '.join(visual_spec.labels) if visual_spec else "НЕ используй визуализацию"}

Формат JSON: (тот же что и раньше)
"""

        from app.services.openai_helpers import openai_chat_async
        import json

        response = await openai_chat_async(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            model="gpt-4o-mini",
            response_format={"type": "json_object"}
        )

        question_data = json.loads(response)

        regenerated = SyncedQuestionVisual(
            question_text=question_data['question_text'],
            question_type=question_data['question_type'],
            options=question_data.get('options', []),
            correct_answer=question_data['correct_answer'],
            visualization=visual_spec,
            visual_references=question_data.get('visual_references', [])
        )

        # Финальная проверка
        final_validation = QuestionVisualSyncService._validate_sync(
            regenerated, visual_spec
        )

        if not final_validation['is_valid']:
            import logging
            logging.error(
                f"Failed to fix question-visual sync: {final_validation['errors']}"
            )

        return regenerated
```

#### Интеграция в `engine.py`

**Модификация функции `_generate_question_llm` (строки 851-1222):**

```python
# backend/app/api/engine.py

from app.services.question_visual_sync import QuestionVisualSyncService

async def _generate_question_llm(
    topic_uid: str,
    neo4j_repo,
    difficulty: Optional[int] = None,
    force_visual: bool = False
) -> dict:
    """
    Обновленная генерация с синхронизацией
    """

    # 1. Получить контекст темы (как раньше)
    topic_context = await _get_topic_context(topic_uid, neo4j_repo)

    # 2. НОВОЕ: Использовать сервис синхронизации
    synced_question = await QuestionVisualSyncService.generate_synced_question(
        topic_context=topic_context,
        force_visual=force_visual
    )

    # 3. Преобразовать в старый формат для совместимости
    result = {
        "question_uid": f"Q-{topic_uid}-{uuid.uuid4().hex[:8]}",
        "topic_uid": topic_uid,
        "question_text": synced_question.question_text,
        "question_type": synced_question.question_type,
        "options": synced_question.options,
        "correct_answer": synced_question.correct_answer,
        "difficulty": difficulty or 5,
        "is_visual": synced_question.visualization is not None,
        "visualization_data": None
    }

    # 4. Добавить визуализацию если есть
    if synced_question.visualization:
        result["visualization_data"] = {
            "shapes": synced_question.visualization.shapes,
            "labels": synced_question.visualization.labels,
            "coordinate_system": synced_question.visualization.coordinate_system
        }

    return result
```

#### План миграции

1. **Создать новый файл** `backend/app/services/question_visual_sync.py`
2. **Добавить unit-тесты** `tests/test_question_visual_sync.py`:
   - Тест генерации без визуализации
   - Тест генерации с визуализацией
   - Тест валидации (корректные/некорректные случаи)
   - Тест retry-логики
3. **Обновить** `engine.py` с использованием нового сервиса
4. **A/B тестирование**:
   - 50% вопросов через старую систему
   - 50% через новую
   - Сравнить метрики качества
5. **Rollout**: Постепенно увеличивать до 100% нового сервиса

#### Метрики успеха

- **Синхронизация**: 0% вопросов с визуализацией без ссылок на неё
- **Консистентность**: 100% упомянутых меток существуют в визуализации
- **Retry rate**: < 5% (вместо текущих ~15-20%)
- **Latency**: < 3 сек на генерацию (включая 2 LLM вызова)

---

## Задача 2: Адаптивное тестирование с объективной оценкой

### Проблема
Текущая система (`engine.py:1272-1691`) имеет ограничения:
- Простая линейная адаптация сложности (+1/-1)
- Критерий завершения основан только на уверенности (85%)
- Финальный скор - простое взвешенное среднее
- Нет оценки надежности результата

### Текущая архитектура
```python
# Адаптация сложности (строки 1422-1487)
if correct:
    current_d = min(current_d + 1, 10)
else:
    current_d = max(current_d - 1, 1)

# Критерий завершения (строки 1514-1532)
if confidence >= target_confidence and len(asked) >= min_questions:
    return finish_assessment()
if len(asked) >= max_questions:
    return finish_assessment()
```

### Решение: Item Response Theory (IRT) + Bayesian Knowledge Tracing

#### Алгоритм реализации

**Шаг 1: Создать новый сервис `backend/app/services/adaptive_assessment.py`**

```python
from typing import Optional, List, Tuple
from pydantic import BaseModel
import math
import numpy as np

class IRTParameters(BaseModel):
    """Параметры вопроса по модели IRT"""
    difficulty: float  # b: сложность (-3 to +3, 0 = средняя)
    discrimination: float  # a: различительная способность (0.5 to 2.5)
    guessing: float = 0.25  # c: вероятность угадывания (0.25 для 4 вариантов)

class KnowledgeState(BaseModel):
    """Состояние знаний студента"""
    theta: float  # Уровень способностей (-3 to +3)
    theta_se: float  # Стандартная ошибка оценки
    confidence: float  # Уверенность в оценке (0-1)
    mastery_probability: float  # Вероятность освоения темы

class AssessmentSession(BaseModel):
    """Сессия адаптивного тестирования"""
    topic_uid: str
    user_id: str
    responses: List[dict] = []
    knowledge_state: KnowledgeState
    questions_asked: int = 0
    is_terminated: bool = False
    termination_reason: Optional[str] = None

class AdaptiveAssessmentEngine:

    # Константы для IRT
    D = 1.7  # Scaling factor для логистической функции

    # Критерии завершения
    MIN_QUESTIONS = 6
    MAX_QUESTIONS = 20
    TARGET_SE = 0.3  # Целевая стандартная ошибка
    MIN_INFO = 15.0  # Минимальная накопленная информация

    @staticmethod
    def initialize_session(topic_uid: str, user_id: str) -> AssessmentSession:
        """
        Инициализация сессии

        Алгоритм:
        1. Начальная оценка theta = 0 (средний уровень)
        2. Начальная SE = 1.0 (высокая неопределенность)
        3. Confidence = 0, mastery = 0.5
        """
        return AssessmentSession(
            topic_uid=topic_uid,
            user_id=user_id,
            knowledge_state=KnowledgeState(
                theta=0.0,
                theta_se=1.0,
                confidence=0.0,
                mastery_probability=0.5
            )
        )

    @staticmethod
    def irt_probability(
        theta: float,
        difficulty: float,
        discrimination: float,
        guessing: float = 0.25
    ) -> float:
        """
        3-параметрическая модель IRT (3PL)

        P(correct | theta, b, a, c) = c + (1-c) / (1 + exp(-D*a*(theta - b)))

        Где:
        - theta: способности студента
        - b (difficulty): сложность вопроса
        - a (discrimination): различительная способность
        - c (guessing): вероятность угадывания
        - D = 1.7: масштабирующий фактор
        """
        exponent = -AdaptiveAssessmentEngine.D * discrimination * (theta - difficulty)
        return guessing + (1 - guessing) / (1 + math.exp(exponent))

    @staticmethod
    def fisher_information(
        theta: float,
        difficulty: float,
        discrimination: float,
        guessing: float = 0.25
    ) -> float:
        """
        Информация Фишера - мера полезности вопроса для оценки theta

        I(theta) = [a^2 * (P - c)^2 * (1 - P)] / [(1 - c)^2 * P]

        Чем выше информация, тем точнее оценка theta после этого вопроса
        """
        P = AdaptiveAssessmentEngine.irt_probability(
            theta, difficulty, discrimination, guessing
        )

        if P <= guessing or P >= 1.0:
            return 0.0

        numerator = (discrimination ** 2) * ((P - guessing) ** 2) * (1 - P)
        denominator = ((1 - guessing) ** 2) * P

        return numerator / denominator if denominator > 0 else 0.0

    @staticmethod
    def select_next_question(
        session: AssessmentSession,
        available_questions: List[dict]
    ) -> dict:
        """
        Выбор следующего вопроса методом Maximum Information

        Алгоритм:
        1. Для каждого доступного вопроса вычислить информацию Фишера
        2. Выбрать вопрос с максимальной информацией
        3. Исключить уже заданные вопросы
        """

        theta = session.knowledge_state.theta
        asked_uids = {r['question_uid'] for r in session.responses}

        best_question = None
        max_info = -1.0

        for q in available_questions:
            if q['question_uid'] in asked_uids:
                continue

            # Получить IRT параметры вопроса
            irt_params = AdaptiveAssessmentEngine._get_irt_parameters(q)

            # Вычислить информацию
            info = AdaptiveAssessmentEngine.fisher_information(
                theta,
                irt_params.difficulty,
                irt_params.discrimination,
                irt_params.guessing
            )

            if info > max_info:
                max_info = info
                best_question = q

        return best_question

    @staticmethod
    def _get_irt_parameters(question: dict) -> IRTParameters:
        """
        Получение/оценка IRT параметров вопроса

        Если параметры не заданы - оценить из метаданных:
        - difficulty: из поля 'difficulty' (1-10) → (-3 to +3)
        - discrimination: из типа вопроса
        - guessing: из количества вариантов
        """

        # Если есть сохраненные IRT параметры
        if 'irt_parameters' in question:
            return IRTParameters(**question['irt_parameters'])

        # Оценка difficulty: 1-10 → -2.5 to +2.5
        raw_diff = question.get('difficulty', 5)
        difficulty = ((raw_diff - 5.5) / 2.0)

        # Оценка discrimination по типу
        question_type = question.get('question_type', 'single_choice')
        discrimination_map = {
            'single_choice': 1.2,
            'numeric': 1.8,  # Более различительные
            'free_text': 1.5,
            'boolean': 0.8  # Менее различительные
        }
        discrimination = discrimination_map.get(question_type, 1.0)

        # Оценка guessing
        if question_type == 'single_choice':
            num_options = len(question.get('options', []))
            guessing = 1.0 / num_options if num_options > 0 else 0.25
        elif question_type == 'boolean':
            guessing = 0.5
        else:
            guessing = 0.0  # numeric, free_text

        return IRTParameters(
            difficulty=difficulty,
            discrimination=discrimination,
            guessing=guessing
        )

    @staticmethod
    def update_knowledge_state(
        session: AssessmentSession,
        question: dict,
        is_correct: bool
    ) -> KnowledgeState:
        """
        Обновление оценки theta методом Maximum Likelihood Estimation (MLE)

        Алгоритм:
        1. Использовать метод Ньютона-Рафсона для поиска theta
        2. Вычислить новую стандартную ошибку
        3. Обновить уверенность и вероятность освоения
        """

        # Добавить ответ в историю
        irt_params = AdaptiveAssessmentEngine._get_irt_parameters(question)
        session.responses.append({
            'question_uid': question['question_uid'],
            'is_correct': is_correct,
            'difficulty': irt_params.difficulty,
            'discrimination': irt_params.discrimination,
            'guessing': irt_params.guessing
        })

        # MLE оценка theta методом Ньютона-Рафсона
        theta_new = AdaptiveAssessmentEngine._estimate_theta_mle(
            session.responses
        )

        # Стандартная ошибка = 1 / sqrt(sum of Fisher information)
        total_info = sum(
            AdaptiveAssessmentEngine.fisher_information(
                theta_new,
                r['difficulty'],
                r['discrimination'],
                r['guessing']
            )
            for r in session.responses
        )

        theta_se = 1.0 / math.sqrt(total_info) if total_info > 0 else 1.0

        # Уверенность: обратная SE, нормализованная
        # SE от 1.0 (низкая) до 0.2 (высокая) → confidence от 0 до 1
        confidence = max(0.0, min(1.0, (1.0 - theta_se) / 0.8))

        # Вероятность освоения: P(theta > threshold)
        # Используем threshold = 0.5 (выше среднего)
        # P = Φ((theta - 0.5) / theta_se), где Φ - CDF нормального распределения
        from scipy.stats import norm
        mastery_threshold = 0.5
        mastery_probability = norm.cdf((theta_new - mastery_threshold) / theta_se)

        return KnowledgeState(
            theta=theta_new,
            theta_se=theta_se,
            confidence=confidence,
            mastery_probability=mastery_probability
        )

    @staticmethod
    def _estimate_theta_mle(responses: List[dict], max_iter: int = 10) -> float:
        """
        Maximum Likelihood Estimation theta методом Ньютона-Рафсона

        Итеративно решаем: theta_new = theta_old - f(theta) / f'(theta)

        Где:
        - f(theta) = первая производная log-likelihood
        - f'(theta) = вторая производная (отрицательная информация)
        """

        theta = 0.0  # Начальная оценка

        for _ in range(max_iter):
            first_deriv = 0.0
            second_deriv = 0.0

            for r in responses:
                P = AdaptiveAssessmentEngine.irt_probability(
                    theta, r['difficulty'], r['discrimination'], r['guessing']
                )

                # Защита от деления на ноль
                P = max(0.001, min(0.999, P))

                # Производные
                W = r['discrimination'] * AdaptiveAssessmentEngine.D * (P - r['guessing']) / (1 - r['guessing'])

                if r['is_correct']:
                    first_deriv += W * (1 - P) / P
                    second_deriv -= W ** 2 * (1 - P) / (P ** 2)
                else:
                    first_deriv -= W * P / (1 - P)
                    second_deriv -= W ** 2 * P / ((1 - P) ** 2)

            # Шаг Ньютона-Рафсона
            if second_deriv != 0:
                theta_new = theta - first_deriv / second_deriv
            else:
                break

            # Проверка сходимости
            if abs(theta_new - theta) < 0.001:
                theta = theta_new
                break

            theta = theta_new

        # Зажать theta в разумных пределах
        return max(-3.0, min(3.0, theta))

    @staticmethod
    def check_termination(session: AssessmentSession) -> Tuple[bool, Optional[str]]:
        """
        Проверка критериев завершения тестирования

        Критерии:
        1. SE <= TARGET_SE (высокая точность оценки)
        2. Достигнут MIN_QUESTIONS И накопленная информация >= MIN_INFO
        3. Достигнут MAX_QUESTIONS (жесткий лимит)
        """

        n_questions = len(session.responses)
        se = session.knowledge_state.theta_se

        # Критерий 3: Максимум вопросов
        if n_questions >= AdaptiveAssessmentEngine.MAX_QUESTIONS:
            return True, f"max_questions_reached ({n_questions})"

        # Критерий 1: Достаточная точность
        if se <= AdaptiveAssessmentEngine.TARGET_SE:
            return True, f"target_precision_achieved (SE={se:.3f})"

        # Критерий 2: Минимум вопросов + достаточная информация
        if n_questions >= AdaptiveAssessmentEngine.MIN_QUESTIONS:
            total_info = 1.0 / (se ** 2) if se > 0 else 0.0
            if total_info >= AdaptiveAssessmentEngine.MIN_INFO:
                return True, f"sufficient_information (I={total_info:.1f})"

        return False, None

    @staticmethod
    def compute_final_score(session: AssessmentSession) -> dict:
        """
        Вычисление финального скора и аналитики

        Метрики:
        1. theta_score: 0-100 на основе theta
        2. mastery_level: процент освоения темы
        3. reliability: надежность оценки (обратная SE)
        4. achievement_band: категория достижения
        """

        theta = session.knowledge_state.theta
        se = session.knowledge_state.theta_se
        mastery = session.knowledge_state.mastery_probability

        # 1. Преобразование theta (-3, +3) → (0, 100)
        # theta = -3 → 0%, theta = 0 → 50%, theta = +3 → 100%
        theta_score = ((theta + 3.0) / 6.0) * 100
        theta_score = max(0.0, min(100.0, theta_score))

        # 2. Mastery level = вероятность освоения * 100
        mastery_level = mastery * 100

        # 3. Reliability = 1 - (SE / max_SE)
        max_se = 1.0  # Начальная SE
        reliability = max(0.0, 1.0 - (se / max_se))

        # 4. Achievement band
        if theta >= 1.5:
            achievement_band = "excellent"  # Отлично
        elif theta >= 0.5:
            achievement_band = "good"  # Хорошо
        elif theta >= -0.5:
            achievement_band = "satisfactory"  # Удовлетворительно
        else:
            achievement_band = "needs_improvement"  # Требует улучшения

        # 5. Confidence interval (95%)
        from scipy.stats import norm
        z_score = norm.ppf(0.975)  # 95% CI
        ci_lower = ((theta - z_score * se) + 3.0) / 6.0 * 100
        ci_upper = ((theta + z_score * se) + 3.0) / 6.0 * 100

        return {
            "theta": round(theta, 3),
            "theta_se": round(se, 3),
            "theta_score": round(theta_score, 1),
            "mastery_level": round(mastery_level, 1),
            "reliability": round(reliability, 2),
            "achievement_band": achievement_band,
            "confidence_interval_95": {
                "lower": round(ci_lower, 1),
                "upper": round(ci_upper, 1)
            },
            "total_questions": len(session.responses),
            "correct_count": sum(1 for r in session.responses if r['is_correct']),
            "termination_reason": session.termination_reason
        }
```

#### Интеграция в `engine.py`

**Модификация функций assessment (строки 1272-1691):**

```python
# backend/app/api/engine.py

from app.services.adaptive_assessment import (
    AdaptiveAssessmentEngine,
    AssessmentSession
)

@app.post("/v1/assessment/start")
async def start_assessment(request: StartAssessmentRequest):
    """Запуск адаптивного тестирования"""

    # Инициализация сессии с IRT
    session = AdaptiveAssessmentEngine.initialize_session(
        topic_uid=request.topic_uid,
        user_id=request.user_id
    )

    # Получить доступные вопросы для темы
    questions = await _get_topic_questions(request.topic_uid)

    # Выбрать первый вопрос (максимальная информация для theta=0)
    first_question = AdaptiveAssessmentEngine.select_next_question(
        session, questions
    )

    # Сохранить сессию в Redis
    await redis_client.setex(
        f"assessment:{session.topic_uid}:{session.user_id}",
        86400,  # 24 часа
        session.json()
    )

    return {
        "question": first_question,
        "progress": {
            "current": 1,
            "min": AdaptiveAssessmentEngine.MIN_QUESTIONS,
            "max": AdaptiveAssessmentEngine.MAX_QUESTIONS
        },
        "current_estimate": {
            "theta": session.knowledge_state.theta,
            "confidence": session.knowledge_state.confidence
        }
    }


@app.post("/v1/assessment/next")
async def next_assessment_question(request: NextAssessmentRequest):
    """Обработка ответа и выдача следующего вопроса"""

    # Загрузить сессию
    session_data = await redis_client.get(
        f"assessment:{request.topic_uid}:{request.user_id}"
    )
    session = AssessmentSession.parse_raw(session_data)

    # Найти вопрос по uid
    question = await _get_question_by_uid(request.question_uid)

    # Оценить ответ
    is_correct = _evaluate_answer(
        question, request.answer, request.answer_type
    )

    # Обновить knowledge state с IRT
    new_knowledge_state = AdaptiveAssessmentEngine.update_knowledge_state(
        session, question, is_correct
    )
    session.knowledge_state = new_knowledge_state
    session.questions_asked += 1

    # Проверить критерии завершения
    should_terminate, reason = AdaptiveAssessmentEngine.check_termination(session)

    if should_terminate:
        session.is_terminated = True
        session.termination_reason = reason

        # Финальный скор
        final_score = AdaptiveAssessmentEngine.compute_final_score(session)

        # Обновить прогресс пользователя
        await _update_user_progress(
            user_id=request.user_id,
            topic_uid=request.topic_uid,
            mastery_level=final_score['mastery_level'] / 100.0
        )

        # Сохранить и вернуть результат
        await redis_client.setex(
            f"assessment:{request.topic_uid}:{request.user_id}",
            86400,
            session.json()
        )

        return {
            "is_finished": True,
            "final_score": final_score,
            "feedback": is_correct,
            "analytics": await _generate_analytics_llm(session)
        }

    # Выбрать следующий вопрос
    questions = await _get_topic_questions(request.topic_uid)
    next_question = AdaptiveAssessmentEngine.select_next_question(
        session, questions
    )

    # Сохранить сессию
    await redis_client.setex(
        f"assessment:{request.topic_uid}:{request.user_id}",
        86400,
        session.json()
    )

    return {
        "is_finished": False,
        "question": next_question,
        "feedback": is_correct,
        "progress": {
            "current": session.questions_asked + 1,
            "min": AdaptiveAssessmentEngine.MIN_QUESTIONS,
            "max": AdaptiveAssessmentEngine.MAX_QUESTIONS,
            "estimated_remaining": max(
                0,
                AdaptiveAssessmentEngine.MIN_QUESTIONS - session.questions_asked - 1
            )
        },
        "current_estimate": {
            "theta": session.knowledge_state.theta,
            "theta_se": session.knowledge_state.theta_se,
            "mastery_probability": session.knowledge_state.mastery_probability,
            "confidence": session.knowledge_state.confidence
        }
    }
```

#### Зависимости

Добавить в `requirements.txt`:
```
scipy>=1.11.0
numpy>=1.24.0
```

#### План миграции

1. **Калибровка IRT параметров**:
   - Запустить пилотное тестирование на 100+ пользователях
   - Собрать данные: (user_id, question_uid, is_correct)
   - Использовать пакет `mirt` (R) или `pyirt` (Python) для калибровки
   - Сохранить параметры в Neo4j: `(Question {irt_difficulty, irt_discrimination})`

2. **A/B тестирование**:
   - Группа A: старая система (линейная адаптация)
   - Группа B: новая система (IRT)
   - Метрики:
     - Точность оценки (корреляция с экспертной оценкой)
     - Количество вопросов до завершения
     - Удовлетворенность пользователей

3. **Rollout**:
   - Постепенное увеличение до 100% IRT

#### Метрики успеха

- **Точность**: Correlation(theta_score, expert_score) > 0.85
- **Эффективность**: Среднее количество вопросов < 12 (вместо текущих 15-20)
- **Надежность**: Средняя SE < 0.35
- **Справедливость**: Нет bias по группам пользователей

---

## Задача 3: Повышение релевантности дорожной карты

### Проблема
Текущая система (`engine.py:155-348`) генерирует roadmap на основе:
- Пререквизитов из графа (недостаточный датасет)
- Простого расстояния в графе
- Одноразового LLM выбора (5-8 тем)

Проблемы:
- Не учитывается семантическая близость тем
- Слабые связи между темами в графе
- Нет адаптации к реальным навыкам пользователя

### Текущая архитектура
```python
# Выбор кандидатов (Neo4j PREREQ)
candidates = neo4j_repo.query("""
    MATCH (t:Topic)-[:BELONGS_TO]->(subj:Subject {uid: $subject_uid})
    OPTIONAL MATCH path=(t)-[:PREREQ*0..3]->(focus:Topic {uid: $focus_uid})
    RETURN t, length(path) as distance
    ORDER BY distance
    LIMIT 50
""")

# LLM персонализация
llm_selected = await openai_chat_async(
    prompt=f"Select 5-8 topics for user with mastery: {progress}",
    candidates=candidates
)
```

### Решение: Гибридная рекомендательная система (Graph + Embedding + IRT)

#### Алгоритм реализации

**Шаг 1: Создать новый сервис `backend/app/services/roadmap_recommender.py`**

```python
from typing import List, Dict, Optional
from pydantic import BaseModel
import numpy as np

class TopicFeatures(BaseModel):
    """Признаки темы для рекомендаций"""
    uid: str
    title: str
    embedding: List[float]  # 1536-dim от OpenAI
    difficulty_irt: float  # Средняя сложность вопросов темы
    importance: float  # In-degree в графе
    unlock_potential: float  # Количество зависимых тем
    mastery_score: float  # Текущее мастерство пользователя

class RoadmapRecommendation(BaseModel):
    """Рекомендация темы"""
    topic_uid: str
    score: float
    reasons: List[str]  # Почему рекомендована
    prerequisites_ready: bool
    estimated_difficulty: float

class HybridRoadmapRecommender:

    # Веса компонентов скоринга
    W_SEMANTIC = 0.3  # Семантическая близость
    W_GRAPH = 0.25     # Структура графа
    W_SKILL = 0.25     # Соответствие навыкам
    W_DIFFICULTY = 0.2 # Оптимальная сложность

    @staticmethod
    async def generate_roadmap(
        subject_uid: str,
        focus_topic_uid: Optional[str],
        user_progress: Dict[str, float],
        user_skills: Dict[str, float],
        limit: int = 8
    ) -> List[RoadmapRecommendation]:
        """
        Генерация персонализированной дорожной карты

        Алгоритм:
        1. Загрузить кандидатов (все темы предмета)
        2. Фильтровать по доступности (пререквизиты)
        3. Вычислить векторные эмбеддинги тем
        4. Скоринг каждой темы по 4 компонентам
        5. Ранжирование и выбор топ-N
        6. LLM описания для пустых полей
        """

        # === ШАГ 1: Загрузка кандидатов ===
        candidates = await HybridRoadmapRecommender._load_candidates(
            subject_uid, user_progress
        )

        # === ШАГ 2: Фильтрация по доступности ===
        available = HybridRoadmapRecommender._filter_available(
            candidates, user_progress
        )

        # === ШАГ 3: Векторные эмбеддинги ===
        if focus_topic_uid:
            focus_embedding = await HybridRoadmapRecommender._get_embedding(
                focus_topic_uid
            )
        else:
            # Если фокуса нет - используем средний вектор целей пользователя
            focus_embedding = await HybridRoadmapRecommender._compute_user_goal_embedding(
                subject_uid, user_skills
            )

        # === ШАГ 4: Скоринг ===
        scored = []
        for topic in available:
            score, reasons = await HybridRoadmapRecommender._score_topic(
                topic=topic,
                focus_embedding=focus_embedding,
                user_progress=user_progress,
                user_skills=user_skills
            )

            scored.append(RoadmapRecommendation(
                topic_uid=topic['uid'],
                score=score,
                reasons=reasons,
                prerequisites_ready=True,  # Уже отфильтровано
                estimated_difficulty=topic.get('difficulty_irt', 0.0)
            ))

        # === ШАГ 5: Ранжирование ===
        scored.sort(key=lambda x: x.score, reverse=True)
        top_recommendations = scored[:limit]

        # === ШАГ 6: Обогащение описаниями через LLM ===
        enriched = await HybridRoadmapRecommender._enrich_with_llm(
            top_recommendations, user_progress, user_skills
        )

        return enriched

    @staticmethod
    async def _load_candidates(
        subject_uid: str,
        user_progress: Dict[str, float]
    ) -> List[dict]:
        """
        Загрузка всех тем предмета с метаданными

        Query Neo4j:
        - Topic properties
        - IRT difficulty (avg of questions)
        - Graph metrics (in-degree, descendants)
        - Skills required
        """
        from app.services.graph.neo4j_repo import get_driver

        query = """
        MATCH (t:Topic)-[:BELONGS_TO*]->(subj:Subject {uid: $subject_uid})

        // IRT difficulty
        OPTIONAL MATCH (t)-[:HAS_QUESTION]->(q:Question)
        WITH t, subj, AVG(q.irt_difficulty) as avg_difficulty

        // Graph metrics
        OPTIONAL MATCH (other:Topic)-[:PREREQ]->(t)
        WITH t, subj, avg_difficulty, COUNT(DISTINCT other) as importance

        OPTIONAL MATCH (t)-[:PREREQ*]->(descendant:Topic)
        WITH t, subj, avg_difficulty, importance, COUNT(DISTINCT descendant) as unlock_potential

        // Skills
        OPTIONAL MATCH (t)-[:REQUIRES_SKILL]->(s:Skill)

        RETURN
            t.uid as uid,
            t.title as title,
            t.description as description,
            t.user_class_min as class_min,
            t.user_class_max as class_max,
            avg_difficulty as difficulty_irt,
            importance,
            unlock_potential,
            COLLECT(DISTINCT s.uid) as required_skills
        """

        async with get_driver().session() as session:
            result = await session.run(query, subject_uid=subject_uid)
            records = await result.data()

        # Добавить текущее мастерство
        for record in records:
            record['mastery_score'] = user_progress.get(record['uid'], 0.0)

        return records

    @staticmethod
    def _filter_available(
        candidates: List[dict],
        user_progress: Dict[str, float],
        prereq_threshold: float = 0.7
    ) -> List[dict]:
        """
        Фильтрация доступных тем

        Алгоритм:
        1. Загрузить пререквизиты из Neo4j
        2. Проверить, что все пререквизиты освоены >= threshold
        3. Исключить уже полностью освоенные (>= 0.85)
        """
        from app.services.graph.neo4j_repo import get_driver

        topic_uids = [c['uid'] for c in candidates]

        # Загрузить все prereq связи одним запросом
        query = """
        UNWIND $topic_uids as uid
        MATCH (t:Topic {uid: uid})<-[:PREREQ]-(prereq:Topic)
        RETURN t.uid as topic_uid, COLLECT(prereq.uid) as prereq_uids
        """

        async with get_driver().session() as session:
            result = await session.run(query, topic_uids=topic_uids)
            prereq_map = {r['topic_uid']: r['prereq_uids'] for r in await result.data()}

        available = []
        for topic in candidates:
            # Исключить полностью освоенные
            if topic['mastery_score'] >= 0.85:
                continue

            # Проверить пререквизиты
            prereqs = prereq_map.get(topic['uid'], [])
            if all(user_progress.get(p, 0.0) >= prereq_threshold for p in prereqs):
                available.append(topic)

        return available

    @staticmethod
    async def _get_embedding(topic_uid: str) -> np.ndarray:
        """
        Получение или генерация эмбеддинга темы

        Источники:
        1. Кэш в Redis
        2. Qdrant vector store
        3. Генерация через OpenAI embeddings API
        """
        from app.services.graph.neo4j_repo import get_driver
        from app.config import redis_client
        import openai

        # Проверить кэш
        cache_key = f"embedding:topic:{topic_uid}"
        cached = await redis_client.get(cache_key)
        if cached:
            import json
            return np.array(json.loads(cached))

        # Загрузить текст темы
        query = """
        MATCH (t:Topic {uid: $topic_uid})
        RETURN t.title as title, t.description as description
        """
        async with get_driver().session() as session:
            result = await session.run(query, topic_uid=topic_uid)
            record = await result.single()

        if not record:
            return np.zeros(1536)

        # Объединить title + description
        text = f"{record['title']}. {record.get('description', '')}"

        # Генерация эмбеддинга
        response = await openai.Embedding.acreate(
            input=text,
            model="text-embedding-3-small"
        )
        embedding = response['data'][0]['embedding']

        # Сохранить в кэш (TTL 7 дней)
        import json
        await redis_client.setex(
            cache_key,
            604800,
            json.dumps(embedding)
        )

        return np.array(embedding)

    @staticmethod
    async def _compute_user_goal_embedding(
        subject_uid: str,
        user_skills: Dict[str, float]
    ) -> np.ndarray:
        """
        Вычисление эмбеддинга цели пользователя

        Алгоритм:
        1. Найти топ-5 навыков с наивысшим приоритетом
        2. Получить эмбеддинги этих навыков
        3. Взвешенное среднее
        """

        # Топ-5 навыков
        sorted_skills = sorted(
            user_skills.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]

        if not sorted_skills:
            return np.zeros(1536)

        embeddings = []
        weights = []

        for skill_uid, weight in sorted_skills:
            emb = await HybridRoadmapRecommender._get_embedding(skill_uid)
            embeddings.append(emb)
            weights.append(weight)

        # Взвешенное среднее
        weights = np.array(weights)
        weights = weights / weights.sum()

        goal_embedding = np.average(embeddings, axis=0, weights=weights)
        return goal_embedding

    @staticmethod
    async def _score_topic(
        topic: dict,
        focus_embedding: np.ndarray,
        user_progress: Dict[str, float],
        user_skills: Dict[str, float]
    ) -> tuple[float, List[str]]:
        """
        Скоринг темы по 4 компонентам

        Компоненты:
        1. Семантическая близость (cosine similarity с фокусом)
        2. Структурная важность (graph metrics)
        3. Соответствие навыкам (skill match)
        4. Оптимальная сложность (IRT difficulty vs user theta)
        """

        reasons = []

        # === КОМПОНЕНТ 1: Семантическая близость ===
        topic_embedding = await HybridRoadmapRecommender._get_embedding(topic['uid'])
        cosine_sim = np.dot(focus_embedding, topic_embedding) / (
            np.linalg.norm(focus_embedding) * np.linalg.norm(topic_embedding) + 1e-8
        )
        semantic_score = (cosine_sim + 1) / 2  # [-1, 1] → [0, 1]

        if semantic_score > 0.7:
            reasons.append("Тематически близка к вашим целям")

        # === КОМПОНЕНТ 2: Структурная важность ===
        importance = topic.get('importance', 0)
        unlock_potential = topic.get('unlock_potential', 0)

        # Нормализация (предполагаем max_importance=10, max_unlock=20)
        importance_norm = min(importance / 10.0, 1.0)
        unlock_norm = min(unlock_potential / 20.0, 1.0)

        graph_score = 0.5 * importance_norm + 0.5 * unlock_norm

        if importance >= 3:
            reasons.append(f"Важная тема ({importance} других тем зависят от неё)")
        if unlock_potential >= 5:
            reasons.append(f"Откроет {unlock_potential} новых тем")

        # === КОМПОНЕНТ 3: Соответствие навыкам ===
        required_skills = topic.get('required_skills', [])

        if not required_skills:
            skill_score = 0.5  # Нейтральный скор
        else:
            # Процент навыков, которые пользователь хочет развивать
            user_skill_set = set(user_skills.keys())
            overlap = len(set(required_skills) & user_skill_set)
            skill_score = overlap / len(required_skills)

            if skill_score > 0.5:
                reasons.append("Развивает важные для вас навыки")

        # === КОМПОНЕНТ 4: Оптимальная сложность ===
        # Zone of Proximal Development: theta ± 0.5
        user_theta = HybridRoadmapRecommender._estimate_user_theta(user_progress)
        topic_difficulty = topic.get('difficulty_irt', 0.0)

        difficulty_gap = abs(topic_difficulty - user_theta)

        if difficulty_gap <= 0.5:
            difficulty_score = 1.0  # Идеальная сложность
            reasons.append("Оптимальная сложность для вашего уровня")
        elif difficulty_gap <= 1.0:
            difficulty_score = 0.7
        elif difficulty_gap <= 1.5:
            difficulty_score = 0.4
        else:
            difficulty_score = 0.2
            if topic_difficulty > user_theta:
                reasons.append("Сложная тема, может потребоваться подготовка")

        # === ИТОГОВЫЙ СКОР ===
        final_score = (
            HybridRoadmapRecommender.W_SEMANTIC * semantic_score +
            HybridRoadmapRecommender.W_GRAPH * graph_score +
            HybridRoadmapRecommender.W_SKILL * skill_score +
            HybridRoadmapRecommender.W_DIFFICULTY * difficulty_score
        )

        return final_score, reasons

    @staticmethod
    def _estimate_user_theta(user_progress: Dict[str, float]) -> float:
        """
        Оценка общего theta пользователя

        Алгоритм:
        1. Взять средний mastery по всем темам
        2. Преобразовать [0, 1] → [-3, +3]
        """
        if not user_progress:
            return 0.0

        avg_mastery = sum(user_progress.values()) / len(user_progress)
        # mastery = 0 → theta = -3, mastery = 0.5 → theta = 0, mastery = 1 → theta = +3
        theta = (avg_mastery - 0.5) * 6.0
        return max(-3.0, min(3.0, theta))

    @staticmethod
    async def _enrich_with_llm(
        recommendations: List[RoadmapRecommendation],
        user_progress: Dict[str, float],
        user_skills: Dict[str, float]
    ) -> List[RoadmapRecommendation]:
        """
        Обогащение описаниями через LLM

        Алгоритм:
        1. Загрузить базовые данные тем из Neo4j
        2. Для тем с пустыми описаниями - генерация через LLM
        3. Добавить персонализированные подсказки
        """
        from app.services.openai_helpers import openai_chat_async
        from app.services.graph.neo4j_repo import get_driver

        # Загрузить данные тем
        topic_uids = [r.topic_uid for r in recommendations]
        query = """
        UNWIND $uids as uid
        MATCH (t:Topic {uid: uid})
        RETURN t.uid as uid, t.title as title, t.description as description
        """

        async with get_driver().session() as session:
            result = await session.run(query, uids=topic_uids)
            topic_data = {r['uid']: r for r in await result.data()}

        # LLM prompt для генерации описаний
        topics_needing_description = [
            r for r in recommendations
            if not topic_data[r.topic_uid].get('description')
        ]

        if topics_needing_description:
            titles = [topic_data[r.topic_uid]['title'] for r in topics_needing_description]

            prompt = f"""Создай краткие описания (1-2 предложения) для следующих учебных тем:

Темы:
{chr(10).join(f"{i+1}. {t}" for i, t in enumerate(titles))}

Контекст пользователя:
- Текущий прогресс: {len([p for p in user_progress.values() if p > 0.5])} тем освоено
- Приоритетные навыки: {', '.join(list(user_skills.keys())[:5])}

Формат JSON:
{{
    "descriptions": [
        {{"title": "...", "description": "...", "hint": "..."}},
        ...
    ]
}}
"""

            response = await openai_chat_async(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                model="gpt-4o-mini",
                response_format={"type": "json_object"}
            )

            import json
            llm_data = json.loads(response)

            # Обновить topic_data
            for i, rec in enumerate(topics_needing_description):
                topic_data[rec.topic_uid]['description'] = llm_data['descriptions'][i]['description']

        return recommendations
```

