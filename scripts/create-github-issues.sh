#!/bin/bash
set -e

# Script to create GitHub issues from comprehensive TODO
# Repository: XTeam-Pro/KnowledgeBaseAI

REPO="XTeam-Pro/KnowledgeBaseAI"
ISSUES_DIR="./github-issues"
mkdir -p "$ISSUES_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Creating GitHub Issues from COMPREHENSIVE_TODO.md${NC}"
echo "Repository: $REPO"
echo ""

# Check if gh is authenticated
if ! gh auth status &>/dev/null; then
    echo -e "${YELLOW}GitHub CLI is not authenticated.${NC}"
    echo "Please authenticate using one of these methods:"
    echo ""
    echo "  1. Interactive login (recommended):"
    echo "     gh auth login"
    echo ""
    echo "  2. Using a token:"
    echo "     export GITHUB_TOKEN=your_token_here"
    echo "     gh auth login --with-token <<<\$GITHUB_TOKEN"
    echo ""
    echo "After authentication, run this script again."
    exit 1
fi

echo -e "${GREEN}✓ GitHub CLI authenticated${NC}"
echo ""

# Create labels if they don't exist
echo "Creating labels..."
gh label create "priority:P0-critical" --color "d73a4a" --description "Critical security/data safety issue" --repo "$REPO" 2>/dev/null || true
gh label create "priority:P1-high" --color "ff6b6b" --description "High priority - fix within sprint" --repo "$REPO" 2>/dev/null || true
gh label create "priority:P2-medium" --color "ffa500" --description "Medium priority - quality improvements" --repo "$REPO" 2>/dev/null || true
gh label create "priority:P3-low" --color "0e8a16" --description "Low priority - enhancements" --repo "$REPO" 2>/dev/null || true
gh label create "security" --color "b60205" --description "Security vulnerability" --repo "$REPO" 2>/dev/null || true
gh label create "performance" --color "fbca04" --description "Performance issue" --repo "$REPO" 2>/dev/null || true
gh label create "bug" --color "d73a4a" --description "Something isn't working" --repo "$REPO" 2>/dev/null || true
gh label create "technical-debt" --color "d4c5f9" --description "Code quality issue" --repo "$REPO" 2>/dev/null || true
gh label create "infrastructure" --color "0052cc" --description "DevOps/Infrastructure" --repo "$REPO" 2>/dev/null || true
gh label create "testing" --color "c5def5" --description "Testing related" --repo "$REPO" 2>/dev/null || true
gh label create "documentation" --color "0075ca" --description "Documentation improvements" --repo "$REPO" 2>/dev/null || true

echo -e "${GREEN}✓ Labels created${NC}"
echo ""

# Create milestones
echo "Creating milestones..."
gh api repos/$REPO/milestones -X POST -f title="Week 1: Critical Security Fixes" -f description="Emergency security fixes and data safety" -f state="open" 2>/dev/null || true
gh api repos/$REPO/milestones -X POST -f title="Week 2: Performance & Stability" -f description="Performance optimizations and stability improvements" -f state="open" 2>/dev/null || true
gh api repos/$REPO/milestones -X POST -f title="Month 2: Code Quality & Testing" -f description="Code quality improvements and comprehensive testing" -f state="open" 2>/dev/null || true
gh api repos/$REPO/milestones -X POST -f title="Month 2: Infrastructure" -f description="CI/CD, monitoring, and operational improvements" -f state="open" 2>/dev/null || true

echo -e "${GREEN}✓ Milestones created${NC}"
echo ""

# Function to create an issue
create_issue() {
    local title="$1"
    local body_file="$2"
    local labels="$3"
    local milestone="$4"

    if [ -f "$body_file" ]; then
        local issue_url=$(gh issue create \
            --repo "$REPO" \
            --title "$title" \
            --body-file "$body_file" \
            --label "$labels" 2>&1)

        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓${NC} Created: $title"
            echo "   URL: $issue_url"
        else
            echo -e "${RED}✗${NC} Failed: $title"
            echo "   Error: $issue_url"
        fi
    else
        echo -e "${YELLOW}⚠${NC} Body file not found: $body_file"
    fi
}

