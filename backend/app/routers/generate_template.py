"""
Template generation router - FastAPI version
Migrated from: frontend/app/api/generate-template/route.ts
Generates poster templates with dummy profile data for preview
"""
import httpx
import base64
from io import BytesIO
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException
from app.config import settings

router = APIRouter()

# ============================================================================
# CONSTANTS AND PROMPTS - EXACT COPY FROM TYPESCRIPT
# ============================================================================

IMAGE_GENERATION_SYSTEM_PROMPT = """You are an expert image designer creating professional, visually stunning poster templates using Gemini's native image generation capabilities.

Key Requirements:
- Generate images directly (you have native image generation capability)
- Create a template design that demonstrates the requested style
- Use placeholder data (this is a template preview)
- Make designs professional, modern, and visually appealing
- Include space for profile picture in corner

OUTPUT: Generate the image directly. Do not output HTML, code, or text descriptions."""

FALLBACK_CREATIVE_DIRECTIVE = """SMART CONTENT-AWARE DESIGN

Analyze the content and choose the BEST visual approach:

1. IF DATA/NUMBERS → Use visual data representation (charts, large numbers, progress indicators)
2. IF COMPARISON → Use split layout, before/after design
3. IF LIST/TIPS → Use numbered visual hierarchy, icons
4. IF QUOTE → Typography-focused, minimal design
5. IF EVENT → Bold date treatment, urgency design
6. IF EDUCATIONAL → Infographic style, clear hierarchy

Choose one strong color palette:
- Dark premium: #0a0a0a background, white text, one warm accent
- Light minimal: #fafafa background, dark text, one muted accent
- Bold vibrant: Strong background color with contrasting text

Typography: Pick ONE font family. Use weight for hierarchy.
- Headlines: 60-120px for impact
- Body: 18-24px for readability

BRANDING: Creator photo (circular, 40-50px) + name in bottom corner. REQUIRED.

Make it look like a professional designer created it, not an AI."""

# Poster size dimensions
POSTER_SIZE_DIMENSIONS = {
    "instagram-square": {"width": 1080, "height": 1080},
    "instagram-portrait": {"width": 1080, "height": 1350},
    "instagram-story": {"width": 1080, "height": 1920},
    "twitter-post": {"width": 1200, "height": 675},
    "linkedin-post": {"width": 1200, "height": 627},
    "facebook-post": {"width": 1200, "height": 630},
    "youtube-thumbnail": {"width": 1280, "height": 720},
}


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class TemplateRequest(BaseModel):
    prompt: str
    size: str = "instagram-square"
    model: str = "pro"  # 'pro' or 'flash'
    selectedRecords: Optional[List[Dict[str, Any]]] = None
    referenceImage: Optional[str] = None
    topmateLogo: Optional[str] = None
    openRouterApiKey: Optional[str] = None


class GeneratedTemplate(BaseModel):
    generationMode: str = "image"
    imageUrl: str
    dimensions: Dict[str, int]
    style: str = "professional"
    topmateProfile: Dict[str, Any]
    generatedAt: str
    variantIndex: int
    strategyName: str


class TemplateResponse(BaseModel):
    success: bool
    templates: Optional[List[GeneratedTemplate]] = None
    mode: str = "template"
    variantCount: int = 0
    error: Optional[str] = None


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_dummy_profile() -> Dict[str, Any]:
    """Create a dummy profile for template preview"""
    return {
        "user_id": "demo-user",
        "username": "yourname",
        "display_name": "Your Name",
        "profile_pic": "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=200&h=200&fit=crop&crop=face",
        "bio": "Your professional bio goes here. Describe your expertise and what you offer.",
        "total_bookings": 150,
        "average_rating": 4.9,
        "testimonials_count": 45,
        "services": [
            {"title": "1:1 Consultation", "charge": {"amount": 500}, "booking_count": 50},
            {"title": "Resume Review", "charge": {"amount": 300}, "booking_count": 35},
            {"title": "Career Coaching", "charge": {"amount": 1000}, "booking_count": 25},
        ]
    }


