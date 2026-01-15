# Codebase Analysis Report

## File: `backend\app\main.py`
### Global Variables
- `tags_metadata = ...`
- `app = ...`
- `REQ_COUNTER = ...`
- `LATENCY = ...`
- `origins = ...`

### Global Functions
#### Function `redoc_html`
```python
@app.get('/redoc', include_in_schema=False)
```
`def redoc_html() -> None`
#### Function `lifespan`
```python
@asynccontextmanager
```
`def lifespan(app: FastAPI) -> None`
#### Function `tenant_middleware`
```python
@app.middleware('http')
```
`def tenant_middleware(request, call_next) -> None`
#### Function `metrics_middleware`
```python
@app.middleware('http')
```
`def metrics_middleware(request, call_next) -> None`
#### Function `_code_for_status`
`def _code_for_status(status: int) -> str`
#### Function `unhandled_exception_handler`
```python
@app.exception_handler(Exception)
```
`def unhandled_exception_handler(request: Request, exc: Exception) -> None`
#### Function `http_exception_handler`
```python
@app.exception_handler(HTTPException)
```
`def http_exception_handler(request: Request, exc: HTTPException) -> None`
#### Function `validation_exception_handler`
```python
@app.exception_handler(RequestValidationError)
```
`def validation_exception_handler(request: Request, exc: RequestValidationError) -> None`
#### Function `health`
```python
@app.get('/health', tags=['Система'], summary='Проверка состояния', description='Возвращает статус доступности ключевых зависимостей.')
```
`def health() -> None`
#### Function `metrics`
```python
@app.get('/metrics', tags=['Система'], summary='Метрики Prometheus', description='Экспорт метрик в формате, совместимом с Prometheus.')
```
`def metrics() -> None`
---

## File: `backend\app\api\admin.py`
### Global Variables
- `router = ...`

---

## File: `backend\app\api\admin_curriculum.py`
### Global Variables
- `router = ...`

### Global Functions
#### Function `admin_create_curriculum`
```python
@router.post('/curriculum', summary='Создать учебный план', description='Создает новый учебный план в Postgres и возвращает его идентификатор.', response_model=CurriculumResponse)
```
`def admin_create_curriculum(payload: CreateCurriculumInput, x_tenant_id: str) -> Dict`

> Принимает:
>   - code: код плана
>   - title: название
>   - standard: образовательный стандарт
>   - language: язык
> 
> Возвращает:
>   - ok: True/False
>   - id: идентификатор созданного плана (при успехе)
>   - error: текст ошибки (если Postgres не настроен)

#### Function `admin_add_curriculum_nodes`
```python
@router.post('/curriculum/nodes', summary='Добавить узлы плана', description='Добавляет узлы (канонические UID) в учебный план с порядком и обязательностью.')
```
`def admin_add_curriculum_nodes(payload: CurriculumNodeInput, x_tenant_id: str) -> Dict`

> Принимает:
>   - code: код плана
>   - nodes: список объектов {kind, canonical_uid, order_index, is_required}
> 
> Возвращает:
>   - ok: True/False
>   - error: текст ошибки (если план не найден или Postgres не настроен)

#### Function `admin_curriculum_graph_view`
```python
@router.get('/curriculum/graph_view', summary='Просмотр плана', description='Возвращает состав учебного плана в виде списка узлов.')
```
`def admin_curriculum_graph_view(code: str) -> Dict`

> Принимает:
>   - code: код плана
> 
> Возвращает:
>   - ok: True/False
>   - nodes: список узлов {kind, canonical_uid, order_index} при успехе
>   - error: текст ошибки

### Classes
#### Class `CreateCurriculumInput(BaseModel)`
**Fields**:
- `code: str`
- `title: str`
- `standard: str`
- `language: str`
#### Class `CurriculumResponse(BaseModel)`
**Fields**:
- `ok: bool`
- `id: Optional[int]`
- `error: Optional[str]`
#### Class `CurriculumNodeInput(BaseModel)`
**Fields**:
- `code: str`
- `nodes: List[Dict]`
---

## File: `backend\app\api\admin_generate.py`
### Global Variables
- `router = ...`

### Global Functions
#### Function `generate_subject`
```python
@router.post('/generate_subject', summary='Генерация предмета (LLM)', description='Генерирует структуру предмета через OpenAI и возвращает результат генерации.')
```
`def generate_subject(payload: GenerateSubjectInput) -> Dict`

> Принимает:
>   - subject_uid: UID предмета
>   - subject_title: название предмета
>   - language: язык генерации
>   - параметры глубины генерации: sections_seed, topics_per_section, skills_per_topic, methods_per_skill, examples_per_topic, concurrency
> 
> Возвращает:
>   - объект результата генерации (асинхронные результаты по шагам)

#### Function `generate_subject_import`
```python
@router.post('/generate_subject_import', summary='Генерация и импорт', description='Генерирует предмет, импортирует в граф, пересчитывает веса и анализирует знания.')
```
`def generate_subject_import(payload: GenerateSubjectInput) -> Dict`

> Принимает:
>   - те же поля, что и generate_subject
> 
> Возвращает:
>   - generated: результат генерации
>   - sync: статистика импорта
>   - weights: результаты пересчета весов
>   - metrics: метрики анализа знаний

### Classes
#### Class `GenerateSubjectInput(BaseModel)`
**Fields**:
- `subject_uid: str`
- `subject_title: str`
- `language: str`
- `sections_seed: List[str] | None`
- `topics_per_section: int`
- `skills_per_topic: int`
- `methods_per_skill: int`
- `examples_per_topic: int`
- `concurrency: int`
---

## File: `backend\app\api\admin_graph.py`
### Global Variables
- `router = ...`

### Global Functions
#### Function `_validate_labels`
`def _validate_labels(labels: List[str]) -> List[str]`
#### Function `_validate_edge_type`
`def _validate_edge_type(t: str) -> str`
#### Function `_validate_props`
`def _validate_props(props: Dict[str, Any]) -> Dict[str, Any]`
#### Function `_execute_admin_proposal`
`def _execute_admin_proposal(tenant_id: str, ops: List[Operation]) -> Dict`
#### Function `create_node`
```python
@router.post('/nodes', summary='Создать узел', description='Создает узел с указанными метками и свойствами (без изменения uid).')
```
`def create_node(payload: NodeCreateInput, x_tenant_id: str) -> Dict`
#### Function `get_node`
```python
@router.get('/nodes/{uid}', summary='Получить узел', description='Возвращает метки и свойства узла по UID.')
```
`def get_node(uid: str, x_tenant_id: str) -> Dict`
#### Function `patch_node`
```python
@router.patch('/nodes/{uid}', summary='Изменить узел', description='Устанавливает/удаляет свойства узла. UID менять нельзя.')
```
`def patch_node(uid: str, payload: NodePatchInput, x_tenant_id: str) -> Dict`
#### Function `delete_node`
```python
@router.delete('/nodes/{uid}', summary='Удалить узел', description='Удаляет узел.')
```
`def delete_node(uid: str, detach: bool, x_tenant_id: str) -> Dict`
#### Function `create_edge`
```python
@router.post('/edges', summary='Создать связь', description='Создает отношение между узлами.')
```
`def create_edge(payload: EdgeCreateInput, x_tenant_id: str) -> Dict`
#### Function `get_edge`
```python
@router.get('/edges/{edge_uid}', summary='Получить связь', description='Возвращает from/to, тип и свойства связи по ее UID.')
```
`def get_edge(edge_uid: str, x_tenant_id: str) -> Dict`
#### Function `list_edges`
```python
@router.get('/edges', summary='Список связей по паре узлов', description='Возвращает список связей между двумя узлами.')
```
`def list_edges(from_uid: str, to_uid: str, type: Optional[str], x_tenant_id: str) -> Dict`
#### Function `patch_edge`
```python
@router.patch('/edges/{edge_uid}', summary='Изменить связь', description='Устанавливает/удаляет свойства отношения.')
```
`def patch_edge(edge_uid: str, payload: EdgePatchInput, x_tenant_id: str) -> Dict`
#### Function `delete_edge`
```python
@router.delete('/edges/{edge_uid}', summary='Удалить связь', description='Удаляет отношение по UID.')
```
`def delete_edge(edge_uid: str, x_tenant_id: str) -> Dict`
### Classes
#### Class `NodeCreateInput(BaseModel)`
**Fields**:
- `uid: str`
- `labels: List[str]`
- `props: Dict[str, Any]`
#### Class `NodePatchInput(BaseModel)`
**Fields**:
- `set: Dict[str, Any]`
- `unset: List[str]`
#### Class `EdgeCreateInput(BaseModel)`
**Fields**:
- `edge_uid: Optional[str]`
- `from_uid: str`
- `to_uid: str`
- `type: str`
- `props: Dict[str, Any]`
#### Class `EdgePatchInput(BaseModel)`
**Fields**:
- `set: Dict[str, Any]`
- `unset: List[str]`
---

## File: `backend\app\api\analytics.py`
### Global Variables
- `router = ...`

### Global Functions
#### Function `stats`
```python
@router.get('/stats', summary='Метрики графа', description='Возвращает сводные метрики графа знаний (число узлов, плотность, средняя исходящая степень).', response_model=StatsResponse, responses={500: {'description': 'Внутренняя ошибка сервера', 'content': {'application/json': {'example': {'code': 'internal_error', 'message': 'graph store unavailable'}}}}})
```
`def stats() -> Dict`

> Принимает:
>   - нет входных параметров
> 
> Возвращает:
>   - graph.total_nodes: количество узлов
>   - graph.avg_out_degree: средняя исходящая степень
>   - graph.density: плотность графа
>   - ai.*: заглушки метрик использования ИИ
>   - quality.*: заглушки метрик качества контента

### Classes
#### Class `GraphStats(BaseModel)`
**Fields**:
- `total_nodes: int`
- `avg_out_degree: float`
- `density: float`
#### Class `AIStats(BaseModel)`
**Fields**:
- `tokens_input: int`
- `tokens_output: int`
- `cost_usd: float`
- `latency_ms: int`
#### Class `QualityStats(BaseModel)`
**Fields**:
- `orphans: int`
- `auto_merged: int`
#### Class `StatsResponse(BaseModel)`
**Fields**:
- `graph: GraphStats`
- `ai: AIStats`
- `quality: QualityStats`
---

