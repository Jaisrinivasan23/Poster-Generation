"""
Batch Processing Router with SSE
Handles batch poster generation with real-time progress updates
"""
import uuid
import asyncio
import json
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel, Field
from typing import List, Dict, Any

from app.services.job_manager import job_manager
from app.services.sse_manager import sse_manager
from app.services.database import database_service
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter()


# ============ Request/Response Models ============

class CreateBatchJobRequest(BaseModel):
    """Request model for creating a batch job"""
    campaignName: str = Field(..., description="Name of the campaign")
    userIdentifiers: str = Field(..., description="Comma or newline separated usernames or user_ids")
    htmlTemplate: str = Field(..., description="HTML template with placeholders")
    posterSize: str = Field(default="instagram-square", description="Poster size preset")
    model: str = Field(default="flash", description="AI model to use")
    topmateLogo: Optional[str] = Field(default=None, description="Topmate logo data URL")
    skipOverlays: bool = Field(default=False, description="Skip logo/profile overlays")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


class CreateBatchJobResponse(BaseModel):
    """Response model for batch job creation"""
    success: bool
    jobId: str
    status: str
    totalItems: int
    campaignName: str
    createdAt: str
    sseEndpoint: str


class JobStatusResponse(BaseModel):
    """Response model for job status"""
    success: bool
    job: Dict[str, Any]


class JobResultsResponse(BaseModel):
    """Response model for job results"""
    success: bool
    jobId: str
    results: List[Dict[str, Any]]
    successCount: int
    failureCount: int


class JobListResponse(BaseModel):
    """Response model for job list"""
    success: bool
    jobs: List[Dict[str, Any]]
    total: int


# ============ Endpoints ============

@router.post("/batch/jobs", response_model=CreateBatchJobResponse)
async def create_batch_job(request: CreateBatchJobRequest):
    """
    Create a new batch poster generation job
    
    Returns job ID and SSE endpoint for real-time progress tracking
    """
    try:
        logger.info("Creating batch job", campaign_name=request.campaignName)
        
        result = await job_manager.create_job(
            campaign_name=request.campaignName,
            user_identifiers=request.userIdentifiers,
            html_template=request.htmlTemplate,
            poster_size=request.posterSize,
            model=request.model,
            topmate_logo=request.topmateLogo,
            skip_overlays=request.skipOverlays,
            metadata=request.metadata
        )
        
        return CreateBatchJobResponse(
            success=True,
            jobId=result["job_id"],
            status=result["status"],
            totalItems=result["total_items"],
            campaignName=result["campaign_name"],
            createdAt=result["created_at"],
            sseEndpoint=f"/api/batch/jobs/{result['job_id']}/stream"
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to create batch job", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/batch/jobs/{job_id}/stream")
async def stream_job_progress(job_id: str, request: Request):
    """
    SSE endpoint for streaming job progress updates
    
    Connect to this endpoint to receive real-time updates:
    - progress: Processing progress updates
    - poster_completed: Individual poster completion
    - job_completed: Job finished successfully
    - job_failed: Job failed with error
    - log: Log messages
    - heartbeat: Keep-alive signal
    """
    # Verify job exists
    job = await job_manager.get_job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Create unique connection ID
    connection_id = f"conn_{uuid.uuid4().hex[:8]}"
    
    logger.info("SSE connection requested", job_id=job_id, connection_id=connection_id)
    
    # Register connection
    connection = await sse_manager.connect(job_id, connection_id)
    
    # Send initial status
    await connection.send("status", {
        "job_id": job_id,
        "status": job["status"],
        "processed": job.get("processed_items", 0),
        "total": job.get("total_items", 0),
        "success_count": job.get("success_count", 0),
        "failure_count": job.get("failure_count", 0)
    })
    
    async def event_generator():
        try:
            heartbeat_count = 0

            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info("SSE client disconnected", job_id=job_id)
                    break

                # Try to get event from queue with very long timeout (no timeout errors)
                try:
                    event = await asyncio.wait_for(connection.queue.get(), timeout=300.0)  # 5 minutes

                    # Yield the event
                    yield ServerSentEvent(
                        data=json.dumps(event["data"]),
                        event=event["event"]
                    )

                    # Check if job completed/failed
                    if event["event"] in ("job_completed", "job_failed"):
                        logger.info("Job finished, ending SSE stream", job_id=job_id, event=event["event"])
                        break

                except asyncio.TimeoutError:
                    # No events in queue, send heartbeat to keep connection alive
                    heartbeat_count += 1
                    if heartbeat_count % 6 == 0:  # Every 30 seconds (6 * 5 seconds)
                        yield ServerSentEvent(
                            data=json.dumps({"status": "alive", "timestamp": datetime.utcnow().isoformat()}),
                            event="heartbeat"
                        )

                    # Also check job status from database as backup
                    current_job = await job_manager.get_job_status(job_id)
                    if not current_job:
                        logger.warning("Job not found during SSE stream", job_id=job_id)
                        break

                    if current_job.get("status") in ("completed", "failed"):
                        # Send completion event if we missed it
                        event_type = "job_completed" if current_job.get("status") == "completed" else "job_failed"
                        completion_data = {
                            "job_id": job_id,
                            "success_count": current_job.get("success_count", 0),
                            "failure_count": current_job.get("failure_count", 0),
                            "total_time_seconds": 0,
                            "results": []
                        }
                        if event_type == "job_failed":
                            completion_data["error"] = current_job.get("error_message", "Unknown error")

                        yield ServerSentEvent(
                            data=json.dumps(completion_data),
                            event=event_type
                        )
                        logger.info("Job finished (backup check), ending SSE stream", job_id=job_id)
                        break

        except Exception as e:
            logger.error("SSE stream error", job_id=job_id, error=str(e))
            try:
                yield ServerSentEvent(
                    data=json.dumps({"error": str(e)}),
                    event="error"
                )
            except:
                pass
        finally:
            await sse_manager.disconnect(connection_id)
            logger.info("SSE connection closed", job_id=job_id, connection_id=connection_id)

    return EventSourceResponse(event_generator())


