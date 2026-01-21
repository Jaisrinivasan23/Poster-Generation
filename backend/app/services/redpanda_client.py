"""
RedPanda (Kafka) Client Service
Handles message publishing and consuming for batch poster generation
"""
import asyncio
import json
import uuid
from typing import Optional, Callable, Dict, Any, List
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from aiokafka.errors import TopicAlreadyExistsError
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

# Topic names
TOPIC_POSTER_REQUESTS = "poster.generation.requests"
TOPIC_POSTER_RESULTS = "poster.generation.results"
TOPIC_POSTER_PROGRESS = "poster.generation.progress"
TOPIC_POSTER_ERRORS = "poster.generation.errors"


class RedPandaClient:
    """
    RedPanda/Kafka client for message streaming
    Supports async producer and consumer operations
    """
    
    def __init__(self):
        self.producer: Optional[AIOKafkaProducer] = None
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.admin_client: Optional[AIOKafkaAdminClient] = None
        self._is_initialized = False
        self._consumer_tasks: List[asyncio.Task] = []
        
    async def initialize(self) -> bool:
        """Initialize RedPanda connections and create topics"""
        try:
            bootstrap_servers = settings.redpanda_broker
            print(f"")
            print(f"🔴 [REDPANDA] Connecting to broker: {bootstrap_servers}")
            logger.info("Initializing RedPanda client", broker=bootstrap_servers)
            
            # Create admin client and topics
            await self._create_topics()
            
            # Initialize producer
            self.producer = AIOKafkaProducer(
                bootstrap_servers=bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                acks='all',
                enable_idempotence=True,
                max_batch_size=16384,
                linger_ms=10,
            )
            await self.producer.start()
            
            self._is_initialized = True
            print(f"✅ [REDPANDA] Client initialized successfully!")
            logger.info("RedPanda client initialized successfully")
            return True
            
        except Exception as e:
            print(f"❌ [REDPANDA] Failed to initialize: {str(e)}")
            logger.error("Failed to initialize RedPanda client", error=str(e))
            return False
    
    async def _create_topics(self):
        """Create required Kafka topics if they don't exist"""
        try:
            self.admin_client = AIOKafkaAdminClient(
                bootstrap_servers=settings.redpanda_broker
            )
            await self.admin_client.start()
            
            topics = [
                NewTopic(
                    name=TOPIC_POSTER_REQUESTS,
                    num_partitions=3,
                    replication_factor=1,
                    topic_configs={"retention.ms": "86400000"}  # 24 hours
                ),
                NewTopic(
                    name=TOPIC_POSTER_RESULTS,
                    num_partitions=3,
                    replication_factor=1,
                    topic_configs={"retention.ms": "86400000"}
                ),
                NewTopic(
                    name=TOPIC_POSTER_PROGRESS,
                    num_partitions=3,
                    replication_factor=1,
                    topic_configs={"retention.ms": "3600000"}  # 1 hour
                ),
                NewTopic(
                    name=TOPIC_POSTER_ERRORS,
                    num_partitions=1,
                    replication_factor=1,
                    topic_configs={"retention.ms": "604800000"}  # 7 days
                ),
            ]
            
            for topic in topics:
                try:
                    await self.admin_client.create_topics([topic])
                    logger.info(f"Created topic: {topic.name}")
                except TopicAlreadyExistsError:
                    logger.debug(f"Topic already exists: {topic.name}")
                except Exception as e:
                    logger.warning(f"Could not create topic {topic.name}: {e}")
                    
            await self.admin_client.close()
            
        except Exception as e:
            logger.error("Failed to create topics", error=str(e))
    
    async def publish_job(self, job_id: str, job_data: Dict[str, Any]) -> bool:
        """
        Publish a new poster generation job to the queue
        
        Args:
            job_id: Unique job identifier
            job_data: Job configuration and data
        """
        if not self._is_initialized or not self.producer:
            print(f"⚠️ [REDPANDA] Client not initialized, cannot publish job")
            logger.error("RedPanda client not initialized")
            return False
            
        try:
            message = {
                "job_id": job_id,
                "timestamp": asyncio.get_event_loop().time(),
                **job_data
            }
            
            print(f"📤 [REDPANDA] Publishing job {job_id} to topic: {TOPIC_POSTER_REQUESTS}")
            await self.producer.send_and_wait(
                topic=TOPIC_POSTER_REQUESTS,
                key=job_id,
                value=message
            )
            
            print(f"✅ [REDPANDA] Job {job_id} published successfully!")
            logger.info("Published job to queue", job_id=job_id)
            return True
            
        except Exception as e:
            print(f"❌ [REDPANDA] Failed to publish job {job_id}: {str(e)}")
            logger.error("Failed to publish job", job_id=job_id, error=str(e))
            return False
    
    async def publish_progress(self, job_id: str, progress_data: Dict[str, Any]) -> bool:
        """Publish progress update for a job"""
        if not self._is_initialized or not self.producer:
            return False
            
        try:
            message = {
                "job_id": job_id,
                "type": "progress",
                "timestamp": asyncio.get_event_loop().time(),
                **progress_data
            }
            
            await self.producer.send_and_wait(
                topic=TOPIC_POSTER_PROGRESS,
                key=job_id,
                value=message
            )
            return True
            
        except Exception as e:
            logger.error("Failed to publish progress", job_id=job_id, error=str(e))
            return False
    
    async def publish_result(self, job_id: str, result_data: Dict[str, Any]) -> bool:
        """Publish result for a completed poster"""
        if not self._is_initialized or not self.producer:
            return False
            
        try:
            message = {
                "job_id": job_id,
                "type": "result",
                "timestamp": asyncio.get_event_loop().time(),
                **result_data
            }
            
            await self.producer.send_and_wait(
                topic=TOPIC_POSTER_RESULTS,
                key=job_id,
                value=message
            )
            return True
            
        except Exception as e:
            logger.error("Failed to publish result", job_id=job_id, error=str(e))
            return False
    
    async def publish_error(self, job_id: str, error_data: Dict[str, Any]) -> bool:
        """Publish error for a failed operation"""
        if not self._is_initialized or not self.producer:
            return False
            
        try:
            message = {
                "job_id": job_id,
                "type": "error",
                "timestamp": asyncio.get_event_loop().time(),
                **error_data
            }
            
            await self.producer.send_and_wait(
                topic=TOPIC_POSTER_ERRORS,
                key=job_id,
                value=message
            )
            return True
            
        except Exception as e:
            logger.error("Failed to publish error", job_id=job_id, error=str(e))
            return False
    
    async def start_consumer(
        self,
        topics: List[str],
        group_id: str,
        handler: Callable[[Dict[str, Any]], None]
    ) -> asyncio.Task:
        """
        Start a consumer for specified topics
        
        Args:
            topics: List of topics to consume from
            group_id: Consumer group ID
            handler: Async function to handle messages
        """
        consumer = AIOKafkaConsumer(
            *topics,
            bootstrap_servers=settings.redpanda_broker,
            group_id=group_id,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            auto_commit_interval_ms=5000,
        )
        
        async def consume():
            await consumer.start()
            try:
                async for msg in consumer:
                    try:
                        await handler(msg.value)
                    except Exception as e:
                        logger.error("Error processing message", error=str(e))
            finally:
                await consumer.stop()
        
        task = asyncio.create_task(consume())
        self._consumer_tasks.append(task)
        return task
    
    async def close(self):
        """Close all connections"""
        logger.info("Closing RedPanda client")
        
        # Cancel consumer tasks
        for task in self._consumer_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        if self.producer:
            await self.producer.stop()
            
        self._is_initialized = False
        logger.info("RedPanda client closed")
    
    @property
    def is_healthy(self) -> bool:
        """Check if the client is healthy"""
        return self._is_initialized and self.producer is not None


# Global singleton instance
redpanda_client = RedPandaClient()


async def get_redpanda_client() -> RedPandaClient:
    """Get the global RedPanda client instance"""
    return redpanda_client