echo "Creating P0 - Critical Issues..."
echo "================================"
echo ""

# SEC-001: Exposed Secrets
cat > "$ISSUES_DIR/sec-001.md" << 'EOF'
## Problem
**CRITICAL SECURITY BREACH**: OpenAI API keys, database passwords, JWT secrets, and other sensitive credentials are committed and exposed in version control.

**Files:**
- `.env.dev` - Contains OpenAI API key, Neo4j password, Postgres password
- `.env.prod` - Contains production credentials (SAME as dev!)

**Exposed credentials:**
- OpenAI API key: `sk-proj-poqHlE98Uf0yR9PJ...` (partially redacted)
- NEO4J_PASSWORD: `12ee8ba019`
- JWT_SECRET_KEY: `SFuw2HJdBTeccHlpx4t5...`
- BOOTSTRAP_ADMIN_PASSWORD: `gfhjkmvfhjkm`
- Multiple database passwords

## Impact
- Unauthorized access to production data
- OpenAI API abuse (financial loss)
- Complete system compromise
- GDPR/compliance violations

## Immediate Actions Required

### 1. Revoke All Credentials (URGENT - Do Now)
```bash
# Immediately revoke OpenAI API key
# Go to: https://platform.openai.com/api-keys

# Generate new secrets
openssl rand -base64 32  # For JWT_SECRET_KEY
openssl rand -base64 24  # For passwords
openssl rand -hex 32     # For API keys
```

### 2. Remove from Git History
```bash
# WARNING: This rewrites history
git filter-branch --tree-filter 'rm -f .env.dev .env.prod .env.stage' -- --all
git push origin --force --all
git push origin --force --tags
```

### 3. Update .gitignore
Add to `.gitignore`:
```
# Secrets
.env
.env.*
.env.*.local
secrets/
private/
*.key
*.pem
credentials.json
```

### 4. Implement Secret Management
Choose one:
- [ ] Option A: Docker secrets
- [ ] Option B: HashiCorp Vault
- [ ] Option C: AWS Secrets Manager

### 5. Rotate All Credentials
- [ ] OpenAI API key
- [ ] JWT_SECRET_KEY
- [ ] NEO4J_PASSWORD
- [ ] POSTGRES_PASSWORD
- [ ] BOOTSTRAP_ADMIN_PASSWORD
- [ ] ADMIN_API_KEY
- [ ] All other API keys/secrets

## Verification
```bash
# Check git history is clean
git log --all --full-history -- ".env*"
# Should return empty

# Verify .gitignore
git check-ignore .env.prod
# Should output: .env.prod
```

## Estimated Time
2-4 hours (URGENT)

## References
- COMPREHENSIVE_TODO.md: SEC-001
- Lines: `.env.dev`, `.env.prod`, `.env.stage`
EOF

create_issue "[SEC-001] CRITICAL: Exposed Secrets in Version Control" \
    "$ISSUES_DIR/sec-001.md" \
    "priority:P0-critical,security" \
    "Week 1: Critical Security Fixes"

# SEC-002: CORS Misconfiguration
cat > "$ISSUES_DIR/sec-002.md" << 'EOF'
## Problem
CORS middleware is misconfigured with a critical bug that allows ALL origins despite configuration.

**File:** `backend/app/main.py` (lines 212-220)

**Current code:**
```python
origins = [o.strip() for o in (settings.cors_allow_origins or "").split(",") if o.strip()]
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # BUG: Hardcoded wildcard!
        allow_credentials=True,  # DANGEROUS with wildcard
        allow_methods=["*"],
        allow_headers=["*"],
    )
```

## Security Impact
- **CSRF attacks**: Any website can make authenticated requests
- **Credential theft**: Cookies exposed to malicious sites
- **Data exfiltration**: Attackers can read user data
- Combined with `allow_credentials=True`, this is CRITICAL

