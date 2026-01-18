# Codebase Analysis Report

## File: `backend/app/api/admin.py`
### Global Variables
- `router`

---

## File: `backend/app/api/admin_curriculum.py`
### Global Variables
- `router`

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

## File: `backend/app/api/admin_graph.py`
### Global Variables
- `router`

### Global Functions
#### Function `_validate_labels`
`def _validate_labels(labels: List[str]) -> List[str]`

#### Function `_validate_edge_type`
`def _validate_edge_type(t: str) -> str`

#### Function `_validate_props`
`def _validate_props(props: Dict[(str, Any)]) -> Dict[(str, Any)]`

### Classes
#### Class `NodeCreateInput(BaseModel)`
**Fields**:
- `uid: str`
- `labels: List[str]`
- `props: Dict[(str, Any)]`

#### Class `NodePatchInput(BaseModel)`
**Fields**:
- `set: Dict[(str, Any)]`
- `unset: List[str]`

#### Class `EdgeCreateInput(BaseModel)`
**Fields**:
- `edge_uid: Optional[str]`
- `from_uid: str`
- `to_uid: str`
- `type: str`
- `props: Dict[(str, Any)]`

#### Class `EdgePatchInput(BaseModel)`
**Fields**:
- `set: Dict[(str, Any)]`
- `unset: List[str]`

---

## File: `backend/app/api/analytics.py`
### Global Variables
- `router`

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

## File: `backend/app/api/assessment.py`
### Global Variables
- `router`

### Global Functions
#### Function `_get_session`
`def _get_session(sid: str) -> Optional[Dict]`

#### Function `_save_session`
`def _save_session(sid: str, data: Dict)`

#### Function `_resolve_level`
`def _resolve_level(uc: UserContext) -> int`

#### Function `_topic_accessible`
`def _topic_accessible(subject_uid: str, topic_uid: str, resolved_level: int) -> bool`

#### Function `_select_question`
`def _select_question(topic_uid: str, difficulty_min: int, difficulty_max: int) -> Dict`

#### Function `_evaluate`
`def _evaluate(answer: AnswerDTO) -> float`

#### Function `_confidence`
`def _confidence(sess: Dict) -> float`

#### Function `_next_question`
`def _next_question(sess: Dict) -> Optional[Dict]`

### Classes
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
- `def check_not_empty(self)`

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

## File: `backend/app/api/assistant.py`
### Global Variables
- `router`

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
- `action: Optional[Literal[('explain_relation', 'viewport', 'roadmap', 'analytics', 'questions')]]`
- `message: str`
- `from_uid: Optional[str]`
- `to_uid: Optional[str]`
- `center_uid: Optional[str]`
- `depth: int`
- `subject_uid: Optional[str]`
- `progress: Dict[(str, float)]`
- `limit: int`
- `count: int`
- `difficulty_min: int`
- `difficulty_max: int`
- `exclude: List[str]`

---

## File: `backend/app/api/auth.py`
### Global Variables
- `router`

### Global Functions
#### Function `_bearer_token`
`def _bearer_token(authorization: str | None) -> str | None`

