Вот готовый файл задачи в формате Markdown. Создайте файл с именем `TASK_UNIVERSAL_CORE.md` в корне вашего проекта и откройте его в IDE.

Этот файл структурирован так, чтобы AI-агент (Trae/Gemini) мог:
1.  Считать контекст и жесткие ограничения (CANON).
2.  Выполнять работу пошагово (Step-by-Step).
3.  Отмечать выполненные чекбоксы `[x]` (Агент умеет редактировать файлы).
4.  Писать отчеты о проблемах в секцию "Agent Logs".

---

```markdown
# TASK: Universal Knowledge Core Migration

**Status:** 🟡 In Progress
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

- [ ] **1.1 Analyze & Deprecate `services/kb/builder.py`**
    - [ ] Remove `MATHEMATICS_ONTOLOGY` constant.
    - [ ] Delete/Rename `build_mathematics_ontology`.
    - [ ] Delete `rebuild_subject_math_with_openai`.
    - [ ] Refactor `bootstrap_subject_from_skill_topics` to be generic (accepting `domain_context` string instead of assuming math).

- [ ] **1.2 Abstract Prompts in `api/admin_generate.py`**
    - [ ] Check `generate_subject` function.
    - [ ] Remove hardcoded educational presets (if any).
    - [ ] Ensure the prompt accepts a dynamic `domain` and `context_type` (e.g., "Academic Subject" vs "Corporate Manual").

- [ ] **1.3 Verify `api/assessment.py`**
    - [ ] Ensure question generation doesn't assume specific "Math" types.
    - [ ] Verify `_age_to_class` usage is safe or deprecated in favor of a generic `user_level` attribute.

---

## 📅 PHASE 2: Universal Ingestion Engine
*Goal: Create a unified pipeline that accepts different input sources but produces the same Canonical Graph Structure.*

- [ ] **2.1 Create Base Service Structure**
    - [ ] Create folder `backend/app/services/ingestion/`.
    - [ ] Create `backend/app/services/ingestion/interface.py`: Define `IngestionStrategy` abstract class with a method `process(source_content) -> List[GraphOperation]`.

- [ ] **2.2 Implement Academic Strategy**
    - [ ] Create `backend/app/services/ingestion/academic.py`.
    - [ ] Implement logic to parse structured inputs (like Table of Contents).
    - [ ] **LLM Prompt:** "Map this TOC to Subject->Section->Subsection->Topic".

- [ ] **2.3 Implement Corporate Strategy**
    - [ ] Create `backend/app/services/ingestion/corporate.py`.
    - [ ] Implement logic for unstructured text (Regiments, Manuals).
    - [ ] **LLM Prompt:** "Analyze text, cluster into Sections/Subsections, extract Topics (Instructions) and Skills (Actions)".

- [ ] **2.4 Expose via API**
    - [ ] Create new router `backend/app/api/ingestion.py`.
    - [ ] Endpoint `POST /ingestion/generate_proposal`:
        - Input: `text` OR `file`, `strategy_type` ("academic" | "corporate").
        - Output: `proposal_id` (Calls `ProposalService`).

---

## 📅 PHASE 3: Curriculum Prism ("The View")
*Goal: Allow filtering the Global Graph based on a specific program (Prism).*

- [ ] **3.1 Update Data Models**
    - [ ] Modify `Curriculum` model (in DB or Pydantic) to include a `filters` JSON field (e.g., `{ "include_sections": [...], "include_subsections": [...] }`).

- [ ] **3.2 Implement "Prism" Logic in Repo**
    - [ ] Update `backend/app/services/curriculum/repo.py`.
    - [ ] Create method `get_curriculum_subgraph(curriculum_code)`.
    - [ ] **Logic:**
        1. Fetch all nodes explicitly defined in `filters`.
        2. Fetch all nodes that are recursive `[:PREREQ]` for the filtered nodes (even if they are outside the filter!).
        3. Return this subset as the Graph View.

- [ ] **3.3 Update Roadmap Planner**
    - [ ] Update `backend/app/services/roadmap_planner.py`.
    - [ ] Ensure `plan_route` accepts a `curriculum_context`.
    - [ ] The algorithm must ONLY consider nodes present in the "Prism" (plus their dependencies).

---

## 📅 PHASE 4: Integrity & Validation
*Goal: Ensure the AI doesn't break the Canon.*

- [ ] **4.1 Update Integrity Service**
    - [ ] Edit `backend/app/services/integrity.py`.
    - [ ] Add check: `check_hierarchy_compliance`: Ensure every Topic has a path to a Subject via Section/Subsection.
    - [ ] Add check: `check_orphan_skills`: Skills must be connected to at least one Topic.

---

## 📝 Agent Logs & Notes
*(Agent: Use this section to record progress, blockers, or decisions made during iterations)*

- **Iteration 1:** [Pending] Waiting to start Phase 1.
- **Iteration 2:** [Completed] Phase 1 executed. Removed hardcoded Math ontology, added domain_context to LLM prompts, and generalized assessment logic.
- **Iteration 3:** [Completed] Phase 2 executed. Created Universal Ingestion Engine with Academic and Corporate strategies. Exposed via API `/ingestion/generate_proposal`.
```
