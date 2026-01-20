"""
FastAPI Poster Generation Backend
Main application entry point
"""
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
)
from app.services.html_to_image import initialize_converter, close_converter


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    print("Starting up...")
    # Note: Playwright initializes lazily on first use (Windows compatibility)
    print("Startup complete")

    yield

    # Shutdown: Close Playwright browser if initialized
    print("Shutting down...")
    await close_converter()
    print("Shutdown complete")


app = FastAPI(
    title="Poster Generation API",
    description="FastAPI backend for poster generation with Topmate integration",
    version="1.0.0",
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
        "version": "1.0.0",
        "topmate_api": settings.django_api_url,
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "topmate_api": settings.django_api_url,
        "s3_bucket": settings.aws_s3_bucket,
        "s3_configured": settings.is_s3_configured,
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
