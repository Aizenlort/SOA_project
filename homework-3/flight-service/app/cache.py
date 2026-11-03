import redis
from redis.sentinel import Sentinel
from config import settings
import logging
import json

logger = logging.getLogger(__name__)

# Инициализация Sentinel
sentinel = Sentinel([(settings.REDIS_SENTINEL_HOST, settings.REDIS_SENTINEL_PORT)], socket_timeout=1.0)

def get_redis_master():
    return sentinel.master_for(settings.REDIS_MASTER_NAME, socket_timeout=1.0, decode_responses=True)

def get_flight_cache_key(flight_id: str) -> str:
    return f"flight:{flight_id}"

def get_search_cache_key(origin: str, destination: str, date: str) -> str:
    return f"search:{origin}:{destination}:{date}"

def cache_get(key: str):
    try:
        r = get_redis_master()
        val = r.get(key)
        if val:
            logger.info(f"CACHE HIT: {key}")
            return json.loads(val)
        logger.info(f"CACHE MISS: {key}")
        return None
    except Exception as e:
        logger.error(f"Redis error on GET {key}: {e}")
        return None

def cache_set(key: str, value: dict, ttl: int = 300): # 5 минут по умолчанию
    try:
        r = get_redis_master()
        r.setex(key, ttl, json.dumps(value))
        logger.info(f"CACHE SET: {key} (TTL: {ttl}s)")
    except Exception as e:
        logger.error(f"Redis error on SET {key}: {e}")

def cache_delete(key: str):
    try:
        r = get_redis_master()
        r.delete(key)
        logger.info(f"CACHE INVALIDATED: {key}")
    except Exception as e:
        logger.error(f"Redis error on DELETE {key}: {e}")