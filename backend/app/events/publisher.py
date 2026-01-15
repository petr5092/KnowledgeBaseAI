import json
from typing import Dict
import redis
from app.config.settings import settings

def get_redis():
    return redis.Redis.from_url(str(settings.redis_url))

def publish_graph_committed(event: Dict) -> None:
    r = get_redis()
    r.lpush("events:graph_committed", json.dumps(event))