## Fix
```python
origins = [o.strip() for o in (settings.cors_allow_origins or "").split(",") if o.strip()]
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,  # Use parsed list, not ["*"]
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],  # Whitelist
        allow_headers=["Content-Type", "Authorization"],  # Whitelist
    )
```

## Testing
```bash
# Before fix - should be rejected but isn't:
curl -H "Origin: https://evil.com" \
     -H "Cookie: session=..." \
     http://localhost:8000/v1/graph/viewport

# After fix - should be rejected:
# Response should NOT include: Access-Control-Allow-Origin: https://evil.com
```

## Estimated Time
30 minutes

## Files
- `backend/app/main.py:216`

## References
- COMPREHENSIVE_TODO.md: SEC-002
EOF

create_issue "[SEC-002] CRITICAL: CORS Allows All Origins" \
    "$ISSUES_DIR/sec-002.md" \
    "priority:P0-critical,security,bug" \
    "Week 1: Critical Security Fixes"

# SEC-003: PostgreSQL Trust Auth
cat > "$ISSUES_DIR/sec-003.md" << 'EOF'
## Problem
PostgreSQL is configured with `trust` authentication method, allowing connections without password.

**File:** `docker-compose.yml` (line 308)

```yaml
postgres:
  environment:
    POSTGRES_HOST_AUTH_METHOD: trust  # INSECURE!
```

## Security Impact
- Anyone with network access can connect to database
- No authentication barrier
- Complete database compromise possible

## Fix
```yaml
postgres:
  environment:
    POSTGRES_HOST_AUTH_METHOD: md5  # Require password
    POSTGRES_USER: ${POSTGRES_USER}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
```

## Verification Steps
1. Change auth method to `md5`
2. Restart postgres container
3. Verify fastapi can still connect (using PG_DSN with password)
4. Test that connection without password fails:
```bash
# Should fail:
docker exec -it knowledgebase-postgres-1 psql -U postgres -h localhost
# Should prompt for password
```

## Estimated Time
15 minutes

## Files
- `docker-compose.yml:308`

## References
- COMPREHENSIVE_TODO.md: SEC-003
EOF

create_issue "[SEC-003] CRITICAL: PostgreSQL Trust Authentication" \
    "$ISSUES_DIR/sec-003.md" \
    "priority:P0-critical,security,infrastructure" \
    "Week 1: Critical Security Fixes"

# SEC-004: Missing Health Checks
cat > "$ISSUES_DIR/sec-004.md" << 'EOF'
## Problem
No health checks configured for any Docker services. Services can fail silently without detection.

**File:** `docker-compose.yml`

## Impact
- Undetected service failures
- No automatic recovery
- Cascading failures
- Prolonged outages

## Fix
Add health checks to all services:

```yaml
fastapi:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 40s

postgres:
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
    interval: 10s
    timeout: 5s
    retries: 5

redis:
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 10s
    timeout: 5s
    retries: 3

neo4j:
  healthcheck:
    test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost:7474"]
    interval: 10s
    timeout: 5s
    retries: 3

qdrant:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:6333/health"]
    interval: 10s
    timeout: 5s
    retries: 3
```

Update depends_on to wait for healthy services:
```yaml
fastapi:
  depends_on:
    postgres:
      condition: service_healthy
    neo4j:
      condition: service_healthy
```

## Verification
```bash
docker-compose up -d
docker ps  # Should show health status
docker-compose ps  # Shows health in status column
```

## Estimated Time
2-3 hours

## Files
- `docker-compose.yml`

## References
- COMPREHENSIVE_TODO.md: SEC-004
EOF

create_issue "[SEC-004] CRITICAL: Missing Health Checks" \
    "$ISSUES_DIR/sec-004.md" \
    "priority:P0-critical,infrastructure" \
    "Week 1: Critical Security Fixes"

echo ""
echo "Creating more issues..."
echo ""