## File: `backend\app\api\assessment.py`
### Global Variables
- `router = ...`

### Global Functions
#### Function `_get_session`
`def _get_session(sid: str) -> Optional[Dict]`
#### Function `_save_session`
`def _save_session(sid: str, data: Dict) -> None`
#### Function `_age_to_class`
`def _age_to_class(age: Optional[int]) -> int`
#### Function `_topic_accessible`
`def _topic_accessible(subject_uid: str, topic_uid: str, resolved_user_class: int) -> bool`
#### Function `_select_question`
`def _select_question(topic_uid: str, difficulty_min: int, difficulty_max: int) -> Dict`
#### Function `start`
```python
@router.post('/start', response_model=StandardResponse, responses={400: {'model': ApiError}, 404: {'model': ApiError}})
```
`def start(payload: StartRequest) -> Dict`
#### Function `_evaluate`
`def _evaluate(answer: AnswerDTO) -> float`
#### Function `_confidence`
`def _confidence(sess: Dict) -> float`
#### Function `_next_question`
`def _next_question(sess: Dict) -> Optional[Dict]`
#### Function `next_question`
```python
@router.post('/next', responses={400: {'model': ApiError}})
```
`def next_question(payload: NextRequest) -> None`
### Classes
#### Class `UserContext(BaseModel)`
**Fields**:
- `user_class: Optional[int]`
- `age: Optional[int]`
#### Class `StartRequest(BaseModel)`
**Fields**:
- `subject_uid: str`
- `topic_uid: str`
- `user_context: UserContext`
#### Class `OptionDTO(BaseModel)`
**Fields**:
- `option_uid: str`
- `text: str`
#### Class `QuestionDTO(BaseModel)`
**Fields**:
- `question_uid: str`
- `subject_uid: str`
- `topic_uid: str`
- `type: str`
- `prompt: str`
- `options: List[OptionDTO]`
- `meta: Dict`
#### Class `StartResponse(BaseModel)`
**Fields**:
- `assessment_session_id: str`
- `question: QuestionDTO`
#### Class `AnswerDTO(BaseModel)`
**Fields**:
- `selected_option_uids: List[str]`
- `text: Optional[str]`
- `value: Optional[float]`

**Methods**:
- `check_not_empty(self) -> None`
#### Class `ClientMeta(BaseModel)`
**Fields**:
- `time_spent_ms: Optional[int]`
- `attempt: Optional[int]`
#### Class `NextRequest(BaseModel)`
**Fields**:
- `assessment_session_id: str`
- `question_uid: str`
- `answer: AnswerDTO`
- `client_meta: Optional[ClientMeta]`
---

## File: `backend\app\api\assistant.py`
### Global Variables
- `router = ...`

### Global Functions
#### Function `tools`
```python
@router.get('/tools', summary='Список инструментов ассистента', description='Возвращает перечень доступных возможностей ИИ-ассистента.', response_model=ToolsResponse)
```
`def tools() -> Dict`

> Принимает:
>   - нет входных параметров
> 
> Возвращает:
>   - tools: список объектов {name, description} доступных действий ассистента

#### Function `chat`
```python
@router.post('/chat', summary='Чат с ИИ-ассистентом', description='Единая точка для ИИ-ассистента. Поддерживает общий диалог или выполнение действий (дорожная карта, аналитика и т.д.) через поле `action`.', responses={400: {'model': ApiError, 'description': 'Некорректные параметры запроса'}, 502: {'model': ApiError, 'description': 'Ошибка запроса к LLM'}, 503: {'model': ApiError, 'description': 'Сервис LLM недоступен'}})
```
`def chat(payload: AssistantChatInput) -> Dict`

> Принимает:
>   - action: одно из [explain_relation, viewport, roadmap, analytics, questions] или None для свободного ответа
>   - message: текст вопроса
>   - context-поля: from_uid/to_uid/center_uid/depth/subject_uid/progress и параметры генерации
> 
> Возвращает:
>   - В зависимости от action:
>     - explain_relation: {answer, usage, context}
>     - viewport: {nodes, edges, center_uid, depth}
>     - roadmap: {items}
>     - analytics: метрики графа
>     - questions: {questions}
>   - Свободный ответ: {answer, usage}

### Classes
#### Class `ToolInfo(BaseModel)`
**Fields**:
- `name: str`
- `description: str`
#### Class `ToolsResponse(BaseModel)`
**Fields**:
- `tools: List[ToolInfo]`
#### Class `AssistantChatInput(BaseModel)`
**Fields**:
- `action: Optional[Literal['explain_relation', 'viewport', 'roadmap', 'analytics', 'questions']]`
- `message: str`
- `from_uid: Optional[str]`
- `to_uid: Optional[str]`
- `center_uid: Optional[str]`
- `depth: int`
- `subject_uid: Optional[str]`
- `progress: Dict[str, float]`
- `limit: int`
- `count: int`
- `difficulty_min: int`
- `difficulty_max: int`
- `exclude: List[str]`
---

## File: `backend\app\api\auth.py`
### Global Variables
- `router = ...`

### Global Functions
#### Function `_bearer_token`
`def _bearer_token(authorization: str | None) -> str | None`
#### Function `register`
```python
@router.post('/register', summary='Регистрация', description='Создает пользователя и возвращает его идентификатор и email.', response_model=RegisterResponse)
```
`def register(payload: RegisterPayload) -> Dict`

> Принимает:
>   - email: почта пользователя
>   - password: пароль в открытом виде
> 
> Возвращает:
>   - ok: True
>   - id: идентификатор пользователя
>   - email: почта пользователя

#### Function `login`
```python
@router.post('/login', summary='Вход', description='Проверяет учетные данные и возвращает пару токенов (access/refresh).', response_model=LoginResponse)
```
`def login(payload: LoginPayload) -> Dict`

> Принимает:
>   - email: почта пользователя
>   - password: пароль
> 
> Возвращает:
>   - access_token: JWT-токен доступа
>   - refresh_token: JWT-токен обновления
>   - token_type: 'bearer'

#### Function `refresh`
```python
@router.post('/refresh', summary='Обновление токена', description='Обновляет пару токенов по действительному refresh токену.', response_model=RefreshResponse)
```
`def refresh(payload: RefreshPayload) -> Dict`

> Принимает:
>   - refresh_token: валидный токен обновления
> 
> Возвращает:
>   - access_token: новый токен доступа
>   - refresh_token: новый токен обновления
>   - token_type: 'bearer'

#### Function `me`
```python
@router.get('/me', summary='Текущий пользователь', description='Возвращает информацию о пользователе по access-токену.', response_model=MeResponse)
```
`def me(authorization: str | None) -> Dict`

> Принимает:
>   - Authorization: заголовок формата 'Bearer <access_token>'
> 
> Возвращает:
>   - id: идентификатор пользователя
>   - email: почта
>   - role: роль пользователя

### Classes
#### Class `RegisterPayload(BaseModel)`
**Fields**:
- `email: str`
- `password: str`
#### Class `LoginPayload(BaseModel)`
**Fields**:
- `email: str`
- `password: str`
#### Class `RefreshPayload(BaseModel)`
**Fields**:
- `refresh_token: str`
#### Class `RegisterResponse(BaseModel)`
**Fields**:
- `ok: bool`
- `id: int`
- `email: str`
- `model_config = ...`
#### Class `LoginResponse(BaseModel)`
**Fields**:
- `access_token: str`
- `refresh_token: str`
- `token_type: str`
- `model_config = ...`
#### Class `RefreshResponse(BaseModel)`
**Fields**:
- `access_token: str`
- `refresh_token: str`
- `token_type: str`
- `model_config = ...`
#### Class `MeResponse(BaseModel)`
**Fields**:
- `id: int`
- `email: str`
- `role: str`
- `model_config = ...`
---

## File: `backend\app\api\common.py`
### Classes
#### Class `ApiError(BaseModel)`
**Fields**:
- `code: str`
- `message: str`
- `target: Optional[str]`
- `details: Optional[Dict[str, Any]]`
- `request_id: Optional[str]`
- `correlation_id: Optional[str]`
- `model_config = ...`
#### Class `StandardResponse(BaseModel)`
**Fields**:
- `items: List[Any]`
- `meta: Dict[str, Any]`
---

## File: `backend\app\api\construct.py`
### Global Variables
- `router = ...`

### Global Functions
#### Function `magic_fill`
```python
@router.post('/magic_fill')
```
`def magic_fill(payload: MagicFillInput) -> Dict`
#### Function `magic_fill_queue`
```python
@router.post('/magic_fill/queue')
```
`def magic_fill_queue(payload: MagicFillInput) -> Dict`
#### Function `propose`
```python
@router.post('/propose')
```
`def propose(payload: ProposeInput) -> Dict`
### Classes
#### Class `MagicFillInput(BaseModel)`
**Fields**:
- `topic_uid: str`
- `topic_title: str`
- `language: str`
#### Class `ProposeInput(BaseModel)`
**Fields**:
- `subject_uid: str | None`
- `text: str`
- `language: str`
---

## File: `backend\app\api\curriculum.py`
### Global Variables
- `router = ...`

### Global Functions
#### Function `pathfind`
```python
@router.post('/pathfind', summary='Построить порядок темы', description='Возвращает упорядоченный список тем из транзитивного замыкания PREREQ для указанной цели.', response_model=PathfindResponse)
```
`def pathfind(payload: PathfindInput) -> Dict`

> Принимает:
>   - target_uid: UID конечной темы
> 
> Возвращает:
>   - target: исходный UID
>   - path: упорядоченный список UID тем для прохождения

#### Function `roadmap`
```python
@router.post('/roadmap', summary='Построить учебный маршрут', description='Возвращает отсортированный по приоритету список тем с учётом прогресса и недостающих PREREQ.', response_model=RoadmapResponse)
```
`def roadmap(payload: RoadmapInput) -> Dict`
### Classes
#### Class `PathfindInput(BaseModel)`
**Fields**:
- `target_uid: str`
#### Class `PathfindResponse(BaseModel)`
**Fields**:
- `target: str`
- `path: List[str]`
#### Class `RoadmapInput(BaseModel)`
**Fields**:
- `subject_uid: str | None`
- `progress: Dict[str, float]`
- `limit: int`
- `penalty_factor: float`
#### Class `RoadmapItem(BaseModel)`
**Fields**:
- `uid: str`
- `title: str | None`
- `mastered: float`
- `missing_prereqs: int`
- `priority: float`
#### Class `RoadmapResponse(BaseModel)`
**Fields**:
- `items: List[RoadmapItem]`
---

