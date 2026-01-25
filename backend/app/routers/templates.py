"""
Template Management Router
For external backend integration (Django Topmate)
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse, ServerSentEvent
from typing import Optional, List, Dict, Any
import time
import json
import asyncio
from datetime import datetime
from uuid import UUID

from app.models.template import (
    UploadTemplateRequest,
    UploadTemplateResponse,
    GenerateFromTemplateRequest,
    GenerateFromTemplateResponse,
    TemplatePreviewResponse,
    ListTemplatesResponse,
    ActivateTemplateResponse,
    UpdateTemplateRequest,
    TemplateInfo,
    PlaceholderInfo
)
from app.services.template_service import (
    extract_placeholders,
    replace_placeholders,
    render_html_to_image,
    render_html_to_base64,
    get_next_version,
    parse_template_id,
    generate_s3_key,
    validate_placeholders
)
from app.services.database import database_service
from app.services.storage_service import upload_to_s3
from app.services.sse_manager import sse_manager
from app.tasks.poster_tasks import process_template_poster_task, process_batch_template_job_task
import uuid
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post("/templates/upload", response_model=UploadTemplateResponse)
async def upload_template(request: UploadTemplateRequest):
    """
    Upload a new HTML template with versioning

    - Extracts placeholders automatically from HTML
    - Auto-increments version number
    - Can set as active template
    """
    try:
        async with database_service.connection() as conn:
            # 1. Get max version for this section
            max_version_row = await conn.fetchrow(
                "SELECT MAX(version) as max_ver FROM templates WHERE section = $1",
                request.section
            )
            max_version = max_version_row['max_ver'] if max_version_row else None
            new_version = get_next_version(request.section, max_version)

            # 2. Extract placeholders
            placeholders = extract_placeholders(request.html_content)

            # 3. Create template
            template_id = await conn.fetchval(
                """
                INSERT INTO templates (section, name, html_content, css_content, version, is_active, preview_data)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                request.section,
                request.name,
                request.html_content,
                request.css_content,
                new_version,
                request.set_as_active,
                json.dumps(request.preview_data) if request.preview_data else None
            )

            # 4. If set as active, deactivate others
            if request.set_as_active:
                await conn.execute(
                    """
                    UPDATE templates
                    SET is_active = false
                    WHERE section = $1 AND id != $2
                    """,
                    request.section,
                    template_id
                )

            # 5. Save placeholders
            placeholder_infos = []
            for placeholder in placeholders:
                sample_value = None
                if request.preview_data and placeholder in request.preview_data:
                    sample_value = str(request.preview_data[placeholder])

                await conn.execute(
                    """
                    INSERT INTO template_placeholders (template_id, placeholder_name, sample_value)
                    VALUES ($1, $2, $3)
                    """,
                    template_id,
                    placeholder,
                    sample_value
                )

                placeholder_infos.append(PlaceholderInfo(
                    name=placeholder,
                    sample_value=sample_value
                ))

            print(f"✅ Template uploaded: {request.name} (version {new_version}, section: {request.section})")

            return UploadTemplateResponse(
                template_id=str(template_id),
                version=new_version,
                section=request.section,
                placeholders=placeholder_infos,
                message=f"Template uploaded successfully (version {new_version})"
            )

    except Exception as e:
        print(f"❌ Template upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/templates/generate")
