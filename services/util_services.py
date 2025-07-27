from fastapi import APIRouter, Request
from src.main_logger import logger
from library.cache_connect import get_redis

util_router = APIRouter()

@util_router.get("/flush-redis")
async def flush_redis(request:Request):
    try:
        redis_instance = get_redis()
        await redis_instance.flushdb()
        logger.info("redis cleaned sucessfully")
        return {
            "message":"redis cleaned sucessfully"
        }
    except Exception as e:
        logger.exception(f"error in flushing redis {e}")
        return {
            "message":"unable to flush redis"
        }