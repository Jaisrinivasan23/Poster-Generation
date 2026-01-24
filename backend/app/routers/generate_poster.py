"""
Generate Poster Router
POST /api/generate-poster - Generate poster with AI (single or carousel)

Uses 3-strategy approach:
- Strategy A: Reference-Faithful (match reference exactly)
- Strategy B: Reference-Remix (creative interpretation)
- Strategy C: AI Creative Director (content-aware design)

Migrated from Next.js TypeScript - exact same logic and prompts.
"""
from fastapi import APIRouter, HTTPException
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
from datetime import datetime
import json
import asyncio

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


async def get_creative_direction(
    model: str,
    prompt: str
) -> dict | None:
    """
    Get creative direction from AI Creative Director

    Args:
        model: Model ID
        prompt: User's prompt

    Returns:
        Creative direction JSON or None if failed
    """
    try:
        print("🎨 Getting creative direction from AI...")

        user_prompt = f"""Analyze this poster/carousel request and provide creative direction:

"{prompt}"

Return ONLY a valid JSON object with your creative direction. No explanation, just JSON."""

        response = await call_openrouter(
            model=model,
            system_prompt=CREATIVE_DIRECTOR_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            reference_image=None,
            max_tokens=2000
        )

        # Parse JSON from response
        # Try to find JSON object in response
        start_idx = response.find('{')
        end_idx = response.rfind('}') + 1

        if start_idx != -1 and end_idx > start_idx:
            json_str = response[start_idx:end_idx]
            direction = json.loads(json_str)
            print(f"✅ Creative direction received: {direction.get('contentType', 'unknown')}")
            return direction

        print("⚠️ Could not parse creative direction JSON")
        return None

    except Exception as e:
        print(f"❌ Creative direction failed: {e}")
        return None


@router.post("/generate-poster", response_model=GeneratePosterResponse)
async def generate_poster(request: GeneratePosterRequest):
    """
    Generate poster with AI using 3-strategy approach

    Strategies:
    - A (reference-faithful): Match reference image exactly
    - B (reference-remix): Creative interpretation of reference
    - C (ai-creative-director): Content-aware design (no reference needed)

    Supports:
    - Single poster generation (3 variants)
    - Carousel generation (preview first slides only)
    - HTML generation mode
    - Reference image support
    """
    try:
        config = request.config

        # Fetch Topmate profile
        try:
            profile = await fetch_topmate_profile(config.topmateUsername)
        except Exception as e:
            raise HTTPException(
                status_code=404,
                detail=f"Failed to fetch Topmate profile for '{config.topmateUsername}'. Please check the username."
            )

        # Get dimensions
        if config.size == "custom" and config.customDimensions:
            dimensions = config.customDimensions
        else:
            dim = POSTER_SIZE_DIMENSIONS.get(
                config.size,
                POSTER_SIZE_DIMENSIONS["instagram-square"]
            )
            dimensions = PosterDimensions(width=dim["width"], height=dim["height"])

        # Select model (force flash for expert mode)
        if request.userMode == "expert":
            model_id = "google/gemini-3-flash-preview"
            print(f"🎨 Expert mode: Using {model_id}")
        else:
            model_id = (
                "google/gemini-3-flash-preview"
                if request.model == "flash"
                else "google/gemini-3-pro-preview"
            )
            print(f"🎨 Admin mode: Using {model_id}")

        # Prepare strategies
        # Get creative direction for Strategy C (in parallel with A & B)
        creative_direction = None
        if not request.referenceImage:
            # Only run creative director if no reference image
            creative_direction = await get_creative_direction(
                model=model_id,
                prompt=config.prompt
            )

        # Build strategies list (both expert and admin use all 3 strategies)
        strategies = []
        for idx, strategy_template in enumerate(POSTER_STRATEGIES):
            strategy = strategy_template.copy()

            # For Strategy C (ai-creative-director), fill in the directive
            if strategy["name"] == "ai-creative-director":
                if creative_direction:
                    strategy["directive"] = build_creative_directive(creative_direction)
                else:
                    strategy["directive"] = FALLBACK_CREATIVE_DIRECTIVE

            strategies.append(strategy)

        # Generate 3 variants (both expert and admin modes)
        posters = []
        has_reference = bool(request.referenceImage)
        total_variants = len(strategies)

        for variant_idx, strategy in enumerate(strategies):
            try:
                # Strategy A & B use reference image (if provided)
                # Strategy C doesn't use reference
                use_reference = has_reference and strategy["type"] == "reference"

                # Build user prompt
                user_prompt = f"""POSTER DIMENSIONS: {dimensions.width}px × {dimensions.height}px

USER'S PROMPT (this is what matters):
"{config.prompt}"

CREATOR BRANDING (for subtle attribution only):
- Name: {profile.display_name}
- Photo URL: {profile.profile_pic}
- Handle: @{profile.username}

CONTEXT DATA (use only if prompt specifically needs it):
- Bio: {profile.bio}
- Stats: {profile.total_bookings} bookings, {profile.average_rating}/5 rating"""

                # Add top services if available
                if profile.services:
                    top_services = profile.services[:3]
                    services_text = "\n".join(f"- {s.title}" for s in top_services)
                    user_prompt += f"\n- Services:\n{services_text}"

                # Add strategy directive
                user_prompt += f"\n\nSTYLE DIRECTION: {strategy['directive']}\n\n"

                if use_reference:
                    user_prompt += """REFERENCE IMAGE PROVIDED: I've attached a reference image. Use it ONLY as VISUAL STYLE inspiration:
- Color palette and mood
- Typography style (fonts, sizing, weight) - NOT the actual text
- Layout structure and composition
- Visual effects and textures

⚠️ CRITICAL: Do NOT copy any text, brand names, logos, slogans, or specific content from the reference image. The reference is for AESTHETIC DIRECTION only."""

                user_prompt += "\n\nGenerate the HTML poster. Be creative with patterns, gradients, SVG, typography. Output only HTML starting with <!DOCTYPE html>"

                # Call OpenRouter
                print(f"🎨 Generating variant {variant_idx + 1}/{total_variants} ({strategy['name']})...")
                html = await call_openrouter(
                    model=model_id,
                    system_prompt=POSTER_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    reference_image=request.referenceImage if use_reference else None,
                    max_tokens=12000
                )

                # Clean HTML
                html = html.replace("```html\n", "").replace("```html", "")
                html = html.replace("```\n", "").replace("```", "").strip()

                # Find <!DOCTYPE if not at start
                if not html.startswith("<!DOCTYPE"):
                    idx = html.find("<!DOCTYPE")
                    if idx != -1:
                        html = html[idx:]

                poster = GeneratedPoster(
                    generationMode="html",
                    html=html,
                    dimensions=dimensions,
                    style=config.style,
                    topmateProfile=profile,
                    generatedAt=datetime.utcnow().isoformat(),
                    variantIndex=variant_idx,
                    strategyName=strategy["name"]
                )

                posters.append(poster)
                print(f"✅ Variant {variant_idx + 1}/{total_variants} generated successfully")

            except Exception as e:
                print(f"❌ Variant {variant_idx + 1} ({strategy['name']}) failed: {e}")
                continue

        if not posters:
            raise HTTPException(
                status_code=500,
                detail="All poster generations failed. Please try again."
            )

        print(f"🎉 Generated {len(posters)}/{total_variants} variants successfully")

        return GeneratePosterResponse(
            success=True,
            posters=posters,
            mode="single"
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Poster generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
