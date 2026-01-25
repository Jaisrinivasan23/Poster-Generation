"""
Save Bulk Posters Router
POST /api/save-bulk-posters - Save generated posters to Topmate Django DB
GET /api/save-bulk-posters/{job_id}/stream - SSE stream for save progress
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
from app.models.poster import SaveBulkPostersRequest, SaveBulkPostersResponse, SaveResult
from app.services.topmate_client import fetch_topmate_profile
from app.services.storage_service import upload_image
from app.services.webhook_service import store_poster_to_django
from app.services.database import database_service
import asyncio
import uuid
import json
from datetime import datetime
from typing import Dict, Any, List

router = APIRouter()

# In-memory store for save jobs (for SSE progress tracking)
save_jobs: Dict[str, Dict[str, Any]] = {}


@router.post("/save-bulk-posters", response_model=None)
async def save_bulk_posters(request: SaveBulkPostersRequest):
    """
    Save bulk generated posters to Topmate Django database
    
    Returns job_id for SSE progress tracking.
    Steps for each poster:
    1. Lookup user_id from username (if not provided)
    2. Upload image to S3 (if data URL)
    3. Store to Django via webhook (Video + UserShareContent)
    """
    try:
        job_id = f"save_{uuid.uuid4().hex[:12]}"
        total_posters = len(request.posters)
        
        print(f"\n{'='*60}")
        print(f"💾 [SAVE-BULK] Starting save job: {job_id}")
        print(f" [SAVE-BULK] Total posters to save: {total_posters}")
        print(f"{'='*60}\n")
        
        # Initialize job state
        save_jobs[job_id] = {
            "status": "processing",
            "total": total_posters,
            "processed": 0,
            "success": 0,
            "failed": 0,
            "results": [],
            "failures": [],
            "logs": [],
            "created_at": datetime.now().isoformat(),
            "poster_name": request.posterName
        }
        
        # Start processing in background
        asyncio.create_task(_process_save_job(job_id, request))
        
        return JSONResponse(content={
            "success": True,
            "jobId": job_id,
            "status": "processing",
            "totalItems": total_posters,
            "sseEndpoint": f"/api/save-bulk-posters/{job_id}/stream",
            "message": "Save job started. Connect to SSE endpoint for progress updates."
        })

    except Exception as e:
        print(f"❌ [SAVE-BULK] Failed to start job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/save-bulk-posters/{job_id}/stream")
async def stream_save_progress(job_id: str):
    """SSE endpoint for save job progress"""
    
    if job_id not in save_jobs:
        raise HTTPException(status_code=404, detail="Save job not found")
    
    async def event_generator():
        last_processed = 0
        last_log_count = 0
        
        while True:
            job = save_jobs.get(job_id)
            if not job:
                yield {
                    "event": "error",
                    "data": json.dumps({"error": "Job not found"})
                }
                break
            
            # Send new logs
            current_logs = job.get("logs", [])
            if len(current_logs) > last_log_count:
                for log in current_logs[last_log_count:]:
                    yield {
                        "event": "log",
                        "data": json.dumps(log)
                    }
                last_log_count = len(current_logs)
            
            # Send progress updates
            if job["processed"] > last_processed:
                progress_data = {
                    "processed": job["processed"],
                    "total": job["total"],
                    "success": job["success"],
                    "failed": job["failed"],
                    "percent": round((job["processed"] / job["total"]) * 100, 1) if job["total"] > 0 else 0
                }
                yield {
                    "event": "progress",
                    "data": json.dumps(progress_data)
                }
                last_processed = job["processed"]
            
            # Check if completed
            if job["status"] in ("completed", "failed"):
                yield {
                    "event": "complete",
                    "data": json.dumps({
                        "status": job["status"],
                        "success": job["success"],
                        "failed": job["failed"],
                        "total": job["total"],
                        "results": job["results"],
                        "failures": job["failures"]
                    })
                }
                break
            
            await asyncio.sleep(0.5)
    
    return EventSourceResponse(event_generator())


@router.get("/save-bulk-posters/{job_id}/status")
async def get_save_job_status(job_id: str):
    """Get current status of a save job"""
    if job_id not in save_jobs:
        raise HTTPException(status_code=404, detail="Save job not found")
    
    job = save_jobs[job_id]
    return {
        "success": True,
        "jobId": job_id,
        "status": job["status"],
        "total": job["total"],
        "processed": job["processed"],
        "success_count": job["success"],
        "failure_count": job["failed"],
        "percent": round((job["processed"] / job["total"]) * 100, 1) if job["total"] > 0 else 0
    }


async def _process_single_save(poster, poster_name: str, job: Dict, add_log, save_job_id: str):
    """Process a single poster save (for parallel execution)"""
    try:
        username = poster.username or "unknown"
        poster_url = poster.posterUrl
        add_log("INFO", f"Saving poster for: {username}")

        # Check if user_id is provided (should be from CSV/database)
        user_id = None
        if poster.userId:
            user_id = int(poster.userId)
            add_log("INFO", f"Using userId: {user_id}", {"username": username})
        else:
            # No user_id provided - this shouldn't happen if CSV has user_id column
            error_msg = "No user_id provided. Please upload CSV with 'user_id' column."
            add_log("ERROR", f"Skipping {username} - {error_msg}")
            job["failed"] += 1
            job["processed"] += 1
            job["failures"].append({
                "username": username,
                "error": error_msg
            })
            # Save failure to database
            try:
                await database_service.log_save_failure(
                    save_job_id=save_job_id,
                    username=username,
                    poster_url=poster_url,
                    error_message=error_msg,
                    error_type="missing_user_id"
                )
            except Exception as db_err:
                add_log("WARNING", f"Failed to log save failure to DB: {db_err}")
            return

        # Upload image if data URL
        final_url = poster.posterUrl
        if poster.posterUrl.startswith("data:image/"):
            add_log("INFO", f"Uploading image for {username}...")
            filename = f"{username}-{int(__import__('time').time() * 1000)}.png"
            final_url = await upload_image(poster.posterUrl, filename)
            add_log("SUCCESS", f"Uploaded to S3: {final_url[:50]}...", {"username": username})

        # Store to Django via webhook
        add_log("INFO", f"Storing to Topmate DB for {username}...")
        result = await store_poster_to_django(
            poster_url=final_url,
            poster_name=poster_name,
            user_id=user_id
        )

        if result.get("success"):
            job["success"] += 1
            job["results"].append({
                "username": username,
                "userId": user_id,
                "posterUrl": final_url,
                "success": True
            })
            add_log("SUCCESS", f"Saved to Topmate DB: {username}", {"userId": user_id})
        else:
            error_msg = result.get("error", "Unknown webhook error")
            job["failed"] += 1
            job["failures"].append({
                "username": username,
                "userId": user_id,
                "error": error_msg
            })
            add_log("ERROR", f"Failed to save to Topmate DB: {error_msg}", {"username": username})
            # Save failure to database
            try:
                await database_service.log_save_failure(
                    save_job_id=save_job_id,
                    username=username,
                    poster_url=final_url,
                    error_message=error_msg,
                    error_type="webhook_failed"
                )
            except Exception as db_err:
                add_log("WARNING", f"Failed to log save failure to DB: {db_err}")

        job["processed"] += 1

    except Exception as e:
        username = poster.username or "unknown"
        error_msg = str(e)
        add_log("ERROR", f"Failed to process {username}: {error_msg}")
        job["failed"] += 1
        job["processed"] += 1
        job["failures"].append({
            "username": username,
            "error": error_msg
        })
        # Save failure to database
        try:
            await database_service.log_save_failure(
                save_job_id=save_job_id,
                username=username,
                poster_url=poster.posterUrl,
                error_message=error_msg,
                error_type="unexpected_error"
            )
        except Exception as db_err:
            add_log("WARNING", f"Failed to log save failure to DB: {db_err}")


async def _process_save_job(job_id: str, request: SaveBulkPostersRequest):
    """Background task to process save job"""
    job = save_jobs[job_id]

    def add_log(level: str, message: str, details: Dict = None):
        log_entry = {
            "level": level,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "details": details or {}
        }
        job["logs"].append(log_entry)
        emoji = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARNING": "⚠️"}.get(level, "📝")
        print(f"{emoji} [SAVE-JOB {job_id}] {message}")
    
    try:
        # Process in PARALLEL batches (fast since user_id is from CSV/database, no API lookups!)
        BATCH_SIZE = 10
        DELAY_BETWEEN_BATCHES = 2  # seconds

        posters = request.posters
        total_batches = (len(posters) + BATCH_SIZE - 1) // BATCH_SIZE

        add_log("INFO", f"Starting PARALLEL processing: {len(posters)} posters in {total_batches} batches")

        for batch_idx in range(0, len(posters), BATCH_SIZE):
            batch = posters[batch_idx:batch_idx + BATCH_SIZE]
            batch_num = batch_idx // BATCH_SIZE + 1

            add_log("INFO", f"[Batch {batch_num}/{total_batches}] Processing {len(batch)} posters in PARALLEL")

            # Create tasks for parallel processing
            tasks = []
            for poster in batch:
                task = _process_single_save(poster, request.posterName, job, add_log, job_id)
                tasks.append(task)

            # Execute batch in parallel
            await asyncio.gather(*tasks, return_exceptions=True)

            # Small delay between batches to avoid overwhelming Django
            if batch_idx + BATCH_SIZE < len(posters):
                add_log("INFO", f"Batch {batch_num} complete. Waiting {DELAY_BETWEEN_BATCHES}s...")
                await asyncio.sleep(DELAY_BETWEEN_BATCHES)
        
        # Mark job as completed
        job["status"] = "completed"
        add_log("SUCCESS", f"Save job completed: {job['success']} success, {job['failed']} failed")
        
        print(f"\n{'='*60}")
        print(f"✅ [SAVE-BULK] Job {job_id} completed!")
        print(f" Success: {job['success']}/{job['total']}")
        print(f"❌ Failed: {job['failed']}/{job['total']}")
        print(f"{'='*60}\n")
        
    except Exception as e:
        job["status"] = "failed"
        add_log("ERROR", f"Job failed with error: {str(e)}")
        print(f"❌ [SAVE-BULK] Job {job_id} failed: {e}")


# Legacy endpoint for backward compatibility (synchronous)
@router.post("/save-bulk-posters-sync", response_model=SaveBulkPostersResponse)
async def save_bulk_posters_sync(request: SaveBulkPostersRequest):
    """
    Legacy synchronous save (no SSE, waits for completion)
    """
    try:
        print(f"💾 [SAVE-BULK-SYNC] Saving {len(request.posters)} posters...")

        results = []
        BATCH_SIZE = 10
        DELAY_BETWEEN_BATCHES = 5
        DELAY_BETWEEN_REQUESTS = 2

        for i in range(0, len(request.posters), BATCH_SIZE):
            batch = request.posters[i:i+BATCH_SIZE]
            print(f"📦 [SAVE-BULK] Batch {i//BATCH_SIZE + 1}/{(len(request.posters) + BATCH_SIZE - 1)//BATCH_SIZE}")

            for poster in batch:
                try:
                    user_id = None
                    if poster.userId:
                        user_id = int(poster.userId)
                    else:
                        MAX_RETRIES = 5
                        for retry in range(MAX_RETRIES):
                            try:
                                profile = await fetch_topmate_profile(poster.username)
                                if profile and profile.user_id:
                                    user_id = int(profile.user_id)
                                    break
                            except Exception as e:
                                if "429" in str(e):
                                    await asyncio.sleep(min(30, 5 * (2 ** retry)))
                                else:
                                    break
                        
                        if not user_id:
                            results.append(SaveResult(success=False, error="Failed to lookup user_id"))
                            continue
                        await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

                    final_url = poster.posterUrl
                    if poster.posterUrl.startswith("data:image/"):
                        filename = f"{poster.username}-{int(__import__('time').time() * 1000)}.png"
                        final_url = await upload_image(poster.posterUrl, filename)

                    result = await store_poster_to_django(
                        poster_url=final_url,
                        poster_name=request.posterName,
                        user_id=user_id
                    )
                    results.append(SaveResult(
                        success=result["success"],
                        userId=user_id,
                        posterUrl=final_url,
                        error=result.get("error")
                    ))
                except Exception as e:
                    results.append(SaveResult(success=False, error=str(e)))

            if i + BATCH_SIZE < len(request.posters):
                await asyncio.sleep(DELAY_BETWEEN_BATCHES)

        success_count = sum(1 for r in results if r.success)
        failure_count = len(results) - success_count
        
        return SaveBulkPostersResponse(
            success=True,
            results=results,
            successCount=success_count,
            failureCount=failure_count
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
