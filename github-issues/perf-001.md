## Problem
Roadmap query uses unbounded graph traversal causing timeouts on large graphs.

**File:** `backend/app/api/engine.py` (lines 187-209)

**Current query:**
```cypher
MATCH (sub:Subject {uid: $su})
MATCH (sub)-[:CONTAINS*]->(t:Topic)  -- No depth limit!
OPTIONAL MATCH path = shortestPath((t)-[:PREREQ*..3]-(f:Topic {uid: $focus}))
RETURN t
LIMIT 50  -- Applied after full scan
```

## Impact
- Query timeouts on large subject trees
- High memory usage
- Slow response times (>10s)
- Poor user experience

## Fix
```cypher
MATCH (sub:Subject {uid: $su})
MATCH (sub)-[:CONTAINS*1..5]->(t:Topic)  -- Add depth limit
WITH t LIMIT 100  -- Limit early
OPTIONAL MATCH path = shortestPath((t)-[:PREREQ*..3]-(f:Topic {uid: $focus}))
RETURN t
LIMIT 50
```

### Additional optimizations:
- [ ] Create index: `CREATE INDEX topic_subject_idx FOR (t:Topic) ON (t.subject_uid)`
- [ ] Add query timeout: Configure `dbms.transaction.timeout`
- [ ] Profile query: Use `PROFILE` to verify improvements

## Testing
```bash
# Profile before fix
PROFILE MATCH (sub:Subject {uid: $su})...

# Check execution time and db hits
# Should be <500ms
```

## Estimated Time
4-5 hours (including testing)

## Files
- `backend/app/api/engine.py:187-209`

## References
- COMPREHENSIVE_TODO.md: PERF-001