# DATA-001: No Backup Strategy
cat > "$ISSUES_DIR/data-001.md" << 'EOF'
## Problem
**CRITICAL**: No backup strategy exists. Complete data loss possible with no recovery mechanism.

**Current state:**
- No backup scripts
- No automated backups
- No documented recovery procedures
- No backup monitoring

## Risk
- Permanent data loss on failure
- No disaster recovery capability
- Compliance violations (if applicable)

## Implementation

### 1. Create Backup Script
File: `scripts/backup.sh`

```bash
#!/bin/bash
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

mkdir -p "$BACKUP_DIR"

# PostgreSQL
echo "Backing up PostgreSQL..."
docker exec knowledgebase-postgres-1 pg_dump -U ${POSTGRES_USER} ${POSTGRES_DB} | \
  gzip > "$BACKUP_DIR/postgres_${TIMESTAMP}.sql.gz"

# Neo4j
echo "Backing up Neo4j..."
docker exec knowledgebase-neo4j-1 neo4j-admin database backup neo4j \
  --to-path=/backups --overwrite-destination=true
docker cp knowledgebase-neo4j-1:/backups/neo4j.backup \
  "$BACKUP_DIR/neo4j_${TIMESTAMP}.backup"

# Qdrant
echo "Backing up Qdrant..."
docker exec knowledgebase-qdrant-1 curl -s http://localhost:6333/collections | \
  jq . > "$BACKUP_DIR/qdrant_${TIMESTAMP}.json"

# Cleanup old backups
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "*.backup" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: $BACKUP_DIR"
ls -lh "$BACKUP_DIR" | tail -5
```

### 2. Create Restore Script
File: `scripts/restore.sh`

### 3. Setup Cron Job
```bash
# Add to crontab
0 2 * * * cd /root/KnowledgeBaseAI && make backup
```

### 4. Test Procedures
- [ ] Test backup script
- [ ] Test restore to separate environment
- [ ] Document recovery procedures
- [ ] Set up backup monitoring

### 5. Add to Makefile
```makefile
.PHONY: backup
backup:
	bash scripts/backup.sh

.PHONY: restore
restore:
	bash scripts/restore.sh $(BACKUP_FILE)
```

## Verification
```bash
# Test backup
make backup

# Verify backup files exist
ls -lh backups/

# Test restore (on dev environment)
make restore BACKUP_FILE=backups/postgres_20260201_020000.sql.gz
```

## Estimated Time
4-6 hours (including testing)

## References
- COMPREHENSIVE_TODO.md: DATA-001
EOF

create_issue "[DATA-001] CRITICAL: No Backup Strategy" \
    "$ISSUES_DIR/data-001.md" \
    "priority:P0-critical,infrastructure" \
    "Week 1: Critical Security Fixes"

# Continue with more P0 issues...
# BUG-001: Neo4j Driver Bug
cat > "$ISSUES_DIR/bug-001.md" << 'EOF'
## Problem
Neo4j driver lifecycle bug causes global driver instance to be closed unexpectedly, breaking subsequent requests.

**File:** `backend/app/services/graph/neo4j_repo.py` (lines 140-222)

**Current code:**
```python
def read_graph(...):
    drv = get_driver()  # Returns global _driver_instance
    # ... use driver ...
    drv.close()  # CLOSES GLOBAL INSTANCE!
    return nodes, edges
```

## Impact
- Connection failures after first request
- "Driver has been closed" errors
- Service degradation
- Requires container restart

## Fix
Remove individual `close()` calls and use proper lifecycle management:

```python
# In neo4j_repo.py - remove close() calls
def read_graph(...):
    driver = get_driver()
    with driver.session() as session:
        result = session.run(query)
        # Session auto-closes, driver stays open
    return result
```

```python
# In main.py - add shutdown handler
@app.on_event("shutdown")
async def shutdown_event():
    driver = get_driver()
    if driver:
        driver.close()
```

## Files to Update
- `backend/app/services/graph/neo4j_repo.py` (remove all `drv.close()` calls)
- `backend/app/main.py` (add shutdown handler)

