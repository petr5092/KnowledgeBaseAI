The implementation for the "Curriculum Generator" described in the document `Внедрение генератора вариативных учебных программ.md` appears to be already present in the codebase.

**Implementation Status:**
1.  **Backend Service**: `backend/app/services/curriculum/builder.py` is implemented and contains the logic to query Neo4j and call the LLM.
2.  **API Endpoint**: `backend/app/api/admin_curriculum.py` exposes the `POST /v1/admin/curriculum/generate` endpoint.
3.  **Database**: `backend/app/db/pg.py` includes the schema for `curricula` and `curriculum_nodes`.
4.  **Demo Scripts**: `backend/scripts/demo_curriculum.py` implements the exact smoke test scenario described in the plan (Corporate Security ingestion + 2 curriculums).

**Proposed Plan:**
1.  **Run Verification**: Execute the existing demo script `backend/scripts/demo_curriculum.py` to verify that the implementation works correctly in the current environment.
    *   This will check DB connectivity, Neo4j ingestion, and the curriculum generation logic (using mocked LLM if no key is present).
2.  **Report Results**: I will share the output of the demo to confirm the feature is functional.

Do you want me to proceed with running the verification script?