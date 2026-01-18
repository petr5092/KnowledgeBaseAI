# TASK: Recursive "Big Bang" Generation (Math) via Builder Service

**Status:** 🟡 Partially Complete (Generation Done, Commit Pending)
**Agent:** Trae Solo Coder
**Objective:** Generate the complete "Mathematics" discipline using the internal `generate_subject_openai_async` service (recursive engine). Convert the resulting file-based KB artifacts into a Graph Proposal to ensure ACID compliance and Integrity checks.

---

## 🛑 CONTEXT & CONSTRAINTS
1.  **Source of Truth:** Use `backend/app/services/kb/builder.py`. It already handles recursion (Subject->Section->Subsection->Topic) and OpenAI calls.
2.  **Write Policy:** The builder writes to JSONL. You must **NOT** let it write to Neo4j directly (if it has such side effects). You must read the JSONL output and transform it into a `Proposal`.
3.  **Clean State:** Verify Neo4j is empty before starting.

---

## 📅 PHASE 1: Create the Generation Script
*Goal: Create a Python script that calls the service layer directly.*

- [x] **1.1 Create `backend/scripts/run_math_generation.py`**
    - [x] Import `generate_subject_openai_async` from `app.services.kb.builder`.
    - [x] Import `create_draft_proposal` from `app.services.proposal_service`.
    - [x] Import `Operation`, `OpType` from `app.schemas.proposal`.
    - [x] Import `load_jsonl` from `app.services.kb.jsonl_io`.

- [x] **1.2 Configure Generation Parameters (The Mega-Seed)**
    - [x] In the script, set up the call:
      ```python
      # Configuration for a Deep Graph
      SEEDS = [
          "Arithmetic", 
          "Algebra", 
          "Geometry", 
          "Trigonometry", 
          "Calculus", 
          "Linear Algebra", 
          "Probability & Statistics"
      ]
      
      # Limits (Adjusted for "Big Bang")
      # This forces the AI to dig deep
      await generate_subject_openai_async(
          subject_uid="MATH-FULL-V1",
          subject_title="Mathematics",
          language="ru",
          domain_context="Academic Curriculum",
          sections_seed=SEEDS,
          topics_per_section=6,    # ~42 topics
          skills_per_topic=2,      # ~84 skills
          methods_per_skill=1,
          examples_per_topic=1,
          concurrency=5
      )
      ```

---

## 📅 PHASE 2: JSONL to Proposal Converter
*Goal: The Builder creates files. We need to parse them into Graph Operations.*

- [x] **2.1 Implement Conversion Logic in Script**
    - [x] After generation finishes, the script must locate the generated files (using `get_subject_dir`).
    - [x] Read `sections.jsonl`, `subsections.jsonl`, `topics.jsonl`, `topic_prereqs.jsonl`, etc.
    - [x] **Transform to Operations:**
        - For every JSON record (Section, Topic, Skill), create a `MERGE_NODE` Operation.
        - For every Prereq/Link record, create a `MERGE_REL` Operation.
        - *Important:* Maintain the strict Canon hierarchy (`Subject->Section->Subsection->Topic`).

- [x] **2.2 Create & Save Proposal**
    - [x] Call `create_draft_proposal` with the list of operations (could be 1000+ ops).
    - [x] Save the Proposal ID to a text file or print it.

---

## 📅 PHASE 3: Execution
*Goal: Run the script and create the massive proposal.*

- [x] **3.1 Run the Script**
    - [x] Execute: `python -m backend.scripts.run_math_generation`
    - [x] *Note:* This will take time (OpenAI API calls).
    - [x] **Monitor:** Ensure no timeouts.

- [ ] **3.2 Verify Proposal Creation**
    - [ ] Check DB `proposals` table or use API `GET /v1/proposals`.
    - [ ] Ensure the proposal contains expected node counts.
    - *Note:* Proposal created in memory (ID: `P-fdb356cb56bc4c299ebb`) but DB save failed due to connectivity issues in dev environment.

---

## 📅 PHASE 4: Integrity Check & Commit
*Goal: The moment of truth.*

- [ ] **4.1 API Cycle Check**
    - [ ] Use `POST /v1/maintenance/proposals/run_integrity_async` (or check manually via script if API is unavailable).
    - [ ] Ensure no cycles in `PREREQ`.

- [ ] **4.2 Commit**
    - [ ] **POST** `/v1/proposals/{proposal_id}/commit`.
    - [ ] Watch the logs. This will write hundreds of nodes to Neo4j.

- [ ] **4.3 Verification**
    - [ ] **POST** `/v1/engine/roadmap` for a Calculus topic.
    - [ ] Verify the path is deep and logical.

---

## 📝 Agent Logs
- **Script Created:** Yes
- **Generation Time:** ~2 minutes
- **Proposal Size:** 3369 operations
- **Proposal ID:** P-fdb356cb56bc4c299ebb
- **Commit Status:** Failed (DB/Neo4j Connectivity Issue in Dev Env)