## Testing
```bash
# Test multiple requests work
for i in {1..10}; do
  curl http://localhost:8000/v1/graph/viewport?center_uid=test&depth=1
done
# All should succeed
```

## Estimated Time
2 hours

## References
- COMPREHENSIVE_TODO.md: BUG-001
EOF

create_issue "[BUG-001] CRITICAL: Neo4j Driver Lifecycle Bug" \
    "$ISSUES_DIR/bug-001.md" \
    "priority:P0-critical,bug" \
    "Week 1: Critical Security Fixes"

# BUG-002: React EditPage Broken
cat > "$ISSUES_DIR/bug-002.md" << 'EOF'
## Problem
EditPage component calls undefined `setNodes()` function, making the graph editor completely broken.

**File:** `frontend/src/pages/EditPage.tsx` (line 73)

**Current code:**
```typescript
const addNode = () => {
  const newNode = { ... }
  setNodes((old) => [...old, newNode])  // setNodes is undefined!
}
```

## Impact
- Edit page completely non-functional
- Cannot add or edit nodes
- Breaks core functionality

## Fix
Use Redux instead of local state:

```typescript
import { useDispatch } from 'react-redux'
import { addNode as addNodeAction } from '../store/editSlice'

export function EditPage() {
  const dispatch = useDispatch()

  const addNode = () => {
    const newNode = {
      id: generateUid(),
      type: 'default',
      position: { x: 0, y: 0 },
      data: { label: 'New Node' }
    }
    dispatch(addNodeAction(newNode))
  }

  return (
    <button onClick={addNode}>Add Node</button>
    // ...
  )
}
```

## Files
- `frontend/src/pages/EditPage.tsx:73`
- `frontend/src/store/editSlice.ts` (ensure addNode action exists)

## Testing
```bash
cd frontend
npm run dev
# Navigate to /edit
# Click "Add Node" button
# Should add node without errors
```

## Estimated Time
1 hour

## References
- COMPREHENSIVE_TODO.md: BUG-002
EOF

create_issue "[BUG-002] CRITICAL: React EditPage Undefined setNodes" \
    "$ISSUES_DIR/bug-002.md" \
    "priority:P0-critical,bug" \
    "Week 1: Critical Security Fixes"

echo ""
echo -e "${GREEN}P0 Critical issues created!${NC}"
echo ""
echo "Creating P1 High Priority Issues..."
echo "===================================="
echo ""

# PERF-001: Inefficient Roadmap Query
cat > "$ISSUES_DIR/perf-001.md" << 'EOF'
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
EOF

create_issue "[PERF-001] Inefficient Roadmap Query Causes Timeouts" \
    "$ISSUES_DIR/perf-001.md" \
    "priority:P1-high,performance" \
    "Week 2: Performance & Stability"

# PERF-002: LLM Caching
cat > "$ISSUES_DIR/perf-002.md" << 'EOF'
## Problem
OpenAI API called repeatedly for identical roadmap requests with no caching.

**File:** `backend/app/api/engine.py` (lines 280-287)

## Impact
- High API costs (GPT-4 is expensive)
- Slow response times (2-5s per request)
- Rate limit exhaustion
- Identical prompts called hundreds of times

## Cost Analysis
- Current: ~$0.03 per roadmap generation
- With 1000 users × 10 roadmaps/day = $300/day = $9000/month
- After caching: ~$50/month (98% reduction)

## Implementation
```python
# File: backend/app/services/llm_cache.py

from functools import wraps
import hashlib
import json
from typing import Any, Callable

def llm_cache(ttl: int = 3600):
    """Cache LLM responses in Redis"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # Create cache key from function arguments
            cache_key = f"llm:{hashlib.sha256(
                json.dumps(kwargs, sort_keys=True).encode()
            ).hexdigest()}"

            # Check cache
            cached = await redis_client.get(cache_key)
            if cached:
                return json.loads(cached)

            # Call function
            result = await func(*args, **kwargs)

            # Store in cache
            await redis_client.setex(
                cache_key,
                ttl,
                json.dumps(result)
            )

            return result
        return wrapper
    return decorator

# Usage:
@llm_cache(ttl=3600)  # 1 hour cache
async def call_llm_for_roadmap(prompt: str, model: str) -> dict:
    completion = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    return json.loads(completion.choices[0].message.content)
```

