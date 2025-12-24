from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from src.services.graph.neo4j_repo import relation_context, neighbors, get_node_details
from src.config.settings import settings
from src.services.roadmap_planner import plan_route
from src.services.questions import select_examples_for_topics, all_topic_uids_from_examples
from src.api.common import ApiError

router = APIRouter(prefix="/v1/graph", tags=["Интеграция с LMS"])

class ViewportQuery(BaseModel):
    center_uid: str = Field(..., description="UID центрального узла для получения его окрестности.")
    depth: int = Field(1, ge=1, le=3, description="Глубина обхода (рекомендуется 1–3).")

class NodeDTO(BaseModel):
    id: int
    uid: Optional[str] = None
    label: Optional[str] = None
    labels: List[str] = []

class EdgeDTO(BaseModel):
    from_: int = Field(..., alias="from")
    to: int
    type: str

class ViewportResponse(BaseModel):
    nodes: List[NodeDTO]
    edges: List[EdgeDTO]
    center_uid: str
    depth: int
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "nodes": [{"id": 1, "uid": "TOP-DEMO", "labels": ["Topic"]}],
                    "edges": [{"from": 1, "to": 2, "type": "PREREQ"}],
                    "center_uid": "TOP-DEMO",
                    "depth": 1,
                }
            ]
        }
    }

@router.get("/node/{uid}")
async def get_node(uid: str) -> Dict:
    data = get_node_details(uid)
    if not data:
        raise HTTPException(status_code=404, detail="Node not found")
    return data

@router.get("/viewport")
async def viewport(center_uid: str, depth: int = 1) -> Dict:
    """
    Принимает:
      - center_uid: UID центрального узла
      - depth: глубина обхода (целое, рекомендовано 1–3)

    Возвращает:
      - nodes: список объектов узлов {id, uid, label, labels}
      - edges: список объектов связей {from, to, type}
      - center_uid: исходный UID
      - depth: фактическая глубина обхода
    """
    ns, es = neighbors(center_uid, depth=depth)
    return {"nodes": ns, "edges": es, "center_uid": center_uid, "depth": depth}

class ChatInput(BaseModel):
    question: str = Field(..., description="Вопрос пользователя о связи между узлами.")
    from_uid: str = Field(..., description="UID исходного узла.")
    to_uid: str = Field(..., description="UID целевого узла.")

class ChatUsage(BaseModel):
    completion_tokens: Optional[int] = None
    prompt_tokens: Optional[int] = None
    total_tokens: Optional[int] = None

class RelationContext(BaseModel):
    rel: Optional[str] = None
    props: Dict = {}
    from_title: Optional[str] = None
    to_title: Optional[str] = None

class ChatResponse(BaseModel):
    answer: str
    usage: Optional[Dict] = None
    context: RelationContext
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "answer": "Тема B опирается на базовые понятия из темы A...",
                    "usage": {"prompt_tokens": 120, "completion_tokens": 56, "total_tokens": 176},
                    "context": {"rel": "PREREQ", "props": {"weight": 0.7}, "from_title": "Тема A", "to_title": "Тема B"},
                }
            ]
        }
    }

@router.post(
    "/chat",
    summary="Объяснение связи (RAG)",
    description="Использует LLM для пояснения семантической связи между двумя узлами, применяя метаданные графа как контекст.",
    response_model=ChatResponse,
    responses={
        400: {"model": ApiError, "description": "Некорректные параметры запроса"},
        502: {"model": ApiError, "description": "Ошибка запроса к LLM"},
        503: {"model": ApiError, "description": "Сервис LLM недоступен"},
    },
)
async def chat(payload: ChatInput) -> Dict:
    """
    Принимает:
      - question: текст вопроса о связи
      - from_uid: UID исходного узла
      - to_uid: UID целевого узла

    Возвращает:
      - answer: текстовое объяснение от LLM
      - usage: метаданные использования токенов модели (если доступны)
      - context: метаданные связи {rel, props, from_title, to_title}
    """
    try:
        from openai import AsyncOpenAI
        from openai import APIConnectionError, APIStatusError, AuthenticationError, RateLimitError
    except Exception:
        raise HTTPException(status_code=503, detail="OpenAI client is not available")

    ctx = relation_context(payload.from_uid, payload.to_uid)
    oai = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())
    messages = [
        {"role": "system", "content": "You are a graph expert. Explain why the relationship exists using provided metadata."},
        {"role": "user", "content": f"Q: {payload.question}\nFrom: {ctx.get('from_title','')} ({payload.from_uid})\nTo: {ctx.get('to_title','')} ({payload.to_uid})\nRelation: {ctx.get('rel','')}\nProps: {ctx.get('props',{})}"},
    ]

    try:
        resp = await oai.chat.completions.create(model="gpt-4o-mini", messages=messages)
    except AuthenticationError:
        raise HTTPException(status_code=503, detail="OpenAI authentication failed (invalid API key)")
    except RateLimitError:
        raise HTTPException(status_code=503, detail="OpenAI rate limit exceeded")
    except APIConnectionError:
        raise HTTPException(status_code=503, detail="OpenAI is unreachable")
    except APIStatusError as e:
        status = getattr(e, "status_code", None)
        if status and 500 <= int(status) < 600:
            raise HTTPException(status_code=503, detail="OpenAI service error")
        raise HTTPException(status_code=502, detail="OpenAI request failed")
    except Exception:
        raise HTTPException(status_code=502, detail="OpenAI request failed")

    usage = resp.usage or None
    answer = resp.choices[0].message.content if resp.choices else ""
    return {"answer": answer, "usage": (usage.model_dump() if hasattr(usage, 'model_dump') else None), "context": ctx}

