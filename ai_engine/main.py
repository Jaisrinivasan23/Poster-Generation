"""
Main FastAPI application for AI Website Builder Engine
"""
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from config import settings, get_redis_client, validate_required_config
from logging_config import logger

# Import routers
from routers import build_website, edit_website, chat, component


# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    logger.info("Starting AI Engine", environment=settings.ENVIRONMENT)

    # Validate required configuration
    validate_required_config()

    # Initialize Sentry if DSN provided
    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.SENTRY_ENVIRONMENT,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            integrations=[FastApiIntegration()],
        )
        logger.info("Sentry initialized")

    # Test Redis connection
    redis_client = get_redis_client()
    if redis_client:
        logger.info("Redis connected successfully")
    else:
        logger.warning("Redis not available, running without cache")

    # Verify API keys
    if not settings.ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY not configured!")
    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not configured")

    logger.info(
        "AI Engine started",
        use_sdk_agents=settings.USE_SDK_AGENTS,
        claude_model=settings.CLAUDE_MODEL_SONNET
    )

    yield

    logger.info("Shutting down AI Engine")


# Create FastAPI app
app = FastAPI(
    title="AI Website Builder Engine",
    description="AI-powered website generation and editing service",
    version="2.0.0",
    lifespan=lifespan
)

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware - Configure from environment
# Parse CORS_ORIGINS from comma-separated string
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in settings.CORS_ORIGINS.split(",")
    if origin.strip()
]

# In development, allow all origins for easier testing
# In production, use the configured allowed origins only
if settings.ENVIRONMENT == "development" or settings.DEBUG:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,  # Cannot use credentials with wildcard origins
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "AI Website Builder Engine",
        "version": "2.0.0",
        "status": "running",
        "sdk_agents_enabled": settings.USE_SDK_AGENTS
    }


@app.get("/health")
async def health_check():
    """Comprehensive health check"""
    health = {
        "status": "healthy",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {}
    }

    # Check Anthropic API key
    health["checks"]["anthropic_api"] = {
        "configured": bool(settings.ANTHROPIC_API_KEY),
        "status": "ok" if settings.ANTHROPIC_API_KEY else "missing"
    }

    # Check Gemini API key
    health["checks"]["gemini_api"] = {
        "configured": bool(settings.GEMINI_API_KEY),
        "status": "ok" if settings.GEMINI_API_KEY else "missing"
    }

    # Check Redis
    try:
        redis_client = get_redis_client()
        if redis_client:
            redis_client.ping()
            health["checks"]["redis"] = {"status": "ok"}
        else:
            health["checks"]["redis"] = {"status": "disabled"}
    except Exception as e:
        health["checks"]["redis"] = {"status": "error", "error": str(e)}

    # Check Playwright
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.PLAYWRIGHT_SERVICE_URL}/health",
                timeout=5
            )
            health["checks"]["playwright"] = {
                "status": "ok" if resp.status_code == 200 else "error"
            }
    except Exception as e:
        health["checks"]["playwright"] = {"status": "error", "error": str(e)}

    # Overall status
    critical_checks = ["anthropic_api"]
    all_critical_ok = all(
        health["checks"].get(check, {}).get("status") == "ok"
        for check in critical_checks
    )

    health["status"] = "healthy" if all_critical_ok else "degraded"

    return health


@app.get("/readiness")
async def readiness_check():
    """Kubernetes readiness probe"""
    health = await health_check()
    critical_checks = ["anthropic_api"]

    ready = all(
        health["checks"].get(check, {}).get("status") == "ok"
        for check in critical_checks
    )

    if ready:
        return {"status": "ready"}
    else:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "checks": health["checks"]}
        )


# Include routers
app.include_router(build_website.router, prefix="/api", tags=["Website Generation"])
app.include_router(edit_website.router, prefix="/api", tags=["Website Editing"])
app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(component.router, prefix="/api", tags=["Component Editor"])


# Error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler with Sentry integration"""
    logger.error(
        "Unhandled exception",
        error=str(exc),
        path=request.url.path,
        exc_info=True
    )

    if settings.SENTRY_DSN:
        sentry_sdk.capture_exception(exc)

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.SENTRY_ENVIRONMENT == "development" else None
        }
    )


if __name__ == "__main__":
    import uvicorn
    # Only enable reload in development
    reload_enabled = settings.ENVIRONMENT == "development" or settings.DEBUG
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=reload_enabled)