async def call_openrouter_for_image(
    api_key: str,
    system_prompt: str,
    user_prompt: str,
    dimensions: Dict[str, int]
) -> Dict[str, str]:
    """Call OpenRouter for IMAGE generation with Gemini"""
    print("🎨 [TEMPLATE] Calling OpenRouter for image generation")
    
    # Calculate aspect ratio
    width = dimensions["width"]
    height = dimensions["height"]
    if width == height:
        aspect_ratio = "1:1"
    elif width > height:
        aspect_ratio = f"{round(width / height * 10) / 10}:1"
    else:
        aspect_ratio = f"1:{round(height / width * 10) / 10}"
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:3000",
                "X-Title": "Email Forge - Template Image Generation",
            },
            json={
                "model": "google/gemini-2.5-flash-image",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "max_tokens": 2000,
                "temperature": 0.7,
                "image_config": {
                    "aspect_ratio": aspect_ratio,
                    "output_format": "image/png"
                }
            }
        )
        
        if response.status_code != 200:
            error_text = response.text
            print(f"❌ [TEMPLATE] OpenRouter image generation error: {response.status_code} {error_text}")
            raise Exception(f"OpenRouter image generation error: {response.status_code}")
        
        data = response.json()
        message = data.get("choices", [{}])[0].get("message", {})
        
        print(f"📦 [TEMPLATE] Message keys: {list(message.keys())}")
        print(f"📦 [TEMPLATE] Has images?: {'images' in message}")
        
        # Check message.images array (OpenRouter format for Gemini image generation)
        if message.get("images") and isinstance(message["images"], list):
            image_item = message["images"][0]
            if image_item.get("image_url", {}).get("url"):
                image_url = image_item["image_url"]["url"]
                print("✅ [TEMPLATE] Successfully extracted image from message.images")
                print(f"📊 [TEMPLATE] Image URL length: {len(image_url)} chars")
                return {"imageUrl": image_url}
        
        # Fallback: Gemini returns image data in message.parts[].inline_data
        if message.get("parts") and isinstance(message["parts"], list):
            for part in message["parts"]:
                if part.get("inline_data", {}).get("data") and part.get("inline_data", {}).get("mime_type"):
                    mime_type = part["inline_data"]["mime_type"]
                    base64_data = part["inline_data"]["data"]
                    data_url = f"data:{mime_type};base64,{base64_data}"
                    print("✅ [TEMPLATE] Successfully extracted image from parts.inline_data")
                    print(f"📊 [TEMPLATE] Image size: {len(base64_data)} chars, type: {mime_type}")
                    return {"imageUrl": data_url}
        
        # Fallback: check message.content
        content = message.get("content")
        if content:
            if isinstance(content, str):
                if content.startswith("data:image/"):
                    print("✅ [TEMPLATE] Found data URL in content string")
                    return {"imageUrl": content}
                if content.startswith("http://") or content.startswith("https://"):
                    print("✅ [TEMPLATE] Found HTTP URL in content string")
                    return {"imageUrl": content}
            if isinstance(content, list):
                for c in content:
                    if c.get("type") in ["image_url", "image"]:
                        if c.get("image_url", {}).get("url"):
                            print("✅ [TEMPLATE] Found image URL in content array")
                            return {"imageUrl": c["image_url"]["url"]}
                        if c.get("inline_data", {}).get("data"):
                            mime_type = c["inline_data"].get("mime_type", "image/png")
                            data_url = f"data:{mime_type};base64,{c['inline_data']['data']}"
                            print("✅ [TEMPLATE] Found inline_data in content array")
                            return {"imageUrl": data_url}
        
        print("❌ [TEMPLATE] No image found in response")
        raise Exception("No image URL found in response")


async def get_creative_direction(api_key: str, model: str, user_prompt: str) -> Optional[str]:
    """Get Creative Director's vision for variant C"""
    try:
        system_prompt = "You are a Creative Director analyzing a poster design request. Provide strategic design direction."
        user_message = f"""Analyze this poster request and provide design direction:

"{user_prompt}"

Provide a concise creative directive (2-3 paragraphs) covering:
1. Content type and best visual approach
2. Recommended color palette and mood
3. Typography style and hierarchy
4. Special visual elements or effects to use

Be specific and actionable."""

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:3000",
                    "X-Title": "Email Forge - Creative Direction",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    "max_tokens": 500,
                    "temperature": 0.7,
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        return None
    except Exception as e:
        print(f"Creative Director failed, using fallback: {e}")
        return None


def build_creative_directive(direction: str) -> str:
    """Build creative directive from Creative Director's response"""
    return f"""CREATIVE DIRECTOR'S VISION

{direction}

Follow this creative direction while maintaining professional design standards.
BRANDING: Creator photo (circular, 40-50px) + name in bottom corner. REQUIRED."""