## File: `backend\app\api\deps.py`
### Global Functions
#### Function `_bearer_token`
`def _bearer_token(authorization: str | None) -> str | None`
#### Function `get_current_user`
`def get_current_user(authorization: str | None) -> None`
#### Function `require_admin`
`def require_admin(authorization: str | None) -> None`
---

## File: `backend\app\api\errors.py`
### Global Variables
- `logger = ...`

### Global Functions
#### Function `http_error_response`
`def http_error_response(status_code: int, message: str, details: Any) -> None`
#### Function `http_exception_handler`
`def http_exception_handler(request: Request, exc: StarletteHTTPException) -> None`
#### Function `validation_exception_handler`
`def validation_exception_handler(request: Request, exc: RequestValidationError) -> None`
#### Function `global_exception_handler`
`def global_exception_handler(request: Request, exc: Exception) -> None`
---

## File: `backend\app\api\graph.py`
### Global Variables
- `router = ...`

### Global Functions
#### Function `get_node`
```python
@router.get('/node/{uid}', response_model=StandardResponse)
```
`def get_node(uid: str) -> Dict`
#### Function `viewport`
```python
@router.get('/viewport', response_model=StandardResponse)
```
`def viewport(center_uid: str, depth: int) -> Dict`

> Принимает:
>   - center_uid: UID центрального узла
>   - depth: глубина обхода (целое, рекомендовано 1–3)
> 
> Возвращает:
>   - nodes: список объектов узлов {id, uid, label, labels}
>   - edges: список объектов связей {from, to, type}
>   - center_uid: исходный UID
>   - depth: фактическая глубина обхода

#### Function `chat`
```python
@router.post('/chat', summary='Объяснение связи (RAG)', description='Использует LLM для пояснения семантической связи между двумя узлами, применяя метаданные графа как контекст.', response_model=ChatResponse, responses={400: {'model': ApiError, 'description': 'Некорректные параметры запроса'}, 502: {'model': ApiError, 'description': 'Ошибка запроса к LLM'}, 503: {'model': ApiError, 'description': 'Сервис LLM недоступен'}})
```
`def chat(payload: ChatInput) -> Dict`

> Принимает:
>   - question: текст вопроса о связи
>   - from_uid: UID исходного узла
>   - to_uid: UID целевого узла
> 
> Возвращает:
>   - answer: текстовое объяснение от LLM
>   - usage: метаданные использования токенов модели (если доступны)
>   - context: метаданные связи {rel, props, from_title, to_title}

#### Function `roadmap`
```python
@router.post('/roadmap', summary='Построить адаптивную дорожную карту', description='Возвращает персональную последовательность тем на основе текущего прогресса и зависимостей графа (PREREQ).', response_model=StandardResponse, responses={400: {'model': ApiError, 'description': 'Некорректные параметры запроса'}, 404: {'model': ApiError, 'description': 'Предмет не найден'}, 500: {'model': ApiError, 'description': 'Внутренняя ошибка сервера'}})
```
`def roadmap(payload: RoadmapInput) -> Dict`

> Принимает:
>   - subject_uid: UID предмета; если None — глобальный поиск
>   - progress: карта прогресса {TopicUID: mastery 0.0–1.0}
>   - limit: максимальное число элементов
> 
> Возвращает:
>   - items: список объектов {uid, title, mastered, missing_prereqs, priority}

#### Function `adaptive_questions`
```python
@router.post('/adaptive_questions', summary='Адаптивные вопросы', description='Подбирает наиболее релевантные вопросы для «зоны ближайшего развития» ученика.', response_model=StandardResponse, responses={400: {'model': ApiError, 'description': 'Некорректные параметры запроса'}, 500: {'model': ApiError, 'description': 'Внутренняя ошибка сервера'}})
```
`def adaptive_questions(payload: AdaptiveQuestionsInput) -> Dict`

> Принимает:
>   - subject_uid: UID предмета
>   - progress: текущий прогресс {TopicUID: mastery 0.0–1.0}
>   - count: требуемое количество вопросов
>   - difficulty_min: минимальная сложность (1–10)
>   - difficulty_max: максимальная сложность (1–10)
>   - exclude: список UID вопросов для исключения
> 
> Возвращает:
>   - questions: список объектов вопросов {uid, title, statement, difficulty 0.0–1.0, topic_uid}

### Classes
#### Class `ViewportQuery(BaseModel)`
**Fields**:
- `center_uid: str`
- `depth: int`
#### Class `NodeDTO(BaseModel)`
**Fields**:
- `id: int`
- `uid: Optional[str]`
- `label: Optional[str]`
- `labels: List[str]`
#### Class `EdgeDTO(BaseModel)`
**Fields**:
- `from_: int`
- `to: int`
- `type: str`
#### Class `ViewportResponse(BaseModel)`
**Fields**:
- `nodes: List[NodeDTO]`
- `edges: List[EdgeDTO]`
- `center_uid: str`
- `depth: int`
- `model_config = ...`
#### Class `ChatInput(BaseModel)`
**Fields**:
- `question: str`
- `from_uid: str`
- `to_uid: str`
#### Class `ChatUsage(BaseModel)`
**Fields**:
- `completion_tokens: Optional[int]`
- `prompt_tokens: Optional[int]`
- `total_tokens: Optional[int]`
#### Class `RelationContext(BaseModel)`
**Fields**:
- `rel: Optional[str]`
- `props: Dict`
- `from_title: Optional[str]`
- `to_title: Optional[str]`
#### Class `ChatResponse(BaseModel)`
**Fields**:
- `answer: str`
- `usage: Optional[Dict]`
- `context: RelationContext`
- `model_config = ...`
#### Class `RoadmapInput(BaseModel)`
**Fields**:
- `subject_uid: Optional[str]`
- `progress: Dict[str, float]`
- `limit: int`
#### Class `RoadmapItem(BaseModel)`
**Fields**:
- `uid: str`
- `title: Optional[str]`
- `mastered: float`
- `missing_prereqs: int`
- `priority: float`
#### Class `RoadmapResponse(BaseModel)`
**Fields**:
- `items: List[RoadmapItem]`
- `model_config = ...`
#### Class `AdaptiveQuestionsInput(BaseModel)`
**Fields**:
- `subject_uid: Optional[str]`
- `progress: Dict[str, float]`
- `count: int`
- `difficulty_min: int`
- `difficulty_max: int`
- `exclude: List[str]`
#### Class `QuestionDTO(BaseModel)`
**Fields**:
- `uid: Optional[str]`
- `title: Optional[str]`
- `statement: Optional[str]`
- `difficulty: Optional[float]`
- `topic_uid: Optional[str]`
#### Class `AdaptiveQuestionsResponse(BaseModel)`
**Fields**:
- `questions: List[QuestionDTO]`
- `model_config = ...`
---

## File: `backend\app\api\graphql.py`
### Global Variables
- `BASE_DIR = ...`
- `KB_DIR = ...`
- `schema = ...`
- `router = ...`

### Global Functions
#### Function `_load_jsonl`
`def _load_jsonl(filename: str) -> None`
#### Function `_graph_from_subject`
`def _graph_from_subject(subject_uid: Optional[str]) -> GraphView`
#### Function `_topic_details`
`def _topic_details(uid: str) -> TopicDetails`
#### Function `_error_details`
`def _error_details(uid: str) -> ErrorNode`
### Classes
#### Class `Node`
**Fields**:
- `uid: str`
- `title: str`
- `type: str`
#### Class `Edge`
**Fields**:
- `source: str`
- `target: str`
- `rel: str`
#### Class `GraphView`
**Fields**:
- `nodes: List[Node]`
- `edges: List[Edge]`
#### Class `Goal`
**Fields**:
- `uid: str`
- `title: str`
#### Class `Objective`
**Fields**:
- `uid: str`
- `title: str`
#### Class `Example`
**Fields**:
- `uid: str`
- `title: str`
- `statement: str`
- `difficulty: float`
#### Class `ErrorNode`
**Fields**:
- `uid: str`
- `title: str`
- `triggers: List[Node]`
- `examples: List[Example]`
#### Class `TopicDetails`
**Fields**:
- `uid: str`
- `title: str`
- `prereqs: List[Node]`
- `goals: List[Goal]`
- `objectives: List[Objective]`
- `methods: List[Node]`
- `examples: List[Example]`
- `errors: List[Node]`
#### Class `Query`

**Methods**:
- `graph(self, subject_uid: Optional[str]) -> GraphView`
- `topic(self, uid: str) -> TopicDetails`
- `error(self, uid: str) -> ErrorNode`
---

## File: `backend\app\api\kb.py`
### Global Variables
- `router = ...`

### Global Functions
#### Function `generate_smart`
```python
@router.post('/generate_smart')
```
`def generate_smart(req: GenerateRequest) -> Dict`
### Classes
#### Class `GenerateRequest(BaseModel)`
**Fields**:
- `subject: str`
- `language: str`
- `import_into_graph: Optional[bool]`
- `limits: Optional[Dict]`
---

## File: `backend\app\api\knowledge.py`
### Global Variables
- `router = ...`

### Global Functions
#### Function `_age_to_class`
`def _age_to_class(age: Optional[int]) -> int`
#### Function `topics_available`
```python
@router.post('/topics/available', responses={400: {'model': ApiError}}, response_model=StandardResponse)
```
`def topics_available(payload: TopicsAvailableRequest) -> Dict`
### Classes
#### Class `UserContext(BaseModel)`
**Fields**:
- `user_class: Optional[int]`
- `age: Optional[int]`
#### Class `TopicsAvailableRequest(BaseModel)`
**Fields**:
- `subject_uid: Optional[str]`
- `subject_title: Optional[str]`
- `user_context: UserContext`
#### Class `TopicItem(BaseModel)`
**Fields**:
- `topic_uid: str`
- `title: Optional[str]`
- `user_class_min: Optional[int]`
- `user_class_max: Optional[int]`
- `difficulty_band: Optional[str]`
- `prereq_topic_uids: List[str]`
#### Class `TopicsAvailableResponse(BaseModel)`
**Fields**:
- `subject_uid: str`
- `resolved_user_class: int`
- `topics: List[TopicItem]`
---

