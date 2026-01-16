# TASK: API Final Polish & De-duplication

**Status:** 🔴 Urgent
**Agent:** Trae Solo Coder
**Objective:** Fix the incomplete refactoring. The API currently has duplicate endpoints, dirty Pydantic schema names, and retains legacy routes. We need a strict consolidation under `/v1/engine`.

---

## 🛑 DEFINITION OF DONE (Checklist)
1.  **Only ONE Roadmap Endpoint:** Available at `POST /v1/engine/roadmap`.
2.  **No Auto-generated Names:** Schemas like `app__schemas__...` must be gone.
3.  **Clean UserContext:** No hardcoded `user_class` or `age` fields.
4.  **No Legacy Routes:** `/v1/admin/generate_subject`, `/v1/graph/*`, `/v1/reasoning/*` must be removed (merged into engine).

---

## 📅 PHASE 1: Data Model Fixes (Strict)

- [ ] **1.1 Fix `UserContext` (app/schemas/context.py)**
    - [ ] Open `app/schemas/context.py`.
    - [ ] **Delete** specific fields: `user_class`, `age`, `level`, `country`, `timezone`.
    - [ ] **Add** generic field: `attributes: Dict[str, Any] = Field(default_factory=dict)`.
    - [ ] *Why:* To support both "5th Grade" and "Senior Engineer" without schema changes.

- [ ] **1.2 Fix `RoadmapRequest` Naming**
    - [ ] Ensure `app/schemas/roadmap.py` defines the class `RoadmapRequest` (or `UnifiedRoadmapRequest`).
    - [ ] Go to `app/api/graph.py`, `app/api/curriculum.py`, `app/api/reasoning.py`.
    - [ ] **REMOVE** any local Pydantic models named `RoadmapInput` or `RoadmapRequest`.
    - [ ] Import the single shared model from `app/schemas/roadmap.py` everywhere.

---

## 📅 PHASE 2: Router Consolidation (Physical Delete)

- [ ] **2.1 Verify `api/engine.py` Content**
    - [ ] Ensure `api/engine.py` contains the logic for:
        - `roadmap` (was in graph/curriculum/reasoning)
        - `viewport` (was in graph)
        - `chat` (was in graph)
        - `recommend` (was in reasoning)
    - [ ] The router prefix in this file (if set) should be compatible with `main.py`.

- [ ] **2.2 Delete Redundant Files**
    - [ ] **DELETE** `backend/app/api/graph.py` (Move logic to engine first if missing).
    - [ ] **DELETE** `backend/app/api/reasoning.py` (Move logic to engine first).
    - [ ] **DELETE** `backend/app/api/admin_generate.py` (Ensure logic is in `ingestion`).
    - [ ] **CLEAN** `backend/app/api/curriculum.py` -> Remove `roadmap`, `pathfind`. Keep only Admin CRUD operations.

---

## 📅 PHASE 3: Main.py Wiring

- [ ] **3.1 Fix `main.py` Routes**
    - [ ] Open `backend/app/main.py`.
    - [ ] **REMOVE** `app.include_router(graph.router)`
    - [ ] **REMOVE** `app.include_router(reasoning.router)`
    - [ ] **REMOVE** `app.include_router(admin_generate.router)`
    - [ ] **ADD** `app.include_router(engine.router, prefix="/v1/engine", tags=["Engine"])`
    - [ ] Ensure `ingestion.router` is included.

---

## 📝 Agent Logs
*(Self-Correction during execution)*

- **Log:** ...