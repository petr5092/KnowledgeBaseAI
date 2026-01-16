# TASK: Global API Refactoring & Cleanup

**Status:** 🟡 In Progress
**Agent:** Trae Solo Coder
**Objective:** Eliminate code duplication, enforce Domain-Agnostic architecture, and clean up the OpenAPI schema by consolidating scattered endpoints into a logical structure.

---

## 🛑 ARCHITECTURAL STANDARDS

1.  **Single Source of Truth:** Logic for "Roadmap" or "Recommendations" must live in ONE service and be exposed via ONE endpoint.
2.  **Domain Agnostic:** No field names like `user_class` or `school_standard`. Use generic `attributes` or `context`.
3.  **Strict Write Flow:** No "Magic Fill" or direct "Generate Subject" endpoints. All content creation flows through `Ingestion -> Proposal`.
4.  **Clean Schemas:** No auto-generated Pydantic names (`app__api__...`). All schemas must have explicit classes.

---

## 📅 PHASE 1: Destructive Cleanup (Remove Trash)
*Goal: Remove legacy, debug, and violating endpoints.*

- [ ] **1.1 Delete `api/construct.py`**
    - [ ] Remove the file.
    - [ ] Remove reference in `main.py`.
    - [ ] *Reason:* Violates the Proposal flow.

- [ ] **1.2 Deprecate/Remove `api/admin_generate.py`**
    - [ ] Ensure the logic for "Subject Generation" is migrated to `api/ingestion.py` (strategy: "academic_generation").
    - [ ] Remove the file `api/admin_generate.py`.
    - [ ] Remove reference in `main.py`.

- [ ] **1.3 Clean `api/admin_curriculum.py`**
    - [ ] Check if `admin_create_curriculum` uses specific school fields. If so, generalize them.

---

## 📅 PHASE 2: Data Model Unification
*Goal: Fix "Spaghetti Schemas" and Hardcoded Context.*

- [ ] **2.1 Universal `UserContext`**
    - [ ] Locate `schemas/user.py` (or where `UserContext` is defined).
    - [ ] Refactor `UserContext` to:
      ```python
      class UserContext(BaseModel):
          attributes: Dict[str, Any] = Field(default_factory=dict, description="e.g. {'grade': 5} or {'role': 'engineer'}")
          # Remove user_class, age
      ```
    - [ ] Update usages in `api/assessment.py` and `services/assessment/`.

- [ ] **2.2 Unified `RoadmapRequest`**
    - [ ] Create/Update `schemas/engine.py`.
    - [ ] Define **ONE** master class `UnifiedRoadmapRequest`:
      ```python
      class UnifiedRoadmapRequest(BaseModel):
          subject_uid: Optional[str]
          progress: Dict[str, float]
          goals: List[str] = []
          curriculum_context: Optional[str] = None # The "Prism" ID
          limit: int = 30
          settings: Dict[str, Any] = {} # penalty, etc.
      ```
    - [ ] Find all references to old `RoadmapInput` (in graph, curriculum, reasoning) and prepare to replace them.

---

## 📅 PHASE 3: Router Consolidation (The "Engine" Concept)
*Goal: Group logic by INTENT, not by implementation detail.*

- [ ] **3.1 Create `api/engine.py`**
    - [ ] This will be the main entry point for the Frontend/LMS.
    - [ ] Move **Roadmap** logic here: `POST /v1/engine/roadmap`. (Calls `services.roadmap_planner`).
    - [ ] Move **Recommendation** logic here: `POST /v1/engine/recommend` (Combines old `next_best_topic` and `adaptive_questions`).
    - [ ] Move **Chat/RAG** logic here: `POST /v1/engine/chat` (Calls `services.rag`).
    - [ ] Move **Viewport** logic here: `GET /v1/engine/viewport`.

- [ ] **3.2 Cleanup Old Routers**
    - [ ] Remove `api/graph.py` (moved to engine).
    - [ ] Remove `api/reasoning.py` (moved to engine).
    - [ ] Remove `api/curriculum.py` (only the public parts moved to engine; keep admin parts in `admin_curriculum`).

- [ ] **3.3 Update `main.py`**
    - [ ] Register `api.engine` router.
    - [ ] Remove deleted routers.

---

## 📅 PHASE 4: Verification & Polish
*Goal: Ensure the API is clean and usable.*

- [ ] **4.1 Fix Pydantic Naming**
    - [ ] Scan `openapi.json` (or generate it).
    - [ ] Ensure no schema names contain double underscores `__`.
    - [ ] Explicitly name response models (e.g., `response_model=RoadmapResponse`).

- [ ] **4.2 Verify Ingestion Flow**
    - [ ] Ensure `api/ingestion.py` is the **only** place to trigger content generation.

---

## 📝 Agent Logs
*(Record any conflicts found or decisions made)*

- **Log:** Waiting to start.