## File: `backend\app\api\levels.py`
### Global Variables
- `router = ...`

### Global Functions
#### Function `level_topic`
```python
@router.get('/topic/{uid}', summary='Уровень темы', description='Возвращает уровень освоения темы для статeless-пользователя.')
```
`def level_topic(uid: str) -> Dict`

> Принимает:
>   - uid: UID темы
> 
> Возвращает:
>   - объект уровня навыка/темы согласно алгоритму get_user_topic_level

#### Function `level_skill`
```python
@router.get('/skill/{uid}', summary='Уровень навыка', description='Возвращает уровень освоения навыка для статeless-пользователя.')
```
`def level_skill(uid: str) -> Dict`

> Принимает:
>   - uid: UID навыка
> 
> Возвращает:
>   - объект уровня навыка согласно алгоритму get_user_skill_level

---

## File: `backend\app\api\maintenance.py`
### Global Variables
- `router = ...`

### Global Functions
#### Function `kb_rebuild_async`
```python
@router.post('/kb/rebuild_async', summary='Асинхронная пересборка KB', description='Запускает задачу пересборки базы знаний (ARQ/Redis), возвращает job_id и WebSocket для прогресса.', response_model=StandardResponse)
```
`def kb_rebuild_async(x_tenant_id: str) -> Dict`

> Принимает:
>   - нет входных параметров
> 
> Возвращает:
>   - job_id: идентификатор задачи
>   - queued: признак постановки в очередь
>   - ws: путь WebSocket для отслеживания прогресса

#### Function `kb_pipeline_async`
```python
@router.post('/kb/pipeline_async', summary='Асинхронный конвейер KB', description='Запускает конвейер пересборки, опционально публикует результаты после валидации.', response_model=StandardResponse)
```
`def kb_pipeline_async(auto_publish: bool, x_tenant_id: str) -> Dict`

> Принимает:
>   - auto_publish: публиковать ли автоматически после успешной валидации
> 
> Возвращает:
>   - job_id: идентификатор задачи
>   - queued: признак постановки в очередь
>   - ws: путь WebSocket
>   - auto_publish: отражение входного параметра

#### Function `kb_rebuild_status`
```python
@router.get('/kb/rebuild_status', summary='Статус пересборки', description='Возвращает статус задачи пересборки по job_id.', response_model=StandardResponse)
```
`def kb_rebuild_status(job_id: str) -> Dict`

> Принимает:
>   - job_id: идентификатор задачи
> 
> Возвращает:
>   - объект статуса пересборки

#### Function `kb_rebuild_state`
```python
@router.get('/kb/rebuild_state', summary='Текущее состояние пересборки', description='Возвращает текущее состояние пересборки (из Redis) или из резервного источника.', response_model=StandardResponse)
```
`def kb_rebuild_state(job_id: str) -> Dict`

> Принимает:
>   - job_id: идентификатор задачи
> 
> Возвращает:
>   - объект текущего состояния

#### Function `kb_validate_state`
```python
@router.get('/kb/validate_state', summary='Состояние валидации', description='Возвращает состояние результата валидации по job_id.', response_model=StandardResponse)
```
`def kb_validate_state(job_id: str) -> Dict`

> Принимает:
>   - job_id: идентификатор задачи
> 
> Возвращает:
>   - объект результата валидации

#### Function `kb_validate_async`
```python
@router.post('/kb/validate_async', summary='Асинхронная валидация', description='Ставит задачу валидации графа в очередь.', response_model=StandardResponse)
```
`def kb_validate_async(job_id: str, subject_uid: str | None, x_tenant_id: str) -> Dict`

> Принимает:
>   - job_id: идентификатор задачи
>   - subject_uid: опционально, конкретный предмет для валидации
> 
> Возвращает:
>   - job_id: идентификатор задачи
>   - queued: признак постановки в очередь
>   - ws: путь WebSocket

#### Function `kb_publish`
```python
@router.post('/kb/publish', summary='Публикация валидированного графа', description='Публикует результат пересборки, если валидация прошла успешно.', response_model=StandardResponse)
```
`def kb_publish(job_id: str, x_tenant_id: str) -> Dict`

> Принимает:
>   - job_id: идентификатор задачи валидации
> 
> Возвращает:
>   - ok: признак успеха
>   - published_at: отметка времени публикации
>   - job_id: идентификатор задачи

#### Function `kb_published`
```python
@router.get('/kb/published', summary='Текущая опубликованная версия', description='Возвращает метаданные последней опубликованной версии графа.', response_model=StandardResponse)
```
`def kb_published() -> Dict`

> Принимает:
>   - нет входных параметров
> 
> Возвращает:
>   - status: 'none' если не публиковалось
>   - иначе объект метаданных публикации

#### Function `recompute_links`
```python
@router.post('/recompute_links', summary='Пересчет весов связей', description='Пересчитывает статические веса отношений в графе.', response_model=StandardResponse)
```
`def recompute_links(x_tenant_id: str) -> Dict`

> Принимает:
>   - нет входных параметров
> 
> Возвращает:
>   - ok: True
>   - stats: объект статистики пересчета

#### Function `run_integrity_async`
```python
@router.post('/proposals/run_integrity_async', summary='Асинхронная проверка целостности заявок', description='Запускает проверку заявок на целостность в фоне.', response_model=StandardResponse)
```
`def run_integrity_async(limit: int, x_tenant_id: str) -> Dict`

> Принимает:
>   - limit: количество заявок для обработки за запуск
> 
> Возвращает:
>   - ok: True
>   - processed: количество обработанных заявок

#### Function `publish_outbox`
```python
@router.post('/events/publish_outbox', summary='Публикация событий из Outbox', description='Публикует накопленные события из Outbox.', response_model=StandardResponse)
```
`def publish_outbox(limit: int, x_tenant_id: str) -> Dict`

> Принимает:
>   - limit: максимальное количество событий для публикации
> 
> Возвращает:
>   - ok: True
>   - processed: количество опубликованных событий

### Classes
#### Class `JobQueuedResponse(BaseModel)`
**Fields**:
- `job_id: str`
- `queued: bool`
- `ws: Optional[str]`
- `auto_publish: Optional[bool]`
#### Class `PublishResponse(BaseModel)`
**Fields**:
- `ok: bool`
- `published_at: Optional[int]`
- `job_id: Optional[str]`
- `status: Optional[str]`
#### Class `ProcessedResponse(BaseModel)`
**Fields**:
- `ok: bool`
- `processed: int`
---

## File: `backend\app\api\proposals.py`
### Global Variables
- `router = ...`

### Global Functions
#### Function `require_tenant`
`def require_tenant() -> str`
#### Function `create_proposal`
```python
@router.post('', summary='Создать черновик заявки', description='Создает новую заявку на изменение графа. Проверяет структуру и фиксирует checksum, но не применяет изменения.', response_model=StandardResponse)
```
`def create_proposal(payload: CreateProposalInput, tenant_id: str, x_tenant_id: str) -> Dict`

> Принимает:
>   - base_graph_version: версия графа-основания для ребейза
>   - operations: список операций [{op_id, op_type, target_id/temp_id, properties_delta, match_criteria, evidence, semantic_impact, requires_review}]
> 
> Возвращает:
>   - proposal_id: идентификатор заявки
>   - proposal_checksum: детерминированная контрольная сумма содержимого
>   - status: текущий статус (DRAFT)

#### Function `commit`
```python
@router.post('/{proposal_id}/commit', summary='Commit Proposal', description='Applies the proposal to the Neo4j graph. This operation is atomic and updates the graph version.', response_model=StandardResponse)
```
`def commit(proposal_id: str, tenant_id: str, x_tenant_id: str) -> Dict`

> Принимает:
>   - proposal_id: идентификатор заявки
> 
> Возвращает:
>   - ok: признак успешного применения
>   - status: DONE | FAILED | CONFLICT | ASYNC_CHECK_REQUIRED
>   - graph_version: новая версия графа (если успешно)
>   - violations: детали нарушений целостности (если есть)
>   - error: текст ошибки (если есть)

#### Function `get`
```python
@router.get('/{proposal_id}', summary='Получить детали заявки', description='Возвращает данные по конкретной заявке: операции, статус и метаданные.')
```
`def get(proposal_id: str, tenant_id: str) -> Dict`

> Принимает:
>   - proposal_id: идентификатор заявки
> 
> Возвращает:
>   - объект заявки из БД: {tenant_id, base_graph_version, status, operations_json}

#### Function `list`
```python
@router.get('', summary='Список заявок', description='Возвращает список заявок, с фильтрацией по статусу и пагинацией.')
```
`def list(status: str | None, limit: int, offset: int, tenant_id: str) -> Dict`

> Принимает:
>   - status: фильтр по статусу
>   - limit: лимит
>   - offset: смещение
> 
> Возвращает:
>   - items: список заявок
>   - limit, offset: параметры пагинации

#### Function `approve`
```python
@router.post('/{proposal_id}/approve', summary='Одобрить заявку', description='Помечает заявку как APPROVED и пытается применить изменения к графу.', response_model=StandardResponse)
```
`def approve(proposal_id: str, tenant_id: str, x_tenant_id: str) -> Dict`

> Принимает:
>   - proposal_id: идентификатор заявки
> 
> Возвращает:
>   - результат коммита (см. /commit): {ok, status, graph_version, ...}

#### Function `reject`
```python
@router.post('/{proposal_id}/reject', summary='Reject Proposal', description='Marks a proposal as REJECTED. It cannot be committed afterwards.')
```
`def reject(proposal_id: str, tenant_id: str, x_tenant_id: str) -> Dict`

> Принимает:
>   - proposal_id: идентификатор заявки
> 
> Возвращает:
>   - ok: True
>   - status: REJECTED

#### Function `diff`
```python
@router.get('/{proposal_id}/diff', summary='Diff по заявке', description='Генерирует наглядный diff (до/после) по операциям заявки для ревью.')
```
`def diff(proposal_id: str, tenant_id: str) -> Dict`