#### Function `register`
```python
@post(...)
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
@post(...)
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
@post(...)
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
@get(...)
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

#### Class `LoginResponse(BaseModel)`
**Fields**:
- `access_token: str`
- `refresh_token: str`
- `token_type: str`

#### Class `RefreshResponse(BaseModel)`
**Fields**:
- `access_token: str`
- `refresh_token: str`
- `token_type: str`

#### Class `MeResponse(BaseModel)`
**Fields**:
- `id: int`
- `email: str`
- `role: str`

---

## File: `backend/app/api/common.py`
### Classes
#### Class `ApiError(BaseModel)`
**Fields**:
- `code: str`
- `message: str`
- `target: Optional[str]`
- `details: Optional[Dict[(str, Any)]]`
- `request_id: Optional[str]`
- `correlation_id: Optional[str]`

#### Class `StandardResponse(BaseModel)`
**Fields**:
- `items: List[Any]`
- `meta: Dict[(str, Any)]`

---

## File: `backend/app/api/deps.py`
### Global Functions
#### Function `_bearer_token`
`def _bearer_token(authorization: str | None) -> str | None`

#### Function `get_current_user`
`def get_current_user(authorization: str | None)`

#### Function `require_admin`
`def require_admin(authorization: str | None)`

---

## File: `backend/app/api/engine.py`
### Global Variables
- `router`

### Global Functions
#### Function `_age_to_class`
`def _age_to_class(age: Optional[int]) -> int`

### Classes
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

#### Class `PathfindInput(BaseModel)`
**Fields**:
- `target_uid: str`

#### Class `PathfindResponse(BaseModel)`
**Fields**:
- `target: str`
- `path: List[str]`

#### Class `ChatInput(BaseModel)`
**Fields**:
- `question: str`
- `from_uid: str`
- `to_uid: str`

#### Class `ChatResponse(BaseModel)`
**Fields**:
- `answer: str`
- `usage: Optional[Dict]`
- `context: Dict`

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

#### Class `AdaptiveQuestionsInput(BaseModel)`
**Fields**:
- `subject_uid: Optional[str]`
- `progress: Dict[(str, float)]`
- `count: int`
- `difficulty_min: int`
- `difficulty_max: int`
- `exclude: List[str]`

#### Class `GapsRequest(BaseModel)`
**Fields**:
- `subject_uid: str`
- `progress: Dict[(str, float)]`
- `goals: Optional[List[str]]`
- `prereq_threshold: float`

#### Class `NextBestRequest(BaseModel)`
**Fields**:
- `subject_uid: str`
- `progress: Dict[(str, float)]`
- `prereq_threshold: float`
- `top_k: int`
- `alpha: float`
- `beta: float`

#### Class `MasteryUpdateRequest(BaseModel)`
**Fields**:
- `entity_uid: str`
- `kind: str`
- `score: float`
- `prior_mastery: float`
- `confidence: Optional[float]`

---

## File: `backend/app/api/errors.py`
### Global Variables
- `logger`

### Global Functions
#### Function `http_error_response`
`def http_error_response(status_code: int, message: str, details: Any)`

#### Function `http_exception_handler`
`def http_exception_handler(request: Request, exc: StarletteHTTPException)`

#### Function `validation_exception_handler`
`def validation_exception_handler(request: Request, exc: RequestValidationError)`

#### Function `global_exception_handler`
`def global_exception_handler(request: Request, exc: Exception)`

---

## File: `backend/app/api/graphql.py`
### Global Variables
- `BASE_DIR`
- `KB_DIR`
- `schema`
- `router`

### Global Functions
#### Function `_load_jsonl`
`def _load_jsonl(filename: str)`

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
- `def graph(self, subject_uid: Optional[str]) -> GraphView`
- `def topic(self, uid: str) -> TopicDetails`
- `def error(self, uid: str) -> ErrorNode`

---

## File: `backend/app/api/ingestion.py`
### Global Variables
- `router`

### Global Functions
#### Function `require_tenant`
`def require_tenant() -> str`

### Classes
#### Class `GenerateProposalInput(BaseModel)`
**Fields**:
- `content: str`
- `strategy_type: Literal[('academic', 'corporate')]`
- `domain_context: str`

---

## File: `backend/app/api/maintenance.py`
### Global Variables
- `router`

### Classes
#### Class `ProcessedResponse(BaseModel)`
**Fields**:
- `ok: bool`
- `processed: int`

---

## File: `backend/app/api/proposals.py`
### Global Variables
- `router`

### Global Functions
#### Function `require_tenant`
`def require_tenant() -> str`

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

## File: `backend/app/api/validation.py`
### Global Variables
- `router`

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

## File: `backend/app/api/ws.py`
### Global Variables
- `router`

---

## File: `backend/app/config/environments/dev.py`
### Global Functions
#### Function `get_settings`
`def get_settings() -> Settings`

---

## File: `backend/app/config/environments/prod.py`
### Global Functions
#### Function `get_settings`
`def get_settings() -> Settings`

---

## File: `backend/app/config/environments/stage.py`
### Global Functions
#### Function `get_settings`
`def get_settings() -> Settings`

---

## File: `backend/app/config/settings.py`
### Global Variables
- `settings`

### Global Functions
#### Function `get_settings`
```python
@lru_cache(...)
```
`def get_settings() -> Settings`

### Classes
#### Class `AppEnv(StrEnum)`

#### Class `Settings(BaseSettings)`
**Fields**:
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

## File: `backend/app/core/canonical.py`
### Global Variables
- `_WS_RE`
- `ALLOWED_NODE_LABELS`
- `ALLOWED_EDGE_TYPES`

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

## File: `backend/app/core/context.py`
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

## File: `backend/app/core/correlation.py`
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

## File: `backend/app/core/logging.py`
### Global Variables
- `logger`

### Global Functions
#### Function `setup_logging`
`def setup_logging() -> None`

---

## File: `backend/app/core/math.py`
### Global Functions
#### Function `clip`
`def clip(x: float, lo: float, hi: float) -> float`

#### Function `w_edge`
`def w_edge(w_static: float, g_diff: float, decay: float, u_conf: float, lo: float, hi: float) -> float`

#### Function `ema`
`def ema(prev: float, value: float, alpha: float) -> float`

---

## File: `backend/app/core/migrations.py`
### Global Variables
- `CODE_SCHEMA_VERSION`

### Global Functions
#### Function `check_and_gatekeep`
`def check_and_gatekeep(tenant_id: str | None) -> bool`

---

## File: `backend/app/db/dao_base.py`
### Classes
#### Class `TenantRequiredError(RuntimeError)`

#### Class `DaoBase`

**Methods**:
- `def __init__(self, tenant_id: Optional[str])`
- `def tenant_id(self) -> str`
- `def inject_tenant(self, params: Dict[(str, Any)] | None) -> Dict[(str, Any)]`

---

## File: `backend/app/db/pg.py`
### Global Functions
#### Function `get_conn`
`def get_conn()`

#### Function `ensure_tables`
`def ensure_tables()`

#### Function `get_graph_version`
`def get_graph_version(tenant_id: str) -> int`

#### Function `set_graph_version`
`def set_graph_version(tenant_id: str, version: int) -> None`

#### Function `add_graph_change`
`def add_graph_change(tenant_id: str, graph_version: int, target_id: str, change_type: str) -> None`

#### Function `get_changed_targets_since`
`def get_changed_targets_since(tenant_id: str, from_version: int, change_type: str | None) -> list[str]`

#### Function `ensure_schema_version`
`def ensure_schema_version()`

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

## File: `backend/app/events/publisher.py`
### Global Functions
#### Function `get_redis`
`def get_redis()`

#### Function `publish_graph_committed`
`def publish_graph_committed(event: Dict) -> None`

---

## File: `backend/app/main.py`
### Global Variables
- `tags_metadata`
- `app`
- `REQ_COUNTER`
- `LATENCY`
- `origins`

### Global Functions
#### Function `_code_for_status`
`def _code_for_status(status: int) -> str`

---

## File: `backend/app/schemas/context.py`
### Classes
#### Class `UserContext(BaseModel)`
**Fields**:
- `language: str`
- `attributes: Dict[(str, Any)]`

---

## File: `backend/app/schemas/proposal.py`
### Classes
#### Class `ProposalStatus(str, Enum)`

#### Class `OpType(str, Enum)`

#### Class `Operation(BaseModel)`
**Fields**:
- `op_id: str`
- `op_type: OpType`
- `target_id: Optional[str]`
- `temp_id: Optional[str]`
- `properties_delta: Dict[(str, Any)]`
- `match_criteria: Dict[(str, Any)]`
- `evidence: Dict[(str, Any)]`
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

## File: `backend/app/schemas/roadmap.py`
### Classes
#### Class `RoadmapRequest(BaseModel)`
**Fields**:
- `subject_uid: Optional[str]`
- `user_context: UserContext`
- `limit: int`
- `current_progress: Dict[(str, float)]`

---

## File: `backend/app/services/ai_engine/ai_engine.py`
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

## File: `backend/app/services/auth/jwt_tokens.py`
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

## File: `backend/app/services/auth/passwords.py`
### Global Functions
#### Function `hash_password`
`def hash_password(password: str) -> str`

#### Function `verify_password`
`def verify_password(password: str, password_hash: str) -> bool`

---

## File: `backend/app/services/auth/users_repo.py`
### Global Functions
#### Function `_get_conn`
`def _get_conn()`

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

## File: `backend/app/services/curriculum/repo.py`
### Global Functions
#### Function `get_conn`
`def get_conn()`

#### Function `create_curriculum`
`def create_curriculum(code: str, title: str, standard: str, language: str) -> Dict`

#### Function `add_curriculum_nodes`
`def add_curriculum_nodes(code: str, nodes: List[Dict]) -> Dict`

#### Function `get_graph_view`
`def get_graph_view(code: str) -> Dict`

---

## File: `backend/app/services/diff.py`
### Global Functions
#### Function `apply_delta`
`def apply_delta(base: Dict[(str, Any)], delta: Dict[(str, Any)]) -> Dict[(str, Any)]`

#### Function `build_diff`
`def build_diff(proposal_id: str) -> Dict`

---

## File: `backend/app/services/embeddings/provider.py`
### Global Functions
#### Function `get_provider`
`def get_provider(dim_default: int) -> BaseEmbeddingProvider`

### Classes
#### Class `BaseEmbeddingProvider`

**Methods**:
- `def embed_text(self, text: str) -> List[float]`

#### Class `HashEmbeddingProvider(BaseEmbeddingProvider)`

**Methods**:
- `def __init__(self, dim: int)`
- `def embed_text(self, text: str) -> List[float]`

#### Class `OpenAIEmbeddingProvider(BaseEmbeddingProvider)`

**Methods**:
- `def __init__(self, dim: int, model: str, api_key: str | None)`
- `def embed_text(self, text: str) -> List[float]`

---

## File: `backend/app/services/evidence.py`
### Global Functions
#### Function `get_chunk_text`
`def get_chunk_text(chunk_id: str) -> Optional[str]`

#### Function `resolve_evidence`
`def resolve_evidence(ev: Dict) -> Dict`

---

## File: `backend/app/services/graph/graph_service.py`
### Global Functions
#### Function `dag_check`
`def dag_check(edges: List[Dict]) -> List[List[str]]`

#### Function `connectivity_stats`
`def connectivity_stats(nodes: List[str], edges: List[Dict]) -> Dict`

#### Function `cognitive_distance`
`def cognitive_distance(root: str, leaves: List[str], edges: List[Dict]) -> Dict[(str, int)]`

---

## File: `backend/app/services/graph/neo4j_repo.py`
### Global Functions
#### Function `get_driver`
`def get_driver()`

#### Function `read_graph`
`def read_graph(subject_uid: str | None, tenant_id: str | None) -> Tuple[(List[Dict], List[Dict])]`

#### Function `relation_context`
`def relation_context(from_uid: str, to_uid: str, tenant_id: str | None) -> Dict`

#### Function `neighbors`
`def neighbors(center_uid: str, depth: int, tenant_id: str | None) -> Tuple[(List[Dict], List[Dict])]`

#### Function `node_by_uid`
`def node_by_uid(uid: str, tenant_id: str) -> Dict`

#### Function `relation_by_pair`
`def relation_by_pair(from_uid: str, to_uid: str, typ: str, tenant_id: str) -> Dict`

#### Function `get_node_details`
`def get_node_details(uid: str, tenant_id: str | None) -> Dict`

### Classes
#### Class `Neo4jRepo`

**Methods**:
- `def __init__(self, uri: Optional[str], user: Optional[str], password: Optional[str], max_retries: int, backoff_sec: float)`
- `def close(self)`
- `def _retry(self, fn: Callable[([Any], Any)]) -> Any`
- `def write(self, query: str, params: Dict | None) -> None`
- `def read(self, query: str, params: Dict | None) -> List[Dict]`
- `def _chunks(self, rows: List[Dict], size: int) -> List[List[Dict]]`
- `def write_unwind(self, query: str, rows: List[Dict], chunk_size: int) -> None`

---

## File: `backend/app/services/impact.py`
### Global Variables
- `_CACHE: Dict[(Tuple[(str, int)], Tuple[(float, Tuple[(List[Dict], List[Dict])])])]`
- `_TTL_S`

### Global Functions
#### Function `_neighbors_cached`
`def _neighbors_cached(uid: str, depth: int) -> Tuple[(List[Dict], List[Dict])]`

#### Function `impact_subgraph_for_proposal`
`def impact_subgraph_for_proposal(proposal_id: str, depth: int, types: Optional[List[str]], max_nodes: Optional[int], max_edges: Optional[int]) -> Dict`

---

## File: `backend/app/services/ingestion/academic.py`
### Classes
#### Class `AcademicIngestionStrategy(IngestionStrategy)`

---

## File: `backend/app/services/ingestion/corporate.py`
### Classes
#### Class `CorporateIngestionStrategy(IngestionStrategy)`

---

## File: `backend/app/services/ingestion/interface.py`
### Classes
#### Class `IngestionStrategy(ABC)`

---

## File: `backend/app/services/integrity.py`
### Global Functions
#### Function `check_canon_compliance`
`def check_canon_compliance(nodes: List[Dict], rels: List[Dict]) -> List[str]`

#### Function `check_prereq_cycles`
`def check_prereq_cycles(rels: List[Dict]) -> List[Tuple[(str, str)]]`

> rels: list of {'type': 'PREREQ', 'from_uid': str, 'to_uid': str}

#### Function `check_orphan_skills`
`def check_orphan_skills(nodes: List[Dict], rels: List[Dict]) -> List[str]`

> nodes: list of {'type': 'Skill', 'uid': str}
> rels: list of {'type': 'USES_SKILL', 'from_uid': str, 'to_uid': str}

#### Function `check_hierarchy_compliance`
`def check_hierarchy_compliance(nodes: List[Dict], rels: List[Dict]) -> List[str]`

> Ensures:
> - Topic has incoming CONTAINS from Subsection
> - Subsection has incoming CONTAINS from Section
> - Section has incoming CONTAINS from Subject
> 
> Only checks nodes present in the list (if a node is created/merged, it must have a parent link in the same changeset OR be valid otherwise).
> Warning: This local check might be too strict for partial updates if not handled carefully.
> For now, we strictly check: IF a node of type T is in 'nodes', it MUST have an incoming CONTAINS in 'rels'.

#### Function `integrity_check_subgraph`
`def integrity_check_subgraph(nodes: List[Dict], rels: List[Dict]) -> Dict`

#### Function `check_skill_based_on_rules`
`def check_skill_based_on_rules(nodes: List[Dict], rels: List[Dict], min_required: int, max_allowed: int | None) -> Dict`

---

## File: `backend/app/services/kb/builder.py`
### Global Variables
- `BASE_DIR`

### Global Functions
#### Function `openai_chat`
`def openai_chat(messages: List[Dict], model: str, temperature: float) -> Dict`

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

#### Function `enrich_topic`
`def enrich_topic(subject_uid: str, topic_uid: str, title: str) -> Dict`

#### Function `enrich_all_topics`
`def enrich_all_topics() -> Dict`

#### Function `truth_check_openai`
`def truth_check_openai(text: str, context: Optional[str]) -> Dict`

#### Function `bootstrap_subject_from_skill_topics`
`def bootstrap_subject_from_skill_topics(subject_uid: str, subject_title: str, section_title: str) -> Dict`

---

## File: `backend/app/services/kb/jsonl_io.py`
### Global Variables
- `BASE_DIR`
- `KB_DIR`

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

## File: `backend/app/services/proposal_service.py`
### Global Variables
- `EVIDENCE_REQUIRED_OPS`

### Global Functions
#### Function `validate_operations`
`def validate_operations(ops: List[Operation]) -> None`

#### Function `_deep_normalize`
`def _deep_normalize(obj)`

#### Function `compute_checksum`
`def compute_checksum(ops: List[Operation]) -> str`

#### Function `create_draft_proposal`
`def create_draft_proposal(tenant_id: str, base_graph_version: int, ops: List[Operation]) -> Proposal`

---

## File: `backend/app/services/questions.py`
### Global Variables
- `BASE_DIR`
- `KB_DIR`

### Global Functions
#### Function `load_jsonl`
`def load_jsonl(filename: str) -> List[Dict]`

#### Function `get_examples_indexed`
```python
@lru_cache(...)
```
`def get_examples_indexed()`

#### Function `select_examples_for_topics`
`def select_examples_for_topics(topic_uids: List[str], limit: int, difficulty_min: int, difficulty_max: int, exclude_uids: Set[str] | None, tenant_id: str | None)`

#### Function `all_topic_uids_from_examples`
`def all_topic_uids_from_examples() -> List[str]`

---

## File: `backend/app/services/reasoning/gaps.py`
### Global Functions
#### Function `compute_gaps`
`def compute_gaps(subject_uid: str, progress: Dict[(str, float)], goals: List[str] | None, prereq_threshold: float) -> Dict[(str, List[Dict])]`

---

## File: `backend/app/services/reasoning/mastery_update.py`
### Global Functions
#### Function `update_mastery`
`def update_mastery(prior_mastery: float, score: float, confidence: float | None) -> Dict`

---

## File: `backend/app/services/reasoning/next_best_topic.py`
### Global Functions
#### Function `next_best_topics`
`def next_best_topics(subject_uid: str, progress: Dict[(str, float)], prereq_threshold: float, top_k: int, alpha: float, beta: float) -> Dict[(str, List[Dict])]`

---

## File: `backend/app/services/reasoning/roadmap.py`
### Global Functions
#### Function `build_roadmap`
`def build_roadmap(subject_uid: str, progress: Dict[(str, float)], goals: List[str] | None, prereq_threshold: float, top_k: int) -> Dict[(str, List[Dict])]`

---

## File: `backend/app/services/rebase.py`
### Global Functions
#### Function `rebase_check`
`def rebase_check(tenant_id: str, base_graph_version: int, target_ids: List[str]) -> RebaseResult`

### Classes
#### Class `RebaseResult(str, Enum)`

---

## File: `backend/app/services/roadmap_planner.py`
### Global Functions
#### Function `plan_route`
`def plan_route(subject_uid: str | None, progress: Dict[(str, float)], limit: int, penalty_factor: float, tenant_id: str | None, curriculum_code: str | None) -> List[Dict]`

---

## File: `backend/app/services/validation.py`
### Global Functions
#### Function `_as_list`
`def _as_list(x)`

#### Function `_index_nodes`
`def _index_nodes(snapshot: Dict) -> Dict[(str, Dict)]`

#### Function `_iter_edges`
`def _iter_edges(snapshot: Dict)`

#### Function `validate_canonical_graph_snapshot`
`def validate_canonical_graph_snapshot(snapshot: Dict) -> Dict`

---

## File: `backend/app/services/vector/indexer.py`
### Global Variables
- `ALLOWED_TYPES`

### Global Functions
#### Function `ensure_collection`
`def ensure_collection(client: QdrantClient, name: str, dim: int) -> None`

#### Function `index_entities`
`def index_entities(tenant_id: str, uids: List[str], collection: str | None, dim: int | None) -> Dict`

---

## File: `backend/app/services/vector/qdrant_service.py`
### Global Variables
- `client`
- `COLLECTION`
- `oai`

### Global Functions
#### Function `query_similar`
`def query_similar(embedding: List[float], top_k: int) -> List[Tuple[(str, float)]]`

---

## File: `backend/app/tasks/worker.py`
### Classes
#### Class `WorkerSettings`

---

## File: `backend/app/utils/atomic_write.py`
### Global Functions
#### Function `write_jsonl_atomic`
`def write_jsonl_atomic(path: str, items: List[Dict], validate: Callable[([Dict], None)]) -> None`

---

## File: `backend/app/workers/commit.py`
### Global Functions
#### Function `_load_proposal`
`def _load_proposal(proposal_id: str) -> Dict | None`

#### Function `_update_proposal_status`
`def _update_proposal_status(proposal_id: str, status: str) -> None`

#### Function `_collect_target_ids`
`def _collect_target_ids(ops: List[Dict[(str, Any)]]) -> List[str]`

#### Function `_collect_prereq_edges`
`def _collect_prereq_edges(ops: List[Dict[(str, Any)]]) -> List[Dict[(str, str)]]`

#### Function `_apply_ops_tx`
`def _apply_ops_tx(tx, tenant_id: str, ops: List[Dict[(str, Any)]]) -> None`

#### Function `commit_proposal`
`def commit_proposal(proposal_id: str) -> Dict`

---

## File: `backend/app/workers/ingestion.py`
### Global Variables
- `_WS`

### Global Functions
#### Function `normalize_text`
`def normalize_text(text: str) -> str`

#### Function `chunk_text`
`def chunk_text(text: str, max_len: int) -> List[Dict]`

#### Function `_hash16`
`def _hash16(text: str) -> List[float]`

#### Function `ensure_collection`
`def ensure_collection(client: QdrantClient, name: str, size: int)`

#### Function `embed_chunks`
`def embed_chunks(tenant_id: str, doc_id: str, chunks: List[Dict], collection: str) -> int`

---

## File: `backend/app/workers/integrity_async.py`
### Global Functions
#### Function `_collect_nodes_and_rels`
`def _collect_nodes_and_rels(ops: List[Dict[(str, Any)]]) -> Dict[(str, List[Dict])]`

#### Function `process_once`
`def process_once(limit: int) -> Dict`

---

## File: `backend/app/workers/outbox_publisher.py`
### Global Functions
#### Function `process_once`
`def process_once(limit: int) -> Dict`

#### Function `process_retry`
`def process_retry(limit: int) -> Dict`

---

## File: `backend/app/workers/vector_sync.py`
### Global Functions
#### Function `mark_entities_updated`
`def mark_entities_updated(tenant_id: str, targets: List[str], collection: str) -> int`

#### Function `consume_graph_committed`
`def consume_graph_committed() -> Dict`

---

## File: `backend/scripts/analyze_codebase.py`
### Global Functions
#### Function `get_type_annotation`
`def get_type_annotation(annotation) -> str`

> Helper to convert AST annotation to string.

#### Function `get_docstring`
`def get_docstring(node) -> str`

> Extract and clean docstring.

#### Function `analyze_function`
`def analyze_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> Dict[(str, Any)]`

#### Function `analyze_class`
`def analyze_class(node: ast.ClassDef) -> Dict[(str, Any)]`

#### Function `analyze_file`
`def analyze_file(file_path: str) -> Dict[(str, Any)]`

#### Function `generate_markdown_report`
`def generate_markdown_report(results: List[Dict[(str, Any)]]) -> str`

#### Function `main`
`def main()`

---

## File: `backend/scripts/apply_schema.py`
### Global Variables
- `SCHEMA_PATH`

### Global Functions
#### Function `main`
`def main()`

---

## File: `backend/scripts/apply_vector_schema.py`
### Global Functions
#### Function `apply_vector_schema`
`def apply_vector_schema()`

---

## File: `backend/scripts/auto_link_skills_methods.py`
### Global Variables
- `logger`

### Global Functions
#### Function `main`
`def main()`

> Основная функция для запуска автоматической привязки

### Classes
#### Class `SkillMethodLinker`

**Methods**:
- `def __init__(self, db_config: Dict[(str, str)])`
- `def _load_applicability_types(self) -> Dict[(str, Dict)]`
- `def connect_db(self)`
- `def get_skills_with_types(self, conn) -> List[Tuple[(str, List[str])]]`
- `def get_methods_with_types(self, conn) -> List[Tuple[(str, List[str])]]`
- `def calculate_compatibility(self, skill_types: List[str], method_types: List[str]) -> float`
- `def _is_key_domain(self, type_name: str) -> bool`
- `def determine_weight(self, compatibility: float) -> str`
- `def link_skills_methods(self, min_compatibility: float) -> List[Dict]`
- `def save_links_to_db(self, links: List[Dict])`
- `def export_links_to_jsonl(self, links: List[Dict], filename: str)`

---

## File: `backend/scripts/auto_link_skills_topics.py`
### Global Variables
- `BASE_DIR`
- `KB_DIR`

### Global Functions
#### Function `load_jsonl`
`def load_jsonl(filename: str) -> List[Dict]`

#### Function `tokenize`
`def tokenize(text: str) -> List[str]`

#### Function `main`
`def main()`

---

## File: `backend/scripts/build_math_ontology.py`
### Global Functions
#### Function `main`
`def main() -> int`

---

## File: `backend/scripts/clean_orphans.py`
### Global Variables
- `KB_DIR`

### Global Functions
#### Function `load_jsonl`
`def load_jsonl(filename: str) -> List[Dict]`

#### Function `save_jsonl`
`def save_jsonl(filename: str, data: List[Dict])`

#### Function `main`
`def main()`

---

## File: `backend/scripts/clear_graph.py`
### Global Variables
- `NEO4J_URI`
- `NEO4J_USER`
- `NEO4J_PASSWORD`

### Global Functions
#### Function `main`
`def main()`

---

## File: `backend/scripts/clear_graph_full.py`
### Global Variables
- `NEO4J_URI`
- `NEO4J_USER`
- `NEO4J_PASSWORD`

### Global Functions
#### Function `main`
`def main()`

---

## File: `backend/scripts/clear_neo4j.py`
### Global Functions
#### Function `get_env`
`def get_env(name: str, default: str | None) -> str`

#### Function `clear_nodes_and_relationships`
`def clear_nodes_and_relationships(session)`

#### Function `drop_constraints`
`def drop_constraints(session)`

#### Function `drop_indexes`
`def drop_indexes(session)`

#### Function `main`
`def main()`

---

## File: `backend/scripts/create_jsonl_data.py`
### Global Variables
- `KB_DIR`
- `SUBJECTS`
- `SECTIONS`
- `TOPICS`
- `SKILLS`

### Global Functions
#### Function `write_jsonl`
`def write_jsonl(filename, data)`

---

## File: `backend/scripts/fast_import.py`
### Global Functions
#### Function `main`
`def main() -> int`

---

## File: `backend/scripts/generate_examples_for_topics.py`
### Global Variables
- `BASE_DIR`
- `KB_DIR`

### Global Functions
#### Function `load_jsonl`
`def load_jsonl(filename: str) -> List[Dict]`

#### Function `append_jsonl`
`def append_jsonl(filename: str, items: List[Dict])`

#### Function `make_example_uid`
`def make_example_uid(topic_uid: str, idx: int) -> str`

#### Function `generate_statement`
`def generate_statement(title: str, description: str) -> str`

#### Function `main`
`def main()`

---

## File: `backend/scripts/load_data.py`
### Global Variables
- `logger`

### Global Functions
#### Function `main`
`def main()`

> Основная функция

### Classes
#### Class `DataLoader`

**Methods**:
- `def __init__(self, db_config: Dict[(str, str)])`
- `def connect_db(self)`
- `def load_jsonl_file(self, filename: str) -> List[Dict]`
- `def load_subjects(self, conn)`
- `def load_sections(self, conn)`
- `def load_topics(self, conn)`
- `def load_skills(self, conn)`
- `def load_methods(self, conn)`
- `def load_examples(self, conn)`
- `def load_errors(self, conn)`
- `def load_skill_methods(self, conn)`
- `def load_all_data(self)`

---

## File: `backend/scripts/migrate_graph_to_canon.py`
### Global Variables
- `NEO4J_URI`
- `NEO4J_USER`
- `NEO4J_PASSWORD`
- `ALLOWED_LABELS`
- `ALLOWED_RELS`

### Global Functions
#### Function `run`
`def run(session, cy: str, params: Dict | None) -> None`

#### Function `migrate_relationships`
`def migrate_relationships(session) -> Dict[(str, int)]`

#### Function `ensure_hierarchy`
`def ensure_hierarchy(session) -> Dict[(str, int)]`

#### Function `remove_orphans`
`def remove_orphans(session) -> Dict[(str, List[str])]`

#### Function `ensure_tenant_id`
`def ensure_tenant_id(session, default_tenant) -> int`

#### Function `delete_user_artifacts`
`def delete_user_artifacts(session) -> Dict[(str, int)]`

#### Function `main`
`def main()`

#### Function `json_dump`
`def json_dump(obj) -> str`

---

## File: `backend/scripts/reset_neo4j_database.py`
### Global Variables
- `NEO4J_URI`
- `NEO4J_USER`
- `NEO4J_PASSWORD`
- `NEO4J_DB`

### Global Functions
#### Function `main`
`def main()`

---

## File: `backend/scripts/show_property_keys.py`
### Global Variables
- `NEO4J_URI`
- `NEO4J_USER`
- `NEO4J_PASSWORD`

### Global Functions
#### Function `main`
`def main()`

---

## File: `backend/scripts/validate_graph_canon.py`
### Global Variables
- `NEO4J_URI`
- `NEO4J_USER`
- `NEO4J_PASSWORD`
- `ALLOWED_LABELS`
- `ALLOWED_RELS`

### Global Functions
#### Function `fail`
`def fail(msg: str) -> None`

#### Function `main`
`def main()`

---

## File: `backend/services/question_selector.py`
### Global Variables
- `__all__`

---

## File: `backend/tests/conftest.py`
### Global Functions
#### Function `_clean_db`
```python
@fixture(...)
```
`def _clean_db()`

---

## File: `backend/tests/integration/test_outbox_delivery.py`
### Global Functions
#### Function `test_outbox_publishes_graph_committed_to_redis`
`def test_outbox_publishes_graph_committed_to_redis()`

---

## File: `backend/tests/test_auth_jwt.py`
### Global Functions
#### Function `test_register_login_me_without_pg`
`def test_register_login_me_without_pg(monkeypatch)`

#### Function `test_admin_requires_auth`
`def test_admin_requires_auth(monkeypatch)`

---

## File: `backend/tests/test_curriculum_repo_no_pg.py`
### Global Functions
#### Function `test_admin_curriculum_without_pg`
`def test_admin_curriculum_without_pg(monkeypatch)`

---

## File: `backend/tests/test_errors.py`
### Global Variables
- `app`
- `client`

### Global Functions
#### Function `http_error`
```python
@get(...)
```
`def http_error()`

#### Function `validation_error`
```python
@post(...)
```
`def validation_error(user: User)`

#### Function `forbidden`
```python
@get(...)
```
`def forbidden()`

#### Function `unavailable`
```python
@get(...)
```
`def unavailable()`

#### Function `test_http_exception`
`def test_http_exception()`

#### Function `test_validation_exception`
`def test_validation_exception()`

#### Function `test_unexpected_exception`
`def test_unexpected_exception()`

#### Function `test_not_found`
`def test_not_found()`

#### Function `test_forbidden`
`def test_forbidden()`

#### Function `test_service_unavailable`
`def test_service_unavailable()`

### Classes
#### Class `User(BaseModel)`
**Fields**:
- `email: EmailStr`

---

## File: `backend/tests/test_errors_graphql.py`
### Global Functions
#### Function `test_graphql_error_details`
`def test_graphql_error_details(monkeypatch)`

---

## File: `backend/tests/test_graphql.py`
### Global Functions
#### Function `test_graphql_topic_details`
`def test_graphql_topic_details(monkeypatch)`

---

## File: `backend/tests/test_graphql_errors_skill.py`
### Global Functions
#### Function `test_graphql_errors_by_skill`
`def test_graphql_errors_by_skill(monkeypatch)`

---

## File: `backend/tests/test_import.py`
### Global Functions
#### Function `test_load_jsonl_handles_missing`
`def test_load_jsonl_handles_missing(tmp_path)`

---

## File: `backend/tests/test_levels.py`
### Global Functions
#### Function `test_levels_endpoints`
`def test_levels_endpoints(monkeypatch)`

---

## File: `backend/tests/test_planner.py`
### Global Functions
#### Function `test_plan_route_basic`
`def test_plan_route_basic(monkeypatch)`

---

## File: `backend/tests/test_selector.py`
### Global Functions
#### Function `test_select_examples_empty_env`
`def test_select_examples_empty_env(monkeypatch)`

---

## File: `backend/tests/unit/test_api_impact.py`
### Global Functions
#### Function `test_api_impact_endpoint_filters_types`
`def test_api_impact_endpoint_filters_types()`

---

## File: `backend/tests/unit/test_ast_write_guard.py`
### Global Variables
- `ALLOWED`
- `WRITE_KEYWORDS`

### Global Functions
#### Function `test_ast_guard_on_write_queries`
`def test_ast_guard_on_write_queries()`

---

## File: `backend/tests/unit/test_async_check_required.py`
### Global Functions
#### Function `test_async_check_triggers_on_threshold`
`def test_async_check_triggers_on_threshold()`

---

## File: `backend/tests/unit/test_canonical.py`
### Global Functions
#### Function `test_normalize_text_whitespace_and_nfkc`
`def test_normalize_text_whitespace_and_nfkc()`

#### Function `test_canonical_json_sorted_keys`
`def test_canonical_json_sorted_keys()`

#### Function `test_sha256_and_hashes_determinism`
`def test_sha256_and_hashes_determinism()`

#### Function `test_canonical_hash_from_text_is_stable_with_dirty_input`
`def test_canonical_hash_from_text_is_stable_with_dirty_input()`

---

## File: `backend/tests/unit/test_context_dao.py`
### Global Functions
#### Function `test_dao_requires_tenant`
`def test_dao_requires_tenant()`

#### Function `test_dao_uses_context_tenant`
`def test_dao_uses_context_tenant()`

---

## File: `backend/tests/unit/test_diff_rel_context.py`
### Global Functions
#### Function `test_diff_rel_contains_from_to_context`
`def test_diff_rel_contains_from_to_context()`

---

## File: `backend/tests/unit/test_events.py`
### Global Functions
#### Function `test_publish_graph_committed_pushes_to_list`
`def test_publish_graph_committed_pushes_to_list()`

---

## File: `backend/tests/unit/test_evidence_text_in_diff.py`
### Global Functions
#### Function `test_diff_contains_chunk_text`
`def test_diff_contains_chunk_text()`

---

## File: `backend/tests/unit/test_graph_changes_type.py`
### Global Functions
#### Function `test_graph_changes_insert_includes_change_type`
`def test_graph_changes_insert_includes_change_type()`

---

## File: `backend/tests/unit/test_hash_embedding_provider.py`
### Global Functions
#### Function `test_hash_embedding_provider_dim`
`def test_hash_embedding_provider_dim()`

---

## File: `backend/tests/unit/test_impact_filters_cache.py`
### Global Functions
#### Function `test_impact_filters_by_type_and_limits`
`def test_impact_filters_by_type_and_limits()`

---

## File: `backend/tests/unit/test_impact_subgraph.py`
### Global Functions
#### Function `test_impact_subgraph_collects_neighbors_from_diff_items`
`def test_impact_subgraph_collects_neighbors_from_diff_items()`

---

## File: `backend/tests/unit/test_ingestion.py`
### Global Functions
#### Function `test_parse_and_chunk`
`def test_parse_and_chunk()`

#### Function `test_embed_chunks_into_qdrant`
`def test_embed_chunks_into_qdrant()`

---

## File: `backend/tests/unit/test_integrity.py`
### Global Functions
#### Function `test_prereq_cycle_detection`
`def test_prereq_cycle_detection()`

#### Function `test_dangling_skills_detection`
`def test_dangling_skills_detection()`

#### Function `test_integrity_check_subgraph`
`def test_integrity_check_subgraph()`

#### Function `test_canon_compliance`
`def test_canon_compliance()`

---

## File: `backend/tests/unit/test_integrity_async_worker.py`
### Global Functions
#### Function `test_integrity_async_marks_ready_for_valid_ops`
`def test_integrity_async_marks_ready_for_valid_ops()`

---

## File: `backend/tests/unit/test_integrity_base_rules.py`
### Global Functions
#### Function `test_commit_fails_on_skill_based_on_exceeding_max`
`def test_commit_fails_on_skill_based_on_exceeding_max()`

---

## File: `backend/tests/unit/test_integrity_dangling_skill.py`
### Global Functions
#### Function `test_commit_rejects_dangling_skill_without_based_on`
`def test_commit_rejects_dangling_skill_without_based_on()`

---

## File: `backend/tests/unit/test_lifecycle_fields.py`
### Global Functions
#### Function `test_created_node_has_lifecycle_and_created_at`
`def test_created_node_has_lifecycle_and_created_at()`

---

## File: `backend/tests/unit/test_math.py`
### Global Functions
#### Function `test_w_edge_clip_bounds`
`def test_w_edge_clip_bounds()`

#### Function `test_ema_stability`
`def test_ema_stability()`

---

## File: `backend/tests/unit/test_math_ontology_builder.py`
### Global Functions
#### Function `test_build_mathematics_ontology_jsonl`
`def test_build_mathematics_ontology_jsonl()`

#### Function `test_enrich_topics_jsonl_only`
`def test_enrich_topics_jsonl_only()`

---

## File: `backend/tests/unit/test_no_direct_writes.py`
### Global Functions
#### Function `test_no_direct_neo4j_writes_outside_commit_worker`
`def test_no_direct_neo4j_writes_outside_commit_worker()`

---

## File: `backend/tests/unit/test_outbox_compensation.py`
### Global Functions
#### Function `test_outbox_marks_failed_on_unsupported_event`
`def test_outbox_marks_failed_on_unsupported_event()`

---

## File: `backend/tests/unit/test_outbox_publisher.py`
### Global Functions
#### Function `test_outbox_publisher_publishes_graph_committed`
`def test_outbox_publisher_publishes_graph_committed()`

---

## File: `backend/tests/unit/test_proposal_checksum.py`
### Global Functions
#### Function `test_checksum_stable_with_key_reordering`
`def test_checksum_stable_with_key_reordering()`

---

## File: `backend/tests/unit/test_proposal_commit_outbox_event2.py`
### Global Functions
#### Function `test_commit_writes_outbox_event`
`def test_commit_writes_outbox_event()`

---

## File: `backend/tests/unit/test_proposal_diff.py`
### Global Functions
#### Function `test_build_diff_for_create_node_and_rel`
`def test_build_diff_for_create_node_and_rel()`

---

## File: `backend/tests/unit/test_proposal_diff_evidence.py`
### Global Functions
#### Function `test_diff_contains_evidence`
`def test_diff_contains_evidence()`

---

## File: `backend/tests/unit/test_proposal_review.py`
### Global Functions
#### Function `test_approve_and_commit_flow`
`def test_approve_and_commit_flow()`

---

## File: `backend/tests/unit/test_proposal_validation.py`
### Global Functions
#### Function `test_evidence_required_for_create`
`def test_evidence_required_for_create()`

#### Function `test_validation_fails_without_evidence`
`def test_validation_fails_without_evidence()`

---

## File: `backend/tests/unit/test_proposals_created_at_sort.py`
### Global Functions
#### Function `test_list_sorted_by_created_at_desc`
`def test_list_sorted_by_created_at_desc()`

---

## File: `backend/tests/unit/test_proposals_list.py`
### Global Functions
#### Function `test_list_proposals_by_tenant_and_status`
`def test_list_proposals_by_tenant_and_status()`

---

## File: `backend/tests/unit/test_reasoning_next_best_determinism.py`
### Global Functions
#### Function `test_next_best_topic_shape`
`def test_next_best_topic_shape()`

---

## File: `backend/tests/unit/test_reasoning_roadmap_shape.py`
### Global Functions
#### Function `test_roadmap_shape`
`def test_roadmap_shape()`

---

## File: `backend/tests/unit/test_rebase.py`
### Global Functions
#### Function `test_same_version`
`def test_same_version()`

#### Function `test_fast_rebase_no_intersection`
`def test_fast_rebase_no_intersection()`

#### Function `test_conflict_with_intersection`
`def test_conflict_with_intersection()`

---

## File: `backend/tests/unit/test_roadmap_planner.py`
### Global Functions
#### Function `test_plan_route_orders_by_priority`
`def test_plan_route_orders_by_priority()`

---

## File: `backend/tests/unit/test_schema_gatekeeper_tenant.py`
### Global Functions
#### Function `test_schema_gatekeeper_tenant`
`def test_schema_gatekeeper_tenant()`

---

## File: `backend/tests/unit/test_vector_dimension_consistency.py`
### Global Functions
#### Function `test_vector_sync_respects_existing_collection_dimension`
`def test_vector_sync_respects_existing_collection_dimension()`

---

## File: `backend/tests/unit/test_vector_indexer_noop.py`
### Global Functions
#### Function `test_indexer_noop_empty`
`def test_indexer_noop_empty()`

---

## File: `backend/tests/unit/test_vector_rescore.py`
### Global Functions
#### Function `test_rescore_entities_on_event`
`def test_rescore_entities_on_event()`

---

## File: `backend/tests/unit/test_vector_sync.py`
### Global Functions
#### Function `test_consume_graph_committed_no_targets`
`def test_consume_graph_committed_no_targets()`

#### Function `test_consume_graph_committed_with_targets`
`def test_consume_graph_committed_with_targets()`

---
