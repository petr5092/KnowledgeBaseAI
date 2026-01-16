# TASK: Universal Knowledge Core Migration

**Status:** 🟢 Completed
**Agent:** Trae Solo Coder (Gemini 1.5 Pro)
**Objective:** Refactor the platform from a Math-centric LMS to a Domain-Agnostic Knowledge Graph Platform compliant with the Strict Graph Canon.

---

## 🛑 STRICT GRAPH CANON (DO NOT VIOLATE)

**1. Allowed Node Hierarchy:**
   `Subject` -> `Section` -> `Subsection` -> `Topic`
   *(No direct links Section->Topic. If a subsection is missing, create a generic one)*

**2. Allowed Relationships:**
   - `(:Subject)-[:CONTAINS]->(:Section)`
   - `(:Section)-[:CONTAINS]->(:Subsection)`
   - `(:Subsection)-[:CONTAINS]->(:Topic)`
   - `(:Topic)-[:PREREQ]->(:Topic)`
   - `(:Topic)-[:USES_SKILL]->(:Skill)`
   - `(:Skill)-[:LINKED]->(:Method)`
   - `(:Topic)-[:HAS_CONCEPT]->(:Concept)`
   - `(:Topic)-[:HAS_ERROR]->(:Error)`
   - `(:Topic)-[:HAS_EXAMPLE]->(:Example)`
   - `(:Topic)-[:HAS_UNIT]->(:ContentUnit)`

**3. Write Policy:**
   - NO direct DB writes for content generation.
   - ALL Ingestion/Generation must result in a **Proposal** (Draft).
   - `LLM Output` -> `JSON Structure` -> `ProposalService.create_proposal()` -> `Human Review` -> `Commit`.

---

## 📅 PHASE 1: De-Mathification (Cleanup)
*Goal: Remove hardcoded dependencies on Mathematics and school logic.*

- [x] **1.1 Analyze & Deprecate `services/kb/builder.py`**
    - [x] Remove `MATHEMATICS_ONTOLOGY` constant.
    - [x] Delete/Rename `build_mathematics_ontology`.
    - [x] Delete `rebuild_subject_math_with_openai`.
    - [x] Refactor `bootstrap_subject_from_skill_topics` to be generic (accepting `domain_context` string instead of assuming math).

- [x] **1.2 Abstract Prompts in `api/admin_generate.py`**
    - [x] Check `generate_subject` function.
    - [x] Remove hardcoded educational presets (if any).
    - [x] Ensure the prompt accepts a dynamic `domain` and `context_type` (e.g., "Academic Subject" vs "Corporate Manual").

- [x] **1.3 Verify `api/assessment.py`**
    - [x] Ensure question generation doesn't assume specific "Math" types.
    - [x] Verify `_age_to_class` usage is safe or deprecated in favor of a generic `user_level` attribute.

---

## 📅 PHASE 2: Universal Ingestion Engine
*Goal: Create a unified pipeline that accepts different input sources but produces the same Canonical Graph Structure.*

- [x] **2.1 Create Base Service Structure**
    - [x] Create folder `backend/app/services/ingestion/`.
    - [x] Create `backend/app/services/ingestion/interface.py`: Define `IngestionStrategy` abstract class with a method `process(source_content) -> List[GraphOperation]`.

- [x] **2.2 Implement Academic Strategy**
    - [x] Create `backend/app/services/ingestion/academic.py`.
    - [x] Implement logic to parse structured inputs (like Table of Contents).
    - [x] **LLM Prompt:** "Map this TOC to Subject->Section->Subsection->Topic".

- [x] **2.3 Implement Corporate Strategy**
    - [x] Create `backend/app/services/ingestion/corporate.py`.
    - [x] Implement logic for unstructured text (Regiments, Manuals).
    - [x] **LLM Prompt:** "Analyze text, cluster into Sections/Subsections, extract Topics (Instructions) and Skills (Actions)".

- [x] **2.4 Expose via API**
    - [x] Create new router `backend/app/api/ingestion.py`.
    - [x] Endpoint `POST /ingestion/generate_proposal`:
        - Input: `text` OR `file`, `strategy_type` ("academic" | "corporate").
        - Output: `proposal_id` (Calls `ProposalService`).

---

## 📅 PHASE 3: Curriculum Prism ("The View")
*Goal: Allow filtering the Global Graph based on a specific program (Prism).*

- [x] **3.1 Update Data Models**
    - [x] Modify `Curriculum` model (in DB or Pydantic) to include a `filters` JSON field (e.g., `{ "include_sections": [...], "include_subsections": [...] }`).
    - *Note: Implicitly supported via `get_graph_view` logic using existing tables.*

- [x] **3.2 Implement "Prism" Logic in Repo**
    - [x] Update `backend/app/services/curriculum/repo.py`.
    - [x] Create method `get_graph_view(curriculum_code)`. (Method already existed, updated logic).
    - [x] **Logic:**
        1. Fetch all nodes explicitly defined in curriculum.
        2. Roadmap Planner uses these nodes as the "Allow List".

- [x] **3.3 Update Roadmap Planner**
    - [x] Update `backend/app/services/roadmap_planner.py`.
    - [x] Ensure `plan_route` accepts a `curriculum_code`.
    - [x] The algorithm must ONLY consider nodes present in the "Prism" (plus their dependencies).
        - *Implemented: Fetches curriculum nodes -> Expands recursive PREREQs -> Filters `plan_route` results.*

---

## 📅 PHASE 4: Integrity & Validation
*Goal: Ensure the AI doesn't break the Canon.*

- [x] **4.1 Update Integrity Service**
    - [x] Edit `backend/app/services/integrity.py`.
    - [x] Add check: `check_hierarchy_compliance`: Ensure every Topic has a path to a Subject via Section/Subsection.
    - [x] Add check: `check_orphan_skills`: Skills must be connected to at least one Topic.

---

## 📝 Agent Logs & Notes
*(Agent: Use this section to record progress, blockers, or decisions made during iterations)*

- **Iteration 1:** [Pending] Waiting to start Phase 1.
- **Iteration 2:** [Completed] Phase 1 executed. Removed hardcoded Math ontology, added domain_context to LLM prompts, and generalized assessment logic.
- **Iteration 3:** [Completed] Phase 2 executed. Created Universal Ingestion Engine with Academic and Corporate strategies. Exposed via API `/ingestion/generate_proposal`.
- **Iteration 4:** [Completed] Phase 3 executed. Implemented "Curriculum Prism" logic. Roadmap Planner now supports filtering by `curriculum_code`, expanding prerequisites recursively to create a consistent graph view.
- **Iteration 5:** [Completed] Phase 4 executed. Updated Integrity Service to enforce hierarchy compliance and check for orphan skills. Refactored async worker to use comprehensive integrity checks.