> Принимает:
>   - proposal_id: идентификатор заявки
> 
> Возвращает:
>   - diff: объект различий (до/после) и фрагменты доказательств (evidence)

#### Function `impact`
```python
@router.get('/{proposal_id}/impact', summary='Calculate Proposal Impact', description='Analyzes which parts of the graph will be affected by this proposal (Impact Analysis).')
```
`def impact(proposal_id: str, depth: int, types: str | None, max_nodes: int | None, max_edges: int | None, tenant_id: str) -> Dict`

> Принимает:
>   - proposal_id: идентификатор заявки
>   - depth: глубина анализа
> 
> Возвращает:
>   - подграф влияния: узлы и связи, затрагиваемые предложенными изменениями

### Classes
#### Class `CreateProposalResponse(BaseModel)`
**Fields**:
- `proposal_id: str`
- `proposal_checksum: str`
- `status: str`
#### Class `CommitResponse(BaseModel)`
**Fields**:
- `ok: bool`
- `status: str`
- `graph_version: Optional[int]`
- `violations: Optional[Dict]`
- `error: Optional[str]`
#### Class `CreateProposalInput(BaseModel)`
**Fields**:
- `base_graph_version: int`
- `operations: List[Dict]`
---

## File: `backend\app\api\reasoning.py`
### Global Variables
- `router = ...`

### Global Functions
#### Function `gaps`
```python
@router.post('/gaps', response_model=StandardResponse, responses={400: {'model': ApiError}})
```
`def gaps(req: GapsRequest) -> None`
#### Function `next_best_topic`
```python
@router.post('/next-best-topic', response_model=StandardResponse, responses={400: {'model': ApiError}})
```
`def next_best_topic(req: NextBestRequest) -> None`
#### Function `roadmap`
```python
@router.post('/roadmap', response_model=StandardResponse, responses={400: {'model': ApiError}})
```
`def roadmap(req: RoadmapRequest) -> None`
#### Function `mastery_update`
```python
@router.post('/mastery/update', response_model=StandardResponse, responses={400: {'model': ApiError}})
```
`def mastery_update(req: MasteryUpdateRequest) -> None`
### Classes
#### Class `Progress(BaseModel)`
**Fields**:
- `topics: Dict[str, float]`
- `skills: Dict[str, float]`
#### Class `GapsRequest(BaseModel)`
**Fields**:
- `subject_uid: str`
- `progress: Dict[str, float]`
- `goals: Optional[List[str]]`
- `prereq_threshold: float`
#### Class `NextBestRequest(BaseModel)`
**Fields**:
- `subject_uid: str`
- `progress: Dict[str, float]`
- `prereq_threshold: float`
- `top_k: int`
- `alpha: float`
- `beta: float`
#### Class `RoadmapRequest(BaseModel)`
**Fields**:
- `subject_uid: str`
- `progress: Dict[str, float]`
- `goals: Optional[List[str]]`
- `prereq_threshold: float`
- `top_k: int`
#### Class `MasteryUpdateRequest(BaseModel)`
**Fields**:
- `entity_uid: str`
- `kind: str`
- `score: float`
- `prior_mastery: float`
- `confidence: Optional[float]`
---

## File: `backend\app\api\user.py`
### Global Variables
- `router = ...`

### Global Functions
#### Function `compute_topic_weight`
```python
@router.post('/compute_topic_weight')
```
`def compute_topic_weight(payload: ComputeTopicInput) -> Dict`
#### Function `compute_skill_weight`
```python
@router.post('/compute_skill_weight')
```
`def compute_skill_weight(payload: ComputeSkillInput) -> Dict`
#### Function `user_roadmap`
```python
@router.post('/roadmap')
```
`def user_roadmap(payload: UserRoadmapInput) -> Dict`
### Classes
#### Class `ComputeTopicInput(BaseModel)`
**Fields**:
- `topic_uid: str`
- `score: float`
- `base_weight: float | None`
#### Class `ComputeSkillInput(BaseModel)`
**Fields**:
- `skill_uid: str`
- `score: float`
- `base_weight: float | None`
#### Class `UserRoadmapInput(BaseModel)`
**Fields**:
- `subject_uid: str | None`
- `progress: Dict[str, float]`
- `limit: int`
---

## File: `backend\app\api\validation.py`
### Global Variables
- `router = ...`

### Global Functions
#### Function `graph_snapshot`
```python
@router.post('/graph_snapshot', summary='Валидация снимка графа', description='Проверяет канонический снимок графа на согласованность и правила целостности.', response_model=ValidationResult, responses={422: {'model': ApiError, 'description': 'Неверная структура снапшота'}})
```
`def graph_snapshot(payload: GraphSnapshotInput) -> Dict`

> Принимает:
>   - snapshot: объект с полями nodes и edges
> 
> Возвращает:
>   - ok: флаг корректности
>   - errors: список ошибок
>   - warnings: список предупреждений

### Classes
#### Class `GraphSnapshotInput(BaseModel)`
**Fields**:
- `snapshot: Dict`
#### Class `ValidationResult(BaseModel)`
**Fields**:
- `ok: bool`
- `errors: list[str]`
- `warnings: list[str]`
---

## File: `backend\app\api\ws.py`
### Global Variables
- `router = ...`

### Global Functions
#### Function `ws_progress`
```python
@router.websocket('/ws/progress')
```
`def ws_progress(ws: WebSocket) -> None`

> Принимает:
>   - query param job_id: идентификатор фоновой задачи
> 
> Возвращает:
>   - поток сообщений JSON с обновлениями прогресса задачи

---

## File: `backend\app\config\settings.py`
### Global Variables
- `settings = ...`

### Global Functions
#### Function `get_settings`
```python
@lru_cache(maxsize=1)
```
`def get_settings() -> Settings`
### Classes
#### Class `AppEnv(StrEnum)`
**Fields**:
- `dev = ...`
- `stage = ...`
- `prod = ...`
#### Class `Settings(BaseSettings)`
**Fields**:
- `model_config = ...`
- `app_env: AppEnv`
- `pg_dsn: PostgresDsn | str`
- `openai_api_key: SecretStr`
- `neo4j_uri: str`
- `neo4j_user: str`
- `neo4j_password: SecretStr`
- `qdrant_url: AnyUrl`
- `redis_url: AnyUrl`
- `qdrant_collection_name: str`
- `qdrant_default_vector_dim: int`
- `prometheus_enabled: bool`
- `cors_allow_origins: str`
- `admin_api_key: SecretStr`
- `jwt_secret_key: SecretStr`
- `jwt_access_ttl_seconds: int`
- `jwt_refresh_ttl_seconds: int`
- `bootstrap_admin_email: str`
- `bootstrap_admin_password: SecretStr`
- `kb_domain: str`
- `kb_alt_domain: str`
- `letsencrypt_email: str`
---

## File: `backend\app\config\environments\dev.py`
### Global Functions
#### Function `get_settings`
`def get_settings() -> Settings`
---

## File: `backend\app\config\environments\prod.py`
### Global Functions
#### Function `get_settings`
`def get_settings() -> Settings`
---

## File: `backend\app\config\environments\stage.py`
### Global Functions
#### Function `get_settings`
`def get_settings() -> Settings`
---

## File: `backend\app\core\canonical.py`
### Global Variables
- `_WS_RE = ...`
- `ALLOWED_NODE_LABELS = ...`
- `ALLOWED_EDGE_TYPES = ...`

### Global Functions
#### Function `normalize_text`
`def normalize_text(text: str) -> str`
#### Function `canonical_json`
`def canonical_json(obj: Any) -> str`
#### Function `hash_sha256`
`def hash_sha256(data: bytes | str) -> str`
#### Function `canonical_hash_from_text`
`def canonical_hash_from_text(text: str) -> str`
#### Function `canonical_hash_from_json`
`def canonical_hash_from_json(obj: Any) -> str`
---

## File: `backend\app\core\context.py`
### Global Variables
- `tenant_id_var: ContextVar[Optional[str]]`

### Global Functions
#### Function `set_tenant_id`
`def set_tenant_id(tenant_id: Optional[str]) -> None`
#### Function `get_tenant_id`
`def get_tenant_id() -> Optional[str]`
#### Function `extract_tenant_id_from_request`
`def extract_tenant_id_from_request(request: Request) -> Optional[str]`
---

## File: `backend\app\core\correlation.py`
### Global Variables
- `correlation_id_var: ContextVar[str | None]`

### Global Functions
#### Function `new_correlation_id`
`def new_correlation_id() -> str`
#### Function `set_correlation_id`
`def set_correlation_id(cid: str) -> None`
#### Function `get_correlation_id`
`def get_correlation_id() -> str | None`
---

## File: `backend\app\core\logging.py`
### Global Variables
- `logger = ...`

### Global Functions
#### Function `setup_logging`
`def setup_logging() -> None`
---

## File: `backend\app\core\math.py`
### Global Functions
#### Function `clip`
`def clip(x: float, lo: float, hi: float) -> float`
#### Function `w_edge`
`def w_edge(w_static: float, g_diff: float, decay: float, u_conf: float, lo: float, hi: float) -> float`
#### Function `ema`
`def ema(prev: float, value: float, alpha: float) -> float`
---

## File: `backend\app\core\migrations.py`
### Global Variables
- `CODE_SCHEMA_VERSION = ...`

### Global Functions
#### Function `check_and_gatekeep`
`def check_and_gatekeep(tenant_id: str | None) -> bool`
---

## File: `backend\app\db\dao_base.py`
### Classes
#### Class `TenantRequiredError(RuntimeError)`
#### Class `DaoBase`

**Methods**:
- `__init__(self, tenant_id: Optional[str]) -> None`
- `tenant_id(self) -> str`
- `inject_tenant(self, params: Dict[str, Any] | None) -> Dict[str, Any]`
---

