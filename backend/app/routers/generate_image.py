"""
AI Image generation router - FastAPI version
Migrated from: frontend/app/api/generate-image/route.ts
Uses OpenRouter with Gemini 3 Pro Image for native image generation
"""
import httpx
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

router = APIRouter()


class GenerateImageRequest(BaseModel):
    apiKey: str  # OpenRouter API key
    prompt: str
    width: int = 1024
    height: int = 1024
    style: str = "professional"


class GenerateImageResponse(BaseModel):
    success: bool
    status: str = "completed"
    imageUrl: Optional[str] = None
    error: Optional[str] = None


@router.post("/generate-image", response_model=GenerateImageResponse)
async def generate_image(request: GenerateImageRequest):
    """
    Generate an image using OpenRouter with Gemini 3 Pro Image.
    Migrated from: frontend/app/api/generate-image/route.ts
    """
    if not request.apiKey:
        raise HTTPException(status_code=400, detail="OpenRouter API key is required")
    
    if not request.prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")
    
    # Enhance prompt for email-appropriate images
    enhanced_prompt = f"Generate an image: {request.prompt}. Style: {request.style}, professional quality, suitable for email marketing, clean composition, high resolution, photorealistic"
    
    # Determine aspect ratio based on dimensions
    ratio = request.width / request.height
    if ratio >= 1.7:
        aspect_ratio = "16:9"
    elif ratio >= 1.4:
        aspect_ratio = "3:2"
    elif ratio >= 1.2:
        aspect_ratio = "4:3"
    elif ratio <= 0.6:
        aspect_ratio = "9:16"
    elif ratio <= 0.7:
        aspect_ratio = "2:3"
    elif ratio <= 0.85:
        aspect_ratio = "3:4"
    else:
        aspect_ratio = "1:1"
    
    print(f"Calling OpenRouter for image generation with Gemini 3 Pro Image")
    print(f"Aspect ratio: {aspect_ratio}")
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {request.apiKey}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:3000",
                    "X-Title": "Email Forge",
                },
                json={
                    "model": "google/gemini-3-pro-image-preview",
                    "messages": [
                        {
                            "role": "user",
                            "content": enhanced_prompt,
                        }
                    ],
                    "modalities": ["image", "text"],
                    "image_config": {
                        "aspect_ratio": aspect_ratio,
                    },
                }
            )
            
            if response.status_code == 401:
                raise HTTPException(status_code=401, detail="OpenRouter API key is invalid or expired")
            if response.status_code == 402:
                raise HTTPException(status_code=402, detail="Insufficient credits on OpenRouter account")
            if response.status_code == 429:
                raise HTTPException(status_code=429, detail="Rate limit exceeded. Please try again later.")
            
            if response.status_code != 200:
                error_text = response.text
                print(f"OpenRouter Image API error: {response.status_code} {error_text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"OpenRouter error ({response.status_code}): {error_text[:200]}"
                )
            
            data = response.json()
            print("OpenRouter image response received")
            
            # Extract image from response
            message = data.get("choices", [{}])[0].get("message", {})
            
            # Check message.images array (OpenRouter format for Gemini image generation)
            if message.get("images") and len(message["images"]) > 0:
                image_url = message["images"][0].get("image_url", {}).get("url")
                if image_url:
                    return GenerateImageResponse(
                        success=True,
                        status="completed",
                        imageUrl=image_url,
                    )
            
            # Alternative: Check content array for image parts
            content = message.get("content")
            if content and isinstance(content, list):
                for part in content:
                    if part.get("type") == "image_url" and part.get("image_url", {}).get("url"):
                        return GenerateImageResponse(
                            success=True,
                            status="completed",
                            imageUrl=part["image_url"]["url"],
                        )
            
            # Check if content is a string with base64 data
            if content and isinstance(content, str) and content.startswith("data:image"):
                return GenerateImageResponse(
                    success=True,
                    status="completed",
                    imageUrl=content,
                )
            
            print(f"Unexpected response format: {data}")
            raise HTTPException(
                status_code=500,
                detail="No image found in response. The model may not have generated an image."
            )
            
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Image generation timed out")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Image generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Image generation failed: {str(e)}")


@router.get("/generate-image")
async def generate_image_info():
    """GET endpoint not needed - Gemini generates synchronously."""
    return {"error": "Use POST to generate images. Gemini generates synchronously."}
