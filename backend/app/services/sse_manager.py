"""
SSE (Server-Sent Events) Manager Service
Manages real-time event streaming to connected clients with Redis pub/sub
"""
import asyncio
import json
from typing import Dict, Set, Optional, Any, AsyncGenerator
from datetime import datetime
import structlog
from sse_starlette.sse import ServerSentEvent
import redis.asyncio as redis

from app.config import settings

logger = structlog.get_logger(__name__)


class SSEConnection:
    """Represents a single SSE connection"""
    
    def __init__(self, connection_id: str, job_id: str):
        self.connection_id = connection_id
        self.job_id = job_id
        self.queue: asyncio.Queue = asyncio.Queue()
        self.created_at = datetime.utcnow()
        self.last_event_at = datetime.utcnow()
        self._closed = False
    
    async def send(self, event_type: str, data: Dict[str, Any]):
        """Queue an event to be sent"""
        if not self._closed:
            await self.queue.put({
                "event": event_type,
                "data": data,
                "timestamp": datetime.utcnow().isoformat()
            })
            self.last_event_at = datetime.utcnow()
    
    async def receive(self) -> Optional[Dict[str, Any]]:
        """Receive next event from queue (no timeout - infinite wait with heartbeats)"""
        if self._closed:
            return None
        try:
            # Wait for event with very long timeout (30 minutes) for heartbeat
            return await asyncio.wait_for(self.queue.get(), timeout=1800.0)
        except asyncio.TimeoutError:
            # Send heartbeat every 30 minutes to keep connection alive
            return {"event": "heartbeat", "data": {"status": "alive", "timestamp": datetime.utcnow().isoformat()}}
    
    def close(self):
        """Close the connection"""
        self._closed = True