## File: `backend\app\db\pg.py`
### Global Functions
#### Function `get_conn`
`def get_conn() -> None`
#### Function `ensure_tables`
`def ensure_tables() -> None`
#### Function `get_graph_version`
`def get_graph_version(tenant_id: str) -> int`
#### Function `set_graph_version`
`def set_graph_version(tenant_id: str, version: int) -> None`
#### Function `add_graph_change`
`def add_graph_change(tenant_id: str, graph_version: int, target_id: str, change_type: str) -> None`
#### Function `get_changed_targets_since`
`def get_changed_targets_since(tenant_id: str, from_version: int, change_type: str | None) -> list[str]`
#### Function `ensure_schema_version`
`def ensure_schema_version() -> None`
#### Function `get_schema_version`
`def get_schema_version() -> int`
#### Function `set_schema_version`
`def set_schema_version(version: int) -> None`
#### Function `get_tenant_schema_version`
`def get_tenant_schema_version(tenant_id: str) -> int`
#### Function `set_tenant_schema_version`
`def set_tenant_schema_version(tenant_id: str, version: int) -> None`
#### Function `get_proposal`
`def get_proposal(proposal_id: str) -> dict | None`
#### Function `set_proposal_status`
`def set_proposal_status(proposal_id: str, status: str) -> None`
#### Function `list_proposals`
`def list_proposals(tenant_id: str, status: str | None, limit: int, offset: int) -> list[dict]`
#### Function `outbox_add`
`def outbox_add(tenant_id: str, event_type: str, payload: Dict) -> str`
#### Function `outbox_fetch_unpublished`
`def outbox_fetch_unpublished(limit: int) -> list[dict]`
#### Function `outbox_mark_published`
`def outbox_mark_published(event_id: str) -> None`
#### Function `outbox_mark_failed`
`def outbox_mark_failed(event_id: str, error: str | None) -> None`
---

## File: `backend\app\events\publisher.py`
### Global Functions
#### Function `get_redis`
`def get_redis() -> None`
#### Function `publish_graph_committed`
`def publish_graph_committed(event: Dict) -> None`
---

## File: `backend\app\schemas\proposal.py`
### Classes
#### Class `ProposalStatus(str, Enum)`
**Fields**:
- `DRAFT = ...`
- `WAITING_REVIEW = ...`
- `APPROVED = ...`
- `REJECTED = ...`
- `CONFLICT = ...`
- `COMMITTING = ...`
- `DONE = ...`
- `FAILED = ...`
#### Class `OpType(str, Enum)`
**Fields**:
- `CREATE_NODE = ...`
- `CREATE_REL = ...`
- `MERGE_NODE = ...`
- `MERGE_REL = ...`
- `UPDATE_NODE = ...`
- `UPDATE_REL = ...`
- `DELETE_NODE = ...`
- `DELETE_REL = ...`
#### Class `Operation(BaseModel)`
**Fields**:
- `op_id: str`
- `op_type: OpType`
- `target_id: Optional[str]`
- `temp_id: Optional[str]`
- `properties_delta: Dict[str, Any]`
- `match_criteria: Dict[str, Any]`
- `evidence: Dict[str, Any]`
- `semantic_impact: str`
- `requires_review: bool`
#### Class `Proposal(BaseModel)`
**Fields**:
- `proposal_id: str`
- `task_id: Optional[str]`
- `tenant_id: str`
- `base_graph_version: int`
- `proposal_checksum: str`
- `status: ProposalStatus`
- `operations: List[Operation]`
---

## File: `backend\app\services\diff.py`
### Global Functions
#### Function `apply_delta`
`def apply_delta(base: Dict[str, Any], delta: Dict[str, Any]) -> Dict[str, Any]`
#### Function `build_diff`
`def build_diff(proposal_id: str) -> Dict`
---

## File: `backend\app\services\evidence.py`
### Global Functions
#### Function `get_chunk_text`
`def get_chunk_text(chunk_id: str) -> Optional[str]`
#### Function `resolve_evidence`
`def resolve_evidence(ev: Dict) -> Dict`
---

## File: `backend\app\services\impact.py`
### Global Variables
- `_CACHE: Dict[Tuple[str, int], Tuple[float, Tuple[List[Dict], List[Dict]]]]`
- `_TTL_S = ...`

### Global Functions
#### Function `_neighbors_cached`
`def _neighbors_cached(uid: str, depth: int) -> Tuple[List[Dict], List[Dict]]`
#### Function `impact_subgraph_for_proposal`
`def impact_subgraph_for_proposal(proposal_id: str, depth: int, types: Optional[List[str]], max_nodes: Optional[int], max_edges: Optional[int]) -> Dict`
---

## File: `backend\app\services\integrity.py`
### Global Functions
#### Function `check_canon_compliance`
`def check_canon_compliance(nodes: List[Dict], rels: List[Dict]) -> List[str]`
#### Function `check_prereq_cycles`
`def check_prereq_cycles(rels: List[Dict]) -> List[Tuple[str, str]]`

> rels: list of {'type': 'PREREQ', 'from_uid': str, 'to_uid': str}

#### Function `check_dangling_skills`
`def check_dangling_skills(nodes: List[Dict], rels: List[Dict]) -> List[str]`

> nodes: list of {'type': 'Skill', 'uid': str}
> rels: list of {'type': 'BASED_ON', 'from_uid': str, 'to_uid': str}

#### Function `integrity_check_subgraph`
`def integrity_check_subgraph(nodes: List[Dict], rels: List[Dict]) -> Dict`
#### Function `check_skill_based_on_rules`
`def check_skill_based_on_rules(nodes: List[Dict], rels: List[Dict], min_required: int, max_allowed: int | None) -> Dict`
---

## File: `backend\app\services\proposal_service.py`
### Global Variables
- `EVIDENCE_REQUIRED_OPS = ...`

### Global Functions
#### Function `validate_operations`
`def validate_operations(ops: List[Operation]) -> None`
#### Function `_deep_normalize`
`def _deep_normalize(obj) -> None`
#### Function `compute_checksum`
`def compute_checksum(ops: List[Operation]) -> str`
#### Function `create_draft_proposal`
`def create_draft_proposal(tenant_id: str, base_graph_version: int, ops: List[Operation]) -> Proposal`
---

## File: `backend\app\services\questions.py`
### Global Variables
- `BASE_DIR = ...`
- `KB_DIR = ...`

### Global Functions
#### Function `load_jsonl`
`def load_jsonl(filename: str) -> List[Dict]`
#### Function `get_examples_indexed`
```python
@lru_cache(maxsize=1)
```
`def get_examples_indexed() -> None`
#### Function `select_examples_for_topics`
`def select_examples_for_topics(topic_uids: List[str], limit: int, difficulty_min: int, difficulty_max: int, exclude_uids: Set[str] | None, tenant_id: str | None) -> None`
#### Function `all_topic_uids_from_examples`
`def all_topic_uids_from_examples() -> List[str]`
---

## File: `backend\app\services\rebase.py`
### Global Functions
#### Function `rebase_check`
`def rebase_check(tenant_id: str, base_graph_version: int, target_ids: List[str]) -> RebaseResult`
### Classes
#### Class `RebaseResult(str, Enum)`
**Fields**:
- `SAME_VERSION = ...`
- `FAST_REBASE = ...`
- `CONFLICT = ...`
---

## File: `backend\app\services\roadmap_planner.py`
### Global Functions
#### Function `plan_route`
`def plan_route(subject_uid: str | None, progress: Dict[str, float], limit: int, penalty_factor: float, tenant_id: str | None) -> List[Dict]`
---

## File: `backend\app\services\validation.py`
### Global Functions
#### Function `_as_list`
`def _as_list(x) -> None`
#### Function `_index_nodes`
`def _index_nodes(snapshot: Dict) -> Dict[str, Dict]`
#### Function `_iter_edges`
`def _iter_edges(snapshot: Dict) -> None`
#### Function `validate_canonical_graph_snapshot`
`def validate_canonical_graph_snapshot(snapshot: Dict) -> Dict`
---

## File: `backend\app\services\ai_engine\ai_engine.py`
### Global Functions
#### Function `generate_concepts_and_skills`
`def generate_concepts_and_skills(topic: str, language: str) -> GeneratedBundle`
### Classes
#### Class `GeneratedConcept(BaseModel)`
**Fields**:
- `title: str`
- `definition: str`
- `reasoning: str`
#### Class `GeneratedSkill(BaseModel)`
**Fields**:
- `title: str`
- `description: str`
#### Class `GeneratedBundle(BaseModel)`
**Fields**:
- `concepts: List[GeneratedConcept]`
- `skills: List[GeneratedSkill]`
---

## File: `backend\app\services\auth\jwt_tokens.py`
### Global Functions
#### Function `_now`
`def _now() -> datetime`
#### Function `create_access_token`
`def create_access_token(user_id: int, role: str) -> str`
#### Function `create_refresh_token`
`def create_refresh_token(user_id: int) -> str`
#### Function `decode_token`
`def decode_token(token: str) -> dict`
---

## File: `backend\app\services\auth\passwords.py`
### Global Functions
#### Function `hash_password`
`def hash_password(password: str) -> str`
#### Function `verify_password`
`def verify_password(password: str, password_hash: str) -> bool`
---

## File: `backend\app\services\auth\users_repo.py`
### Global Functions
#### Function `_get_conn`
`def _get_conn() -> None`
#### Function `ensure_users_table`
`def ensure_users_table() -> None`
#### Function `create_user`
`def create_user(email: str, password_hash: str, role: str) -> User`
#### Function `ensure_bootstrap_admin`
`def ensure_bootstrap_admin() -> None`
#### Function `get_user_by_email`
`def get_user_by_email(email: str) -> Optional[User]`
#### Function `get_user_by_id`
`def get_user_by_id(user_id: int) -> Optional[User]`
### Classes
#### Class `User`
**Fields**:
- `id: int`
- `email: str`
- `password_hash: str`
- `role: str`
- `is_active: bool`
---

## File: `backend\app\services\curriculum\repo.py`
### Global Functions
#### Function `get_conn`
`def get_conn() -> None`
#### Function `create_curriculum`
`def create_curriculum(code: str, title: str, standard: str, language: str) -> Dict`
#### Function `add_curriculum_nodes`
`def add_curriculum_nodes(code: str, nodes: List[Dict]) -> Dict`
#### Function `get_graph_view`
`def get_graph_view(code: str) -> Dict`
---

## File: `backend\app\services\embeddings\provider.py`
### Global Functions
#### Function `get_provider`
`def get_provider(dim_default: int) -> BaseEmbeddingProvider`
### Classes
#### Class `BaseEmbeddingProvider`

