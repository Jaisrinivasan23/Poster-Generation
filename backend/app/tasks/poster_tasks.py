"""
TaskIQ Tasks for Poster Generation
Async tasks that are queued and processed by workers
"""
import asyncio
from typing import Dict, Any, List
import structlog
from taskiq import Context

from app.services.taskiq_broker import broker
from app.services.database import database_service
from app.services.redpanda_client import redpanda_client
from app.services.sse_manager import sse_manager
from app.services.job_manager import job_manager

logger = structlog.get_logger(__name__)


@broker.task(task_name="process_batch_job")
async def process_batch_job_task(
    job_id: str,
    job_type: str,
    job_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    TaskIQ task to process a batch poster generation job
    This task orchestrates the entire job processing

    Args:
        job_id: Unique job identifier
        job_type: Type of job ("html" or "csv")
        job_data: Job configuration and data

    Returns:
        Job result summary
    """
    try:
        logger.info("TaskIQ: Starting job processing", job_id=job_id, job_type=job_type)
        print(f"")
        print(f"🔵 [TASKIQ] Task started for job: {job_id} (type: {job_type})")
        print(f"")

        # Ensure services are initialized
        await ensure_services_initialized()

        # Update job status to processing
        await database_service.update_job_status(job_id, "processing")
        await sse_manager.send_log(job_id, "INFO", f"Job processing started (TaskIQ worker)")

        # Process based on job type
        if job_type == "csv":
            result = await job_manager._process_csv_job_with_redpanda(job_data)
        else:
            result = await job_manager._process_html_job_with_redpanda(job_data)

        logger.info("TaskIQ: Job processing completed", job_id=job_id, result=result)
        print(f"✅ [TASKIQ] Task completed for job: {job_id}")

        return result

    except Exception as e:
        error_msg = str(e)
        logger.error("TaskIQ: Job processing failed", job_id=job_id, error=error_msg)
        print(f"❌ [TASKIQ] Task failed for job: {job_id} - {error_msg}")

        # Update job status to failed
        await database_service.update_job_status(
            job_id=job_id,
            status="failed",
            error_message=error_msg
        )

        # Send failure event via SSE
        await sse_manager.send_job_failed(
            job_id=job_id,
            error=error_msg,
            details={"task": "process_batch_job"}
        )

        raise


@broker.task(task_name="process_single_poster")
async def process_single_poster_task(
    job_id: str,
    poster_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    TaskIQ task to process a single poster
    This is sent to RedPanda for parallel processing

    Args:
        job_id: Parent job identifier
        poster_data: Data for generating single poster

    Returns:
        Poster generation result
    """
    try:
        # Publish to RedPanda for parallel processing
        await redpanda_client.publish_job(
            job_id=f"{job_id}_poster_{poster_data.get('username')}",
            job_data={
                "parent_job_id": job_id,
                "type": "single_poster",
                **poster_data
            }
        )

        return {"success": True, "username": poster_data.get("username")}

    except Exception as e:
        logger.error("Failed to queue poster", job_id=job_id, error=str(e))
        raise


@broker.task(task_name="process_template_poster")
async def process_template_poster_task(
    job_id: str,
    template_id: str,
    custom_data: Dict[str, Any],
    metadata: Dict[str, Any]
) -> Dict[str, Any]:
    """
    TaskIQ task to process a single template-based poster
    This is sent to RedPanda for parallel processing

    Args:
        job_id: Job identifier for tracking
        template_id: Template identifier (e.g., 'testimonial_latest')
        custom_data: Placeholder values for the template
        metadata: Additional metadata (user_id, entity_id, etc.)

    Returns:
        Generation result with S3 URL
    """
    try:
        logger.info("TaskIQ: Processing template poster", job_id=job_id, template_id=template_id)

        # Ensure services are initialized
        await ensure_services_initialized()

        # Import here to avoid circular dependencies
        from app.services.template_service import (
            parse_template_id,
            replace_placeholders,
            render_html_to_image,
            generate_s3_key,
            validate_placeholders
        )
        from app.services.storage_service import upload_to_s3
        from app.services.database import database_service
        import time

        start_time = time.time()

        async with database_service.connection() as conn:
            # 1. Parse template_id to get section
            section = parse_template_id(template_id)

            # 2. Fetch active template (including dimensions)
            template = await conn.fetchrow(
                """
                SELECT id, name, html_content, css_content, version, width, height
                FROM templates
                WHERE section = $1 AND is_active = true
                ORDER BY version DESC
                LIMIT 1
                """,
                section
            )

            if not template:
                raise Exception(f"No active template found for section '{section}'")

            # 3. Validate placeholders
            validation = validate_placeholders(template['html_content'], custom_data)
            if validation['missing']:
                logger.warning("Missing placeholders", missing=validation['missing'])

            # 4. Replace placeholders using same method as bulk generation
            from app.services.image_processor import replace_placeholders as replace_placeholders_bulk
            from app.services.html_to_image import convert_html_to_png
            
            # Convert {{placeholder}} to {placeholder} format for consistency with bulk generation
            template_html = template['html_content']
            import re
            # Replace {{key}} with {key} for image_processor compatibility
            template_html_converted = re.sub(r'\{\{([^}]+)\}\}', r'{\1}', template_html)
            
            # Use bulk generation's replace_placeholders (handles nested data via flattening)
            # Flatten nested data: overlay.fill_color becomes overlay_fill_color
            flattened_data = {}
            def flatten_dict(d, parent_key=''):
                for k, v in d.items():
                    new_key = f"{parent_key}_{k}" if parent_key else k
                    if isinstance(v, dict):
                        flatten_dict(v, new_key)
                    else:
                        flattened_data[new_key] = v
            
            flatten_dict(custom_data)
            
            # Replace placeholders
            filled_html = replace_placeholders_bulk(template_html_converted, flattened_data)
            
            print(f"[TEMPLATE] Template HTML prepared for rendering (section: {section})")

            # 5. Render to image using dimensions from template
            dimensions = {
                'width': template.get('width') or 1080,
                'height': template.get('height') or 1080
            }
            
            print(f"[TEMPLATE] Rendering poster: {section} ({dimensions['width']}x{dimensions['height']}, entity_id: {custom_data.get('testimonial_id') or metadata.get('id', 'unknown')})")
            image_bytes = await convert_html_to_png(
                html=filled_html,
                dimensions=dimensions
            )

            # 6. Upload to S3
            entity_id = custom_data.get('testimonial_id') or metadata.get('id', 'unknown')
            s3_key = generate_s3_key(section, str(entity_id))
            s3_url = await upload_to_s3(image_bytes, s3_key)
            print(f"[TEMPLATE] Uploaded to S3: {s3_url}")

            # 7. Calculate generation time
            generation_time_ms = int((time.time() - start_time) * 1000)

            # 8. Log to template_poster_results
            import json
            await conn.execute(
                """
                INSERT INTO template_poster_results
                (job_id, template_id, entity_id, custom_data, output_url, s3_key, status, template_version, generation_time_ms, metadata)
                VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7, $8, $9, $10::jsonb)
                """,
                job_id,
                template['id'],
                str(entity_id),
                json.dumps(custom_data),
                s3_url,
                s3_key,
                'completed',
                template['version'],
                generation_time_ms,
                json.dumps(metadata)
            )

            # 9. Send progress via SSE
            await sse_manager.send_poster_completed(
                job_id=job_id,
                username=str(entity_id),
                poster_url=s3_url,
                success=True
            )

        logger.info("TaskIQ: Template poster completed", job_id=job_id, url=s3_url, time_ms=generation_time_ms)

        return {
            "success": True,
            "url": s3_url,
            "entity_id": str(entity_id),
            "generation_time_ms": generation_time_ms,
            "template_version": template['version']
        }

    except Exception as e:
        error_msg = str(e)
        logger.error("TaskIQ: Template poster failed", job_id=job_id, error=error_msg)

        # Log failure
        try:
            import json
            async with database_service.connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO template_poster_results
                    (job_id, entity_id, custom_data, status, error_message, metadata)
                    VALUES ($1, $2, $3::jsonb, $4, $5, $6::jsonb)
                    """,
                    job_id,
                    custom_data.get('testimonial_id', 'unknown'),
                    json.dumps(custom_data),
                    'failed',
                    error_msg,
                    json.dumps(metadata)
                )

                # Log to template_generation_logs
                await conn.execute(
                    """
                    INSERT INTO template_generation_logs (job_id, level, message, details)
                    VALUES ($1, $2, $3, $4::jsonb)
                    """,
                    job_id,
                    'ERROR',
                    f"Failed to generate poster: {error_msg}",
                    json.dumps({'custom_data': custom_data, 'error': error_msg})
                )
        except:
            pass

        # Send failure via SSE
        await sse_manager.send_poster_completed(
            job_id=job_id,
            username=custom_data.get('testimonial_id', 'unknown'),
            poster_url="",
            success=False,
            error=error_msg
        )

        return {
            "success": False,
            "error": error_msg,
            "entity_id": custom_data.get('testimonial_id', 'unknown')
        }


@broker.task(task_name="process_batch_template_job")
async def process_batch_template_job_task(
    job_id: str,
    template_id: str,
    items: List[Dict[str, Any]],
    metadata: Dict[str, Any]
) -> Dict[str, Any]:
    """
    TaskIQ task to process batch template poster generation
    Publishes individual items to RedPanda for parallel processing

    Args:
        job_id: Unique job identifier
        template_id: Template identifier (e.g., 'testimonial_latest')
        items: List of custom_data dicts for each poster
        metadata: Additional job metadata

    Returns:
        Job summary
    """
    try:
        logger.info("TaskIQ: Starting batch template job", job_id=job_id, total_items=len(items))

        # Ensure services are initialized
        await ensure_services_initialized()

        async with database_service.connection() as conn:
            # Update job status to processing
            await conn.execute(
                """
                UPDATE template_generation_jobs
                SET status = 'processing', started_at = NOW()
                WHERE job_id = $1
                """,
                job_id
            )

            # Send log
            await sse_manager.send_log(job_id, "INFO", f"Processing {len(items)} template posters in parallel")

            # Publish each item to RedPanda for parallel processing
            for idx, item in enumerate(items):
                try:
                    await redpanda_client.publish_job(
                        job_id=f"{job_id}_item_{idx}",
                        job_data={
                            "parent_job_id": job_id,
                            "type": "template_poster",
                            "template_id": template_id,
                            "custom_data": item,
                            "metadata": metadata,
                            "index": idx
                        }
                    )
                except Exception as e:
                    logger.error("Failed to publish item", job_id=job_id, index=idx, error=str(e))

            logger.info("TaskIQ: All items published to RedPanda", job_id=job_id)

            return {
                "success": True,
                "job_id": job_id,
                "total_items": len(items),
                "message": "Items queued for parallel processing"
            }

    except Exception as e:
        error_msg = str(e)
        logger.error("TaskIQ: Batch template job failed", job_id=job_id, error=error_msg)

        # Update job status to failed
        try:
            async with database_service.connection() as conn:
                await conn.execute(
                    """
                    UPDATE template_generation_jobs
                    SET status = 'failed', error_message = $2, completed_at = NOW()
                    WHERE job_id = $1
                    """,
                    job_id,
                    error_msg
                )
        except:
            pass

        raise


@broker.task(task_name="cleanup_old_jobs")
async def cleanup_old_jobs_task():
    """
    Periodic task to cleanup old completed jobs
    Runs daily to maintain database size
    """
    try:
        # TODO: Implement cleanup logic
        # - Delete jobs older than 30 days
        # - Archive completed jobs
        logger.info("Cleanup task executed")
        return {"success": True, "message": "Cleanup completed"}
    except Exception as e:
        logger.error("Cleanup task failed", error=str(e))
        raise


# Helper function to ensure services are initialized
async def ensure_services_initialized():
    """Ensure database and RedPanda are initialized before processing tasks"""
    # Check if database is already initialized
    if not database_service.is_healthy:
        logger.info("TaskIQ: Initializing database...")
        db_initialized = await database_service.initialize()
        if db_initialized:
            logger.info("TaskIQ: Database initialized successfully")
        else:
            logger.warning("TaskIQ: Database initialization failed")

    # Check if RedPanda is already initialized
    if not redpanda_client.is_healthy:
        logger.info("TaskIQ: Initializing RedPanda...")
        try:
            rp_initialized = await redpanda_client.initialize()
            if rp_initialized:
                logger.info("TaskIQ: RedPanda initialized successfully")
            else:
                logger.warning("TaskIQ: RedPanda initialization failed")
        except Exception as e:
            logger.error("TaskIQ: RedPanda initialization error", error=str(e))
