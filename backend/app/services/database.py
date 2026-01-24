"""
PostgreSQL Database Service
Handles database connections and operations for job management
"""
import asyncio
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
from datetime import datetime
import asyncpg
import structlog
import json

from app.config import settings

logger = structlog.get_logger(__name__)


class DatabaseService:
    """
    PostgreSQL database service using asyncpg for async operations
    """
    
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self._is_initialized = False
    
    async def initialize(self) -> bool:
        """Initialize the database connection pool"""
        try:
            dsn = f"postgresql://{settings.postgres_user}:{settings.postgres_password}@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
            
            logger.info("Initializing database connection pool", 
                       host=settings.postgres_host, 
                       database=settings.postgres_db)
            
            self.pool = await asyncpg.create_pool(
                dsn=dsn,
                min_size=5,
                max_size=20,
                command_timeout=60,
            )
            
            # Verify connection
            async with self.pool.acquire() as conn:
                version = await conn.fetchval("SELECT version()")
                logger.info("Database connected", version=version[:50])
            
            self._is_initialized = True
            return True
            
        except Exception as e:
            logger.error("Failed to initialize database", error=str(e))
            return False
    
    async def close(self):
        """Close the database connection pool"""
        if self.pool:
            await self.pool.close()
            self._is_initialized = False
            logger.info("Database connection pool closed")
    
    @asynccontextmanager
    async def connection(self):
        """Get a database connection from the pool"""
        if not self.pool:
            raise RuntimeError("Database not initialized")
        async with self.pool.acquire() as conn:
            yield conn
    
    # ============ Batch Jobs ============
    
    async def create_batch_job(
        self,
        job_id: str,
        campaign_name: str,
        total_items: int,
        template_html: Optional[str] = None,
        template_url: Optional[str] = None,
        poster_size: str = "instagram-square",
        model: str = "flash",
        user_identifiers: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a new batch job record"""
        async with self.connection() as conn:
            result = await conn.fetchrow(
                """
                INSERT INTO batch_jobs (
                    job_id, campaign_name, status, total_items, 
                    template_html, template_url, poster_size, model,
                    user_identifiers, metadata
                ) VALUES ($1, $2, 'pending', $3, $4, $5, $6, $7, $8, $9)
                RETURNING id, job_id
                """,
                job_id, campaign_name, total_items,
                template_html, template_url, poster_size, model,
                user_identifiers, json.dumps(metadata or {})
            )
            logger.info("Created batch job", job_id=job_id, total_items=total_items)
            return result['job_id']
    
    async def update_job_status(
        self,
        job_id: str,
        status: str,
        processed_items: Optional[int] = None,
        success_count: Optional[int] = None,
        failure_count: Optional[int] = None,
        error_message: Optional[str] = None
    ):
        """Update batch job status"""
        async with self.connection() as conn:
            update_parts = ["status = $2"]
            params = [job_id, status]
            param_idx = 3
            
            if status == 'processing':
                update_parts.append(f"started_at = CURRENT_TIMESTAMP")
            elif status in ('completed', 'failed'):
                update_parts.append(f"completed_at = CURRENT_TIMESTAMP")
            
            if processed_items is not None:
                update_parts.append(f"processed_items = ${param_idx}")
                params.append(processed_items)
                param_idx += 1
            
            if success_count is not None:
                update_parts.append(f"success_count = ${param_idx}")
                params.append(success_count)
                param_idx += 1
            
            if failure_count is not None:
                update_parts.append(f"failure_count = ${param_idx}")
                params.append(failure_count)
                param_idx += 1
            
            if error_message is not None:
                update_parts.append(f"error_message = ${param_idx}")
                params.append(error_message)
                param_idx += 1
            
            query = f"UPDATE batch_jobs SET {', '.join(update_parts)} WHERE job_id = $1"
            await conn.execute(query, *params)
            logger.debug("Updated job status", job_id=job_id, status=status)
    
    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get batch job by ID"""
        async with self.connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM batch_jobs WHERE job_id = $1",
                job_id
            )
            if row:
                return dict(row)
            return None
    
    async def get_jobs(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get batch jobs with optional filtering"""
        async with self.connection() as conn:
            if status:
                rows = await conn.fetch(
                    """
                    SELECT * FROM batch_jobs 
                    WHERE status = $1 
                    ORDER BY created_at DESC 
                    LIMIT $2 OFFSET $3
                    """,
                    status, limit, offset
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM batch_jobs 
                    ORDER BY created_at DESC 
                    LIMIT $1 OFFSET $2
                    """,
                    limit, offset
                )
            return [dict(row) for row in rows]
    
    # ============ Job Logs ============
    
    async def add_log(
        self,
        job_id: str,
        level: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """Add a log entry for a job"""
        async with self.connection() as conn:
            await conn.execute(
                """
                INSERT INTO job_logs (job_id, level, message, details)
                VALUES ($1, $2, $3, $4)
                """,
                job_id, level, message, json.dumps(details or {})
            )
    
    async def get_job_logs(
        self,
        job_id: str,
        level: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get logs for a specific job"""
        async with self.connection() as conn:
            if level:
                rows = await conn.fetch(
                    """
                    SELECT * FROM job_logs 
                    WHERE job_id = $1 AND level = $2
                    ORDER BY created_at DESC 
                    LIMIT $3
                    """,
                    job_id, level, limit
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM job_logs 
                    WHERE job_id = $1 
                    ORDER BY created_at DESC 
                    LIMIT $2
                    """,
                    job_id, limit
                )
            return [dict(row) for row in rows]
    
    # ============ Generated Posters ============
    
    async def create_poster_record(
        self,
        job_id: str,
        user_identifier: str,
        username: Optional[str] = None,
        display_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a pending poster record"""
        async with self.connection() as conn:
            result = await conn.fetchrow(
                """
                INSERT INTO generated_posters (
                    job_id, user_identifier, username, display_name, status, metadata
                ) VALUES ($1, $2, $3, $4, 'pending', $5)
                RETURNING id
                """,
                job_id, user_identifier, username, display_name, json.dumps(metadata or {})
            )
            return str(result['id'])
    
    async def update_poster_status(
        self,
        poster_id: str,
        status: str,
        poster_url: Optional[str] = None,
        s3_key: Optional[str] = None,
        processing_time_ms: Optional[int] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Update poster generation status"""
        async with self.connection() as conn:
            update_parts = ["status = $2"]
            params = [poster_id, status]
            param_idx = 3
            
            if poster_url:
                update_parts.append(f"poster_url = ${param_idx}")
                params.append(poster_url)
                param_idx += 1
            
            if s3_key:
                update_parts.append(f"s3_key = ${param_idx}")
                params.append(s3_key)
                param_idx += 1
            
            if processing_time_ms is not None:
                update_parts.append(f"processing_time_ms = ${param_idx}")
                params.append(processing_time_ms)
                param_idx += 1
            
            if error_message:
                update_parts.append(f"error_message = ${param_idx}")
                params.append(error_message)
                param_idx += 1
            
            if metadata:
                update_parts.append(f"metadata = ${param_idx}")
                params.append(json.dumps(metadata))
                param_idx += 1
            
            query = f"UPDATE generated_posters SET {', '.join(update_parts)} WHERE id = $1::uuid"
            await conn.execute(query, *params)
    
    async def get_job_posters(self, job_id: str) -> List[Dict[str, Any]]:
        """Get all posters for a job"""
        async with self.connection() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM generated_posters 
                WHERE job_id = $1 
                ORDER BY created_at ASC
                """,
                job_id
            )
            return [dict(row) for row in rows]
    
    async def get_job_statistics(self, job_id: str) -> Dict[str, Any]:
        """Get statistics for a job"""
        async with self.connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT 
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE status = 'completed') as success,
                    COUNT(*) FILTER (WHERE status = 'failed') as failed,
                    COUNT(*) FILTER (WHERE status = 'processing') as processing,
                    COUNT(*) FILTER (WHERE status = 'pending') as pending,
                    AVG(processing_time_ms) FILTER (WHERE processing_time_ms IS NOT NULL) as avg_time_ms
                FROM generated_posters 
                WHERE job_id = $1
                """,
                job_id
            )
            return dict(row) if row else {}
    
    async def log_poster_failure(
        self,
        job_id: str,
        poster_id: Optional[str],
        user_identifier: str,
        username: str,
        failure_type: str,
        error_message: str,
        error_details: Optional[Dict[str, Any]] = None,
        html_template: Optional[str] = None
    ):
        """Log poster generation failure details"""
        async with self.connection() as conn:
            await conn.execute(
                """
                INSERT INTO poster_failure_details (
                    job_id, poster_id, user_identifier, username,
                    failure_type, error_message, error_details, html_template
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                job_id,
                poster_id if poster_id else None,
                user_identifier,
                username,
                failure_type,
                error_message,
                json.dumps(error_details or {}),
                html_template
            )

    async def log_save_failure(
        self,
        save_job_id: str,
        username: str,
        poster_url: str,
        error_message: str,
        error_type: str = "save_to_topmate_db_failed"
    ):
        """Log failure when saving poster to Topmate DB"""
        async with self.connection() as conn:
            await conn.execute(
                """
                INSERT INTO poster_failure_details (
                    job_id, user_identifier, username,
                    failure_type, error_message, error_details
                ) VALUES ($1, $2, $3, $4, $5, $6)
                """,
                save_job_id,
                username,
                username,
                error_type,
                error_message,
                json.dumps({"poster_url": poster_url, "save_stage": "topmate_db"})
            )

    async def get_job_failures(self, job_id: str) -> List[Dict[str, Any]]:
        """Get all failure details for a job"""
        async with self.connection() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM poster_failure_details
                WHERE job_id = $1
                ORDER BY created_at DESC
                """,
                job_id
            )
            return [dict(row) for row in rows]

    @property
    def is_healthy(self) -> bool:
        """Check if database is healthy"""
        return self._is_initialized and self.pool is not None


# Global singleton instance
database_service = DatabaseService()


async def get_database() -> DatabaseService:
    """Get the global database service instance"""
    return database_service