**Methods**:
- `embed_text(self, text: str) -> List[float]`
#### Class `HashEmbeddingProvider(BaseEmbeddingProvider)`

**Methods**:
- `__init__(self, dim: int) -> None`
- `embed_text(self, text: str) -> List[float]`
#### Class `OpenAIEmbeddingProvider(BaseEmbeddingProvider)`

**Methods**:
- `__init__(self, dim: int, model: str, api_key: str | None) -> None`
- `embed_text(self, text: str) -> List[float]`
---

## File: `backend\app\services\graph\graph_service.py`
### Global Functions
#### Function `dag_check`
`def dag_check(edges: List[Dict]) -> List[List[str]]`
#### Function `connectivity_stats`
`def connectivity_stats(nodes: List[str], edges: List[Dict]) -> Dict`
#### Function `cognitive_distance`
`def cognitive_distance(root: str, leaves: List[str], edges: List[Dict]) -> Dict[str, int]`
---

## File: `backend\app\services\graph\neo4j_repo.py`
### Global Functions
#### Function `get_driver`
`def get_driver() -> None`
#### Function `read_graph`
`def read_graph(subject_uid: str | None, tenant_id: str | None) -> Tuple[List[Dict], List[Dict]]`
#### Function `relation_context`
`def relation_context(from_uid: str, to_uid: str, tenant_id: str | None) -> Dict`
#### Function `neighbors`
`def neighbors(center_uid: str, depth: int, tenant_id: str | None) -> Tuple[List[Dict], List[Dict]]`
#### Function `node_by_uid`
`def node_by_uid(uid: str, tenant_id: str) -> Dict`
#### Function `relation_by_pair`
`def relation_by_pair(from_uid: str, to_uid: str, typ: str, tenant_id: str) -> Dict`
#### Function `get_node_details`
`def get_node_details(uid: str, tenant_id: str | None) -> Dict`
### Classes
#### Class `Neo4jRepo`

**Methods**:
- `__init__(self, uri: Optional[str], user: Optional[str], password: Optional[str], max_retries: int, backoff_sec: float) -> None`
- `close(self) -> None`
- `_retry(self, fn: Callable[[Any], Any]) -> Any`
- `write(self, query: str, params: Dict | None) -> None`
- `read(self, query: str, params: Dict | None) -> List[Dict]`
- `_chunks(self, rows: List[Dict], size: int) -> List[List[Dict]]`
- `write_unwind(self, query: str, rows: List[Dict], chunk_size: int) -> None`
---

## File: `backend\app\services\graph\utils.py`
### Global Functions
#### Function `compute_user_weight`
`def compute_user_weight(base_weight: float, score: float) -> float`
#### Function `compute_topic_user_weight`
`def compute_topic_user_weight(topic_uid: str, score: float, base_weight: float | None) -> Dict`
#### Function `compute_skill_user_weight`
`def compute_skill_user_weight(skill_uid: str, score: float, base_weight: float | None) -> Dict`
#### Function `knowledge_level_from_weight`
`def knowledge_level_from_weight(weight: float) -> str`
#### Function `ensure_constraints`
`def ensure_constraints(session) -> None`
#### Function `ensure_weight_defaults`
`def ensure_weight_defaults(session) -> None`
#### Function `ensure_weight_defaults_repo`
`def ensure_weight_defaults_repo(repo: Neo4jRepo) -> None`
#### Function `sync_from_jsonl`
`def sync_from_jsonl() -> Dict`
#### Function `sync_from_jsonl_dir`
`def sync_from_jsonl_dir(base_dir: str) -> Dict`
#### Function `sync_from_jsonl_dir_sections`
`def sync_from_jsonl_dir_sections(base_dir: str, section_uids: List[str]) -> Dict`
#### Function `sync_from_jsonl_dir_subsections`
`def sync_from_jsonl_dir_subsections(base_dir: str, subsection_uids: List[str]) -> Dict`
#### Function `build_graph_from_neo4j`
`def build_graph_from_neo4j(subject_filter: str | None) -> Dict`
#### Function `analyze_knowledge`
`def analyze_knowledge(subject_uid: str | None) -> Dict`
#### Function `update_dynamic_weight`
`def update_dynamic_weight(topic_uid: str, score: float) -> Dict`
#### Function `update_skill_dynamic_weight`
`def update_skill_dynamic_weight(skill_uid: str, score: float) -> Dict`
#### Function `get_current_knowledge_level`
`def get_current_knowledge_level(topic_uid: str) -> Dict`
#### Function `get_current_skill_level`
`def get_current_skill_level(skill_uid: str) -> Dict`
#### Function `build_adaptive_roadmap`
`def build_adaptive_roadmap(subject_uid: str | None, limit: int) -> List[Dict]`
#### Function `build_user_roadmap_stateless`
`def build_user_roadmap_stateless(subject_uid: str | None, user_topic_weights: Dict[str, float], user_skill_weights: Dict[str, float] | None, limit: int, penalty_factor: float) -> List[Dict]`
#### Function `recompute_relationship_weights`
`def recompute_relationship_weights() -> Dict`
#### Function `recompute_adaptive_for_skill`
`def recompute_adaptive_for_skill(skill_uid: str) -> Dict`
#### Function `update_user_topic_weight`
`def update_user_topic_weight(user_id: str, topic_uid: str, score: float) -> Dict`
#### Function `update_user_skill_weight`
`def update_user_skill_weight(user_id: str, skill_uid: str, score: float) -> Dict`
#### Function `get_user_topic_level`
`def get_user_topic_level(user_id: str, topic_uid: str) -> Dict`
#### Function `get_user_skill_level`
`def get_user_skill_level(user_id: str, skill_uid: str) -> Dict`
#### Function `build_user_roadmap`
`def build_user_roadmap(user_id: str, subject_uid: str | None, limit: int, penalty_factor: float) -> List[Dict]`
#### Function `complete_user_topic`
`def complete_user_topic(user_id: str, topic_uid: str, time_spent_sec: float, errors: int) -> Dict`
#### Function `complete_user_skill`
`def complete_user_skill(user_id: str, skill_uid: str, time_spent_sec: float, errors: int) -> Dict`
#### Function `search_titles`
`def search_titles(q: str, limit: int) -> List[Dict]`
#### Function `health`
`def health() -> Dict`
#### Function `list_items`
`def list_items(kind: str, subject_uid: str | None, section_uid: str | None) -> List[Dict]`
#### Function `get_node_details`
`def get_node_details(uid: str) -> Dict`
#### Function `fix_orphan_section`
`def fix_orphan_section(section_uid: str, subject_uid: str) -> Dict`
#### Function `compute_static_weights`
`def compute_static_weights() -> Dict`
#### Function `analyze_prereqs`
`def analyze_prereqs(subject_uid: str | None) -> Dict`
#### Function `add_prereqs_heuristic`
`def add_prereqs_heuristic() -> Dict`
#### Function `link_remaining_skills_methods`
`def link_remaining_skills_methods() -> Dict`
#### Function `link_skill_to_best`
`def link_skill_to_best(skill_uid: str, method_candidates: List[str]) -> Dict`
---

## File: `backend\app\services\jobs\rebuild.py`
### Global Variables
- `_jobs: Dict[str, Dict]`

### Global Functions
#### Function `_run_job`
`def _run_job(job_id: str) -> None`
#### Function `start_rebuild_async`
`def start_rebuild_async() -> Dict`
#### Function `get_job_status`
`def get_job_status(job_id: str) -> Dict`
---

## File: `backend\app\services\kb\builder.py`
### Global Variables
- `BASE_DIR = ...`
- `MATHEMATICS_ONTOLOGY: Dict`