async def generate_from_template(request: GenerateFromTemplateRequest):
    """
    Generate poster from template using TaskIQ (fast async, returns immediately with SSE endpoint)

    Request: {"template_id": "testimonial_latest", "custom_data": {...}, "metadata": {...}}
    Response: {"job_id": "...", "status": "queued", "sse_endpoint": "/api/templates/generate/{job_id}/stream"}

    - Returns immediately with job_id and SSE endpoint for real-time progress
    - Use SSE stream to get progress updates and final result
    """
    try:
        async with database_service.connection() as conn:
            # Parse template_id to get section
            section = parse_template_id(request.template_id)

            # Fetch template to get ID, version, and name
            template = await conn.fetchrow(
                """
                SELECT id, version, name
                FROM templates
                WHERE section = $1 AND is_active = true
                ORDER BY version DESC
                LIMIT 1
                """,
                section
            )

            if not template:
                raise HTTPException(
                    status_code=404,
                    detail=f"No active template found for section '{section}'"
                )

            # Generate unique job ID
            job_id = f"template_gen_{uuid.uuid4().hex[:12]}"

            # Create job record in DB
            await conn.execute(
                """
                INSERT INTO template_generation_jobs
                (job_id, template_id, template_section, template_version, status, total_items, input_data, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb)
                """,
                job_id,
                template['id'],
                section,
                template['version'],
                'queued',
                1,
                json.dumps(request.custom_data),
                json.dumps(request.metadata)
            )

            # Log job creation
            await conn.execute(
                """
                INSERT INTO template_generation_logs (job_id, level, message, details)
                VALUES ($1, $2, $3, $4::jsonb)
                """,
                job_id,
                'INFO',
                f"Poster generation started for section: {section}",
                json.dumps({'template_id': request.template_id, 'section': section})
            )

            logger.info("Template generation job created", job_id=job_id, section=section)
            print(f"✅ Job created: {job_id} (section: {section})")

        # Send immediate SSE progress event (0% - starting)
        await sse_manager.send_progress(
            job_id=job_id,
            processed=0,
            total=1,
            success_count=0,
            failure_count=0,
            current_user=None,
            phase="starting"
        )
        await sse_manager.send_log(job_id, "INFO", f"Starting poster generation for {section}")

        # Queue to TaskIQ (non-blocking)
        await process_template_poster_task.kiq(
            job_id=job_id,
            template_id=request.template_id,
            custom_data=request.custom_data,
            metadata=request.metadata
        )

        # Return immediately with SSE endpoint
        return {
            "success": True,
            "job_id": job_id,
            "status": "queued",
            "template_version": template['version'],
            "template_name": template['name'],
            "sse_endpoint": f"/api/templates/generate/{job_id}/stream",
            "poll_endpoint": f"/api/templates/job/{job_id}",
            "message": "Generation started. Connect to SSE endpoint for real-time progress."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Template generation error", error=str(e))
        print(f"❌ Generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates/generate/{job_id}/stream")
async def stream_template_generation(job_id: str, request: Request):
    """
    SSE endpoint for streaming single template generation progress
    
    Connect to receive real-time updates:
    - connected: Connection established
    - progress: Generation progress (0% -> 100%)
    - poster_completed: Generation finished with URL
    - job_failed: Generation failed
    - heartbeat: Keep-alive signal
    """
    # Verify job exists
    async with database_service.connection() as conn:
        job = await conn.fetchrow(
            """
            SELECT job_id, status, template_section, template_version
            FROM template_generation_jobs
            WHERE job_id = $1
            """,
            job_id
        )
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
    
    # Create unique connection ID
    connection_id = f"tpl_conn_{uuid.uuid4().hex[:8]}"
    
    logger.info("Template SSE connection requested", job_id=job_id, connection_id=connection_id)
    
    # Register connection
    connection = await sse_manager.connect(job_id, connection_id)
    
    # Send initial status
    await connection.send("status", {
        "job_id": job_id,
        "status": job["status"],
        "processed": 0,
        "total": 1,
        "phase": "starting"
    })
    
    async def event_generator():
        poll_interval = 0.5  # Poll every 500ms for faster updates
        max_wait = 120  # 2 minutes max
        waited = 0
        
        try:
            while waited < max_wait:
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info("SSE client disconnected", job_id=job_id)
                    break

                # Try to get event from queue with short timeout for responsiveness
                try:
                    event = await asyncio.wait_for(connection.queue.get(), timeout=poll_interval)

                    # Yield the event
                    yield ServerSentEvent(
                        data=json.dumps(event["data"]),
                        event=event["event"]
                    )

                    # Check if job completed/failed
                    if event["event"] in ("poster_completed", "job_completed", "job_failed"):
                        logger.info("Template generation finished", job_id=job_id, event=event["event"])
                        break

                except asyncio.TimeoutError:
                    waited += poll_interval
                    
                    # Check database for completion (backup mechanism)
                    async with database_service.connection() as conn:
                        result = await conn.fetchrow(
                            """
                            SELECT output_url, generation_time_ms, status, error_message, template_version
                            FROM template_poster_results
                            WHERE job_id = $1
                            """,
                            job_id
                        )
                        
                        if result:
                            if result['status'] == 'completed' and result['output_url']:
                                # Send completion event
                                yield ServerSentEvent(
                                    data=json.dumps({
                                        "job_id": job_id,
                                        "success": True,
                                        "url": result['output_url'],
                                        "generation_time_ms": result['generation_time_ms'] or 0,
                                        "template_version": result['template_version']
                                    }),
                                    event="poster_completed"
                                )
                                logger.info("Template generation completed (from DB)", job_id=job_id)
                                break
                            elif result['status'] == 'failed':
                                # Send failure event
                                yield ServerSentEvent(
                                    data=json.dumps({
                                        "job_id": job_id,
                                        "success": False,
                                        "error": result['error_message'] or 'Generation failed'
                                    }),
                                    event="job_failed"
                                )
                                logger.info("Template generation failed (from DB)", job_id=job_id)
                                break
                    
                    # Send heartbeat every 5 seconds
                    if int(waited) % 5 == 0 and waited > 0:
                        yield ServerSentEvent(
                            data=json.dumps({"status": "alive", "waited": waited}),
                            event="heartbeat"
                        )

            # If we timed out, send error
            if waited >= max_wait:
                yield ServerSentEvent(
                    data=json.dumps({"job_id": job_id, "error": "Generation timeout"}),
                    event="job_failed"
                )

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
            logger.info("Template SSE connection closed", job_id=job_id, connection_id=connection_id)

    return EventSourceResponse(event_generator())


@router.get("/templates/job/{job_id}")
async def get_template_job_status(job_id: str):
    """
    Get status of a template generation job
    """
    try:
        async with database_service.connection() as conn:
            # Fetch job
            job = await conn.fetchrow(
                """
                SELECT * FROM template_generation_jobs
                WHERE job_id = $1
                """,
                job_id
            )

            if not job:
                raise HTTPException(status_code=404, detail="Job not found")

            # Fetch results
            results = await conn.fetch(
                """
                SELECT entity_id, output_url, status, generation_time_ms, error_message
                FROM template_poster_results
                WHERE job_id = $1
                ORDER BY created_at
                """,
                job_id
            )

            return {
                "job_id": job_id,
                "status": job['status'],
                "template_section": job['template_section'],
                "template_version": job['template_version'],
                "total_items": job['total_items'],
                "processed_items": job['processed_items'],
                "success_count": job['success_count'],
                "failure_count": job['failure_count'],
                "created_at": job['created_at'].isoformat(),
                "started_at": job['started_at'].isoformat() if job['started_at'] else None,
                "completed_at": job['completed_at'].isoformat() if job['completed_at'] else None,
                "results": [
                    {
                        "entity_id": r['entity_id'],
                        "url": r['output_url'],
                        "status": r['status'],
                        "generation_time_ms": r['generation_time_ms'],
                        "error": r['error_message']
                    }
                    for r in results
                ]
            }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Job status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates/{template_id}/preview", response_model=TemplatePreviewResponse)
async def preview_template(template_id: str):
    """
    Preview template with sample data

    - Fetches template
    - Replaces placeholders with preview_data
    - Renders to base64 image for display
    """
    try:
        async with database_service.connection() as conn:
            # Fetch template
            template = await conn.fetchrow(
                "SELECT * FROM templates WHERE id = $1",
                UUID(template_id)
            )

            if not template:
                raise HTTPException(status_code=404, detail="Template not found")

            # Get placeholders
            placeholder_rows = await conn.fetch(
                "SELECT placeholder_name, sample_value FROM template_placeholders WHERE template_id = $1",
                UUID(template_id)
            )

            placeholders = [
                PlaceholderInfo(name=row['placeholder_name'], sample_value=row['sample_value'])
                for row in placeholder_rows
            ]

            # Replace with preview data
            preview_data = template['preview_data'] or {}
            html_preview = replace_placeholders(template['html_content'], preview_data)

            # Render to base64
            preview_image_base64 = await render_html_to_base64(
                html_preview,
                template['css_content']
            )

            return TemplatePreviewResponse(
                template_id=str(template['id']),
                html_preview=html_preview,
                preview_image_base64=preview_image_base64,
                placeholders=placeholders
            )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Preview error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates", response_model=ListTemplatesResponse)
async def list_templates(section: Optional[str] = None):
    """
    List all templates, optionally filtered by section

    - Shows version history
    - Indicates active template
    """
    try:
        async with database_service.connection() as conn:
            if section:
                templates = await conn.fetch(
                    """
                    SELECT id, section, name, version, is_active, created_at, html_content, css_content
                    FROM templates
                    WHERE section = $1
                    ORDER BY version DESC
                    """,
                    section
                )
            else:
                templates = await conn.fetch(
                    """
                    SELECT id, section, name, version, is_active, created_at, html_content, css_content
                    FROM templates
                    ORDER BY section, version DESC
                    """
                )

            template_infos = []
            active_template = None

            for t in templates:
                # Get placeholders
                placeholders = await conn.fetch(
                    "SELECT placeholder_name, sample_value FROM template_placeholders WHERE template_id = $1",
                    t['id']
                )

                template_info = TemplateInfo(
                    id=str(t['id']),
                    section=t['section'],
                    name=t['name'],
                    version=t['version'],
                    is_active=t['is_active'],
                    created_at=t['created_at'],
                    html_content=t['html_content'],
                    css_content=t['css_content'],
                    placeholders=[
                        PlaceholderInfo(name=p['placeholder_name'], sample_value=p['sample_value'])
                        for p in placeholders
                    ]
                )

                template_infos.append(template_info)

                if t['is_active'] and active_template is None:
                    active_template = template_info

            return ListTemplatesResponse(
                section=section or 'all',
                templates=template_infos,
                active_template=active_template
            )

    except Exception as e:
        print(f"❌ List templates error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/templates/{template_id}/activate", response_model=ActivateTemplateResponse)
async def activate_template(template_id: str):
    """
    Activate a specific template version

    - Deactivates all other templates in same section
    - Sets this template as active
    """
    try:
        async with database_service.connection() as conn:
            # Get template
            template = await conn.fetchrow(
                "SELECT id, section, version, name FROM templates WHERE id = $1",
                UUID(template_id)
            )

            if not template:
                raise HTTPException(status_code=404, detail="Template not found")

            # Deactivate all templates in section
            await conn.execute(
                "UPDATE templates SET is_active = false WHERE section = $1",
                template['section']
            )

            # Activate this template
            await conn.execute(
                "UPDATE templates SET is_active = true, updated_at = NOW() WHERE id = $1",
                UUID(template_id)
            )

            print(f"✅ Template activated: {template['name']} (version {template['version']})")

            return ActivateTemplateResponse(
                template_id=str(template['id']),
                section=template['section'],
                version=template['version'],
                is_active=True,
                message=f"Template '{template['name']}' activated for {template['section']} generation"
            )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Activation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/templates/{template_id}")
async def update_template(template_id: str, request: UpdateTemplateRequest):
    """
    Update template (creates new version)

    - Creates a new template with incremented version
    - Keeps old version for history
    """
    try:
        async with database_service.connection() as conn:
            # Get existing template
            existing = await conn.fetchrow(
                "SELECT * FROM templates WHERE id = $1",
                UUID(template_id)
            )

            if not existing:
                raise HTTPException(status_code=404, detail="Template not found")

            # Get next version
            new_version = existing['version'] + 1

            # Use new values or keep existing
            html_content = request.html_content or existing['html_content']
            css_content = request.css_content if request.css_content is not None else existing['css_content']
            name = request.name or existing['name']
            preview_data = request.preview_data or existing['preview_data']

            # Create new version
            new_template_id = await conn.fetchval(
                """
                INSERT INTO templates (section, name, html_content, css_content, version, is_active, preview_data)
                VALUES ($1, $2, $3, $4, $5, false, $6)
                RETURNING id
                """,
                existing['section'],
                name,
                html_content,
                css_content,
                new_version,
                json.dumps(preview_data) if preview_data else None
            )

            # Extract and save placeholders
            placeholders = extract_placeholders(html_content)
            for placeholder in placeholders:
                sample_value = None
                if preview_data and placeholder in preview_data:
                    sample_value = str(preview_data[placeholder])

                await conn.execute(
                    """
                    INSERT INTO template_placeholders (template_id, placeholder_name, sample_value)
                    VALUES ($1, $2, $3)
                    """,
                    new_template_id,
                    placeholder,
                    sample_value
                )

            print(f"✅ New template version created: {name} (version {new_version})")

            return {
                "template_id": str(new_template_id),
                "version": new_version,
                "message": f"New version {new_version} created"
            }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
