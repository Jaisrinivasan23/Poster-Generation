"""
SSE (Server-Sent Events) Manager Service
Manages real-time event streaming to connected clients
"""
import asyncio
import json
from typing import Dict, Set, Optional, Any, AsyncGenerator
from datetime import datetime
import structlog
from sse_starlette.sse import ServerSentEvent

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
        """Receive next event from queue"""
        if self._closed:
            return None
        try:
            return await asyncio.wait_for(self.queue.get(), timeout=30.0)
        except asyncio.TimeoutError:
            # Send heartbeat
            return {"event": "heartbeat", "data": {"status": "alive"}}
    
    def close(self):
        """Close the connection"""
        self._closed = True


class SSEManager:
    """
    Manages Server-Sent Events connections and broadcasting
    """
    
    def __init__(self):
        # job_id -> Set of connections
        self._connections: Dict[str, Set[SSEConnection]] = {}
        # connection_id -> SSEConnection
        self._connection_map: Dict[str, SSEConnection] = {}
        self._lock = asyncio.Lock()
    
    async def connect(self, job_id: str, connection_id: str) -> SSEConnection:
        """Register a new SSE connection"""
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
        """Broadcast an event to all connections for a specific job"""
        async with self._lock:
            if job_id in self._connections:
                connections = list(self._connections[job_id])
                
        if job_id not in self._connections:
            return
        
        for connection in connections:
            try:
                await connection.send(event_type, data)
            except Exception as e:
                logger.error("Failed to send SSE event", 
                            connection_id=connection.connection_id, 
                            error=str(e))
    
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
