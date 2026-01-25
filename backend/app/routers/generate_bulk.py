"""
Generate Bulk Router
POST /api/generate-bulk - Bulk poster generation via RedPanda batch processing
GET /api/generate-bulk/{job_id}/stream - SSE stream for generation progress

All bulk generation is processed via RedPanda queue for reliability and scalability.
SSE is used for real-time progress tracking in the frontend.
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
from app.models.poster import GenerateBulkRequest, GenerateBulkResponse, BulkGenerationResult
from app.services.topmate_client import parse_user_identifiers
from app.services.job_manager import job_manager
from app.services.sse_manager import sse_manager
from app.services.database import database_service
import structlog

logger = structlog.get_logger(__name__)
router = APIRouter()

# Poster size dimensions
POSTER_SIZE_DIMENSIONS = {
    "instagram-square": {"width": 1080, "height": 1080},
    "instagram-portrait": {"width": 1080, "height": 1350},
    "instagram-story": {"width": 1080, "height": 1920},
    "linkedin-post": {"width": 1200, "height": 1200},
    "twitter-post": {"width": 1200, "height": 675},
    "facebook-post": {"width": 1200, "height": 630},
    "a4-portrait": {"width": 2480, "height": 3508}
}


@router.post("/generate-bulk", response_model=None)
async def generate_bulk(request: GenerateBulkRequest):
    """
    Bulk poster generation via RedPanda batch processing
    
    Supports 2 modes:
    1. CSV Mode: Upload CSV + HTML template → batch generate via RedPanda
    2. HTML Mode: HTML template + user identifiers → batch generate via RedPanda
    
    Returns job_id and SSE endpoint for real-time progress tracking.
    All processing is handled by RedPanda workers for reliability.
    """
    try:
        print(f"\n{'='*60}")
        print(f"🎨 [GENERATE-BULK] Received bulk generation request")
        print(f" [GENERATE-BULK] Mode: {request.bulkMethod}")
        print(f"{'='*60}\n")
        
        # CSV MODE: Convert CSV data to user identifiers for RedPanda processing
        if request.bulkMethod == "csv" and request.csvTemplate and request.csvData and request.csvColumns:
            print(f"📋 [CSV MODE] Processing {len(request.csvData)} CSV rows")
            
            # For CSV mode, we create the job with CSV data in metadata
            job_result = await job_manager.create_csv_job(
                campaign_name=f"CSV Bulk Generation",
                csv_data=request.csvData,
                csv_template=request.csvTemplate,
                csv_columns=request.csvColumns,
                poster_size=request.size,
                model=request.model,
                topmate_logo=request.topmateLogo,
                skip_overlays=request.skipOverlays,
                metadata={
                    "bulk_method": "csv",
                    "custom_width": request.customWidth,
                    "custom_height": request.customHeight
                }
            )
            
            return JSONResponse(content={
                "success": True,
                "jobId": job_result["job_id"],
                "status": job_result["status"],
                "totalItems": job_result["total_items"],
                "campaignName": job_result["campaign_name"],
                "createdAt": job_result["created_at"],
                "sseEndpoint": f"/api/batch/jobs/{job_result['job_id']}/stream",
                "message": "🔴 Job queued for RedPanda processing. Connect to SSE endpoint for live progress."
            })
        
        # HTML MODE: Use HTML template with user identifiers
        elif request.bulkMethod == "html" and request.htmlTemplate and request.userIdentifiers:
            print(f"📋 [HTML MODE] Using HTML template with user identifiers")
            
            # Create job via job_manager (goes through RedPanda)
            job_result = await job_manager.create_job(
                campaign_name=f"Bulk Generation",
                user_identifiers=request.userIdentifiers,
                html_template=request.htmlTemplate,
                poster_size=request.size,
                model=request.model,
                topmate_logo=request.topmateLogo,
                skip_overlays=request.skipOverlays,
                metadata={
                    "bulk_method": "html",
                    "custom_width": request.customWidth,
                    "custom_height": request.customHeight
                }
            )
            
            return JSONResponse(content={
                "success": True,
                "jobId": job_result["job_id"],
                "status": job_result["status"],
                "totalItems": job_result["total_items"],
                "campaignName": job_result["campaign_name"],
                "createdAt": job_result["created_at"],
                "sseEndpoint": f"/api/batch/jobs/{job_result['job_id']}/stream",
                "message": "🔴 Job queued for RedPanda processing. Connect to SSE endpoint for live progress."
            })
        
        else:
            raise HTTPException(status_code=400, detail="Invalid bulk generation request. Provide either CSV data or HTML template with user identifiers.")

    except ValueError as e:
        print(f"❌ [GENERATE-BULK] Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ [GENERATE-BULK] Failed to create job: {e}")
        logger.error("Failed to create bulk generation job", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/generate-bulk/{job_id}/stream")
async def stream_generation_progress(job_id: str, request: Request):
    """
    SSE endpoint for generation job progress.
    Proxies to the main SSE manager which handles all job types.
    """
    print(f"📡 [SSE] Client connecting to stream for job: {job_id}")
    
    async def event_generator():
        async for event in sse_manager.subscribe(job_id):
            if await request.is_disconnected():
                print(f"📡 [SSE] Client disconnected from job: {job_id}")
                break
            yield event
    
    return EventSourceResponse(event_generator())


@router.get("/generate-bulk/{job_id}/status")
async def get_generation_job_status(job_id: str):
    """Get current status of a generation job"""
    try:
        job = await database_service.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        stats = await database_service.get_job_statistics(job_id)
        
        return {
            "success": True,
            "jobId": job_id,
            "status": job.get("status"),
            "total": job.get("total_items", 0),
            "processed": job.get("processed_items", 0),
            "success_count": job.get("success_count", 0),
            "failure_count": job.get("failure_count", 0),
            "percent": round((job.get("processed_items", 0) / max(job.get("total_items", 1), 1)) * 100, 1),
            "campaignName": job.get("campaign_name"),
            "createdAt": job.get("created_at").isoformat() if job.get("created_at") else None,
            "startedAt": job.get("started_at").isoformat() if job.get("started_at") else None,
            "completedAt": job.get("completed_at").isoformat() if job.get("completed_at") else None,
            "statistics": stats
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get job status", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/generate-bulk/{job_id}/results")
async def get_generation_job_results(job_id: str):
    """Get all results (posters) for a completed job"""
    try:
        job = await database_service.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        posters = await database_service.get_job_posters(job_id)
        
        results = []
        failures = []
        
        for poster in posters:
            if poster.get("status") == "completed":
                results.append({
                    "username": poster.get("username"),
                    "userId": poster.get("user_identifier"),
                    "posterUrl": poster.get("poster_url"),
                    "imageUrl": poster.get("poster_url"),
                    "success": True
                })
            else:
                failures.append({
                    "username": poster.get("username"),
                    "userId": poster.get("user_identifier"),
                    "error": poster.get("error_message"),
                    "success": False
                })
        
        return {
            "success": True,
            "jobId": job_id,
            "status": job.get("status"),
            "results": results,
            "failures": failures,
            "successCount": len(results),
            "failureCount": len(failures)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get job results", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/generate-bulk/{job_id}")
async def cancel_generation_job(job_id: str):
    """Cancel a running generation job"""
    try:
        success = await job_manager.cancel_job(job_id)
        if success:
            return {"success": True, "message": f"Job {job_id} cancelled"}
        else:
            raise HTTPException(status_code=400, detail="Job could not be cancelled")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to cancel job", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
