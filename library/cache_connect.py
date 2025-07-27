import redis.asyncio as redis
from src.common import get_config
from src.main_logger import logger

redis_creds = get_config("redis")
redis_client = redis.Redis(**redis_creds, decode_responses=True)
logger.info("connected to redis sucessfully")

def get_redis():
    """ Returns a Redis Client """
    try:
        global redis_client
        if redis_client:
            logger.info("returning global redis")
            return redis_client
        client = redis.Redis(**redis_creds, decode_responses=True)
        return client
    except Exception as e:
        logger.exception(f"error in getting redis connection {e}")
        return None