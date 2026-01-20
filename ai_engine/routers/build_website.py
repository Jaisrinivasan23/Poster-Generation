"""
Website generation API router
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List
import time
import httpx

from logging_config import logger
from config import settings
from services.openrouter_website_generator import (
    OpenRouterWebsiteGenerator,
    get_available_templates,
    WEBSITE_TEMPLATES
)
from services.design_context_extractor import extract_design_context
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


class BuildWebsiteRequest(BaseModel):
    """Request model for building a website"""
    username: str
    user_prompt: Optional[str] = ""
    template_id: Optional[str] = "modern-minimal"


class BuildWebsiteResponse(BaseModel):
    """Response model for building a website"""
    success: bool
    html: Optional[str] = None
    error: Optional[str] = None
    username: Optional[str] = None
    model: Optional[str] = None
    template_id: Optional[str] = None
    execution_time: Optional[float] = None
    token_usage: Optional[dict] = None
    design_context: Optional[dict] = None  # Design context for consistent edits


class TemplateInfo(BaseModel):
    """Template information model"""
    id: str
    name: str
    description: str
    preview: str


class TemplatesResponse(BaseModel):
    """Response model for templates list"""
    success: bool
    templates: List[TemplateInfo]


@router.get("/build/templates", response_model=TemplatesResponse)
async def get_templates():
    """
    Get list of available website templates.

    Returns all templates with their names, descriptions, and preview images.
    """
    templates = get_available_templates()
    return TemplatesResponse(
        success=True,
        templates=[TemplateInfo(**t) for t in templates]
    )


@router.post("/build/website", response_model=BuildWebsiteResponse)
@limiter.limit("5/minute")  # Rate limit: 5 requests per minute
async def build_website(request: Request, data: BuildWebsiteRequest):
    """
    Generate a complete website from Topmate username.

    This endpoint:
    1. Fetches user profile from Topmate API (includes services, badges, testimonials)
    2. Generates a professional portfolio website using AI (Gemini via OpenRouter)
    3. Returns complete HTML with embedded CSS/JS

    Parameters:
    - username: Topmate username to fetch profile data
    - user_prompt: Optional custom instructions for the website
    - template_id: Template style to use (default: modern-minimal)

    Available templates:
    - modern-minimal: Clean, minimalist design
    - bold-creative: Vibrant colors and dynamic layouts
    - professional-corporate: Trust-building business design
    - dark-elegant: Sophisticated dark theme
    - vibrant-gradient: Eye-catching gradients with glass effects

    Rate limit: 5 requests per minute
    """
    try:
        start_time = time.time()

        # Validate template_id
        template_id = data.template_id or "modern-minimal"
        if template_id not in WEBSITE_TEMPLATES:
            template_id = "modern-minimal"

        logger.info(
            "Website build request received",
            username=data.username,
            template_id=template_id,
            has_user_prompt=bool(data.user_prompt)
        )

        # Check if SDK agents enabled (feature flag)
        if settings.USE_SDK_AGENTS:
            # TODO: Use Claude Agents SDK orchestrator (Phase 2)
            return BuildWebsiteResponse(
                success=False,
                error="SDK agents not yet implemented. Set USE_SDK_AGENTS=false"
            )

        # Use OpenRouter generator with Gemini (default)
        generator = OpenRouterWebsiteGenerator()
        result = await generator.generate_website(
            username=data.username,
            user_prompt=data.user_prompt,
            template_id=template_id
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Unknown error during generation")
            )

        execution_time = time.time() - start_time

        logger.info(
            "Website built successfully",
            username=data.username,
            template_id=template_id,
            execution_time=execution_time
        )

        return BuildWebsiteResponse(
            success=True,
            html=result.get("html"),
            username=data.username,
            model=result.get("model"),
            template_id=template_id,
            execution_time=execution_time,
            token_usage=result.get("token_usage"),
            design_context=result.get("design_context")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error building website: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class ExtractContextRequest(BaseModel):
    """Request model for extracting design context"""
    html: str


class ExtractContextResponse(BaseModel):
    """Response model for design context extraction"""
    success: bool
    design_context: Optional[dict] = None
    error: Optional[str] = None


@router.post("/build/extract-context", response_model=ExtractContextResponse)
async def extract_context_from_html(data: ExtractContextRequest):
    """
    Extract design context from uploaded HTML.

    This endpoint parses the HTML to extract:
    - Fonts (Google Fonts, system fonts)
    - Colors (CSS variables, inline colors)
    - Sections (header, hero, about, services, etc.)
    - Design tokens (spacing, border-radius, shadows)

    This context is used to maintain design consistency during edits.
    """
    try:
        if not data.html or len(data.html) < 50:
            return ExtractContextResponse(
                success=False,
                error="Invalid or empty HTML"
            )

        # Extract design context
        context = extract_design_context(data.html, template_id="uploaded")

        logger.info(
            "Design context extracted",
            fonts=context.get("fonts", {}).get("display", "unknown"),
            has_colors=bool(context.get("colors")),
            sections_count=len(context.get("sections", []))
        )

        return ExtractContextResponse(
            success=True,
            design_context=context
        )

    except Exception as e:
        logger.error(f"Error extracting design context: {str(e)}")
        return ExtractContextResponse(
            success=False,
            error=str(e)
        )


class FetchUrlRequest(BaseModel):
    """Request model for fetching HTML from URL"""
    url: str


class FetchUrlResponse(BaseModel):
    """Response model for URL fetch"""
    success: bool
    html: Optional[str] = None
    error: Optional[str] = None
    url: Optional[str] = None


@router.post("/build/fetch-url", response_model=FetchUrlResponse)
async def fetch_html_from_url(data: FetchUrlRequest):
    """
    Fetch HTML content from a given URL.

    This endpoint acts as a proxy to bypass CORS restrictions.
    It fetches the HTML from the provided URL and returns it.
    """
    try:
        url = data.url.strip()

        # Validate URL
        if not url:
            return FetchUrlResponse(
                success=False,
                error="URL is required"
            )

        # Add protocol if missing
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        logger.info(f"Fetching HTML from URL: {url}")

        # Fetch the HTML
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                }
            )

            if response.status_code != 200:
                return FetchUrlResponse(
                    success=False,
                    error=f"Failed to fetch URL: HTTP {response.status_code}"
                )

            html = response.text

            # Basic validation that it looks like HTML
            if not html or '<' not in html:
                return FetchUrlResponse(
                    success=False,
                    error="Response does not appear to be valid HTML"
                )

            logger.info(f"Successfully fetched HTML from {url}, size: {len(html)} bytes")

            return FetchUrlResponse(
                success=True,
                html=html,
                url=url
            )

    except httpx.TimeoutException:
        logger.error(f"Timeout fetching URL: {data.url}")
        return FetchUrlResponse(
            success=False,
            error="Request timed out. The website might be slow or unavailable."
        )
    except httpx.RequestError as e:
        logger.error(f"Request error fetching URL: {str(e)}")
        return FetchUrlResponse(
            success=False,
            error=f"Failed to connect: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error fetching URL: {str(e)}")
        return FetchUrlResponse(
            success=False,
            error=str(e)
        )
