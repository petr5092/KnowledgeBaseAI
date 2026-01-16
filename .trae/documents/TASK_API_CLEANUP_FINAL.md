# TASK: API Final Cleanup (Dead Code Removal)

**Status:** 🔴 Urgent
**Agent:** Trae Solo Coder
**Objective:** Remove duplicate routers and fix Pydantic schema naming conflicts visible in `openapi.json`.

---

## 🔍 Diagnosis
The API currently exposes **duplicate endpoints** for Roadmap and other logic because old routers were not fully removed from `main.py` or the codebase.

1.  `/v1/curriculum/roadmap` exists alongside `/v1/engine/roadmap`.
2.  `/v1/reasoning/*` routes still exist.
3.  Schema names like `app__api__reasoning__RoadmapRequest` indicate class name conflicts.

---

## 📅 ACTION PLAN

- [ ] **1. Clean `backend/app/main.py`**
    - [ ] Open `main.py`.
    - [ ] **Delete** `app.include_router(curriculum.router)` (if it exists).
    - [ ] **Delete** `app.include_router(reasoning.router)` (if it exists).
    - [ ] **Delete** `app.include_router(knowledge.router)` (Move `topics_available` to `engine.py` first!).
    - [ ] Verify that ONLY `engine`, `assessment`, `auth`, `admin`, `ingestion` routers remain.

- [ ] **2. Move Orphaned Methods to Engine**
    - [ ] Move logic from `api/knowledge.py` (`topics_available`) -> `api/engine.py`.
    - [ ] Move logic from `api/curriculum.py` (`pathfind`) -> `api/engine.py` (if relevant for frontend).
    - [ ] *Note:* Keep `api/admin_curriculum.py` for Admin CRUD, but ensure it doesn't expose public calculation methods.

- [ ] **3. Delete Dead Files**
    - [ ] **DELETE** `backend/app/api/curriculum.py` (The public one, keep admin).
    - [ ] **DELETE** `backend/app/api/reasoning.py`.
    - [ ] **DELETE** `backend/app/api/knowledge.py`.

- [ ] **4. Verification**
    - [ ] Regenerate OpenAPI.
    - [ ] Ensure `RoadmapRequest` appears **only once** in schemas and has a clean name.