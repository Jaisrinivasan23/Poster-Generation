"""
Job Manager Service
Orchestrates batch poster generation jobs with RedPanda and PostgreSQL
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
        job_type = message.get("job_type", "html")  # Default to HTML job type
        print(f"🔴 [REDPANDA] Received job message: {job_id} (type: {job_type})")
        if not job_id:
            logger.error("Received message without job_id")
            return
        
        logger.info("Processing job from queue", job_id=job_id, job_type=job_type)
        
        # Start processing in background based on job type
        if job_type == "csv":
            task = asyncio.create_task(self._process_csv_job(message))
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
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        
        print(f"🚀 [JOB] Creating job {job_id} with campaign: {campaign_name}")
        
        # Parse identifiers
        usernames, user_ids = parse_user_identifiers(user_identifiers)
        total_items = len(usernames) + len(user_ids)
        
        print(f"📋 [JOB] Parsed {len(usernames)} usernames, {len(user_ids)} user IDs (total: {total_items})")
        
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
        
        # Log job creation
        await database_service.add_log(
            job_id=job_id,
            level="INFO",
            message=f"Job created with {total_items} users",
            details={"campaign_name": campaign_name, "poster_size": poster_size}
        )
        
        # Publish to RedPanda queue
        job_data = {
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
        
        published = await redpanda_client.publish_job(job_id, job_data)
        
        print(f"🔴 [REDPANDA] Published to queue: {published}")
        
        if published:
            print(f"✅ [JOB] Job {job_id} queued for RedPanda processing")
            await database_service.update_job_status(job_id, "queued")
            await database_service.add_log(
                job_id=job_id,
                level="INFO",
                message="Job queued for processing"
            )
        else:
            # If RedPanda is not available, process synchronously
            print(f"⚠️ [JOB] RedPanda not available, processing {job_id} synchronously")
            logger.warning("RedPanda not available, processing synchronously", job_id=job_id)
            asyncio.create_task(self._process_job({"job_id": job_id, **job_data}))
        
        return {
            "job_id": job_id,
            "status": "queued",
            "total_items": total_items,
            "campaign_name": campaign_name,
            "created_at": datetime.utcnow().isoformat()
        }
    
    async def _process_job(self, job_data: Dict[str, Any]):
        """Process a batch job"""
        job_id = job_data["job_id"]
        start_time = time.time()
        
        print(f"")
        print(f"{'='*60}")
        print(f"🔄 [PROCESS] Starting job processing: {job_id}")
        print(f"{'='*60}")
        
        try:
            await database_service.update_job_status(job_id, "processing")
            await sse_manager.send_log(job_id, "INFO", "Job processing started")
            
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
            
            # Process posters in batches of 8
            BATCH_SIZE = 8
            total_batches = (len(profiles) + BATCH_SIZE - 1) // BATCH_SIZE
            print(f"📦 [PROCESS] Processing {len(profiles)} posters in {total_batches} batches")
            
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
                    
                    await sse_manager.send_progress(job_id, processed, total_items, success_count, failure_count, identifier)
                
                # Update database
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
            
            # Create poster record in database
            poster_id = await database_service.create_poster_record(
                job_id=job_id,
                user_identifier=identifier,
                username=username,
                display_name=profile.get("display_name")
            )
            
            # Replace placeholders in HTML
            personalized_html = replace_placeholders(html_template, profile)
            
            # Convert HTML to PNG (returns data URL)
            image_data_url = await convert_html_to_png(
                html=personalized_html,
                dimensions=dimensions
            )
            
            if not image_data_url:
                raise Exception("Failed to convert HTML to image")
            
            # Apply overlays if needed
            if not skip_overlays:
                profile_image_url = profile.get("profile_image")
                if profile_image_url:
                    profile_image_data = await fetch_image_as_data_url(profile_image_url)
                else:
                    profile_image_data = None
                
                if topmate_logo or profile_image_data:
                    image_data_url = await overlay_logo_and_profile(
                        base_image_url=image_data_url,
                        logo_url=topmate_logo,
                        profile_pic_url=profile_image_data,
                        dimensions=dimensions
                    )
            
            # Upload to S3 (upload_image takes data_url, filename and returns URL string)
            poster_url = await upload_image(
                image_data_url,
                f"{job_id}/{username}_{int(time.time())}.png"
            )
            
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Update poster record
            await database_service.update_poster_status(
                poster_id=poster_id,
                status="completed",
                poster_url=poster_url,
                s3_key=None,
                processing_time_ms=processing_time_ms
            )
            
            return {
                "username": username,
                "success": True,
                "posterUrl": poster_url,
                "s3Key": None,
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
        
        # Publish to RedPanda queue
        job_data = {
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
        
        published = await redpanda_client.publish_job(job_id, job_data)
        
        print(f"🔴 [REDPANDA] CSV job published to queue: {published}")
        
        if published:
            print(f"✅ [JOB] CSV Job {job_id} queued for RedPanda processing")
            await database_service.update_job_status(job_id, "queued")
            await database_service.add_log(
                job_id=job_id,
                level="INFO",
                message="CSV job queued for processing"
            )
        else:
            print(f"⚠️ [JOB] RedPanda not available, processing CSV job {job_id} synchronously")
            asyncio.create_task(self._process_csv_job({"job_id": job_id, **job_data}))
        
        return {
            "job_id": job_id,
            "status": "queued",
            "total_items": total_items,
            "campaign_name": campaign_name,
            "created_at": datetime.utcnow().isoformat()
        }
    
    async def create_single_job(
        self,
        topmate_username: str,
        prompt: str,
        poster_size: str = "instagram-square",
        model: str = "flash",
        user_mode: str = "admin",
        reference_image: Optional[str] = None,
        topmate_logo: Optional[str] = None,
        custom_dimensions: Optional[Dict[str, int]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a single AI poster generation job (3 variants) via RedPanda
        """
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        total_items = 3  # Always 3 variants
        
        print(f"🚀 [JOB] Creating single AI job {job_id} for {topmate_username}")
        
        if custom_dimensions:
            dimensions = custom_dimensions
        else:
            dimensions = POSTER_SIZE_DIMENSIONS.get(poster_size, POSTER_SIZE_DIMENSIONS["instagram-square"])
        
        # Create job in database
        await database_service.create_batch_job(
            job_id=job_id,
            campaign_name=f"Single: {topmate_username}",
            total_items=total_items,
            template_html="",  # No template for AI generation
            poster_size=poster_size,
            model=model,
            metadata={
                "job_type": "single",
                "topmate_username": topmate_username,
                "prompt": prompt,
                "reference_image": reference_image is not None,
                "dimensions": dimensions,
                **(metadata or {})
            }
        )
        
        await database_service.add_log(
            job_id=job_id,
            level="INFO",
            message=f"Single AI job created for {topmate_username}",
            details={"poster_size": poster_size, "model": model}
        )
        
        # Publish to RedPanda queue
        job_data = {
            "job_type": "single",
            "topmate_username": topmate_username,
            "prompt": prompt,
            "poster_size": poster_size,
            "model": model,
            "user_mode": user_mode,
            "reference_image": reference_image,
            "topmate_logo": topmate_logo,
            "dimensions": dimensions,
            "metadata": metadata or {}
        }
        
        published = await redpanda_client.publish_job(job_id, job_data)
        
        print(f"🔴 [REDPANDA] Single AI job published to queue: {published}")
        
        if published:
            print(f"✅ [JOB] Single AI Job {job_id} queued for RedPanda processing")
            await database_service.update_job_status(job_id, "queued")
        else:
            print(f"⚠️ [JOB] RedPanda not available, processing single AI job {job_id} synchronously")
            asyncio.create_task(self._process_single_ai_job({"job_id": job_id, **job_data}))
        
        return {
            "job_id": job_id,
            "status": "queued",
            "total_items": total_items,
            "created_at": datetime.utcnow().isoformat()
        }
    
    async def _process_single_ai_job(self, job_data: Dict[str, Any]):
        """Process a single AI poster generation job (3 variants)"""
        job_id = job_data["job_id"]
        start_time = time.time()
        
        print(f"")
        print(f"{'='*60}")
        print(f"🎨 [PROCESS] Starting single AI job: {job_id}")
        print(f"{'='*60}")
        
        try:
            await database_service.update_job_status(job_id, "processing")
            await sse_manager.send_log(job_id, "INFO", "Starting AI poster generation")
            
            topmate_username = job_data.get("topmate_username")
            prompt = job_data.get("prompt", "")
            model = job_data.get("model", "flash")
            user_mode = job_data.get("user_mode", "admin")
            reference_image = job_data.get("reference_image")
            topmate_logo = job_data.get("topmate_logo")
            dimensions = job_data.get("dimensions", {"width": 1080, "height": 1080})
            
            # Fetch Topmate profile
            print(f"📊 [PROCESS] Fetching profile for {topmate_username}...")
            await sse_manager.send_progress(job_id, 0, 3, 0, 0, topmate_username, "fetching_profile")
            
            profile = await fetch_topmate_profile(topmate_username)
            
            # Select model
            if user_mode == "expert":
                model_id = "google/gemini-3-flash-preview"
            else:
                model_id = "google/gemini-3-flash-preview" if model == "flash" else "google/gemini-3-pro-preview"
            
            print(f"🤖 [PROCESS] Using model: {model_id}")
            
            # Get creative direction for Strategy C
            creative_direction = None
            if not reference_image:
                try:
                    print(f"🎨 [PROCESS] Getting creative direction...")
                    await sse_manager.send_log(job_id, "INFO", "Getting AI creative direction")
                    
                    cd_prompt = f'Analyze this poster request and provide creative direction:\n\n"{prompt}"\n\nReturn ONLY valid JSON.'
                    cd_response = await call_openrouter(
                        model=model_id,
                        system_prompt=CREATIVE_DIRECTOR_SYSTEM_PROMPT,
                        user_prompt=cd_prompt,
                        reference_image=None,
                        max_tokens=2000
                    )
                    
                    import json
                    start_idx = cd_response.find('{')
                    end_idx = cd_response.rfind('}') + 1
                    if start_idx != -1 and end_idx > start_idx:
                        creative_direction = json.loads(cd_response[start_idx:end_idx])
                        print(f"✅ [PROCESS] Creative direction received")
                except Exception as e:
                    print(f"⚠️ [PROCESS] Creative direction failed: {e}")
            
            # Build strategies
            strategies = []
            for idx, strategy_template in enumerate(POSTER_STRATEGIES):
                strategy = strategy_template.copy()
                if strategy["name"] == "ai-creative-director":
                    if creative_direction:
                        strategy["directive"] = build_creative_directive(creative_direction)
                    else:
                        strategy["directive"] = FALLBACK_CREATIVE_DIRECTIVE
                strategies.append(strategy)
            
            total_variants = len(strategies)
            success_count = 0
            failure_count = 0
            results = []
            
            has_reference = bool(reference_image)
            
            for variant_idx, strategy in enumerate(strategies):
                variant_name = strategy["name"]
                print(f"🎨 [VARIANT {variant_idx + 1}/{total_variants}] Generating {variant_name}...")
                await sse_manager.send_progress(job_id, variant_idx, total_variants, success_count, failure_count, variant_name, "generating")
                await sse_manager.send_log(job_id, "INFO", f"Generating variant {variant_idx + 1}: {variant_name}")
                
                try:
                    use_reference = has_reference and strategy["type"] == "reference"
                    
                    # Build user prompt
                    user_prompt = f"""POSTER DIMENSIONS: {dimensions['width']}px × {dimensions['height']}px

USER'S PROMPT (this is what matters):
"{prompt}"

CREATOR BRANDING (for subtle attribution only):
- Name: {profile.display_name}
- Photo URL: {profile.profile_pic}
- Handle: @{profile.username}

CONTEXT DATA (use only if prompt specifically needs it):
- Bio: {profile.bio}
- Stats: {profile.total_bookings} bookings, {profile.average_rating}/5 rating"""

                    if profile.services:
                        top_services = profile.services[:3]
                        services_text = "\n".join(f"- {s.title}" for s in top_services)
                        user_prompt += f"\n- Services:\n{services_text}"
                    
                    user_prompt += f"\n\nSTYLE DIRECTION: {strategy['directive']}\n\n"
                    
                    if use_reference:
                        user_prompt += """REFERENCE IMAGE PROVIDED: Use it ONLY as VISUAL STYLE inspiration.
⚠️ CRITICAL: Do NOT copy any text, brand names, logos from the reference."""
                    
                    user_prompt += "\n\nGenerate the HTML poster. Output only HTML starting with <!DOCTYPE html>"
                    
                    # Call OpenRouter
                    html = await call_openrouter(
                        model=model_id,
                        system_prompt=POSTER_SYSTEM_PROMPT,
                        user_prompt=user_prompt,
                        reference_image=reference_image if use_reference else None,
                        max_tokens=12000
                    )
                    
                    # Clean HTML
                    html = html.replace("```html\n", "").replace("```html", "")
                    html = html.replace("```\n", "").replace("```", "").strip()
                    if not html.startswith("<!DOCTYPE"):
                        idx = html.find("<!DOCTYPE")
                        if idx != -1:
                            html = html[idx:]
                    
                    success_count += 1
                    results.append({
                        "variantIndex": variant_idx,
                        "strategyName": variant_name,
                        "success": True,
                        "html": html,
                        "dimensions": dimensions
                    })
                    
                    print(f"✅ [VARIANT {variant_idx + 1}] Generated successfully")
                    await sse_manager.send_poster_completed(job_id, variant_name, "", True)
                    
                except Exception as e:
                    failure_count += 1
                    error_msg = str(e)
                    print(f"❌ [VARIANT {variant_idx + 1}] Failed: {error_msg[:50]}...")
                    results.append({
                        "variantIndex": variant_idx,
                        "strategyName": variant_name,
                        "success": False,
                        "error": error_msg
                    })
                    await sse_manager.send_poster_completed(job_id, variant_name, "", False, error_msg)
                
                await sse_manager.send_progress(job_id, variant_idx + 1, total_variants, success_count, failure_count, variant_name, "processing")
            
            elapsed_time = time.time() - start_time
            
            print(f"")
            print(f"{'='*60}")
            print(f"🎉 [COMPLETE] Single AI Job {job_id} finished!")
            print(f"   ✅ Success: {success_count}")
            print(f"   ❌ Failed: {failure_count}")
            print(f"   ⏱️ Time: {round(elapsed_time, 2)}s")
            print(f"{'='*60}")
            
            await database_service.update_job_status(
                job_id=job_id,
                status="completed",
                processed_items=total_variants,
                success_count=success_count,
                failure_count=failure_count
            )
            
            # Send results with HTML included
            await sse_manager.send_job_completed(job_id, success_count, failure_count, elapsed_time, results)
            
        except Exception as e:
            logger.error("Single AI job failed", job_id=job_id, error=str(e))
            print(f"💥 [ERROR] Single AI Job {job_id} FAILED: {str(e)}")
            
            await database_service.update_job_status(
                job_id=job_id,
                status="failed",
                error_message=str(e)
            )
            await sse_manager.send_job_failed(job_id, str(e))
    
    async def _process_csv_job(self, job_data: Dict[str, Any]):
        """Process a CSV-based batch job"""
        job_id = job_data["job_id"]
        start_time = time.time()
        
        print(f"")
        print(f"{'='*60}")
        print(f"🔄 [PROCESS] Starting CSV job processing: {job_id}")
        print(f"{'='*60}")
        
        try:
            await database_service.update_job_status(job_id, "processing")
            await sse_manager.send_log(job_id, "INFO", "CSV job processing started")
            
            csv_data = job_data.get("csv_data", [])
            csv_template = job_data.get("csv_template", "")
            csv_columns = job_data.get("csv_columns", [])
            dimensions = job_data.get("dimensions", {"width": 1080, "height": 1080})
            topmate_logo = job_data.get("topmate_logo")
            skip_overlays = job_data.get("skip_overlays", False)
            
            total_items = len(csv_data)
            print(f"📋 [PROCESS] Job {job_id}: {total_items} CSV rows to process")
            processed = 0
            success_count = 0
            failure_count = 0
            results = []
            
            # Process in batches
            BATCH_SIZE = 8
            total_batches = (len(csv_data) + BATCH_SIZE - 1) // BATCH_SIZE
            print(f"📦 [PROCESS] Processing {len(csv_data)} rows in {total_batches} batches")
            
            for i in range(0, len(csv_data), BATCH_SIZE):
                batch = csv_data[i:i + BATCH_SIZE]
                batch_num = i // BATCH_SIZE + 1
                
                print(f"🔄 [BATCH {batch_num}/{total_batches}] Processing {len(batch)} rows...")
                await sse_manager.send_log(job_id, "INFO", f"Processing batch {batch_num}/{total_batches}")
                
                for row in batch:
                    username = row.get("username") or row.get("Username") or f"row_{processed+1}"
                    try:
                        result = await self._generate_csv_poster(
                            job_id=job_id,
                            row=row,
                            csv_template=csv_template,
                            csv_columns=csv_columns,
                            dimensions=dimensions,
                            topmate_logo=topmate_logo,
                            skip_overlays=skip_overlays
                        )
                        
                        processed += 1
                        success_count += 1
                        results.append(result)
                        print(f"✅ [POSTER] Success: {username} ({processed}/{total_items})")
                        await sse_manager.send_poster_completed(job_id, username, result.get("posterUrl", ""), True)
                        await sse_manager.send_progress(job_id, processed, total_items, success_count, failure_count, username)
                        
                    except Exception as e:
                        processed += 1
                        failure_count += 1
                        error_msg = str(e)
                        print(f"❌ [POSTER] Failed: {username} - {error_msg[:50]}...")
                        results.append({"username": username, "success": False, "error": error_msg})
                        await sse_manager.send_poster_completed(job_id, username, "", False, error_msg)
                        await sse_manager.send_progress(job_id, processed, total_items, success_count, failure_count, username)
                
                await database_service.update_job_status(
                    job_id=job_id,
                    status="processing",
                    processed_items=processed,
                    success_count=success_count,
                    failure_count=failure_count
                )
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
        
        # Create poster record
        poster_id = await database_service.create_poster_record(
            job_id=job_id,
            user_identifier=username,
            username=username,
            display_name=row.get("display_name") or row.get("name") or username
        )
        
        # Replace placeholders in template
        filled_html = replace_placeholders(csv_template, row, csv_columns)
        
        # Convert HTML to PNG (returns data URL)
        image_data_url = await convert_html_to_png(
            html=filled_html,
            dimensions=dimensions
        )
        
        if not image_data_url:
            raise Exception("Failed to convert HTML to image")
        
        # Apply overlays if needed
        if not skip_overlays and topmate_logo:
            image_data_url = await overlay_logo_and_profile(
                base_image_url=image_data_url,
                logo_url=topmate_logo,
                profile_pic_url=None,
                dimensions=dimensions
            )
        
        # Upload to S3 (upload_image takes data_url, filename and returns URL string)
        poster_url = await upload_image(
            image_data_url,
            f"{job_id}/{username}_{int(time.time())}.png"
        )
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        await database_service.update_poster_status(
            poster_id=poster_id,
            status="completed",
            poster_url=poster_url,
            s3_key=None,
            processing_time_ms=processing_time_ms
        )
        
        return {
            "username": username,
            "success": True,
            "posterUrl": poster_url,
            "s3Key": None,
            "processingTimeMs": processing_time_ms
        }


# Global singleton instance
job_manager = JobManager()


async def get_job_manager() -> JobManager:
    """Get the global job manager instance"""
    return job_manager
