"""
Generate Poster Router
POST /api/generate-poster - Generate poster with AI (single or carousel)
GET /api/generate-poster/{job_id}/stream - SSE stream for real-time progress

Uses 3-strategy approach:
- Strategy A: Reference-Faithful (match reference exactly)
- Strategy B: Reference-Remix (creative interpretation)
- Strategy C: AI Creative Director (content-aware design)

Now uses TaskIQ for async processing with SSE progress updates.
"""
from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse, ServerSentEvent
from typing import Optional, List, Dict, Any
from app.models.poster import GeneratePosterRequest, GeneratePosterResponse, GeneratedPoster, PosterDimensions
from app.services.topmate_client import fetch_topmate_profile
from app.services.openrouter_client import call_openrouter, call_openrouter_for_image
from app.services.prompts import (
    POSTER_SYSTEM_PROMPT,
    SINGLE_POSTER_SYSTEM_PROMPT,
    CAROUSEL_FIRST_SLIDE_SYSTEM_PROMPT,
    IMAGE_GENERATION_SYSTEM_PROMPT,
    CREATIVE_DIRECTOR_SYSTEM_PROMPT,
    FALLBACK_CREATIVE_DIRECTIVE,
    POSTER_STRATEGIES,
    CAROUSEL_STRATEGIES,
    IMAGE_GENERATION_STRATEGIES,
    build_creative_directive,
    process_mcp_data
)
from app.services.sse_manager import sse_manager
from app.tasks.poster_tasks import (
    process_ai_poster_generation_task,
    get_ai_poster_job,
    set_ai_poster_job,
    update_ai_poster_job
)
from datetime import datetime
import json
import asyncio
import uuid
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


@router.post("/generate-poster")
async def generate_poster(request: GeneratePosterRequest):
    """
    Generate poster with AI using 3-strategy approach (async with SSE)

    Returns immediately with job_id and SSE endpoint for real-time progress.
    Connect to SSE endpoint to receive progress updates and final result.

    Strategies:
    - A (reference-faithful): Match reference image exactly
    - B (reference-remix): Creative interpretation of reference
    - C (ai-creative-director): Content-aware design (no reference needed)
    """
    try:
        # Validate profile exists first (fast check before queuing)
        config = request.config
        try:
            profile = await fetch_topmate_profile(config.topmateUsername)
        except Exception as e:
            raise HTTPException(
                status_code=404,
                detail=f"Failed to fetch Topmate profile for '{config.topmateUsername}'. Please check the username."
            )
        
        # Generate job ID
        job_id = f"poster_{uuid.uuid4().hex[:12]}"
        
        # Initialize job in shared memory storage
        set_ai_poster_job(job_id, {
            "status": "queued",
            "created_at": datetime.utcnow().isoformat(),
            "result": None,
            "error": None
        })
        
        # Send initial SSE event
        await sse_manager.send_progress(job_id, 0, 3, 0, 0, None, "queued")
        await sse_manager.send_log(job_id, "INFO", "Job queued for processing")
        
        # Prepare request data for task
        request_data = {
            "config": {
                "topmateUsername": config.topmateUsername,
                "style": config.style,
                "size": config.size,
                "mode": config.mode,
                "prompt": config.prompt,
                "customDimensions": {"width": config.customDimensions.width, "height": config.customDimensions.height} if config.customDimensions else None,
            },
            "referenceImage": request.referenceImage,
            "model": request.model,
            "userMode": request.userMode,
        }
        
        # Queue task to TaskIQ
        await process_ai_poster_generation_task.kiq(
            job_id=job_id,
            request_data=request_data
        )
        
        logger.info("AI poster generation queued", job_id=job_id)
        print(f"✅ Job queued: {job_id}")
        
        # Return immediately with SSE endpoint
        return {
            "success": True,
            "job_id": job_id,
            "status": "queued",
            "sse_endpoint": f"/api/generate-poster/{job_id}/stream",
            "message": "Generation started. Connect to SSE endpoint for real-time progress."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Poster generation error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/generate-poster/{job_id}/stream")
async def stream_poster_generation(job_id: str, request: Request):
    """
    SSE endpoint for streaming AI poster generation progress
    
    Events:
    - connected: Connection established
    - progress: Generation progress (0-3 variants)
    - log: Log messages
    - job_completed: All variants generated with full result
    - job_failed: Generation failed
    - heartbeat: Keep-alive signal
    """
    # Check job exists
    job = get_ai_poster_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Create connection
    connection_id = f"poster_conn_{uuid.uuid4().hex[:8]}"
    logger.info("SSE connection for poster generation", job_id=job_id, connection_id=connection_id)
    
    connection = await sse_manager.connect(job_id, connection_id)
    
    # Send initial status
    await connection.send("status", {
        "job_id": job_id,
        "status": job["status"],
        "phase": "starting"
    })
    
    async def event_generator():
        poll_interval = 1.0  # Wait for events from Redis pub/sub
        max_wait = 180  # 3 minutes max for AI generation
        waited = 0
        
        try:
            while waited < max_wait:
                if await request.is_disconnected():
                    logger.info("SSE client disconnected", job_id=job_id)
                    break
                
                try:
                    # Wait for events from Redis pub/sub via connection queue
                    event = await asyncio.wait_for(connection.queue.get(), timeout=poll_interval)
                    
                    yield ServerSentEvent(
                        data=json.dumps(event["data"]),
                        event=event["event"]
                    )
                    
                    # Check if completed or failed
                    if event["event"] in ("job_completed", "job_failed"):
                        break
                        
                except asyncio.TimeoutError:
                    waited += poll_interval
                    
                    # Send heartbeat every 10 seconds to keep connection alive
                    if int(waited) % 10 == 0 and waited > 0:
                        yield ServerSentEvent(
                            data=json.dumps({"status": "alive", "waited": round(waited, 1)}),
                            event="heartbeat"
                        )
            
            # Timeout
            if waited >= max_wait:
                yield ServerSentEvent(
                    data=json.dumps({"job_id": job_id, "error": "Generation timeout"}),
                    event="job_failed"
                )
                
        except Exception as e:
            logger.error("SSE stream error", job_id=job_id, error=str(e))
            yield ServerSentEvent(data=json.dumps({"error": str(e)}), event="error")
        finally:
            await sse_manager.disconnect(connection_id)
    
    return EventSourceResponse(event_generator())


@router.get("/generate-poster/{job_id}/result")
async def get_poster_result(job_id: str):
    """
    Get the result of a completed poster generation job.
    Use this as fallback if SSE doesn't work.
    """
    job = get_ai_poster_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job["status"] == "completed" and job.get("result"):
        return job["result"]
    elif job["status"] == "failed":
        raise HTTPException(status_code=500, detail=job.get("error", "Generation failed"))
    else:
        return {
            "success": False,
            "status": job["status"],
            "message": "Job is still processing"
        }
