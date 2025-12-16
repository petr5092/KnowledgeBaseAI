# Changelog

Date: 2025-12-16

- Completed Task 0.1.1.1 (Canonicalization Service): `backend/src/core/canonical.py`; unit tests passed (4)
- Completed Task 0.1.2.1 (Tenant Context & DAO Base): tenant middleware and DAO base; unit tests passed (2)
- Completed Task 1.2.1.1 (Proposal Creation & Validation): `POST /v1/proposals`, evidence validation and deterministic checksum; unit tests passed (3)
- Completed Task 1.2.2.1 (Rebase Logic ID-only): rebase check, PG graph_version & changes; unit tests passed (3)
- Completed Task 1.2.3.1 (Integrity Gate Subgraph Check): cycle/dangling detection; unit tests passed (3)
- Completed Task 1.2.4.1 (Commit Worker Atomic Write): commit worker, endpoint `/v1/proposals/{id}/commit`, audit log and graph_version update; verified by live commit
- Completed Subtask (Graph.Committed publish): Redis publisher `publish_graph_committed`; unit test passed (1)
- Completed Task 2.1.1.1 (Ingestion Parse/Chunk/Embed): normalization, chunking and deterministic embedding to Qdrant; unit tests passed (2)
- Completed Task 2.2.1.1 (Vector Sync Job): Graph.Committed consumer and Qdrant payload update; unit tests passed (2)
- Completed Task 2.3.1.1 (Math Core): W_edge with clip and EMA; unit tests passed (2)
- Completed Task 4.1.1.1 (Observability): correlation_id propagation and `/metrics`; integration verified
- Completed Task 4.2.1.1 (Schema Gatekeeper): `schema_version` table and startup gate; startup check enabled
- Completed Task 3.2.1.1 (Diff Interface Backend): `/v1/proposals/{id}/diff`; unit test passed
- Completed Subtasks (Approve/Reject + Evidence in Diff): endpoints and evidence rendering in Diff; unit test passed
- Completed Task (Vector Rescore): entity embedding upsert on Graph.Committed; unit test passed
- Completed Task 1.2.1.2 (HITL Review API): GET/approve/reject endpoints; unit test passed
- Completed Task (Evidence Text in Diff): evidence_chunk text resolution via Qdrant; unit test passed
- Checkpoint: Backend aligns with MDD invariants (Proposals flow, ID-only rebase, tenant isolation, commit worker, Redis events, Qdrant sync). Gaps addressed: lifecycle fields on commit, Integrity Gate rejects dangling Skill, initial Prometheus counters added, test guard against direct Neo4j writes. Remaining: finer-grained metrics and full canonicalization enforcement across proposal hashing inputs.
- Checkpoint Update: Enforced lifecycle fields on commit, Integrity Gate rejects dangling Skill, added counters (integrity_violation_total, proposal_auto_rebase_total), guard test against direct Neo4j writes; all new tests passed
- Strengthened canonicalization: deep string normalization before checksum; ingestion success counter; integrity latency histogram; ASYNC_CHECK fallback when threshold exceeded
- Implemented evidence graph mapping: create `SourceChunk` and `EVIDENCED_BY` relation for node changes with evidence

TODO:

- Add detailed Prometheus metrics (rates/latency distributions) and integrity violation classifications
- Enforce canonicalization across all proposal inputs
- Implement `EVIDENCED_BY` for relations or equivalent evidence representation for edges
- Create ASYNC queue worker to process `ASYNC_CHECK_REQUIRED` proposals
