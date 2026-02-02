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
