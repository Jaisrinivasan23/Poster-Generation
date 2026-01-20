"""
OpenRouter API Client
Handles AI generation via OpenRouter (Gemini models)
"""
import httpx
import base64
from typing import Optional, Dict, Any
from app.config import settings


async def call_openrouter(
    model: str,
    system_prompt: str,
    user_prompt: str,
    reference_image: Optional[str] = None,
    max_tokens: int = 12000
) -> str:
    """
    Call OpenRouter API for text/HTML generation

    Args:
        model: Model ID (e.g., "google/gemini-3-pro-preview")
        system_prompt: System prompt
        user_prompt: User prompt
        reference_image: Optional base64 data URL for reference
        max_tokens: Maximum tokens to generate

    Returns:
        Generated text/HTML
    """
    # Build message content
    content = []

    # Add reference image first if provided
    if reference_image and reference_image.startswith("data:image/"):
        content.append({
            "type": "image_url",
            "image_url": {"url": reference_image}
        })

    # Add text prompt
    content.append({
        "type": "text",
        "text": user_prompt
    })

    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content if len(content) > 1 else user_prompt}
        ]
    }

    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": settings.base_url,
        "X-Title": "Poster Creator"
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            json=payload,
            headers=headers
        )

        if not response.is_success:
            error_text = response.text
            if response.status_code == 401:
                raise Exception("OpenRouter API key is invalid or expired")
            elif response.status_code == 402:
                raise Exception("OpenRouter account has insufficient credits")
            elif response.status_code == 429:
                raise Exception("OpenRouter rate limit exceeded. Please try again later")
            elif response.status_code == 413:
                raise Exception("Request too large. Try using a smaller reference image")
            else:
                raise Exception(f"OpenRouter API error ({response.status_code}): {error_text}")

        data = response.json()
        return data["choices"][0]["message"]["content"]


async def call_openrouter_for_image(
    system_prompt: str,
    user_prompt: str,
    dimensions: Dict[str, int],
    reference_image: Optional[str] = None,
    profile_pic_url: Optional[str] = None
) -> Dict[str, str]:
    """
    Call OpenRouter API for direct image generation (Gemini 2.5 Flash Image)

    Args:
        system_prompt: System prompt
        user_prompt: User prompt
        dimensions: Image dimensions {width, height}
        reference_image: Optional reference template
        profile_pic_url: Optional profile picture URL

    Returns:
        Dict with imageUrl and optionally imageData
    """
    content = []

    # Add reference image first
    if reference_image and reference_image.startswith("data:image/"):
        content.append({
            "type": "image_url",
            "image_url": {"url": reference_image}
        })

    # Add profile picture
    if profile_pic_url:
        # Fetch and convert to data URL
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(profile_pic_url)
                if response.is_success:
                    image_data = base64.b64encode(response.content).decode()
                    content_type = response.headers.get("content-type", "image/png")
                    profile_data_url = f"data:{content_type};base64,{image_data}"
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": profile_data_url}
                    })

                    # Enhance prompt to use profile picture
                    user_prompt += '\n\nCRITICAL: Include the circular profile picture in the final poster (typically bottom-right or top-left corner, ~80-120px diameter).'
        except Exception as e:
            print(f"Warning: Failed to fetch profile picture: {e}")

    # Add text prompt
    content.append({
        "type": "text",
        "text": user_prompt
    })

    # Calculate aspect ratio
    aspect_ratio = "1:1" if dimensions["width"] == dimensions["height"] else f"{dimensions['width']}:{dimensions['height']}"

    payload = {
        "model": "google/gemini-2.5-flash-image",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content}
        ]
    }

    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": settings.base_url,
        "X-Title": "Poster Creator"
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            json=payload,
            headers=headers
        )

        if not response.is_success:
            raise Exception(f"OpenRouter image generation error: {response.status_code} - {response.text}")

        data = response.json()
        message = data["choices"][0]["message"]

        # Check for images array (OpenRouter format)
        if message.get("images") and isinstance(message["images"], list):
            img = message["images"][0]
            if img.get("image_url", {}).get("url"):
                return {"imageUrl": img["image_url"]["url"], "imageData": img["image_url"]["url"]}

        # Check for parts.inline_data (Gemini format)
        if message.get("parts") and isinstance(message["parts"], list):
            for part in message["parts"]:
                if part.get("inline_data", {}).get("data") and part.get("inline_data", {}).get("mime_type"):
                    mime_type = part["inline_data"]["mime_type"]
                    base64_data = part["inline_data"]["data"]
                    data_url = f"data:{mime_type};base64,{base64_data}"
                    return {"imageUrl": data_url, "imageData": data_url}

        # Check message.content
        if message.get("content"):
            content = message["content"]
            if isinstance(content, str) and content.startswith("data:image/"):
                return {"imageUrl": content, "imageData": content}

        raise Exception("No image data found in OpenRouter response")


async def fetch_image_as_data_url(image_url: str) -> Optional[str]:
    """
    Fetch image from URL and convert to base64 data URL

    Args:
        image_url: Image URL

    Returns:
        Base64 data URL or None if failed
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(image_url)
            if not response.is_success:
                return None

            # Get content type
            content_type = response.headers.get("content-type", "")

            # Detect from URL if content-type is generic
            if not content_type or content_type in ["binary/octet-stream", "application/octet-stream"]:
                url_lower = image_url.lower()
                if ".jpg" in url_lower or ".jpeg" in url_lower:
                    content_type = "image/jpeg"
                elif ".png" in url_lower:
                    content_type = "image/png"
                elif ".gif" in url_lower:
                    content_type = "image/gif"
                elif ".webp" in url_lower:
                    content_type = "image/webp"
                else:
                    content_type = "image/png"

            # Ensure content_type is valid
            if not content_type.startswith("image/"):
                content_type = "image/png"

            # Convert to base64
            base64_data = base64.b64encode(response.content).decode()
            return f"data:{content_type};base64,{base64_data}"

    except Exception as e:
        print(f"Failed to fetch image: {e}")
        return None
