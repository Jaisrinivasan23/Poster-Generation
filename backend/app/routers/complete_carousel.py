"""
Complete Carousel Router
POST /api/complete-carousel - Generate remaining slides for a carousel

Takes a first slide HTML and generates the remaining slides
to match the visual style and continue the content logically.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from app.services.openrouter_client import call_openrouter
from datetime import datetime
import json
import re


router = APIRouter()


# Poster size dimensions mapping
POSTER_SIZE_DIMENSIONS = {
    "instagram-square": {"width": 1080, "height": 1080},
    "instagram-portrait": {"width": 1080, "height": 1350},
    "instagram-story": {"width": 1080, "height": 1920},
    "linkedin-post": {"width": 1200, "height": 1200},
    "twitter-post": {"width": 1200, "height": 675},
    "facebook-post": {"width": 1200, "height": 630},
    "a4-portrait": {"width": 2480, "height": 3508}
}


# System prompt for completing remaining carousel slides
CAROUSEL_COMPLETION_SYSTEM_PROMPT = """You complete a carousel by generating the remaining slides to match an existing first slide.

## YOUR TASK
Given a first slide and topic, create the remaining slides that:
1. Match the EXACT visual style of slide 1 (fonts, colors, backgrounds, effects)
2. Continue the content logically
3. End with a strong conclusion

## SLIDE STRUCTURE
- Given: Slide 1 (hook/intro)
- Generate: Slides 2 to N
  - Middle slides: Key points, one idea per slide
  - Last slide: Conclusion/takeaway

## RULES
1. **USE ACTUAL DATABASE DATA** - If database records are provided below, use the EXACT data consistently across all slides
2. EXACT same visual style as slide 1
3. Same fonts, colors, backgrounds
4. Same branding placement
5. One idea per slide - mobile readable
6. Return JSON array of HTML strings (slides 2 to N only)"""


class ProfileData(BaseModel):
    """Profile data for carousel branding"""
    display_name: str
    username: str
    profile_pic: str


class GeneratedCarouselSlide(BaseModel):
    """Generated carousel slide output"""
    generationMode: str = "html"
    html: str
    dimensions: Dict[str, int]
    style: str = "professional"
    topmateProfile: Dict[str, Any]
    generatedAt: str
    slideIndex: int
    variantIndex: int


class CompleteCarouselRequest(BaseModel):
    """Request body for complete-carousel endpoint"""
    firstSlide: str  # The selected first slide HTML
    prompt: str  # Original prompt
    profile: ProfileData  # Profile data for branding
    totalSlides: Optional[int] = 5  # Total number of slides
    variantIndex: Optional[int] = 0  # Which variant was selected
    size: Optional[str] = "instagram-square"  # Poster size
    selectedRecords: Optional[List[Dict[str, Any]]] = None  # Database records from MCP


class CompleteCarouselResponse(BaseModel):
    """Response body for complete-carousel endpoint"""
    success: bool
    slides: Optional[List[GeneratedCarouselSlide]] = None
    slideCount: Optional[int] = None
    error: Optional[str] = None


def format_data_for_carousel(records: List[Dict[str, Any]], table_name: str) -> str:
    """Format database records for inclusion in carousel prompt"""
    if not records:
        return ""
    
    text = f"\n\n## DATABASE RECORDS FROM '{table_name}' TABLE\n"
    text += "Use this ACTUAL data in your carousel slides:\n\n"
    
    for i, record in enumerate(records):
        text += f"### Record {i + 1}:\n"
        for key, value in record.items():
            if key != "_table" and value is not None:
                text += f"- {key}: {value}\n"
        text += "\n"
    
    return text


def build_completion_prompt(
    first_slide_html: str,
    prompt: str,
    profile: ProfileData,
    dimensions: Dict[str, int],
    total_slides: int,
    selected_records: Optional[List[Dict[str, Any]]] = None
) -> str:
    """Build the completion prompt for remaining slides"""
    text = f"""FIRST SLIDE HTML (match this style exactly):
```html
{first_slide_html}
```

CAROUSEL TOPIC: "{prompt}"

CREATOR BRANDING (same placement as slide 1):
- Name: {profile.display_name}
- Photo: {profile.profile_pic}
- Handle: @{profile.username}"""

    # Add database data context if available
    if selected_records and len(selected_records) > 0:
        table_name = selected_records[0].get("_table", "unknown") if selected_records else "unknown"
        text += format_data_for_carousel(selected_records, table_name)

    text += f"""

