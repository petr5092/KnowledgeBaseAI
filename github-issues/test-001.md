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