class SSEManager:
    """
    Manages Server-Sent Events connections and broadcasting with Redis pub/sub
    """

    def __init__(self):
        # job_id -> Set of connections
        self._connections: Dict[str, Set[SSEConnection]] = {}
        # connection_id -> SSEConnection
        self._connection_map: Dict[str, SSEConnection] = {}
        self._lock = asyncio.Lock()

        # Redis pub/sub for cross-process communication
        self._redis_client: Optional[redis.Redis] = None
        self._pubsub: Optional[redis.client.PubSub] = None
        self._subscriber_task: Optional[asyncio.Task] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize Redis pub/sub for cross-process event broadcasting"""
        if self._initialized:
            return

        try:
            redis_url = f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}"
            self._redis_client = await redis.from_url(redis_url, decode_responses=True)
            self._pubsub = self._redis_client.pubsub()

            # Subscribe to SSE events channel
            await self._pubsub.subscribe("sse_events")

            # Start subscriber task
            self._subscriber_task = asyncio.create_task(self._redis_subscriber())

            self._initialized = True
            logger.info("SSE Manager: Redis pub/sub initialized")
        except Exception as e:
            logger.error("SSE Manager: Failed to initialize Redis pub/sub", error=str(e))

    async def close(self):
        """Close Redis pub/sub connections"""
        if self._subscriber_task:
            self._subscriber_task.cancel()
            try:
                await self._subscriber_task
            except asyncio.CancelledError:
                pass

        if self._pubsub:
            await self._pubsub.unsubscribe("sse_events")
            await self._pubsub.close()

        if self._redis_client:
            await self._redis_client.close()

        self._initialized = False
        logger.info("SSE Manager: Redis pub/sub closed")

    async def _redis_subscriber(self):
        """Background task to receive Redis pub/sub messages and broadcast to SSE connections"""
        logger.info("SSE Manager: Redis subscriber started, listening for events...")
        try:
            async for message in self._pubsub.listen():
                if message["type"] == "message":
                    try:
                        event_data = json.loads(message["data"])
                        job_id = event_data.get("job_id")
                        event_type = event_data.get("event_type")
                        data = event_data.get("data", {})

                        logger.debug("SSE Manager: Received Redis message", 
                                   job_id=job_id, event_type=event_type)
                        print(f"📥 [SSE] Received Redis event: {event_type} for job {job_id}")

                        if job_id and event_type:
                            # Broadcast to local connections
                            await self._broadcast_local(job_id, event_type, data)
                    except Exception as e:
                        logger.error("SSE Manager: Error processing Redis message", error=str(e))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("SSE Manager: Redis subscriber error", error=str(e))

    async def _broadcast_local(self, job_id: str, event_type: str, data: Dict[str, Any]):
        """Broadcast event to local SSE connections for this job"""
        async with self._lock:
            if job_id in self._connections:
                connections = list(self._connections[job_id])
                print(f"📤 [SSE] Broadcasting {event_type} to {len(connections)} connections for job {job_id}")
            else:
                print(f"⚠️ [SSE] No connections for job {job_id}, event {event_type} dropped")
                logger.debug("SSE Manager: No connections for job, event dropped", 
                           job_id=job_id, event_type=event_type,
                           registered_jobs=list(self._connections.keys()))
                return

        for connection in connections:
            try:
                await connection.send(event_type, data)
            except Exception as e:
                logger.error("Failed to send SSE event to connection",
                           connection_id=connection.connection_id,
                           error=str(e))

    async def connect(self, job_id: str, connection_id: str) -> SSEConnection:
        """Register a new SSE connection"""
        # Ensure Redis pub/sub is initialized
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            connection = SSEConnection(connection_id, job_id)

            if job_id not in self._connections:
                self._connections[job_id] = set()

            self._connections[job_id].add(connection)
            self._connection_map[connection_id] = connection

            logger.info("SSE connection established",
                       job_id=job_id,
                       connection_id=connection_id,
                       total_connections=len(self._connection_map))

            # Send initial connection event
            await connection.send("connected", {
                "job_id": job_id,
                "connection_id": connection_id,
                "message": "Connected to job updates"
            })

            return connection
    
    async def disconnect(self, connection_id: str):
        """Remove an SSE connection"""
        async with self._lock:
            if connection_id in self._connection_map:
                connection = self._connection_map[connection_id]
                connection.close()
                
                job_id = connection.job_id
                if job_id in self._connections:
                    self._connections[job_id].discard(connection)
                    if not self._connections[job_id]:
                        del self._connections[job_id]
                
                del self._connection_map[connection_id]
                
                logger.info("SSE connection closed", 
                           job_id=job_id, 
                           connection_id=connection_id,
                           total_connections=len(self._connection_map))
    
    async def broadcast_to_job(self, job_id: str, event_type: str, data: Dict[str, Any]):
        """Broadcast an event to all connections for a specific job via Redis pub/sub"""
        try:
            # Ensure Redis is initialized
            if not self._initialized:
                await self.initialize()

            # Publish to Redis so all backend processes receive it
            if self._redis_client:
                event_message = json.dumps({
                    "job_id": job_id,
                    "event_type": event_type,
                    "data": data
                })
                await self._redis_client.publish("sse_events", event_message)
                logger.debug("Published SSE event to Redis", job_id=job_id, event_type=event_type)
            else:
                # Fallback to local broadcast if Redis not available
                await self._broadcast_local(job_id, event_type, data)
        except Exception as e:
            logger.error("Failed to broadcast SSE event", job_id=job_id, error=str(e))
            # Fallback to local broadcast
            await self._broadcast_local(job_id, event_type, data)
    
    async def send_progress(
        self,
        job_id: str,
        processed: int,
        total: int,
        success_count: int,
        failure_count: int,
        current_user: Optional[str] = None,
        phase: str = "processing"
    ):
        """Send progress update event"""
        await self.broadcast_to_job(job_id, "progress", {
            "job_id": job_id,
            "processed": processed,
            "total": total,
            "success_count": success_count,
            "failure_count": failure_count,
            "percent_complete": round((processed / total) * 100, 1) if total > 0 else 0,
            "current_user": current_user,
            "phase": phase
        })
    
    async def send_poster_completed(
        self,
        job_id: str,
        username: str,
        poster_url: str,
        success: bool,
        error: Optional[str] = None
    ):
        """Send individual poster completion event"""
        await self.broadcast_to_job(job_id, "poster_completed", {
            "job_id": job_id,
            "username": username,
            "poster_url": poster_url,
            "success": success,
            "error": error
        })
    
    async def send_job_completed(
        self,
        job_id: str,
        success_count: int,
        failure_count: int,
        total_time_seconds: float,
        results: list
    ):
        """Send job completion event"""
        await self.broadcast_to_job(job_id, "job_completed", {
            "job_id": job_id,
            "success_count": success_count,
            "failure_count": failure_count,
            "total_time_seconds": round(total_time_seconds, 2),
            "results": results
        })
    
    async def send_job_failed(
        self,
        job_id: str,
        error: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """Send job failure event"""
        await self.broadcast_to_job(job_id, "job_failed", {
            "job_id": job_id,
            "error": error,
            "details": details or {}
        })
    
    async def send_log(
        self,
        job_id: str,
        level: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """Send log event"""
        await self.broadcast_to_job(job_id, "log", {
            "job_id": job_id,
            "level": level,
            "message": message,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def get_connection_count(self, job_id: Optional[str] = None) -> int:
        """Get number of active connections"""
        if job_id:
            return len(self._connections.get(job_id, set()))
        return len(self._connection_map)
    
    async def event_generator(self, connection: SSEConnection) -> AsyncGenerator[ServerSentEvent, None]:
        """Generate SSE events for a connection"""
        try:
            while True:
                event = await connection.receive()
                if event is None:
                    break
                
                yield ServerSentEvent(
                    data=json.dumps(event["data"]),
                    event=event["event"]
                )
        except asyncio.CancelledError:
            pass
        finally:
            await self.disconnect(connection.connection_id)
    
    async def subscribe(self, job_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Subscribe to SSE events for a job - yields formatted SSE events"""
        import uuid
        connection_id = f"conn_{uuid.uuid4().hex[:8]}"
        connection = await self.connect(job_id, connection_id)
        
        try:
            while True:
                event = await connection.receive()
                if event is None:
                    break
                
                yield {
                    "event": event["event"],
                    "data": json.dumps(event["data"])
                }
                
                # Check if job completed/failed
                if event["event"] in ("job_completed", "job_failed"):
                    break
        except asyncio.CancelledError:
            pass
        finally:
            await self.disconnect(connection_id)


# Global singleton instance
sse_manager = SSEManager()


async def get_sse_manager() -> SSEManager:
    """Get the global SSE manager instance"""
    return sse_manager