Generate slides 2 through {total_slides}. Each slide is {dimensions['width']}x{dimensions['height']}px.
- Slides 2-{total_slides - 1}: Key points/content
- Slide {total_slides}: Conclusion

Return a JSON array with {total_slides - 1} HTML strings:
["<!DOCTYPE html>...", "<!DOCTYPE html>...", ...]"""

    return text


def clean_html(html: str) -> str:
    """Clean HTML response from markdown code blocks"""
    html = html.replace("```html\n", "").replace("```html", "")
    html = html.replace("```\n", "").replace("```", "").strip()
    
    if not html.startswith("<!DOCTYPE"):
        idx = html.find("<!DOCTYPE")
        if idx != -1:
            html = html[idx:]
    
    return html


@router.post("/complete-carousel", response_model=CompleteCarouselResponse)
async def complete_carousel(request: CompleteCarouselRequest):
    """
    Complete a carousel by generating remaining slides.
    
    Takes the selected first slide HTML and generates slides 2-N
    that match the visual style and continue the content logically.
    
    Returns array of all slides (including the first slide).
    """
    try:
        # Validate required fields
        if not request.firstSlide or not request.prompt or not request.profile:
            raise HTTPException(
                status_code=400,
                detail="Missing required fields: firstSlide, prompt, profile"
            )
        
        # Get dimensions from size
        dimensions = POSTER_SIZE_DIMENSIONS.get(
            request.size,
            POSTER_SIZE_DIMENSIONS["instagram-square"]
        )
        
        slide_count = request.totalSlides or 5
        
        # Use Gemini Pro for carousel completion
        model = "google/gemini-3-pro-preview"
        
        # Build completion prompt
        completion_prompt = build_completion_prompt(
            first_slide_html=request.firstSlide,
            prompt=request.prompt,
            profile=request.profile,
            dimensions=dimensions,
            total_slides=slide_count,
            selected_records=request.selectedRecords
        )
        
        print(f"🎠 Completing carousel with {slide_count - 1} remaining slides...")
        
        # Call OpenRouter for remaining slides
        response = await call_openrouter(
            model=model,
            system_prompt=CAROUSEL_COMPLETION_SYSTEM_PROMPT,
            user_prompt=completion_prompt,
            reference_image=None,
            max_tokens=20000
        )
        
        # Parse the response as JSON array
        remaining_slides: List[str] = []
        
        try:
            # Try to extract JSON array from response
            json_match = re.search(r'\[[\s\S]*\]', response)
            if json_match:
                remaining_slides = json.loads(json_match.group(0))
            else:
                raise ValueError("No JSON array found")
        except (json.JSONDecodeError, ValueError):
            # Fallback: split by DOCTYPE
            parts = re.split(r'(?=<!DOCTYPE)', response, flags=re.IGNORECASE)
            parts = [p for p in parts if p.strip().startswith("<!DOCTYPE")]
            remaining_slides = [clean_html(p) for p in parts]
        
        # Clean all slides
        remaining_slides = [clean_html(h) for h in remaining_slides]
        
        if not remaining_slides:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate remaining slides"
            )
        
        print(f"✅ Generated {len(remaining_slides)} remaining slides")
        
        # Create profile dict for response
        profile_dict = {
            "display_name": request.profile.display_name,
            "username": request.profile.username,
            "profile_pic": request.profile.profile_pic,
        }
        
        # Combine first slide + remaining slides
        all_slides: List[GeneratedCarouselSlide] = [
            GeneratedCarouselSlide(
                generationMode="html",
                html=request.firstSlide,
                dimensions=dimensions,
                style="professional",
                topmateProfile=profile_dict,
                generatedAt=datetime.utcnow().isoformat(),
                slideIndex=0,
                variantIndex=request.variantIndex or 0
            )
        ]
        
        # Add remaining slides
        for index, html in enumerate(remaining_slides):
            all_slides.append(
                GeneratedCarouselSlide(
                    generationMode="html",
                    html=html,
                    dimensions=dimensions,
                    style="professional",
                    topmateProfile=profile_dict,
                    generatedAt=datetime.utcnow().isoformat(),
                    slideIndex=index + 1,
                    variantIndex=request.variantIndex or 0
                )
            )
        
        print(f"🎉 Carousel complete with {len(all_slides)} total slides")
        
        return CompleteCarouselResponse(
            success=True,
            slides=all_slides,
            slideCount=len(all_slides)
        )
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"❌ Carousel completion error: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        return CompleteCarouselResponse(
            success=False,
            error=str(e)
        )
