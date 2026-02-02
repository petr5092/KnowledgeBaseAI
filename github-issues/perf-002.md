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