### Global Functions
#### Function `openai_chat`
`def openai_chat(messages: List[Dict], model: str, temperature: float) -> Dict`
#### Function `openai_chat_async`
`def openai_chat_async(messages: List[Dict], model: str, temperature: float) -> Dict`
#### Function `generate_goals_and_objectives`
`def generate_goals_and_objectives() -> Dict`
#### Function `autolink_skills_methods`
`def autolink_skills_methods(max_links_per_skill: int) -> Dict`
#### Function `add_subject`
`def add_subject(title: str, description: str, uid: Optional[str]) -> Dict`
#### Function `add_section`
`def add_section(subject_uid: str, title: str, description: str, uid: Optional[str]) -> Dict`
#### Function `add_subsection`
`def add_subsection(section_uid: str, title: str, description: str, uid: Optional[str]) -> Dict`
#### Function `add_topic`
`def add_topic(section_uid: str, title: str, description: str, uid: Optional[str]) -> Dict`
#### Function `add_topic_to_subsection`
`def add_topic_to_subsection(subsection_uid: str, title: str, description: str, uid: Optional[str]) -> Dict`
#### Function `add_skill`
`def add_skill(subject_uid: str, title: str, definition: str, uid: Optional[str]) -> Dict`
#### Function `add_method`
`def add_method(title: str, method_text: str, applicability_types: Optional[List[str]], uid: Optional[str]) -> Dict`
#### Function `link_topic_skill`
`def link_topic_skill(topic_uid: str, skill_uid: str, weight: str, confidence: float) -> Dict`
#### Function `link_topic_skill_fallback`
`def link_topic_skill_fallback(topic_uid: str, skill_uid: str, weight: str, confidence: float) -> Dict`
#### Function `link_skill_method`
`def link_skill_method(skill_uid: str, method_uid: str, weight: str, confidence: float, is_auto_generated: bool) -> Dict`
#### Function `add_example`
`def add_example(title: str, statement: str, topic_uid: Optional[str], difficulty: int, uid: Optional[str]) -> Dict`
#### Function `link_topic_prereq`
`def link_topic_prereq(target_topic_uid: str, prereq_topic_uid: str, weight: float) -> Dict`
#### Function `add_content_unit`
`def add_content_unit(topic_uid: str, branch: str, unit_type: str, content: Dict, complexity: float, uid: Optional[str]) -> Dict`
#### Function `link_example_skill`
`def link_example_skill(example_uid: str, skill_uid: str, role: str) -> Dict`
#### Function `add_error`
`def add_error(title: str, error_text: str, triggers: Optional[List[str]], uid: Optional[str]) -> Dict`
#### Function `link_error_skill`
`def link_error_skill(error_uid: str, skill_uid: str) -> Dict`
#### Function `link_error_example`
`def link_error_example(error_uid: str, example_uid: str) -> Dict`
#### Function `add_topic_goal`
`def add_topic_goal(topic_uid: str, title: str, uid: Optional[str]) -> Dict`
#### Function `add_topic_objective`
`def add_topic_objective(topic_uid: str, title: str, uid: Optional[str]) -> Dict`
#### Function `add_lesson_step`
`def add_lesson_step(topic_uid: str, role: str, text: str) -> Dict`
#### Function `add_theory`
`def add_theory(topic_uid: str, text: str) -> Dict`
#### Function `add_concept_unit`
`def add_concept_unit(topic_uid: str, text: str) -> Dict`
#### Function `add_formula_unit`
`def add_formula_unit(topic_uid: str, text: str) -> Dict`
#### Function `generate_theory_for_topic_openai`
`def generate_theory_for_topic_openai(topic_uid: str, max_tokens: int) -> Dict`
#### Function `generate_examples_for_topic_openai`
`def generate_examples_for_topic_openai(topic_uid: str, count: int, difficulty: int) -> Dict`
#### Function `generate_methods_for_skill_openai`
`def generate_methods_for_skill_openai(skill_uid: str, count: int) -> Dict`
#### Function `generate_topic_bundle_openai`
`def generate_topic_bundle_openai(topic_uid: str, examples_count: int) -> Dict`
#### Function `generate_sections_openai_async`
`def generate_sections_openai_async(subject_title: str, language: str, count: int) -> List[str]`
#### Function `generate_topics_for_section_openai_async`
`def generate_topics_for_section_openai_async(section_title: str, language: str, count: int) -> List[Dict]`
#### Function `enrich_topic`
`def enrich_topic(subject_uid: str, topic_uid: str, title: str) -> Dict`
#### Function `enrich_all_topics`
`def enrich_all_topics() -> Dict`
#### Function `generate_skills_for_topic_openai_async`
`def generate_skills_for_topic_openai_async(topic_title: str, language: str, count: int) -> List[Dict]`
#### Function `generate_methods_for_skill_openai_async`
`def generate_methods_for_skill_openai_async(skill_title: str, count: int) -> List[Dict]`
#### Function `generate_subsections_openai_async`
`def generate_subsections_openai_async(section_title: str, language: str, count: int) -> List[str]`
#### Function `generate_topics_with_prereqs_openai_async`
`def generate_topics_with_prereqs_openai_async(subsection_title: str, language: str, count: int) -> List[Dict]`
#### Function `generate_subject_with_llm`
`def generate_subject_with_llm(subject_title: str, language: str, limits: Dict | None) -> Dict`
#### Function `build_mathematics_ontology`
`def build_mathematics_ontology() -> Dict`
#### Function `generate_examples_for_topic_openai_async`
`def generate_examples_for_topic_openai_async(topic_title: str, count: int, difficulty: int) -> List[Dict]`
#### Function `generate_subject_openai_async`
`def generate_subject_openai_async(subject_uid: str, subject_title: str, language: str, sections_seed: Optional[List[str]], topics_per_section: int, skills_per_topic: int, methods_per_skill: int, examples_per_topic: int, concurrency: int) -> Dict`
#### Function `rebuild_subject_math_with_openai`
`def rebuild_subject_math_with_openai(section_title: str) -> Dict`
#### Function `truth_check_openai`
`def truth_check_openai(text: str, context: Optional[str]) -> Dict`
#### Function `bootstrap_subject_from_skill_topics`
`def bootstrap_subject_from_skill_topics(subject_uid: str, section_title: str) -> Dict`
---

## File: `backend\app\services\kb\jsonl_io.py`
### Global Variables
- `BASE_DIR = ...`
- `KB_DIR = ...`

### Global Functions
#### Function `load_jsonl`
`def load_jsonl(filepath: str) -> List[Dict]`
#### Function `append_jsonl`
`def append_jsonl(filepath: str, record: Dict) -> None`
#### Function `rewrite_jsonl`
`def rewrite_jsonl(filepath: str, records: List[Dict]) -> None`
#### Function `get_path`
`def get_path(name: str) -> str`
#### Function `get_subject_dir`
`def get_subject_dir(subject_slug: str, language: str) -> str`
#### Function `get_path_in`
`def get_path_in(base_dir: str, name: str) -> str`
#### Function `_translit_en`
`def _translit_en(s: str) -> str`
#### Function `make_uid`
`def make_uid(prefix: str, title: str) -> str`
#### Function `tokens`
`def tokens(text: str) -> Set[str]`
#### Function `normalize_skill_topics_to_topic_skills`
`def normalize_skill_topics_to_topic_skills() -> Dict`
#### Function `normalize_kb`
`def normalize_kb() -> Dict`
#### Function `normalize_kb_dir`
`def normalize_kb_dir(base_dir: str) -> Dict`
---

## File: `backend\app\services\reasoning\gaps.py`
### Global Functions
#### Function `compute_gaps`
`def compute_gaps(subject_uid: str, progress: Dict[str, float], goals: List[str] | None, prereq_threshold: float) -> Dict[str, List[Dict]]`
---

## File: `backend\app\services\reasoning\mastery_update.py`
### Global Functions
#### Function `update_mastery`
`def update_mastery(prior_mastery: float, score: float, confidence: float | None) -> Dict`
---

## File: `backend\app\services\reasoning\next_best_topic.py`
### Global Functions
#### Function `next_best_topics`
`def next_best_topics(subject_uid: str, progress: Dict[str, float], prereq_threshold: float, top_k: int, alpha: float, beta: float) -> Dict[str, List[Dict]]`
---

## File: `backend\app\services\reasoning\roadmap.py`
### Global Functions
#### Function `build_roadmap`
`def build_roadmap(subject_uid: str, progress: Dict[str, float], goals: List[str] | None, prereq_threshold: float, top_k: int) -> Dict[str, List[Dict]]`
---

## File: `backend\app\services\vector\indexer.py`
### Global Variables
- `ALLOWED_TYPES = ...`

### Global Functions
#### Function `ensure_collection`
`def ensure_collection(client: QdrantClient, name: str, dim: int) -> None`
#### Function `index_entities`
`def index_entities(tenant_id: str, uids: List[str], collection: str | None, dim: int | None) -> Dict`
---

## File: `backend\app\services\vector\qdrant_service.py`
### Global Variables
- `client = ...`
- `COLLECTION = ...`
- `oai = ...`

### Global Functions
#### Function `embed_text`
`def embed_text(text: str) -> List[float]`
#### Function `upsert_concept`
`def upsert_concept(uid: str, title: str, definition: str, embedding: List[float]) -> None`
#### Function `query_similar`
`def query_similar(embedding: List[float], top_k: int) -> List[Tuple[str, float]]`
---

## File: `backend\app\tasks\worker.py`
### Global Variables
- `KB_STATE_TTL_SEC = ...`

### Global Functions
#### Function `publish_progress`
`def publish_progress(ctx, job_id: str, step: str, payload: dict) -> None`
#### Function `persist_kb_rebuild_state`
`def persist_kb_rebuild_state(ctx, job_id: str, state: dict) -> None`
#### Function `magic_fill_job`
`def magic_fill_job(ctx, job_id: str, topic_uid: str, topic_title: str) -> None`
#### Function `kb_validate_job`
`def kb_validate_job(ctx, job_id: str, subject_uid: str | None, auto_publish: bool) -> None`
#### Function `kb_rebuild_job`
`def kb_rebuild_job(ctx, job_id: str, auto_publish: bool) -> None`
#### Function `vector_consume_job`
`def vector_consume_job(ctx) -> None`
#### Function `outbox_publish_job`
`def outbox_publish_job(ctx) -> None`
### Classes
#### Class `WorkerSettings`
**Fields**:
- `redis_settings = ...`
- `functions = ...`
- `cron_jobs = ...`
---

## File: `backend\app\utils\atomic_write.py`
### Global Functions
#### Function `write_jsonl_atomic`
`def write_jsonl_atomic(path: str, items: List[Dict], validate: Callable[[Dict], None]) -> None`
---

## File: `backend\app\workers\commit.py`
### Global Functions
#### Function `_load_proposal`
`def _load_proposal(proposal_id: str) -> Dict | None`
#### Function `_update_proposal_status`
`def _update_proposal_status(proposal_id: str, status: str) -> None`
#### Function `_collect_target_ids`
`def _collect_target_ids(ops: List[Dict[str, Any]]) -> List[str]`
#### Function `_collect_prereq_edges`
`def _collect_prereq_edges(ops: List[Dict[str, Any]]) -> List[Dict[str, str]]`
#### Function `_apply_ops_tx`
`def _apply_ops_tx(tx, tenant_id: str, ops: List[Dict[str, Any]]) -> None`
#### Function `commit_proposal`
`def commit_proposal(proposal_id: str) -> Dict`
---

## File: `backend\app\workers\ingestion.py`
### Global Variables
- `_WS = ...`

### Global Functions
#### Function `normalize_text`
`def normalize_text(text: str) -> str`
#### Function `chunk_text`
`def chunk_text(text: str, max_len: int) -> List[Dict]`
#### Function `_hash16`
`def _hash16(text: str) -> List[float]`
#### Function `ensure_collection`
`def ensure_collection(client: QdrantClient, name: str, size: int) -> None`
#### Function `embed_chunks`
`def embed_chunks(tenant_id: str, doc_id: str, chunks: List[Dict], collection: str) -> int`
---

## File: `backend\app\workers\integrity_async.py`
### Global Functions
#### Function `_collect_nodes_and_rels`
`def _collect_nodes_and_rels(ops: List[Dict[str, Any]]) -> Dict[str, List[Dict]]`
#### Function `process_once`
`def process_once(limit: int) -> Dict`
---

## File: `backend\app\workers\outbox_publisher.py`
### Global Functions
#### Function `process_once`
`def process_once(limit: int) -> Dict`
#### Function `process_retry`
`def process_retry(limit: int) -> Dict`
---

## File: `backend\app\workers\vector_sync.py`
### Global Functions
#### Function `mark_entities_updated`
`def mark_entities_updated(tenant_id: str, targets: List[str], collection: str) -> int`
#### Function `consume_graph_committed`
`def consume_graph_committed() -> Dict`
---
