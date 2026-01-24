"""
Job Manager Service
Orchestrates batch poster generation jobs with TaskIQ, RedPanda and PostgreSQL
"""
import asyncio
import uuid
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
import structlog

from app.services.database import database_service
from app.services.redpanda_client import redpanda_client, TOPIC_POSTER_REQUESTS
from app.services.sse_manager import sse_manager
from app.services.topmate_client import fetch_topmate_profile, fetch_profile_by_user_id, parse_user_identifiers
from app.services.html_to_image import convert_html_to_png
from app.services.image_processor import replace_placeholders, overlay_logo_and_profile
from app.services.storage_service import upload_image
from app.services.openrouter_client import fetch_image_as_data_url
from app.config import settings

logger = structlog.get_logger(__name__)

# Poster dimensions
POSTER_SIZE_DIMENSIONS = {
    "instagram-square": {"width": 1080, "height": 1080},
    "instagram-portrait": {"width": 1080, "height": 1350},
    "instagram-story": {"width": 1080, "height": 1920},
    "linkedin-post": {"width": 1200, "height": 1200},
    "twitter-post": {"width": 1200, "height": 675},
    "facebook-post": {"width": 1200, "height": 630},
    "a4-portrait": {"width": 2480, "height": 3508}
}


class JobManager:
    """
    Manages the lifecycle of batch poster generation jobs
    """
    
    def __init__(self):
        self._active_jobs: Dict[str, asyncio.Task] = {}
        self._is_running = False
        self._worker_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the job manager and consumer"""
        if self._is_running:
            return
        
        self._is_running = True
        logger.info("Job manager started")
        
        # Start message consumer
        if redpanda_client.is_healthy:
            self._worker_task = await redpanda_client.start_consumer(
                topics=[TOPIC_POSTER_REQUESTS],
                group_id="poster-generation-workers",
                handler=self._handle_job_message
            )
            logger.info("Job consumer started")
    
    async def stop(self):
        """Stop the job manager"""
        self._is_running = False
        
        # Cancel active jobs
        for job_id, task in self._active_jobs.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._active_jobs.clear()
        logger.info("Job manager stopped")
    
    async def _handle_job_message(self, message: Dict[str, Any]):
        """Handle incoming job message from RedPanda"""
        job_id = message.get("job_id")
        job_type = message.get("type") or message.get("job_type", "html")  # Support both 'type' and 'job_type'
        print(f"🔴 [REDPANDA] Received job message: {job_id} (type: {job_type})")
        if not job_id:
            logger.error("Received message without job_id")
            return

        logger.info("Processing job from queue", job_id=job_id, job_type=job_type)

        # Start processing in background based on job type
        if job_type == "csv":
            task = asyncio.create_task(self._process_csv_job(message))
        elif job_type == "template_poster":
            task = asyncio.create_task(self._process_template_poster(message))
        else:
            task = asyncio.create_task(self._process_job(message))
        self._active_jobs[job_id] = task

        try:
            await task
        finally:
            self._active_jobs.pop(job_id, None)
    
    async def create_job(
        self,
        campaign_name: str,
        user_identifiers: str,
        html_template: str,
        poster_size: str = "instagram-square",
        model: str = "flash",
        topmate_logo: Optional[str] = None,
        skip_overlays: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new batch job and queue it for processing

        Returns job details immediately for SSE tracking
        """
        import time as time_module
        start_time = time_module.time()
        job_id = f"job_{uuid.uuid4().hex[:12]}"

        print(f"🚀 [JOB {job_id}] Creating job with campaign: {campaign_name} (t=0.000s)")
        
        # Parse identifiers
        usernames, user_ids = parse_user_identifiers(user_identifiers)
        total_items = len(usernames) + len(user_ids)

        elapsed = time_module.time() - start_time
        print(f"📋 [JOB {job_id}] Parsed {len(usernames)} usernames, {len(user_ids)} user IDs (total: {total_items}) (t={elapsed:.3f}s)")

        if total_items == 0:
            raise ValueError("No valid user identifiers provided")

        # Get dimensions
        dimensions = POSTER_SIZE_DIMENSIONS.get(poster_size, POSTER_SIZE_DIMENSIONS["instagram-square"])

        # Create job in database
        await database_service.create_batch_job(
            job_id=job_id,
            campaign_name=campaign_name,
            total_items=total_items,
            template_html=html_template,
            poster_size=poster_size,
            model=model,
            user_identifiers=user_identifiers,
            metadata={
                "skip_overlays": skip_overlays,
                "topmate_logo": topmate_logo,
                "dimensions": dimensions,
                **(metadata or {})
            }
        )

        elapsed = time_module.time() - start_time
        print(f"💾 [JOB {job_id}] Database job created (t={elapsed:.3f}s)")

        # Log job creation
        await database_service.add_log(
            job_id=job_id,
            level="INFO",
            message=f"Job created with {total_items} users",
            details={"campaign_name": campaign_name, "poster_size": poster_size}
        )
        
        # Queue to TaskIQ for async processing
        job_data = {
            "job_id": job_id,
            "job_type": "html",
            "campaign_name": campaign_name,
            "usernames": usernames,
            "user_ids": user_ids,
            "html_template": html_template,
            "poster_size": poster_size,
            "model": model,
            "dimensions": dimensions,
            "topmate_logo": topmate_logo,
            "skip_overlays": skip_overlays,
            "metadata": metadata or {}
        }

        # Import here to avoid circular import
        from app.tasks.poster_tasks import process_batch_job_task

        # Queue task to TaskIQ
        task = await process_batch_job_task.kiq(
            job_id=job_id,
            job_type="html",
            job_data=job_data
        )

        elapsed = time_module.time() - start_time
        print(f"🔵 [JOB {job_id}] TaskIQ job queued (task_id: {task.task_id}) (t={elapsed:.3f}s)")

        await database_service.update_job_status(job_id, "queued")
        await database_service.add_log(
            job_id=job_id,
            level="INFO",
            message=f"HTML job queued for TaskIQ processing (task_id: {task.task_id})"
        )

        elapsed = time_module.time() - start_time
        print(f"✅ [JOB {job_id}] Job creation complete, ready for processing (t={elapsed:.3f}s)")

        return {
            "job_id": job_id,
            "task_id": str(task.task_id),
            "status": "queued",
            "total_items": total_items,
            "campaign_name": campaign_name,
            "created_at": datetime.utcnow().isoformat()
        }
    
    async def _process_html_job_with_redpanda(self, job_data: Dict[str, Any]):
        """Process a batch job"""
        job_id = job_data["job_id"]
        start_time = time.time()

        print(f"")
        print(f"{'='*60}")
        print(f"⚡ [WORKER {job_id}] TaskIQ worker picked up job (t=0.000s)")
        print(f"🔄 [PROCESS] Starting job processing: {job_id}")
        print(f"{'='*60}")
        
        try:
            await database_service.update_job_status(job_id, "processing")

            usernames = job_data.get("usernames", [])
            user_ids = job_data.get("user_ids", [])
            html_template = job_data.get("html_template", "")
            dimensions = job_data.get("dimensions", {"width": 1080, "height": 1080})
            topmate_logo = job_data.get("topmate_logo")
            skip_overlays = job_data.get("skip_overlays", False)

            total_items = len(usernames) + len(user_ids)
            print(f"📋 [PROCESS] Job {job_id}: {total_items} items to process")
            processed = 0
            success_count = 0
            failure_count = 0
            results = []

            # Send initial progress immediately (0/total) so frontend shows it started
            await sse_manager.send_progress(job_id, 0, total_items, 0, 0, None, "starting")
            await sse_manager.send_log(job_id, "INFO", f"Job processing started - {total_items} posters to generate")
            
            # Fetch all profiles first
            profiles = []
            
            # Fetch username profiles
            for username in usernames:
                try:
                    await sse_manager.send_log(job_id, "DEBUG", f"Fetching profile: {username}")
                    profile = await fetch_topmate_profile(username)
                    profiles.append({"type": "username", "identifier": username, "profile": profile})
                except Exception as e:
                    logger.error("Failed to fetch profile", username=username, error=str(e))
                    await sse_manager.send_log(job_id, "WARNING", f"Failed to fetch {username}: {str(e)}")
                    failure_count += 1
                    processed += 1
                    results.append({
                        "username": username,
                        "success": False,
                        "error": str(e)
                    })
                    await sse_manager.send_progress(job_id, processed, total_items, success_count, failure_count, username)
            
            # Fetch user_id profiles
            for user_id in user_ids:
                try:
                    await sse_manager.send_log(job_id, "DEBUG", f"Fetching profile for user_id: {user_id}")
                    profile = await fetch_profile_by_user_id(user_id)
                    profiles.append({"type": "user_id", "identifier": user_id, "profile": profile})
                except Exception as e:
                    logger.error("Failed to fetch profile", user_id=user_id, error=str(e))
                    await sse_manager.send_log(job_id, "WARNING", f"Failed to fetch user {user_id}: {str(e)}")
                    failure_count += 1
                    processed += 1
                    results.append({
                        "user_id": user_id,
                        "success": False,
                        "error": str(e)
                    })
                    await sse_manager.send_progress(job_id, processed, total_items, success_count, failure_count, str(user_id))
            
            await sse_manager.send_log(job_id, "INFO", f"Fetched {len(profiles)} profiles, generating posters...")
            print(f"✅ [PROCESS] Fetched {len(profiles)} profiles successfully")
            
            # Process posters in batches of 10 (parallel processing)
            BATCH_SIZE = settings.batch_size  # 10 parallel jobs
            total_batches = (len(profiles) + BATCH_SIZE - 1) // BATCH_SIZE
            print(f"📦 [PROCESS] Processing {len(profiles)} posters in {total_batches} batches (batch size: {BATCH_SIZE})")
            
            for i in range(0, len(profiles), BATCH_SIZE):
                batch = profiles[i:i + BATCH_SIZE]
                batch_num = i//BATCH_SIZE + 1
                
                print(f"🔄 [BATCH {batch_num}/{total_batches}] Processing {len(batch)} posters...")
                await sse_manager.send_log(job_id, "INFO", f"Processing batch {batch_num}/{total_batches}")
                
                # Create tasks for batch processing
                tasks = []
                for item in batch:
                    task = self._generate_single_poster(
                        job_id=job_id,
                        profile=item["profile"],
                        identifier=item["identifier"],
                        html_template=html_template,
                        dimensions=dimensions,
                        topmate_logo=topmate_logo,
                        skip_overlays=skip_overlays
                    )
                    tasks.append(task)
                
                # Execute batch
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for idx, result in enumerate(batch_results):
                    processed += 1
                    item = batch[idx]
                    identifier = item["identifier"]
                    
                    if isinstance(result, Exception):
                        failure_count += 1
                        error_msg = str(result)
                        print(f"❌ [POSTER] Failed: {identifier} - {error_msg[:50]}...")

                        # Determine failure type
                        failure_type = "unknown"
                        if "Timeout" in error_msg:
                            failure_type = "timeout"
                        elif "HTML to PNG" in error_msg:
                            failure_type = "html_conversion"
                        elif "S3" in error_msg or "upload" in error_msg.lower():
                            failure_type = "upload"
                        elif "profile" in error_msg.lower():
                            failure_type = "profile_fetch"

                        # Log failure details
                        await database_service.log_poster_failure(
                            job_id=job_id,
                            poster_id=None,
                            user_identifier=identifier,
                            username=identifier,
                            failure_type=failure_type,
                            error_message=error_msg,
                            error_details={"profile": item.get("profile", {})}
                        )

                        results.append({
                            "username": identifier,
                            "success": False,
                            "error": error_msg
                        })
                        await sse_manager.send_poster_completed(job_id, identifier, "", False, error_msg)
                    else:
                        success_count += 1
                        print(f"✅ [POSTER] Success: {identifier} ({processed}/{total_items})")
                        results.append(result)
                        await sse_manager.send_poster_completed(job_id, identifier, result.get("posterUrl", ""), True)

                    # Send progress update for EACH poster
                    await sse_manager.send_progress(job_id, processed, total_items, success_count, failure_count, identifier)

                    # Update database for EACH poster (so progress is real-time)
                    await database_service.update_job_status(
                        job_id=job_id,
                        status="processing",
                        processed_items=processed,
                        success_count=success_count,
                        failure_count=failure_count
                    )
                
                # Brief delay between batches
                await asyncio.sleep(0.5)
            
            # Job completed
            elapsed_time = time.time() - start_time
            
            print(f"")
            print(f"{'='*60}")
            print(f"🎉 [COMPLETE] Job {job_id} finished!")
            print(f"   ✅ Success: {success_count}")
            print(f"   ❌ Failed: {failure_count}")
            print(f"   ⏱️ Time: {round(elapsed_time, 2)}s")
            print(f"{'='*60}")
            print(f"")
            
            await database_service.update_job_status(
                job_id=job_id,
                status="completed",
                processed_items=processed,
                success_count=success_count,
                failure_count=failure_count
            )
            
            await database_service.add_log(
                job_id=job_id,
                level="INFO",
                message=f"Job completed: {success_count} success, {failure_count} failures",
                details={"elapsed_time_seconds": round(elapsed_time, 2)}
            )
            
            await sse_manager.send_job_completed(job_id, success_count, failure_count, elapsed_time, results)
            
            # Publish result to RedPanda
            await redpanda_client.publish_result(job_id, {
                "success_count": success_count,
                "failure_count": failure_count,
                "elapsed_time": elapsed_time,
                "results": results
            })
            print(f"🔴 [REDPANDA] Published job result to results topic")
            
            logger.info("Job completed", 
                       job_id=job_id, 
                       success=success_count, 
                       failed=failure_count,
                       elapsed=round(elapsed_time, 2))
            
        except Exception as e:
            logger.error("Job failed", job_id=job_id, error=str(e))
            print(f"")
            print(f"{'='*60}")
            print(f"💥 [ERROR] Job {job_id} FAILED!")
            print(f"   Error: {str(e)}")
            print(f"{'='*60}")
            print(f"")
            
            await database_service.update_job_status(
                job_id=job_id,
                status="failed",
                error_message=str(e)
            )
            
            await database_service.add_log(
                job_id=job_id,
                level="ERROR",
                message=f"Job failed: {str(e)}"
            )
            
            await sse_manager.send_job_failed(job_id, str(e))
            
            # Publish error to RedPanda
            await redpanda_client.publish_error(job_id, {
                "error": str(e)
            })
    
    async def _generate_single_poster(
        self,
        job_id: str,
        profile: Dict[str, Any],
        identifier: str,
        html_template: str,
        dimensions: Dict[str, int],
        topmate_logo: Optional[str],
        skip_overlays: bool
    ) -> Dict[str, Any]:
        """Generate a single poster for a profile"""
        start_time = time.time()
        
        try:
            username = profile.get("username", identifier)
            
            # Create poster record in database with user_id in metadata
            metadata = {}
            if profile.get("user_id"):
                metadata["user_id"] = profile.get("user_id")
            
            poster_id = await database_service.create_poster_record(
                job_id=job_id,
                user_identifier=identifier,
                username=username,
                display_name=profile.get("display_name"),
                metadata=metadata
            )
            
            # Replace placeholders in HTML
            personalized_html = replace_placeholders(html_template, profile)
            
            # Convert HTML to PNG
            image_bytes = await convert_html_to_png(
                html=personalized_html,
                dimensions=dimensions
            )
            
            if not image_bytes:
                raise Exception("Failed to convert HTML to image")
            
            # Apply overlays if needed
            if not skip_overlays:
                profile_image_url = profile.get("profile_image")
                if profile_image_url:
                    profile_image_data = await fetch_image_as_data_url(profile_image_url)
                else:
                    profile_image_data = None
                
                if topmate_logo or profile_image_data:
                    image_bytes = await overlay_logo_and_profile(
                        base_image_bytes=image_bytes,
                        topmate_logo=topmate_logo,
                        profile_image=profile_image_data
                    )
            
            # Upload to S3
            s3_result = await upload_image(
                image_bytes=image_bytes,
                filename=f"{job_id}/{username}_{int(time.time())}.png"
            )
            
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Update poster record
            await database_service.update_poster_status(
                poster_id=poster_id,
                status="completed",
                poster_url=s3_result.get("url"),
                s3_key=s3_result.get("key"),
                processing_time_ms=processing_time_ms
            )
            
            return {
                "username": username,
                "success": True,
                "posterUrl": s3_result.get("url"),
                "s3Key": s3_result.get("key"),
                "processingTimeMs": processing_time_ms
            }
            
        except Exception as e:
            logger.error("Failed to generate poster", 
                        job_id=job_id, 
                        identifier=identifier, 
                        error=str(e))
            raise
    
    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of a job"""
        job = await database_service.get_job(job_id)
        if not job:
            return None
        
        stats = await database_service.get_job_statistics(job_id)
        
        return {
            "job_id": job_id,
            "status": job["status"],
            "campaign_name": job.get("campaign_name"),
            "total_items": job.get("total_items", 0),
            "processed_items": job.get("processed_items", 0),
            "success_count": job.get("success_count", 0),
            "failure_count": job.get("failure_count", 0),
            "percent_complete": round((job.get("processed_items", 0) / job.get("total_items", 1)) * 100, 1),
            "created_at": job.get("created_at").isoformat() if job.get("created_at") else None,
            "started_at": job.get("started_at").isoformat() if job.get("started_at") else None,
            "completed_at": job.get("completed_at").isoformat() if job.get("completed_at") else None,
            "error_message": job.get("error_message"),
            "statistics": stats
        }
    
    async def get_job_results(self, job_id: str) -> List[Dict[str, Any]]:
        """Get results for a completed job"""
        posters = await database_service.get_job_posters(job_id)
        return [
            {
                "username": p.get("username"),
                "display_name": p.get("display_name"),
                "poster_url": p.get("poster_url"),
                "success": p.get("status") == "completed",
                "error": p.get("error_message"),
                "processing_time_ms": p.get("processing_time_ms")
            }
            for p in posters
        ]
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel an active job"""
        if job_id in self._active_jobs:
            self._active_jobs[job_id].cancel()
            await database_service.update_job_status(job_id, "cancelled")
            await sse_manager.send_job_failed(job_id, "Job cancelled by user")
            return True
        return False
    
    async def create_csv_job(
        self,
        campaign_name: str,
        csv_data: list,
        csv_template: str,
        csv_columns: list,
        poster_size: str = "instagram-square",
        model: str = "flash",
        topmate_logo: Optional[str] = None,
        skip_overlays: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a CSV-based batch job and queue it for RedPanda processing
        
        CSV data is processed differently - we generate posters from CSV rows
        without fetching Topmate profiles
        """
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        total_items = len(csv_data)
        
        print(f"🚀 [JOB] Creating CSV job {job_id} with {total_items} rows")
        
        if total_items == 0:
            raise ValueError("No CSV data provided")
        
        dimensions = POSTER_SIZE_DIMENSIONS.get(poster_size, POSTER_SIZE_DIMENSIONS["instagram-square"])
        
        # Create job in database
        await database_service.create_batch_job(
            job_id=job_id,
            campaign_name=campaign_name,
            total_items=total_items,
            template_html=csv_template,
            poster_size=poster_size,
            model=model,
            metadata={
                "csv_columns": csv_columns,
                "skip_overlays": skip_overlays,
                "topmate_logo": topmate_logo,
                "dimensions": dimensions,
                "bulk_method": "csv",
                **(metadata or {})
            }
        )
        
        await database_service.add_log(
            job_id=job_id,
            level="INFO",
            message=f"CSV job created with {total_items} rows",
            details={"campaign_name": campaign_name, "poster_size": poster_size}
        )
        
        # Queue to TaskIQ for async processing
        job_data = {
            "job_id": job_id,
            "job_type": "csv",
            "csv_data": csv_data,
            "csv_template": csv_template,
            "csv_columns": csv_columns,
            "poster_size": poster_size,
            "model": model,
            "dimensions": dimensions,
            "topmate_logo": topmate_logo,
            "skip_overlays": skip_overlays,
            "metadata": metadata or {}
        }

        # Import here to avoid circular import
        from app.tasks.poster_tasks import process_batch_job_task

        # Queue task to TaskIQ
        task = await process_batch_job_task.kiq(
            job_id=job_id,
            job_type="csv",
            job_data=job_data
        )

        print(f"🔵 [TASKIQ] CSV job queued: {job_id} (task_id: {task.task_id})")

        await database_service.update_job_status(job_id, "queued")
        await database_service.add_log(
            job_id=job_id,
            level="INFO",
            message=f"CSV job queued for TaskIQ processing (task_id: {task.task_id})"
        )

        return {
            "job_id": job_id,
            "task_id": str(task.task_id),
            "status": "queued",
            "total_items": total_items,
            "campaign_name": campaign_name,
            "created_at": datetime.utcnow().isoformat()
        }
    
    async def _process_csv_job_with_redpanda(self, job_data: Dict[str, Any]):
        """Process a CSV-based batch job"""
        job_id = job_data["job_id"]
        start_time = time.time()

        print(f"")
        print(f"{'='*60}")
        print(f"⚡ [WORKER {job_id}] TaskIQ worker picked up CSV job (t=0.000s)")
        print(f"🔄 [PROCESS] Starting CSV job processing: {job_id}")
        print(f"{'='*60}")

        try:
            await database_service.update_job_status(job_id, "processing")
            elapsed = time.time() - start_time
            print(f"💾 [WORKER {job_id}] Status updated to 'processing' (t={elapsed:.3f}s)")

            csv_data = job_data.get("csv_data", [])
            csv_template = job_data.get("csv_template", "")
            csv_columns = job_data.get("csv_columns", [])
            dimensions = job_data.get("dimensions", {"width": 1080, "height": 1080})
            topmate_logo = job_data.get("topmate_logo")
            skip_overlays = job_data.get("skip_overlays", False)

            total_items = len(csv_data)
            elapsed = time.time() - start_time
            print(f"📋 [WORKER {job_id}] Parsed job data: {total_items} CSV rows to process (t={elapsed:.3f}s)")
            processed = 0
            success_count = 0
            failure_count = 0
            results = []

            # Send initial progress immediately (0/total) so frontend shows it started
            await sse_manager.send_progress(job_id, 0, total_items, 0, 0, None, "starting")
            elapsed = time.time() - start_time
            print(f"📡 [WORKER {job_id}] Initial SSE progress sent to frontend (t={elapsed:.3f}s)")
            await sse_manager.send_log(job_id, "INFO", f"CSV job processing started - {total_items} posters to generate")
            
            # Process in batches of 10 (parallel processing with RedPanda)
            BATCH_SIZE = settings.batch_size  # 10 parallel jobs
            total_batches = (len(csv_data) + BATCH_SIZE - 1) // BATCH_SIZE
            print(f"📦 [PROCESS] Processing {len(csv_data)} rows in {total_batches} batches (batch size: {BATCH_SIZE})")
            
            for i in range(0, len(csv_data), BATCH_SIZE):
                batch = csv_data[i:i + BATCH_SIZE]
                batch_num = i // BATCH_SIZE + 1

                print(f"🔄 [BATCH {batch_num}/{total_batches}] Processing {len(batch)} rows in parallel...")
                await sse_manager.send_log(job_id, "INFO", f"Processing batch {batch_num}/{total_batches}")

                # Create tasks for PARALLEL batch processing
                tasks = []
                for row in batch:
                    task = self._generate_csv_poster(
                        job_id=job_id,
                        row=row,
                        csv_template=csv_template,
                        csv_columns=csv_columns,
                        dimensions=dimensions,
                        topmate_logo=topmate_logo,
                        skip_overlays=skip_overlays
                    )
                    tasks.append(task)

                # Execute batch in parallel using asyncio.gather
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)

                # Process results
                for idx, result in enumerate(batch_results):
                    processed += 1
                    row = batch[idx]
                    username = row.get("username") or row.get("Username") or f"row_{processed}"

                    if isinstance(result, Exception):
                        failure_count += 1
                        error_msg = str(result)
                        print(f"❌ [POSTER] Failed: {username} - {error_msg[:50]}...")

                        # Determine failure type
                        failure_type = "unknown"
                        if "Timeout" in error_msg:
                            failure_type = "timeout"
                        elif "HTML to PNG" in error_msg:
                            failure_type = "html_conversion"
                        elif "S3" in error_msg or "upload" in error_msg.lower():
                            failure_type = "upload"

                        # Log failure details to database
                        await database_service.log_poster_failure(
                            job_id=job_id,
                            poster_id=None,
                            user_identifier=username,
                            username=username,
                            failure_type=failure_type,
                            error_message=error_msg,
                            error_details={"row": row},
                            html_template=csv_template
                        )

                        results.append({"username": username, "success": False, "error": error_msg})
                        await sse_manager.send_poster_completed(job_id, username, "", False, error_msg)
                    else:
                        success_count += 1
                        print(f"✅ [POSTER] Success: {username} ({processed}/{total_items})")
                        results.append(result)
                        await sse_manager.send_poster_completed(job_id, username, result.get("posterUrl", ""), True)

                    # Send progress update for EACH poster
                    await sse_manager.send_progress(job_id, processed, total_items, success_count, failure_count, username)

                    # Update database for EACH poster (so progress is real-time)
                    await database_service.update_job_status(
                        job_id=job_id,
                        status="processing",
                        processed_items=processed,
                        success_count=success_count,
                        failure_count=failure_count
                    )

                # Brief delay between batches
                await asyncio.sleep(0.5)
            
            elapsed_time = time.time() - start_time
            
            print(f"")
            print(f"{'='*60}")
            print(f"🎉 [COMPLETE] CSV Job {job_id} finished!")
            print(f"   ✅ Success: {success_count}")
            print(f"   ❌ Failed: {failure_count}")
            print(f"   ⏱️ Time: {round(elapsed_time, 2)}s")
            print(f"{'='*60}")
            
            await database_service.update_job_status(
                job_id=job_id,
                status="completed",
                processed_items=processed,
                success_count=success_count,
                failure_count=failure_count
            )
            
            await database_service.add_log(
                job_id=job_id,
                level="INFO",
                message=f"CSV job completed: {success_count} success, {failure_count} failures",
                details={"elapsed_time_seconds": round(elapsed_time, 2)}
            )
            
            await sse_manager.send_job_completed(job_id, success_count, failure_count, elapsed_time, results)
            
        except Exception as e:
            logger.error("CSV job failed", job_id=job_id, error=str(e))
            print(f"💥 [ERROR] CSV Job {job_id} FAILED: {str(e)}")
            
            await database_service.update_job_status(
                job_id=job_id,
                status="failed",
                error_message=str(e)
            )
            await sse_manager.send_job_failed(job_id, str(e))
    
    async def _generate_csv_poster(
        self,
        job_id: str,
        row: Dict[str, Any],
        csv_template: str,
        csv_columns: list,
        dimensions: Dict[str, int],
        topmate_logo: Optional[str],
        skip_overlays: bool
    ) -> Dict[str, Any]:
        """Generate a single poster from CSV row data"""
        start_time = time.time()
        username = row.get("username") or row.get("Username") or "unknown"

        # Extract user_id from CSV (case-insensitive, whitespace-tolerant)
        user_id = None
        for key, value in row.items():
            normalized_key = key.strip().lower().replace(" ", "")
            if normalized_key in ["user_id", "userid", "id"]:
                user_id = value
                break

        # Clean and validate user_id
        if user_id:
            # Remove whitespace and convert to string first
            user_id_str = str(user_id).strip()
            # Check if it's not empty and not just "None"
            if user_id_str and user_id_str.lower() != "none":
                try:
                    user_id = int(float(user_id_str))  # Handle both "123" and "123.0"
                except (ValueError, TypeError):
                    logger.warning(f"Invalid user_id format: {user_id_str} for user {username}")
                    user_id = None
            else:
                user_id = None

        # If no user_id in CSV, fetch from Topmate API
        topmate_profile = None
        if not user_id:
            print(f"🔍 [CSV-POSTER {username}] No user_id in CSV - fetching from Topmate API...")
            try:
                from app.services.topmate_client import fetch_topmate_profile
                topmate_profile = await fetch_topmate_profile(username)
                if topmate_profile:
                    user_id = topmate_profile.user_id
                    print(f"✅ [CSV-POSTER {username}] Fetched from Topmate API: user_id={user_id}")
                else:
                    print(f"⚠️ [CSV-POSTER {username}] Profile not found on Topmate")
            except Exception as e:
                print(f"❌ [CSV-POSTER {username}] Failed to fetch from Topmate API: {e}")

        # Create metadata with user_id and profile data
        metadata = {}
        if user_id:
            metadata["user_id"] = user_id
        if topmate_profile:
            # Store full profile data for later use
            metadata["display_name"] = topmate_profile.display_name
            metadata["profile_pic"] = topmate_profile.profile_pic
            metadata["bio"] = topmate_profile.bio
            metadata["fetched_from_api"] = True

        # Debug logging
        if user_id:
            print(f"✅ [CSV-POSTER {username}] user_id: {user_id} (from {'CSV' if not topmate_profile else 'Topmate API'})")
        else:
            print(f"⚠️ [CSV-POSTER {username}] No user_id available - poster will NOT be saveable to database")

        # Get display_name from topmate_profile, CSV, or fallback to username
        display_name = row.get("display_name") or row.get("name") or username
        if topmate_profile and topmate_profile.display_name:
            display_name = topmate_profile.display_name

        poster_id = await database_service.create_poster_record(
            job_id=job_id,
            user_identifier=username,
            username=username,
            display_name=display_name,
            metadata=metadata
        )

        print(f"💾 [CSV-POSTER {username}] Poster record created (ID: {poster_id})")
        print(f"📋 [CSV-POSTER {username}] Metadata: {metadata}")
        
        # Replace placeholders in template
        filled_html = replace_placeholders(csv_template, row, csv_columns)
        
        # Convert HTML to PNG
        image_bytes = await convert_html_to_png(
            html=filled_html,
            dimensions=dimensions
        )
        
        if not image_bytes:
            raise Exception("Failed to convert HTML to image")
        
        # Apply overlays if needed
        if not skip_overlays and topmate_logo:
            image_bytes = await overlay_logo_and_profile(
                base_image_bytes=image_bytes,
                topmate_logo=topmate_logo,
                profile_image=None
            )
        
        # Upload to S3
        s3_result = await upload_image(
            image_bytes=image_bytes,
            filename=f"{job_id}/{username}_{int(time.time())}.png"
        )
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        await database_service.update_poster_status(
            poster_id=poster_id,
            status="completed",
            poster_url=s3_result.get("url"),
            s3_key=s3_result.get("key"),
            processing_time_ms=processing_time_ms
        )
        
        return {
            "username": username,
            "success": True,
            "posterUrl": s3_result.get("url"),
            "s3Key": s3_result.get("key"),
            "processingTimeMs": processing_time_ms
        }

    async def _process_template_poster(self, message: Dict[str, Any]):
        """
        Process a single template poster job from RedPanda
        Called when a template_poster message is received from the queue
        """
        parent_job_id = message.get("parent_job_id")
        template_id = message.get("template_id")
        custom_data = message.get("custom_data", {})
        metadata = message.get("metadata", {})

        print(f"🎨 [TEMPLATE] Processing template poster: {parent_job_id}")
        logger.info("Processing template poster", parent_job_id=parent_job_id, template_id=template_id)

        try:
            # Import the task and execute it
            from app.tasks.poster_tasks import process_template_poster_task

            # Call the task directly (already in RedPanda consumer, no need to re-queue)
            result = await process_template_poster_task.kicker()(
                job_id=parent_job_id,
                template_id=template_id,
                custom_data=custom_data,
                metadata=metadata
            )

            # Update parent job progress
            if parent_job_id:
                await self._update_template_job_progress(parent_job_id, success=result.get("success", False))

            logger.info("Template poster completed", parent_job_id=parent_job_id, success=result.get("success"))

        except Exception as e:
            error_msg = str(e)
            logger.error("Template poster failed", parent_job_id=parent_job_id, error=error_msg)

            # Update parent job progress
            if parent_job_id:
                await self._update_template_job_progress(parent_job_id, success=False)

    async def _update_template_job_progress(self, job_id: str, success: bool):
        """Update progress counters for template generation job"""
        try:
            if success:
                await database_service.execute(
                    """
                    UPDATE template_generation_jobs
                    SET processed_items = processed_items + 1,
                        success_count = success_count + 1
                    WHERE job_id = $1
                    """,
                    job_id
                )
            else:
                await database_service.execute(
                    """
                    UPDATE template_generation_jobs
                    SET processed_items = processed_items + 1,
                        failure_count = failure_count + 1
                    WHERE job_id = $1
                    """,
                    job_id
                )

            # Check if job is complete
            job = await database_service.fetchrow(
                """
                SELECT total_items, processed_items
                FROM template_generation_jobs
                WHERE job_id = $1
                """,
                job_id
            )

            if job and job['processed_items'] >= job['total_items']:
                # Mark job as completed
                await database_service.execute(
                    """
                    UPDATE template_generation_jobs
                    SET status = 'completed', completed_at = NOW()
                    WHERE job_id = $1
                    """,
                    job_id
                )

                # Send completion event via SSE
                await sse_manager.send_job_completed(
                    job_id=job_id,
                    success_count=job['processed_items'],
                    total_count=job['total_items']
                )

                logger.info("Template job completed", job_id=job_id)

        except Exception as e:
            logger.error("Failed to update template job progress", job_id=job_id, error=str(e))


# Global singleton instance
job_manager = JobManager()


async def get_job_manager() -> JobManager:
    """Get the global job manager instance"""
    return job_manager