## Cache Strategy
- Roadmap generation: 1 hour TTL
- Chat responses: 10 minutes TTL
- Curriculum-specific: 24 hours TTL
- Cache warming for popular curricula

## Files
- Create: `backend/app/services/llm_cache.py`
- Update: `backend/app/api/engine.py`
- Update: `backend/app/api/assistant.py`

## Testing
```bash
# Measure cache hit rate
curl http://localhost:8000/metrics | grep llm_cache_hit_rate
# Target: >80% after 24 hours
```

## Estimated Time
3-4 hours

## References
- COMPREHENSIVE_TODO.md: PERF-002
EOF

create_issue "[PERF-002] Add LLM Response Caching" \
    "$ISSUES_DIR/perf-002.md" \
    "priority:P1-high,performance" \
    "Week 2: Performance & Stability"

# DATA-002: Connection Pooling
cat > "$ISSUES_DIR/data-002.md" << 'EOF'
## Problem
PostgreSQL creates new connection per request with no connection pooling.

**File:** `backend/app/db/pg.py` (lines 5-9)

```python
def get_conn():
    dsn = str(settings.pg_dsn)
    return psycopg2.connect(dsn)  # New connection every time!
```

## Impact
- Connection exhaustion (PostgreSQL default: 100 connections)
- High connection overhead (~50ms per connection)
- Performance degradation under load
- Service failures when connection limit reached

## Solution: Add PgBouncer

### 1. Add to docker-compose.yml
```yaml
pgbouncer:
  image: pgbouncer/pgbouncer:1.21
  environment:
    DATABASES_HOST: postgres
    DATABASES_PORT: 5432
    DATABASES_USER: ${POSTGRES_USER}
    DATABASES_PASSWORD: ${POSTGRES_PASSWORD}
    DATABASES_DBNAME: ${POSTGRES_DB}
    POOL_MODE: transaction
    MAX_CLIENT_CONN: 1000
    DEFAULT_POOL_SIZE: 25
    MIN_POOL_SIZE: 5
  ports:
    - "6432:6432"
  depends_on:
    postgres:
      condition: service_healthy
  restart: unless-stopped
```

### 2. Update PG_DSN
```bash
# In .env files, change:
# FROM: postgresql://user:pass@postgres:5432/db
# TO:   postgresql://user:pass@pgbouncer:6432/db
```

### 3. No code changes needed!
PgBouncer is transparent to application.

## Testing
```bash
# Monitor connections
docker exec postgres psql -U ${POSTGRES_USER} -c "SELECT count(*) FROM pg_stat_activity;"
# Should stay low (<10) even under load

# Load test
ab -n 1000 -c 50 http://localhost:8000/v1/graph/viewport?center_uid=test&depth=1
```

## Performance Improvement
- Before: ~150ms per request (includes connection time)
- After: ~50ms per request
- **3x performance improvement**

## Files
- `docker-compose.yml`
- `.env.prod`, `.env.dev` (update PG_DSN)

## Estimated Time
3-4 hours (including testing)

## References
- COMPREHENSIVE_TODO.md: DATA-002
EOF

create_issue "[DATA-002] Add Database Connection Pooling" \
    "$ISSUES_DIR/data-002.md" \
    "priority:P1-high,performance,infrastructure" \
    "Week 2: Performance & Stability"

echo ""
echo -e "${GREEN}P1 High priority issues created!${NC}"
echo ""
echo "Creating P2 Medium Priority Issues (sample)..."
echo "=============================================="
echo ""

