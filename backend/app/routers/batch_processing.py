"""
Batch Processing Router with SSE
Handles batch poster generation with real-time progress updates
"""
import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
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
            async for event in sse_manager.event_generator(connection):
                # Check if client disconnected
                if await request.is_disconnected():
                    break
                yield event
        except Exception as e:
            logger.error("SSE stream error", job_id=job_id, error=str(e))
        finally:
            await sse_manager.disconnect(connection_id)
    
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
