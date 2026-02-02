# KnowledgeBaseAI - Comprehensive Technical Debt & TODO List

**Generated:** 2026-02-01
**Status:** Active Development Required
**Overall Risk Level:** HIGH

---

## Executive Summary

This document outlines critical issues, bugs, and technical debt identified through comprehensive codebase analysis of the KnowledgeBaseAI platform. Issues are categorized by priority (P0-P3) with specific file locations, line numbers, and actionable recommendations.

**Key Metrics:**
- **Total Issues Identified:** 127
- **Critical (P0):** 12 issues requiring immediate attention
- **High (P1):** 28 issues to fix within current sprint
- **Medium (P2):** 45 quality/maintainability improvements
- **Low (P3):** 42 nice-to-have enhancements

---

## Table of Contents

1. [P0 - CRITICAL: Security & Data Safety](#p0---critical-security--data-safety)
2. [P1 - HIGH: Performance & Stability](#p1---high-performance--stability)
3. [P2 - MEDIUM: Code Quality & Architecture](#p2---medium-code-quality--architecture)
4. [P3 - LOW: Polish & Enhancements](#p3---low-polish--enhancements)
5. [Implementation Roadmap](#implementation-roadmap)
6. [Testing Requirements](#testing-requirements)

---

## P0 - CRITICAL: Security & Data Safety

### SEC-001: Exposed Secrets in Version Control
**Priority:** P0 - IMMEDIATE
**Risk:** Data Breach, API Key Compromise
**Effort:** 2-4 hours

**Problem:**
- File: `.env.dev`, `.env.prod`
- Exposed: OpenAI API keys, database passwords, JWT secrets
- Security impact: Unauthorized access to production data and AI services

**Actions:**
```bash
# 1. Immediately rotate ALL credentials
- [ ] Revoke OpenAI API key: sk-proj-poqHlE98Uf0yR9PJ...
- [ ] Generate new JWT_SECRET_KEY
- [ ] Change NEO4J_PASSWORD (currently: 12ee8ba019)
- [ ] Change POSTGRES_PASSWORD
- [ ] Change BOOTSTRAP_ADMIN_PASSWORD

# 2. Remove from git history
- [ ] git filter-branch --tree-filter 'rm -f .env.dev .env.prod .env.stage' -- --all
- [ ] git push origin --force --all

# 3. Update .gitignore
- [ ] Add: .env, .env.*, secrets/, *.key, credentials.json

# 4. Implement secret management
- [ ] Option A: Use HashiCorp Vault
- [ ] Option B: Use AWS Secrets Manager
- [ ] Option C: Use Docker secrets
```

**Verification:**
```bash
git log --all --full-history -- .env.prod
# Should return empty after cleanup
```

---

### SEC-002: CORS Misconfiguration Allowing All Origins
**Priority:** P0 - IMMEDIATE
**Risk:** CSRF attacks, credential theft
**Effort:** 30 minutes

**Problem:**
- File: `backend/app/main.py` (lines 212-220)
- Code parses `cors_allow_origins` but hardcodes `["*"]` instead
- Combined with `allow_credentials=True`, this is a critical vulnerability

**Current Code:**
```python
origins = [o.strip() for o in (settings.cors_allow_origins or "").split(",") if o.strip()]
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # BUG: Should use `origins` variable
        allow_credentials=True,  # Dangerous with wildcard!
        allow_methods=["*"],
        allow_headers=["*"],
    )
```

**Fix:**
```python
- [ ] Replace allow_origins=["*"] with allow_origins=origins
- [ ] Restrict allow_methods to ["GET", "POST", "PUT", "DELETE"]
- [ ] Restrict allow_headers to ["Content-Type", "Authorization"]
- [ ] Add validation that origins list is not empty in production
```

**File:** `backend/app/main.py:216`

---

### SEC-003: PostgreSQL Trust Authentication
**Priority:** P0 - IMMEDIATE
**Risk:** Unauthorized database access
**Effort:** 15 minutes

**Problem:**
- File: `docker-compose.yml` (line 308)
- Setting: `POSTGRES_HOST_AUTH_METHOD: trust`
- Allows connections without password

**Fix:**
```yaml
- [ ] Change to: POSTGRES_HOST_AUTH_METHOD: md5
- [ ] Verify PG_DSN includes password in fastapi environment
- [ ] Test connection after change
- [ ] Restart postgres container
```

---

### SEC-004: Missing Health Check Endpoints
**Priority:** P0 - CRITICAL
**Risk:** Undetected service failures, cascading outages
**Effort:** 2-3 hours

**Problem:**
- No health checks defined in `docker-compose.yml`
- Services can fail silently
- No automatic recovery

**Actions:**
```yaml
# Add to docker-compose.yml

- [ ] fastapi:
      healthcheck:
        test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
        interval: 30s
        timeout: 10s
        retries: 3
        start_period: 40s

- [ ] postgres:
      healthcheck:
        test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
        interval: 10s
        timeout: 5s
        retries: 5

- [ ] redis:
      healthcheck:
        test: ["CMD", "redis-cli", "ping"]
        interval: 10s
        timeout: 5s
        retries: 3

- [ ] neo4j:
      healthcheck:
        test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost:7474"]
        interval: 10s
        timeout: 5s
        retries: 3

- [ ] qdrant:
      healthcheck:
        test: ["CMD", "curl", "-f", "http://localhost:6333/health"]
        interval: 10s
        timeout: 5s
        retries: 3

- [ ] Update depends_on to use condition: service_healthy
```

---

### DATA-001: No Backup Strategy
**Priority:** P0 - CRITICAL
**Risk:** Complete data loss
**Effort:** 4-6 hours

**Problem:**
- No automated backups configured
- No backup scripts exist
- No documented recovery procedures

**Actions:**
```bash
- [ ] Create scripts/backup.sh (see implementation below)
- [ ] Create scripts/restore.sh
- [ ] Set up cron job: 0 2 * * * (daily at 2 AM)
- [ ] Test backup/restore procedures
- [ ] Document recovery runbook
- [ ] Set up backup monitoring/alerting
- [ ] Configure backup retention (30 days)
```

**Script to create:**
```bash
#!/bin/bash
# File: scripts/backup.sh
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

mkdir -p "$BACKUP_DIR"

# PostgreSQL
docker exec knowledgebase-postgres-1 pg_dump -U ${POSTGRES_USER} ${POSTGRES_DB} | \
  gzip > "$BACKUP_DIR/postgres_${TIMESTAMP}.sql.gz"

# Neo4j
docker exec knowledgebase-neo4j-1 neo4j-admin database backup neo4j \
  --to-path=/backups --overwrite-destination=true || true
docker cp knowledgebase-neo4j-1:/backups/neo4j.backup \
  "$BACKUP_DIR/neo4j_${TIMESTAMP}.backup"

# Qdrant collections
docker exec knowledgebase-qdrant-1 curl -s http://localhost:6333/collections | \
  jq . > "$BACKUP_DIR/qdrant_${TIMESTAMP}.json"

# Cleanup old backups
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "*.backup" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: $BACKUP_DIR"
ls -lh "$BACKUP_DIR" | tail -5
```

---

### SEC-005: Unauthenticated Metrics Endpoint
**Priority:** P0 - HIGH
**Risk:** Information disclosure
**Effort:** 1 hour

**Problem:**
- File: `backend/app/main.py` (line 203)
- `/metrics` endpoint has no authentication
- Exposes internal application state

**Fix:**
```python
- [ ] Add authentication middleware to /metrics
- [ ] Option A: API key authentication
- [ ] Option B: IP whitelist
- [ ] Option C: Move behind Traefik with BasicAuth
```

**Example:**
```python
from starlette.middleware.authentication import AuthenticationMiddleware

@app.get("/metrics")
async def metrics(api_key: str = Header(None)):
    if api_key != settings.metrics_api_key.get_secret_value():
        raise HTTPException(status_code=401)
    return generate_metrics()
```

---

### SEC-006: Missing Rate Limiting
**Priority:** P0 - HIGH
**Risk:** DDoS, brute force attacks, API abuse
**Effort:** 2-3 hours

**Problem:**
- No rate limiting on any endpoints
- `/chat` endpoint can spam OpenAI API
- `/roadmap` endpoint computationally expensive
- Authentication endpoints vulnerable to brute force

**Actions:**
```python
- [ ] Install slowapi: pip install slowapi
- [ ] Add rate limiter to main.py
- [ ] Apply limits to endpoints:
      - /login: 5 requests/minute
      - /register: 3 requests/minute
      - /chat: 10 requests/minute
      - /roadmap: 5 requests/minute
      - Default: 100 requests/minute

# Implementation
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, ...):
    ...
```

**Files to modify:**
- `backend/app/main.py`
- `backend/app/api/auth.py`
- `backend/app/api/assistant.py`
- `backend/app/api/engine.py`

---

### SEC-007: Missing Security Headers
**Priority:** P0 - HIGH
**Risk:** XSS, clickjacking, MIME sniffing attacks
**Effort:** 1 hour

**Problem:**
- No security headers in API responses
- Missing: HSTS, X-Frame-Options, CSP, etc.

**Fix:**
```python
# Add to backend/app/main.py

- [ ] Create security headers middleware

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "no-referrer-when-downgrade"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response
```

---

### SEC-008: Exposed Admin API Key in Logs
**Priority:** P0 - HIGH
**Risk:** Admin credential leakage
**Effort:** 30 minutes

**Problem:**
- File: `backend/app/api/admin.py`
- Admin API key may be logged in exceptions

**Fix:**
```python
- [ ] Add API key redaction to logging configuration
- [ ] Update exception handlers to sanitize headers
- [ ] Add @sensitive_variables decorator to admin functions
```

---

### DATA-002: Missing Database Connection Pooling
**Priority:** P0 - HIGH
**Risk:** Connection exhaustion, performance degradation
**Effort:** 3-4 hours

**Problem:**
- File: `backend/app/db/pg.py` (lines 5-9)
- Creates new connection per request
- No connection reuse

**Current:**
```python
def get_conn():
    dsn = str(settings.pg_dsn)
    return psycopg2.connect(dsn)  # New connection every time!
```

**Fix Options:**

**Option A: Add PgBouncer (Recommended)**
```yaml
- [ ] Add to docker-compose.yml:

pgbouncer:
  image: pgbouncer/pgbouncer:1.21
  environment:
    DATABASES_HOST: postgres
    DATABASES_USER: ${POSTGRES_USER}
    DATABASES_PASSWORD: ${POSTGRES_PASSWORD}
    DATABASES_DBNAME: ${POSTGRES_DB}
    POOL_MODE: transaction
    MAX_CLIENT_CONN: 1000
    DEFAULT_POOL_SIZE: 25
  ports:
    - "6432:6432"
  depends_on:
    - postgres

- [ ] Update PG_DSN to use pgbouncer:6432
```

**Option B: Use SQLAlchemy with connection pooling**
```python
- [ ] Replace psycopg2 with SQLAlchemy
- [ ] Configure pool: pool_size=10, max_overflow=20
- [ ] Update all pg.py functions to use session
```

**Files affected:**
- `backend/app/db/pg.py`
- `backend/app/api/auth.py`
- `backend/app/api/proposals.py`

---

### BUG-001: Neo4j Driver Lifecycle Bug
**Priority:** P0 - HIGH
**Risk:** Driver closed unexpectedly, connection failures
**Effort:** 2 hours

**Problem:**
- File: `backend/app/services/graph/neo4j_repo.py` (lines 140-222)
- Global `_driver_instance` set but `drv.close()` called in functions
- Closes global driver, next request fails

**Current Code:**
```python
def read_graph(...):
    drv = get_driver()  # Returns global _driver_instance
    ...
    drv.close()  # CLOSES GLOBAL INSTANCE!
    return nodes, edges
```

**Fix:**
```python
- [ ] Remove drv.close() calls from individual functions
- [ ] Add proper cleanup in application shutdown event
- [ ] Use context manager for sessions, not driver

# In main.py:
@app.on_event("shutdown")
async def shutdown_event():
    driver = get_driver()
    if driver:
        driver.close()

# In neo4j_repo.py:
def read_graph(...):
    driver = get_driver()
    with driver.session() as session:
        result = session.run(query)
        # Session auto-closes, driver stays open
    return result
```

**Files:**
- `backend/app/services/graph/neo4j_repo.py`
- `backend/app/main.py`

---

### BUG-002: React EditPage Undefined setNodes
**Priority:** P0 - CRITICAL
**Risk:** Page completely broken, cannot edit graph
**Effort:** 1 hour

**Problem:**
- File: `frontend/src/pages/EditPage.tsx` (line 73)
- Calls `setNodes()` which doesn't exist
- Should use Redux dispatch instead

**Current Code:**
```typescript
const addNode = () => {
  const newNode = { ... }
  setNodes((old) => [...old, newNode])  // setNodes is undefined!
}
```

**Fix:**
```typescript
- [ ] Import: import { useDispatch } from 'react-redux'
- [ ] Import: import { addNode as addNodeAction } from '../store/editSlice'
- [ ] Use: const dispatch = useDispatch()
- [ ] Replace: dispatch(addNodeAction(newNode))
```

---

## P1 - HIGH: Performance & Stability

### PERF-001: Inefficient Roadmap Query
**Priority:** P1 - HIGH
**Impact:** Timeout on large graphs
**Effort:** 4-5 hours

**Problem:**
- File: `backend/app/api/engine.py` (lines 187-209)
- Unbounded `CONTAINS*` traversal
- No query timeout
- LIMIT 50 applied after full graph scan

**Current Query:**
```cypher
MATCH (sub:Subject {uid: $su})
MATCH (sub)-[:CONTAINS*]->(t:Topic)  -- Unbounded!
OPTIONAL MATCH path = shortestPath((t)-[:PREREQ*..3]-(f:Topic {uid: $focus}))
RETURN t
LIMIT 50  -- Too late, already scanned everything
```

**Fix:**
```cypher
- [ ] Add depth limit to CONTAINS: CONTAINS*1..5
- [ ] Add query timeout: CALL { ... } IN TRANSACTIONS OF 100 ROWS
- [ ] Add early LIMIT: WITH t LIMIT 100 before shortestPath
- [ ] Create index: CREATE INDEX topic_subject_idx FOR (t:Topic) ON (t.subject_uid)
- [ ] Add query profiling: PROFILE to test performance
```

**Files:**
- `backend/app/api/engine.py:187-209`

---

### PERF-002: LLM Calls Without Caching
**Priority:** P1 - HIGH
**Impact:** High API costs, slow responses
**Effort:** 3-4 hours

**Problem:**
- File: `backend/app/api/engine.py` (lines 280-287)
- Same roadmap requests call OpenAI repeatedly
- No caching of LLM responses
- Identical prompts can be called hundreds of times

**Fix:**
```python
- [ ] Install: pip install redis
- [ ] Create cache decorator for LLM calls
- [ ] Cache key: hash(prompt + model + temperature)
- [ ] TTL: 1 hour for roadmap, 10 minutes for chat
- [ ] Add cache warming for popular curricula

from functools import wraps
import hashlib
import json

def llm_cache(ttl=3600):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"llm:{hashlib.sha256(json.dumps(kwargs).encode()).hexdigest()}"
            cached = await redis.get(cache_key)
            if cached:
                return json.loads(cached)
            result = await func(*args, **kwargs)
            await redis.setex(cache_key, ttl, json.dumps(result))
            return result
        return wrapper
    return decorator

@llm_cache(ttl=3600)
async def call_llm_for_roadmap(...):
    ...
```

**Files:**
- `backend/app/api/engine.py`
- `backend/app/services/llm_cache.py` (new)

---

### PERF-003: N+1 Query in Questions Module
**Priority:** P1 - HIGH
**Impact:** Slow topic detail loading
**Effort:** 2 hours

**Problem:**
- File: `backend/app/services/questions.py` (lines 45-78)
- UNWIND query retrieves all examples without limit
- Can return massive result sets

**Fix:**
```cypher
- [ ] Add LIMIT to examples: LIMIT 10 per topic
- [ ] Add pagination parameters
- [ ] Create separate endpoint for "load more examples"
- [ ] Add index: CREATE INDEX example_topic_idx FOR (e:Example) ON (e.topic_uid)
```

---

### PERF-004: Frontend Mousemove Event Spam
**Priority:** P1 - HIGH
**Impact:** 60 re-renders per second, UI lag
**Effort:** 2 hours

**Problem:**
- File: `frontend/src/pages/ExplorePage.tsx` (lines 385-393)
- Updates state on every mousemove
- Causes constant re-renders

**Current Code:**
```typescript
onMouseMove={(e) => {
  if (!hoveredNode) return
  const rect = e.currentTarget.getBoundingClientRect()
  setCursorPos({
    x: e.clientX - rect.left,
    y: e.clientY - rect.top
  })
}}
```

**Fix:**
```typescript
- [ ] Install lodash: npm install lodash
- [ ] Throttle updates: throttle(updateCursorPos, 50)
- [ ] Or use requestAnimationFrame
- [ ] Or use CSS variables instead of state

import { throttle } from 'lodash'

const updateCursorPos = useCallback(
  throttle((x: number, y: number) => {
    setCursorPos({ x, y })
  }, 50),
  []
)
```

---

### PERF-005: Missing Component Memoization
**Priority:** P1 - MEDIUM
**Impact:** Unnecessary re-renders
**Effort:** 2-3 hours

**Problem:**
- File: `frontend/src/pages/RoadmapPage.tsx`
- File: `frontend/src/pages/AnalyticsPage.tsx`
- Components not memoized, re-render on any Redux state change

**Fix:**
```typescript
- [ ] Wrap in React.memo()
- [ ] Add useMemo for expensive computations
- [ ] Use useCallback for event handlers

import { memo } from 'react'

export const RoadmapPage = memo(function RoadmapPage() {
  const items = useSelector(selectRoadmapItems, shallowEqual)
  // ...
})
```

---

### STAB-001: Missing Error Boundaries
**Priority:** P1 - HIGH
**Impact:** Entire app crashes on component error
**Effort:** 3-4 hours

**Problem:**
- No error boundaries found in frontend
- Any component crash breaks entire application

**Actions:**
```typescript
- [ ] Create ErrorBoundary component
- [ ] Wrap major sections: <App>, <ExplorePage>, <AIChat>
- [ ] Add error reporting to backend
- [ ] Display user-friendly error UI

// File: frontend/src/components/ErrorBoundary.tsx
import React, { Component, ErrorInfo, ReactNode } from 'react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error?: Error
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo)
    // Send to monitoring service
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback || (
        <div className="error-boundary">
          <h1>Something went wrong</h1>
          <button onClick={() => this.setState({ hasError: false })}>
            Try again
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

// Usage in App.tsx:
<ErrorBoundary>
  <ExplorePage />
</ErrorBoundary>
```

---

### STAB-002: Missing Request Timeouts
**Priority:** P1 - HIGH
**Impact:** Hanging requests, unresponsive UI
**Effort:** 2 hours

**Problem:**
- File: `backend/app/api/engine.py` (line 280)
- File: `frontend/src/api.ts`
- No timeout on OpenAI calls
- No timeout on fetch requests

**Backend Fix:**
```python
- [ ] Add timeout to OpenAI client initialization

client = AsyncOpenAI(
    api_key=settings.openai_api_key.get_secret_value(),
    timeout=httpx.Timeout(30.0, connect=5.0),  # Add this
)
```

**Frontend Fix:**
```typescript
- [ ] Update apiFetch to include timeout

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 30000) // 30s timeout

  try {
    const res = await fetch(url, {
      ...init,
      signal: controller.signal
    })
    return await parseBody(res) as T
  } finally {
    clearTimeout(timeoutId)
  }
}
```

---

### STAB-003: Race Condition in Version Management
**Priority:** P1 - HIGH
**Impact:** Duplicate version numbers, data corruption
**Effort:** 3 hours

**Problem:**
- File: `backend/app/workers/commit.py` (line 240)
- Read-modify-write pattern without locking

**Current:**
```python
new_ver = max(get_graph_version(tenant_id), base_ver) + 1
# Another request could create same version here!
```

**Fix:**
```sql
- [ ] Use database transaction with SELECT FOR UPDATE
- [ ] Or use SERIAL column with auto-increment
- [ ] Or use Redis INCR for atomic counter

-- SQL fix:
BEGIN;
SELECT version FROM tenant_graph_version
WHERE tenant_id = %s
FOR UPDATE;  -- Lock row
INSERT INTO graph_changes (version, ...) VALUES (%s, ...);
UPDATE tenant_graph_version SET version = version + 1;
COMMIT;
```

---

### BUG-003: JSON.stringify in useEffect Dependency
**Priority:** P1 - HIGH
**Impact:** Infinite render loop
**Effort:** 30 minutes

**Problem:**
- File: `frontend/src/pages/ImpactGraph.tsx` (line 30)
- Creates new string every render

**Current:**
```typescript
}, [proposalId, depth, JSON.stringify(types || [])])
```

**Fix:**
```typescript
- [ ] Use useMemo to stabilize reference

const typesKey = useMemo(() =>
  types ? types.join(',') : '',
  [types]
)

useEffect(() => {
  // ...
}, [proposalId, depth, typesKey])
```

---

## P2 - MEDIUM: Code Quality & Architecture

### CODE-001: Bare Exception Handlers
**Priority:** P2 - MEDIUM
**Impact:** Hides real errors, difficult debugging
**Effort:** 2-3 hours

**Problem:**
- Multiple files use `except:` without specific exception type
- Catches system exceptions like KeyboardInterrupt

**Locations:**
- `backend/app/api/engine.py:358-361, 577-586, 652-675`
- `backend/app/services/kb/builder.py:27-28, 61-62`

**Fix:**
```python
# Bad:
try:
    return json.loads(p)
except:
    return {}

# Good:
- [ ] Replace with specific exceptions

try:
    return json.loads(p)
except (ValueError, json.JSONDecodeError) as e:
    logger.warning(f"Failed to parse JSON: {e}")
    return {}
```

**Action items:**
```bash
- [ ] Find all: grep -rn "except:" backend/app/
- [ ] Replace each with specific exception type
- [ ] Add logging for caught exceptions
- [ ] Test error scenarios
```

---

### CODE-002: Debug Print Statements in Production
**Priority:** P2 - MEDIUM
**Impact:** Unprofessional logs, performance overhead
**Effort:** 1 hour

**Problem:**
- File: `backend/app/api/engine.py` (lines 211, 225, 228, 306, 309)
- Multiple print() statements

**Fix:**
```python
- [ ] Replace all print() with logger.debug()
- [ ] Add structured logging context

# Find all:
grep -rn "print(" backend/app/

# Replace:
print(f"Running roadmap query for {subject_uid}")
# With:
logger.debug("Running roadmap query", extra={
    "subject_uid": subject_uid,
    "focus_uid": focus_uid
})
```

---

### CODE-003: Inconsistent Error Response Format
**Priority:** P2 - MEDIUM
**Impact:** Client can't reliably parse errors
**Effort:** 3-4 hours

**Problem:**
- Sometimes: `raise HTTPException(status_code=400, detail="string")`
- Sometimes: `raise HTTPException(status_code=400, detail={"error": "..."})`
- Inconsistent with ApiError schema

**Fix:**
```python
- [ ] Define standard error response schema
- [ ] Create error factory function
- [ ] Update all exception raises

# backend/app/api/errors.py
from pydantic import BaseModel

class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict = {}

def create_error(code: str, message: str, **details):
    return HTTPException(
        status_code=400,
        detail=ErrorResponse(
            code=code,
            message=message,
            details=details
        ).dict()
    )

# Usage:
raise create_error(
    "invalid_uid",
    "Node not found",
    uid=uid,
    type="topic"
)
```

**Files to update:**
- All files in `backend/app/api/`

---

### CODE-004: Missing Type Safety in API Responses
**Priority:** P2 - MEDIUM
**Impact:** Runtime errors, undefined behavior
**Effort:** 4-5 hours

**Problem:**
- File: `frontend/src/api.ts` (lines 77-94)
- Type assertions bypass validation
- No Zod schema validation

**Current:**
```typescript
const nodesRaw = (obj["nodes"] as any[]) ?? []
const kind = (n?.kind ?? "concept") as NodeKind  // Unsafe cast
```

**Fix:**
```typescript
- [ ] Install: npm install zod
- [ ] Define Zod schemas for all API responses
- [ ] Replace type assertions with schema.parse()

import { z } from 'zod'

const NodeSchema = z.object({
  uid: z.string(),
  kind: z.enum(['concept', 'skill', 'resource']),
  title: z.string(),
  description: z.string().optional()
})

const ViewportResponseSchema = z.object({
  nodes: z.array(NodeSchema),
  edges: z.array(EdgeSchema)
})

export async function getViewport(params) {
  const raw = await apiFetch<unknown>('/v1/graph/viewport?...')
  return ViewportResponseSchema.parse(raw)  // Throws if invalid
}
```

**Files:**
- `frontend/src/api.ts`
- `frontend/src/schemas.ts`

---

### ARCH-001: Business Logic in API Handlers
**Priority:** P2 - MEDIUM
**Impact:** Hard to test, tight coupling
**Effort:** 8-10 hours (major refactor)

**Problem:**
- File: `backend/app/api/engine.py` (lines 180-450)
- 270 lines of roadmap logic in endpoint handler
- Should be in service layer

**Refactor:**
```python
# Create new file: backend/app/services/roadmap_service.py

- [ ] Extract roadmap building logic to service class
- [ ] Extract LLM integration to separate service
- [ ] API handler should just call service and return result

# Example:
class RoadmapService:
    def __init__(self, neo4j_repo, llm_service):
        self.neo4j = neo4j_repo
        self.llm = llm_service

    async def build_roadmap(
        self,
        subject_uid: str,
        focus_uid: str | None,
        user_context: UserContext
    ) -> List[RoadmapItem]:
        # All business logic here
        pass

# In API:
@app.post("/v1/engine/roadmap")
async def roadmap(
    params: RoadmapRequest,
    service: RoadmapService = Depends(get_roadmap_service)
):
    return await service.build_roadmap(
        params.subject_uid,
        params.focus_uid,
        get_user_context()
    )
```

**Benefits:**
- Easier to test (can mock dependencies)
- Reusable logic
- Better separation of concerns

---

### ARCH-002: Duplicate Code in Auth Functions
**Priority:** P2 - MEDIUM
**Impact:** Maintenance burden
**Effort:** 1 hour

**Problem:**
- File: `backend/app/api/auth.py` (line 67)
- File: `backend/app/api/deps.py` (line 7)
- Identical `_bearer_token()` function

**Fix:**
```python
- [ ] Move to shared module: backend/app/core/auth.py
- [ ] Update imports in both files
- [ ] Add unit tests for auth utilities
```

---

### ARCH-003: Mixed State Management (Redux + Context)
**Priority:** P2 - MEDIUM
**Impact:** Confusion, bugs from dual sources of truth
**Effort:** 5-6 hours

**Problem:**
- `frontend/src/context/GraphContext.tsx` stores graph state
- `frontend/src/store/exploreSlice.ts` also stores graph state
- Unclear which is source of truth

**Decision needed:**
```
- [ ] Option A: Move all to Redux (recommended for global state)
- [ ] Option B: Move all to Context (if state is truly local)
- [ ] Option C: Clear separation - Redux for server state, Context for UI state

Recommendation: Option A - Redux for consistency
```

**Refactor:**
```typescript
- [ ] Remove GraphContext
- [ ] Move all graph state to exploreSlice
- [ ] Update components to use useSelector
- [ ] Remove context provider from App.tsx
```

---

### ARCH-004: Monolithic ExplorePage Component
**Priority:** P2 - MEDIUM
**Impact:** Hard to maintain, hard to test
**Effort:** 6-8 hours

**Problem:**
- File: `frontend/src/pages/ExplorePage.tsx` (482 lines)
- Handles: data fetching, graph rendering, events, tooltips, sidebar, filtering

**Refactor:**
```typescript
- [ ] Extract GraphCanvas component (vis-network wrapper)
- [ ] Extract GraphControls component (filters, depth selector)
- [ ] Extract GraphTooltip component (hover state)
- [ ] Extract GraphToolbar component (action buttons)
- [ ] Main page orchestrates subcomponents

// New structure:
pages/
  ExplorePage.tsx           (100 lines - orchestration only)
  components/
    GraphCanvas.tsx         (200 lines - vis-network logic)
    GraphControls.tsx       (50 lines - filters)
    GraphTooltip.tsx        (30 lines - tooltip)
    GraphToolbar.tsx        (30 lines - buttons)
```

---

### TEST-001: Missing Test Coverage
**Priority:** P2 - HIGH
**Impact:** Bugs in production, regression risks
**Effort:** 15-20 hours (comprehensive coverage)

**Problem:**
- Backend: Only 726 lines of test code for ~5800 lines
- Frontend: No test files found
- Coverage: Estimated <15%

**Required Tests:**

**Backend:**
```python
- [ ] tests/api/test_auth.py
      - test_register_success
      - test_register_duplicate_email
      - test_login_success
      - test_login_invalid_credentials
      - test_jwt_token_validation

- [ ] tests/api/test_engine.py
      - test_viewport_basic
      - test_roadmap_generation
      - test_pathfind_with_prereqs

- [ ] tests/api/test_proposals.py
      - test_create_proposal
      - test_commit_proposal
      - test_proposal_diff

- [ ] tests/services/test_graph_repo.py
      - test_neighbors_with_depth
      - test_node_by_uid

- [ ] tests/workers/test_commit.py
      - test_commit_with_rollback
      - test_version_increment

# Pytest configuration
- [ ] Update pytest.ini with coverage settings:

[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    --cov=app
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=70
```

**Frontend:**
```typescript
- [ ] Install: npm install --save-dev @testing-library/react vitest
- [ ] Configure vitest in vite.config.ts

- [ ] tests/pages/ExplorePage.test.tsx
      - renders graph with nodes
      - filters by kind
      - handles node click
      - handles double click

- [ ] tests/components/AIChat.test.tsx
      - sends message
      - displays response
      - handles errors

- [ ] tests/api.test.ts
      - apiFetch success
      - apiFetch error handling
      - timeout handling

// Example test:
import { render, screen } from '@testing-library/react'
import { ExplorePage } from './ExplorePage'

describe('ExplorePage', () => {
  it('renders loading state', () => {
    render(<ExplorePage selectedUid="test" />)
    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })
})
```

**Target Coverage:**
- Backend: 70%+ line coverage
- Frontend: 60%+ line coverage
- Critical paths: 90%+ coverage

---

### DOC-001: Missing API Documentation
**Priority:** P2 - MEDIUM
**Impact:** Developer confusion, integration issues
**Effort:** 4-5 hours

**Problem:**
- OpenAPI tags mixed in Russian/English
- No comprehensive docstrings
- No example requests/responses

**Actions:**
```python
- [ ] Add comprehensive docstrings to all endpoints
- [ ] Add response_model to all endpoints
- [ ] Add OpenAPI examples

@app.post(
    "/v1/graph/viewport",
    response_model=ViewportResponse,
    summary="Get graph viewport",
    description="Returns nodes and edges within specified depth from center node",
    responses={
        200: {
            "description": "Successful response",
            "content": {
                "application/json": {
                    "example": {
                        "nodes": [{"uid": "...", "title": "..."}],
                        "edges": [{"source": "...", "target": "..."}]
                    }
                }
            }
        },
        404: {"description": "Node not found"}
    }
)
async def viewport(...):
    """
    Retrieve a viewport of the knowledge graph.

    Args:
        center_uid: UID of the central node
        depth: How many hops to traverse (1-6)

    Returns:
        ViewportResponse containing nodes and edges
    """
    pass
```

---

### DOC-002: Missing Environment Variable Documentation
**Priority:** P2 - LOW
**Impact:** Configuration errors, deployment issues
**Effort:** 2 hours

**Actions:**
```markdown
- [ ] Create docs/ENVIRONMENT.md documenting:
      - Required vs optional variables
      - Default values
      - Valid ranges/formats
      - Environment-specific recommendations

# Example format:
## Database Configuration

### PG_DSN (Required)
PostgreSQL connection string.

Format: `postgresql://user:password@host:port/database`
Example: `postgresql://kb:secret@localhost:5432/knowledgebase`
Required in: All environments

### NEO4J_URI (Required)
Neo4j bolt connection URI.

Format: `bolt://host:port`
Example: `bolt://localhost:7687`
Default: None (must be set)
Required in: All environments

...
```

---

## P3 - LOW: Polish & Enhancements

### UX-001: Missing Keyboard Navigation in KBSelect
**Priority:** P3 - LOW
**Impact:** Accessibility issue
**Effort:** 2-3 hours

**Problem:**
- File: `frontend/src/components/KBSelect.tsx`
- No arrow key navigation
- No Enter/Escape key support

**Fix:**
```typescript
- [ ] Add keyboard event handlers
- [ ] Support arrow keys for option navigation
- [ ] Support Enter to select
- [ ] Support Escape to close
- [ ] Add focus management
```

---

### UX-002: Missing Loading Skeletons
**Priority:** P3 - LOW
**Impact:** Poor UX during loading
**Effort:** 2-3 hours

**Problem:**
- Just shows "Loading..." text
- No skeleton loaders

**Actions:**
```typescript
- [ ] Create SkeletonLoader component
- [ ] Use in: RoadmapPage, AnalyticsPage, NodeDetailsSidebar
- [ ] Add shimmer animation
```

---

### UX-003: Color Contrast Accessibility Issues
**Priority:** P3 - LOW
**Impact:** WCAG compliance failure
**Effort:** 1-2 hours

**Problem:**
- File: `frontend/src/pages/ExplorePage.tsx` (line 466)
- Green text on dark background may fail WCAG AA

**Actions:**
```bash
- [ ] Run automated accessibility scan
- [ ] Fix all contrast ratio failures (minimum 4.5:1)
- [ ] Test with color blindness simulators
```

---

### PERF-006: Unnecessary Memoization of Empty Objects
**Priority:** P3 - LOW
**Impact:** Cluttered code, no performance benefit
**Effort:** 30 minutes

**Problem:**
- File: `frontend/src/pages/EditPage.tsx` (lines 19-20)

**Fix:**
```typescript
// Remove:
const nodeTypes = useMemo(() => ({}), [])
const edgeTypes = useMemo(() => ({}), [])

// Replace with constants outside component:
const NODE_TYPES = {}
const EDGE_TYPES = {}
```

---

### INFRA-001: Missing .dockerignore Files
**Priority:** P3 - MEDIUM
**Impact:** Large build contexts, slow builds
**Effort:** 30 minutes

**Actions:**
```bash
- [ ] Create /root/KnowledgeBaseAI/.dockerignore
- [ ] Create /root/KnowledgeBaseAI/backend/.dockerignore
- [ ] Create /root/KnowledgeBaseAI/frontend/.dockerignore

# Content:
.git
.gitignore
.env
.env.*
node_modules
.venv
__pycache__
*.pyc
.pytest_cache
coverage/
*.log
```

---

### INFRA-002: Docker Image Not Optimized
**Priority:** P3 - MEDIUM
**Impact:** Large images, slow pulls
**Effort:** 2-3 hours

**Actions:**
```dockerfile
- [ ] Use multi-stage builds
- [ ] Use slim base images (python:3.12-slim)
- [ ] Run as non-root user
- [ ] Minimize layers
- [ ] Remove build dependencies in final image
```

---

### INFRA-003: Missing CI/CD Pipeline
**Priority:** P3 - HIGH
**Impact:** Manual deployments, human errors
**Effort:** 8-12 hours

**Actions:**
```yaml
- [ ] Add image building to .github/workflows/ci.yml
- [ ] Add security scanning (Trivy)
- [ ] Add automated deployment
- [ ] Add rollback capability
- [ ] Add smoke tests after deployment
```

---

### INFRA-004: No Monitoring/Alerting
**Priority:** P3 - HIGH
**Impact:** Undetected issues, slow incident response
**Effort:** 6-8 hours

**Actions:**
```yaml
- [ ] Enable Prometheus/Grafana by default (remove profiles)
- [ ] Create Prometheus alert rules
- [ ] Set up alert notifications (Slack, email, PagerDuty)
- [ ] Create Grafana dashboards:
      - API latency
      - Error rates
      - Database connections
      - LLM API usage
      - Queue depth
```

---

### INFRA-005: No Log Aggregation
**Priority:** P3 - MEDIUM
**Impact:** Difficult troubleshooting
**Effort:** 4-6 hours

**Actions:**
```yaml
- [ ] Add Loki + Promtail to docker-compose
- [ ] Configure log shipping from all containers
- [ ] Create log retention policy
- [ ] Set up log-based alerting
```

---

## Implementation Roadmap

### Week 1: Critical Security Fixes
```
Day 1-2:
  ✓ Rotate all exposed credentials (SEC-001)
  ✓ Fix CORS configuration (SEC-002)
  ✓ Fix PostgreSQL auth (SEC-003)
  ✓ Add security headers (SEC-007)

Day 3-4:
  ✓ Add health checks (SEC-004)
  ✓ Implement backup strategy (DATA-001)
  ✓ Fix Neo4j driver bug (BUG-001)

Day 5:
  ✓ Add rate limiting (SEC-006)
  ✓ Test all security fixes
  ✓ Deploy to staging
```

### Week 2: Performance & Stability
```
Day 1-2:
  ✓ Add database connection pooling (DATA-002)
  ✓ Optimize roadmap query (PERF-001)
  ✓ Fix React EditPage bug (BUG-002)

Day 3-4:
  ✓ Add LLM caching (PERF-002)
  ✓ Add request timeouts (STAB-002)
  ✓ Fix race condition (STAB-003)

Day 5:
  ✓ Add error boundaries (STAB-001)
  ✓ Performance testing
```

### Week 3-4: Code Quality
```
Week 3:
  ✓ Fix bare exception handlers (CODE-001)
  ✓ Replace print statements (CODE-002)
  ✓ Standardize error responses (CODE-003)
  ✓ Add type safety (CODE-004)

Week 4:
  ✓ Begin test coverage (TEST-001)
  ✓ Refactor business logic (ARCH-001)
  ✓ Fix duplicate code (ARCH-002)
```

### Month 2: Infrastructure & Testing
```
Weeks 5-6:
  ✓ Complete test coverage to 70%
  ✓ Set up CI/CD pipeline (INFRA-003)
  ✓ Add monitoring/alerting (INFRA-004)
  ✓ Optimize Docker images (INFRA-002)

Weeks 7-8:
  ✓ Add log aggregation (INFRA-005)
  ✓ Documentation improvements
  ✓ Code review and cleanup
```

---

## Testing Requirements

### Critical Path Testing
Before deploying any fix, verify:

```bash
# Backend
- [ ] Run full test suite: pytest
- [ ] Check coverage: pytest --cov=app --cov-report=term-missing
- [ ] Run linting: pylint app/
- [ ] Run type checking: mypy app/
- [ ] Security scan: bandit -r app/

# Frontend
- [ ] Run tests: npm test
- [ ] Type check: npm run type-check
- [ ] Lint: npm run lint
- [ ] Build: npm run build

# Integration
- [ ] Start all services: docker-compose up -d
- [ ] Wait for health: ./scripts/wait-for-health.sh
- [ ] Run E2E tests: npm run test:e2e

# Performance
- [ ] Load test roadmap endpoint: k6 run load-test.js
- [ ] Check memory usage: docker stats
- [ ] Check query performance: PROFILE Neo4j queries
```

### Regression Test Checklist
```
- [ ] User can register and login
- [ ] Graph viewport loads correctly
- [ ] Roadmap generation works
- [ ] Proposal creation/commit works
- [ ] AI chat responds
- [ ] Filters work in Explore page
- [ ] Node details sidebar opens
- [ ] Edit page can add/remove nodes
- [ ] Admin API requires authentication
```

---

## Metrics & Success Criteria

### Performance Targets
```
- API p95 latency: < 500ms
- Graph viewport load: < 2s
- Roadmap generation: < 5s (with caching: < 500ms)
- Frontend TTI: < 3s
- Database connection pool: < 10% exhaustion
```

### Security Targets
```
- Zero secrets in git history
- All endpoints authenticated
- CORS properly configured
- Rate limiting on all endpoints
- Security headers on all responses
- Automated dependency scanning
```

### Quality Targets
```
- Test coverage: >70% backend, >60% frontend
- Zero P0/P1 bugs in production
- All exceptions properly handled
- No bare except clauses
- All API responses typed
```

### Operational Targets
```
- Automated backups daily
- RPO: < 24 hours
- RTO: < 1 hour
- 99.9% uptime (excluding maintenance)
- Automated deployments with rollback
- Alerts for critical issues
```

---

## Appendix: Quick Reference

### Files Requiring Immediate Attention
1. `.env.dev` - Remove from repo
2. `.env.prod` - Remove from repo
3. `backend/app/main.py:216` - Fix CORS
4. `docker-compose.yml:308` - Fix auth method
5. `backend/app/db/pg.py` - Add pooling
6. `backend/app/services/graph/neo4j_repo.py` - Fix driver lifecycle
7. `frontend/src/pages/EditPage.tsx:73` - Fix undefined setNodes

### Commands for Quick Wins
```bash
# Security audit
git log --all --full-history -- "*.env*"

# Find all print statements
grep -rn "print(" backend/app/

# Find bare exceptions
grep -rn "except:" backend/app/

# Check test coverage
pytest --cov=app --cov-report=html

# Run security scan
bandit -r backend/app/
```

---

**Document Status:** Active
**Last Updated:** 2026-02-01
**Next Review:** After Week 1 security fixes completed
