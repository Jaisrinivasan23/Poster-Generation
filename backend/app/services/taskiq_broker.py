"""
TaskIQ Broker Configuration
Handles async task queuing and processing
"""
from taskiq import TaskiqScheduler
from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend
from app.config import settings
import structlog

logger = structlog.get_logger(__name__)

# Redis connection URL
REDIS_URL = f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}"

# Create broker with Redis backend
broker = ListQueueBroker(
    url=REDIS_URL,
    queue_name="poster-generation-queue",
    max_connection_pool_size=50,
)

# Result backend for storing task results
result_backend = RedisAsyncResultBackend(
    redis_url=REDIS_URL,
    result_ex_time=3600,  # Results expire after 1 hour
)

broker = broker.with_result_backend(result_backend)


async def startup_broker():
    """Initialize TaskIQ broker on startup"""
    try:
        await broker.startup()
        logger.info("TaskIQ broker started successfully", redis_url=REDIS_URL)
    except Exception as e:
        logger.error("Failed to start TaskIQ broker", error=str(e))
        raise


async def shutdown_broker():
    """Shutdown TaskIQ broker"""
    try:
        await broker.shutdown()
        logger.info("TaskIQ broker shutdown successfully")
    except Exception as e:
        logger.error("Failed to shutdown TaskIQ broker", error=str(e))