# CODE-001: Bare Exception Handlers
cat > "$ISSUES_DIR/code-001.md" << 'EOF'
## Problem
Multiple files use bare `except:` clauses that catch all exceptions including system-level ones.

**Locations:**
- `backend/app/api/engine.py:358-361, 577-586, 652-675`
- `backend/app/services/kb/builder.py:27-28, 61-62`

**Example:**
```python
try:
    return json.loads(p)
except:  # Catches KeyboardInterrupt, SystemExit!
    return {}
```

## Impact
- Hides real errors
- Difficult debugging
- May suppress critical errors
- Unprofessional code quality

## Fix
Replace with specific exception types:

```python
try:
    return json.loads(p)
except (ValueError, json.JSONDecodeError) as e:
    logger.warning(f"Failed to parse JSON: {e}", exc_info=True)
    return {}
```

## Action Plan
1. Find all bare except: `grep -rn "except:" backend/app/`
2. Replace each with specific exception
3. Add logging for caught exceptions
4. Test error scenarios

## Estimated Time
2-3 hours

## References
- COMPREHENSIVE_TODO.md: CODE-001
EOF

create_issue "[CODE-001] Replace Bare Exception Handlers" \
    "$ISSUES_DIR/code-001.md" \
    "priority:P2-medium,technical-debt" \
    "Month 2: Code Quality & Testing"

# TEST-001: Coverage
cat > "$ISSUES_DIR/test-001.md" << 'EOF'
## Problem
Minimal test coverage: ~15% estimated

**Current state:**
- Backend: 726 lines of tests for ~5800 lines of code
- Frontend: No test files found
- Missing: Auth, proposals, engine, services

## Target Coverage
- Backend: 70%+ line coverage
- Frontend: 60%+ line coverage
- Critical paths: 90%+ coverage

## Implementation Plan

### 1. Setup Test Infrastructure
```bash
# Backend
pip install pytest-cov pytest-asyncio

# Frontend
npm install --save-dev @testing-library/react vitest @testing-library/jest-dom
```

### 2. Priority Test Areas (Backend)
- [ ] `tests/api/test_auth.py` - Authentication flow
- [ ] `tests/api/test_engine.py` - Roadmap generation
- [ ] `tests/api/test_proposals.py` - Proposal lifecycle
- [ ] `tests/services/test_graph_repo.py` - Graph operations
- [ ] `tests/workers/test_commit.py` - Transaction handling

### 3. Priority Test Areas (Frontend)
- [ ] `tests/pages/ExplorePage.test.tsx` - Graph visualization
- [ ] `tests/components/AIChat.test.tsx` - Chat functionality
- [ ] `tests/api.test.ts` - API client
- [ ] `tests/store/exploreSlice.test.ts` - Redux state

### 4. Configure Coverage
```ini
# pytest.ini
[pytest]
testpaths = tests
addopts =
    --cov=app
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=70
```

### 5. CI Integration
Add to `.github/workflows/ci.yml`:
```yaml
- name: Run tests with coverage
  run: |
    pytest --cov=app --cov-report=xml

- name: Upload coverage
  uses: codecov/codecov-action@v3
```

## Estimated Time
15-20 hours (comprehensive coverage)

## References
- COMPREHENSIVE_TODO.md: TEST-001
EOF

create_issue "[TEST-001] Increase Test Coverage to 70%" \
    "$ISSUES_DIR/test-001.md" \
    "priority:P2-medium,testing" \
    "Month 2: Code Quality & Testing"

echo ""
echo -e "${GREEN}✓ Sample issues created successfully!${NC}"
echo ""
echo "Summary:"
echo "--------"
gh issue list --repo "$REPO" --limit 20

echo ""
echo -e "${YELLOW}Note: Only critical and high priority issues were created as samples.${NC}"
echo "To create all issues from COMPREHENSIVE_TODO.md, modify this script to include P2 and P3 issues."
echo ""
echo -e "${GREEN}Done! View all issues at: https://github.com/$REPO/issues${NC}"
EOF