# ============================================================================
# API ENDPOINT
# ============================================================================

@router.post("/generate-template", response_model=TemplateResponse)
async def generate_template(request: TemplateRequest):
    """
    Generate poster templates with dummy profile data.
    Migrated from: frontend/app/api/generate-template/route.ts
    """
    try:
        if not request.prompt:
            raise HTTPException(status_code=400, detail="Prompt is required")
        
        # Create dummy profile
        dummy_profile = create_dummy_profile()
        
        # Get dimensions
        dimensions = POSTER_SIZE_DIMENSIONS.get(
            request.size,
            POSTER_SIZE_DIMENSIONS["instagram-square"]
        )
        
        # Use OpenRouter with selected model
        api_key = request.openRouterApiKey or settings.openrouter_api_key
        if not api_key:
            raise HTTPException(status_code=400, detail="OpenRouter API key is required")
        
        model = "google/gemini-3-flash-preview" if request.model == "flash" else "google/gemini-3-pro-preview"
        
        # Get Creative Director's vision
        creative_direction = await get_creative_direction(api_key, model, request.prompt)
        
        # Define strategies
        strategies = [
            {
                "name": "reference-faithful",
                "type": "reference",
                "directive": """REFERENCE IMAGE ANALYSIS - FAITHFUL INTERPRETATION
Study the reference image carefully and create a poster that CAPTURES ITS ESSENCE."""
            },
            {
                "name": "reference-remix",
                "type": "reference",
                "directive": """REFERENCE IMAGE ANALYSIS - CREATIVE REMIX
Study the reference image and create a FRESH INTERPRETATION."""
            },
            {
                "name": "ai-creative-director",
                "type": "creative",
                "directive": build_creative_directive(creative_direction) if creative_direction else FALLBACK_CREATIVE_DIRECTIVE
            }
        ]
        
        # Generate templates
        templates = []
        from datetime import datetime
        
        for index, strategy in enumerate(strategies):
            try:
                print(f"🎨 [TEMPLATE] Generating variant {index + 1} ({strategy['name']})")
                
                # Build simple prompt for image generation
                image_prompt = f"Create a professional poster template for: {request.prompt}\n\n"
                image_prompt += f"Placeholder Data:\n"
                image_prompt += f"- Name: {dummy_profile['display_name']}\n"
                image_prompt += f"- Username: @{dummy_profile['username']}\n"
                image_prompt += f"- Bookings: {dummy_profile['total_bookings']}\n"
                image_prompt += f"- Rating: {dummy_profile['average_rating']}/5\n\n"
                image_prompt += f"Size: {dimensions['width']}x{dimensions['height']}px\n\n"
                
                if strategy["type"] == "reference":
                    style_text = "Clean and professional design" if strategy["name"] == "reference-faithful" else "Creative and bold design"
                    image_prompt += f"Style: {style_text}\n"
                else:
                    image_prompt += "Style: Modern and eye-catching design with strong visual hierarchy\n"
                
                image_prompt += "\nInclude: Large numbers, clear text, profile picture space in corner, professional color scheme."
                
                if request.topmateLogo:
                    image_prompt += "\n\n🔴 CRITICAL: A Topmate logo image has been provided. MUST include this logo in the poster (typically top-right or bottom-left corner, 60-80px size)."
                
                # Generate IMAGE
                image_result = await call_openrouter_for_image(
                    api_key,
                    IMAGE_GENERATION_SYSTEM_PROMPT,
                    image_prompt,
                    dimensions
                )
                
                print(f"✅ [TEMPLATE] Generated variant {index + 1}")
                
                templates.append(GeneratedTemplate(
                    generationMode="image",
                    imageUrl=image_result["imageUrl"],
                    dimensions=dimensions,
                    style="professional",
                    topmateProfile=dummy_profile,
                    generatedAt=datetime.utcnow().isoformat(),
                    variantIndex=index,
                    strategyName=strategy["name"],
                ))
                
            except Exception as err:
                print(f"❌ [TEMPLATE] Strategy {strategy['name']} failed: {err}")
                continue
        
        if not templates:
            raise HTTPException(status_code=500, detail="All template generations failed")
        
        print(f"🎉 [TEMPLATE] Successfully generated {len(templates)} image templates")
        
        return TemplateResponse(
            success=True,
            templates=templates,
            mode="template",
            variantCount=len(templates),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Template generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate template: {str(e)}")
