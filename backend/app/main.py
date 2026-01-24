"""
FastAPI Poster Generation Backend
Main application entry point
"""
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from app.config import settings
from app.routers import (
    generate_poster,
    generate_bulk,
    save_bulk_posters,
    export_poster,
    complete_carousel,
    generate,
    chat,
    analyze_design,
    analyze_prompt,
    generate_image,
    generate_template,
    upload_s3,
    edit_poster,
    batch_processing,
    templates,
)
from app.services.html_to_image import initialize_converter, close_converter
from app.services.database import database_service
from app.services.redpanda_client import redpanda_client
from app.services.job_manager import job_manager
from app.services.taskiq_broker import startup_broker, shutdown_broker
from app.services.sse_manager import sse_manager

# Configure structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    logger.info("Starting up poster generation API...")
    
    # Initialize database
    try:
        db_initialized = await database_service.initialize()
        if db_initialized:
            logger.info("Database initialized successfully")
        else:
            logger.warning("Database initialization failed - running without persistence")
    except Exception as e:
        logger.error("Database initialization error", error=str(e))
    
    # Initialize TaskIQ broker
    try:
        await startup_broker()
        logger.info("TaskIQ broker initialized successfully")
    except Exception as e:
        logger.error("TaskIQ initialization error", error=str(e))

    # Initialize SSE Manager with Redis pub/sub
    try:
        await sse_manager.initialize()
        logger.info("SSE Manager initialized successfully with Redis pub/sub")
    except Exception as e:
        logger.error("SSE Manager initialization error", error=str(e))

    # Initialize RedPanda
    try:
        rp_initialized = await redpanda_client.initialize()
        if rp_initialized:
            logger.info("RedPanda initialized successfully")
            # Start job manager (for RedPanda consumer)
            await job_manager.start()
            logger.info("Job manager started")
        else:
            logger.warning("RedPanda initialization failed - batch jobs will run synchronously")
    except Exception as e:
        logger.error("RedPanda initialization error", error=str(e))

    # Note: Playwright initializes lazily on first use (Windows compatibility)
    logger.info("Startup complete")

    yield

    # Shutdown
    logger.info("Shutting down...")

    # Stop job manager
    await job_manager.stop()

    # Shutdown SSE Manager
    await sse_manager.close()

    # Shutdown TaskIQ broker
    await shutdown_broker()

    # Close RedPanda
    await redpanda_client.close()

    # Close database
    await database_service.close()

    # Close Playwright browser if initialized
    await close_converter()

    logger.info("Shutdown complete")


app = FastAPI(
    title="Poster Generation API",
    description="FastAPI backend for poster generation with Topmate integration, RedPanda streaming, and real-time SSE updates",
    version="2.0.0",
    lifespan=lifespan
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health Check
@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "Poster Generation API is running",
        "version": "2.0.0",
        "topmate_api": settings.django_api_url,
        "features": ["batch_processing", "sse_streaming", "redpanda_queue"]
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "topmate_api": settings.django_api_url,
        "s3_bucket": settings.aws_s3_bucket,
        "s3_configured": settings.is_s3_configured,
        "database": database_service.is_healthy,
        "redpanda": redpanda_client.is_healthy,
    }

# Include API routers
app.include_router(generate_poster.router, prefix="/api", tags=["Generate Poster"])
app.include_router(generate_bulk.router, prefix="/api", tags=["Generate Bulk"])
app.include_router(save_bulk_posters.router, prefix="/api", tags=["Save Bulk"])
app.include_router(export_poster.router, prefix="/api", tags=["Export Poster"])
app.include_router(complete_carousel.router, prefix="/api", tags=["Complete Carousel"])
app.include_router(edit_poster.router, tags=["Edit Poster"])
app.include_router(generate.router, prefix="/api", tags=["Generate Email"])
app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(analyze_design.router, prefix="/api", tags=["Analyze Design"])
app.include_router(analyze_prompt.router, prefix="/api", tags=["Analyze Prompt"])
app.include_router(generate_image.router, prefix="/api", tags=["Generate Image"])
app.include_router(generate_template.router, prefix="/api", tags=["Generate Template"])
app.include_router(upload_s3.router, prefix="/api", tags=["Upload S3"])
app.include_router(batch_processing.router, prefix="/api", tags=["Batch Processing"])
app.include_router(templates.router, prefix="/api", tags=["Templates"])

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": str(exc)
        }
    )