class RoadmapInput(BaseModel):
    subject_uid: Optional[str] = Field(None, description="UID предмета (например, 'MATH-EGE'). Если None — поиск глобально (не рекомендуется).")
    progress: Dict[str, float] = Field(..., description="Карта прогресса: 'UID узла' -> Уровень освоения (0.0–1.0). 1.0 означает полностью освоено.")
    limit: int = Field(30, description="Максимальное число элементов в ответе.")

class RoadmapItem(BaseModel):
    uid: str
    title: Optional[str] = None
    mastered: float
    missing_prereqs: int
    priority: float

class RoadmapResponse(BaseModel):
    items: List[RoadmapItem]
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "items": [
                        {"uid": "TOP-ALG-1", "title": "Алгебра: основы", "mastered": 0.2, "missing_prereqs": 1, "priority": 0.91},
                        {"uid": "TOP-ALG-2", "title": "Линейные уравнения", "mastered": 0.0, "missing_prereqs": 0, "priority": 0.85},
                    ]
                }
            ]
        }
    }

@router.post(
    "/roadmap",
    summary="Построить адаптивную дорожную карту",
    description="Возвращает персональную последовательность тем на основе текущего прогресса и зависимостей графа (PREREQ).",
    response_model=RoadmapResponse,
    responses={
        400: {"model": ApiError, "description": "Некорректные параметры запроса"},
        404: {"model": ApiError, "description": "Предмет не найден"},
        500: {"model": ApiError, "description": "Внутренняя ошибка сервера"},
    },
)
async def roadmap(payload: RoadmapInput) -> Dict:
    """
    Принимает:
      - subject_uid: UID предмета; если None — глобальный поиск
      - progress: карта прогресса {TopicUID: mastery 0.0–1.0}
      - limit: максимальное число элементов

    Возвращает:
      - items: список объектов {uid, title, mastered, missing_prereqs, priority}
    """
    items = plan_route(payload.subject_uid, payload.progress, limit=payload.limit)
    return {"items": items}

class AdaptiveQuestionsInput(BaseModel):
    subject_uid: Optional[str] = Field(None, description="UID предмета.")
    progress: Dict[str, float] = Field(..., description="Текущий прогресс пользователя.")
    count: int = Field(10, description="Количество вопросов.")
    difficulty_min: int = Field(1, ge=1, le=10, description="Минимальная сложность (1–10).")
    difficulty_max: int = Field(5, ge=1, le=10, description="Максимальная сложность (1–10).")
    exclude: List[str] = Field([], description="Список UID вопросов для исключения (уже отвечены).")

class QuestionDTO(BaseModel):
    uid: Optional[str] = None
    title: Optional[str] = None
    statement: Optional[str] = None
    difficulty: Optional[float] = None
    topic_uid: Optional[str] = None

class AdaptiveQuestionsResponse(BaseModel):
    questions: List[QuestionDTO]
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "questions": [
                        {"uid": "Q-123", "title": "Решите уравнение", "statement": "2x+3=7", "difficulty": 0.4, "topic_uid": "TOP-ALG-2"},
                        {"uid": "Q-456", "title": "График функции", "statement": "y=2x+1", "difficulty": 0.6, "topic_uid": "TOP-ALG-1"},
                    ]
                }
            ]
        }
    }

@router.post(
    "/adaptive_questions",
    summary="Адаптивные вопросы",
    description="Подбирает наиболее релевантные вопросы для «зоны ближайшего развития» ученика.",
    response_model=AdaptiveQuestionsResponse,
    responses={
        400: {"model": ApiError, "description": "Некорректные параметры запроса"},
        500: {"model": ApiError, "description": "Внутренняя ошибка сервера"},
    },
)
async def adaptive_questions(payload: AdaptiveQuestionsInput) -> Dict:
    """
    Принимает:
      - subject_uid: UID предмета
      - progress: текущий прогресс {TopicUID: mastery 0.0–1.0}
      - count: требуемое количество вопросов
      - difficulty_min: минимальная сложность (1–10)
      - difficulty_max: максимальная сложность (1–10)
      - exclude: список UID вопросов для исключения

    Возвращает:
      - questions: список объектов вопросов {uid, title, statement, difficulty 0.0–1.0, topic_uid}
    """
    roadmap = plan_route(payload.subject_uid, payload.progress, limit=payload.count * 3)
    topic_uids = [it["uid"] for it in roadmap] or all_topic_uids_from_examples()
    examples = select_examples_for_topics(
        topic_uids=topic_uids,
        limit=payload.count,
        difficulty_min=payload.difficulty_min,
        difficulty_max=payload.difficulty_max,
        exclude_uids=set(payload.exclude),
    )
    return {"questions": examples}