@router.get("/batch/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Get current status of a batch job"""
    job = await job_manager.get_job_status(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobStatusResponse(
        success=True,
        job=job
    )


@router.get("/batch/jobs/{job_id}/results", response_model=JobResultsResponse)
async def get_job_results(job_id: str):
    """Get results for a completed batch job"""
    job = await job_manager.get_job_status(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    results = await job_manager.get_job_results(job_id)

    success_count = sum(1 for r in results if r.get("success"))
    failure_count = len(results) - success_count

    return JobResultsResponse(
        success=True,
        jobId=job_id,
        results=results,
        successCount=success_count,
        failureCount=failure_count
    )


@router.get("/batch/jobs/{job_id}/posters-for-save")
async def get_posters_for_save(job_id: str):
    """
    Get all generated posters formatted for save-bulk-posters endpoint

    Returns poster data in the format expected by /api/save-bulk-posters:
    {
        "posters": [
            {
                "username": "johndoe",
                "posterUrl": "https://...",
                "userId": 12345  // optional, will lookup if not provided
            }
        ]
    }
    """
    job = await job_manager.get_job_status(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Get all generated posters from database
    posters = await database_service.get_job_posters(job_id)

    # Filter only successful posters and format for save endpoint
    formatted_posters = []
    missing_user_ids = []

    for poster in posters:
        if poster.get("status") == "completed" and poster.get("poster_url"):
            # Extract user_id from metadata (stored during generation)
            metadata = poster.get("metadata", {})
            if isinstance(metadata, str):
                import json
                try:
                    metadata = json.loads(metadata)
                except:
                    metadata = {}

            user_id = metadata.get("user_id")

            if user_id:
                formatted_posters.append({
                    "username": poster.get("username"),
                    "posterUrl": poster.get("poster_url"),
                    "userId": int(user_id)
                })
            else:
                missing_user_ids.append(poster.get("username"))

    # If any posters missing user_id, include warning
    warning = None
    if missing_user_ids:
        warning = f"⚠️ {len(missing_user_ids)} posters missing user_id. Please upload CSV with 'user_id' column."

    return {
        "success": True,
        "jobId": job_id,
        "campaignName": job.get("campaign_name"),
        "totalPosters": len(formatted_posters),
        "totalMissingUserId": len(missing_user_ids),
        "missingUserIdPosters": missing_user_ids[:10] if missing_user_ids else [],  # Show first 10
        "warning": warning,
        "posters": formatted_posters
    }


@router.get("/batch/jobs/{job_id}/logs")
async def get_job_logs(
    job_id: str,
    level: Optional[str] = Query(None, description="Filter by log level"),
    limit: int = Query(100, ge=1, le=500)
):
    """Get logs for a batch job"""
    job = await job_manager.get_job_status(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    logs = await database_service.get_job_logs(job_id, level=level, limit=limit)
    
    return {
        "success": True,
        "jobId": job_id,
        "logs": logs,
        "count": len(logs)
    }


@router.post("/batch/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Cancel an active batch job"""
    job = await job_manager.get_job_status(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job["status"] not in ("pending", "queued", "processing"):
        raise HTTPException(status_code=400, detail="Job cannot be cancelled")
    
    cancelled = await job_manager.cancel_job(job_id)
    
    return {
        "success": cancelled,
        "jobId": job_id,
        "message": "Job cancelled" if cancelled else "Failed to cancel job"
    }


@router.get("/batch/jobs", response_model=JobListResponse)
async def list_jobs(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """List batch jobs with optional filtering"""
    jobs = await database_service.get_jobs(status=status, limit=limit, offset=offset)
    
    # Convert datetime objects to strings
    for job in jobs:
        for key in ["created_at", "started_at", "completed_at", "updated_at"]:
            if job.get(key):
                job[key] = job[key].isoformat()
    
    return JobListResponse(
        success=True,
        jobs=jobs,
        total=len(jobs)
    )


@router.get("/batch/health")
async def batch_health_check():
    """Check health of batch processing services"""
    from app.services.redpanda_client import redpanda_client

    return {
        "success": True,
        "services": {
            "database": database_service.is_healthy,
            "redpanda": redpanda_client.is_healthy,
            "sse_connections": sse_manager.get_connection_count()
        }
    }


@router.post("/batch/log-frontend-error")
async def log_frontend_error(request: dict):
    """
    Log frontend errors to PostgreSQL database

    Request body:
    {
        "jobId": "job_xxx",
        "errorType": "sse_error",
        "errorMessage": "Connection failed",
        "errorStack": "...",
        "userAgent": "...",
        "url": "...",
        "timestamp": "2026-01-21T12:00:00"
    }
    """
    try:
        job_id = request.get("jobId", "frontend")
        error_type = request.get("errorType", "unknown")
        error_message = request.get("errorMessage", "No message")
        error_stack = request.get("errorStack")
        user_agent = request.get("userAgent")
        url = request.get("url")
        timestamp = request.get("timestamp")

        # Log to database as job log
        await database_service.add_log(
            job_id=job_id,
            level="ERROR",
            message=f"[FRONTEND ERROR] {error_type}: {error_message}",
            details={
                "error_type": error_type,
                "error_message": error_message,
                "error_stack": error_stack,
                "user_agent": user_agent,
                "url": url,
                "timestamp": timestamp,
                "source": "frontend"
            }
        )

        logger.error("Frontend error logged",
                    job_id=job_id,
                    error_type=error_type,
                    error_message=error_message)

        return {
            "success": True,
            "message": "Frontend error logged to database"
        }

    except Exception as e:
        logger.error("Failed to log frontend error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
