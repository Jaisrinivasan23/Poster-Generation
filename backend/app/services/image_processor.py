"""
Image Processing Service
Handles image overlay using Pillow (Sharp equivalent in Python)
"""
import io
import base64
import httpx
from PIL import Image, ImageDraw
from typing import Optional, Dict


async def overlay_logo_and_profile(
    base_image_url: str,
    logo_url: Optional[str],
    profile_pic_url: Optional[str],
    dimensions: Dict[str, int]
) -> str:
    """
    Overlay logo and profile picture on base image

    Args:
        base_image_url: Base image as data URL or HTTP URL
        logo_url: Topmate logo as data URL (optional)
        profile_pic_url: Profile picture URL (optional)
        dimensions: Image dimensions {width, height}

    Returns:
        Composited image as data URL
    """
    print("[OVERLAY] Starting image composition")

    # Load base image
    if base_image_url.startswith("data:image/"):
        # Parse data URL
        base64_data = base_image_url.split(",", 1)[1]
        image_data = base64.b64decode(base64_data)
        base_image = Image.open(io.BytesIO(image_data))
    else:
        # Fetch from URL
        async with httpx.AsyncClient() as client:
            response = await client.get(base_image_url)
            base_image = Image.open(io.BytesIO(response.content))

    # Resize to target dimensions
    base_image = base_image.resize((dimensions["width"], dimensions["height"]), Image.Resampling.LANCZOS)
    base_image = base_image.convert("RGBA")

    # Add logo overlay (top-right corner)
    if logo_url:
        print("[OVERLAY] Adding Topmate logo")
        try:
            if logo_url.startswith("data:"):
                logo_data = base64.b64decode(logo_url.split(",", 1)[1])
                logo_image = Image.open(io.BytesIO(logo_data))
            else:
                async with httpx.AsyncClient() as client:
                    response = await client.get(logo_url)
                    logo_image = Image.open(io.BytesIO(response.content))

            # Resize logo to 70px width (maintain aspect ratio)
            logo_aspect = logo_image.height / logo_image.width
            logo_width = 70
            logo_height = int(logo_width * logo_aspect)
            logo_image = logo_image.resize((logo_width, logo_height), Image.Resampling.LANCZOS)
            logo_image = logo_image.convert("RGBA")

            # Position in top-right with 20px padding
            logo_position = (dimensions["width"] - logo_width - 20, 20)
            base_image.paste(logo_image, logo_position, logo_image)
            print("[OVERLAY] Logo added at top-right")

        except Exception as e:
            print(f"[OVERLAY] Failed to add logo: {e}")

    # Add profile picture overlay (bottom-left corner, circular)
    if profile_pic_url:
        print("[OVERLAY] Adding profile picture")
        try:
            # Fetch profile picture
            async with httpx.AsyncClient() as client:
                response = await client.get(profile_pic_url)
                profile_image = Image.open(io.BytesIO(response.content))

            # Create circular mask
            size = 100  # Profile picture diameter
            profile_image = profile_image.resize((size, size), Image.Resampling.LANCZOS)
            profile_image = profile_image.convert("RGBA")

            # Create circular mask
            mask = Image.new("L", (size, size), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, size, size), fill=255)

            # Apply mask
            circular_profile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            circular_profile.paste(profile_image, (0, 0))
            circular_profile.putalpha(mask)

            # Add white border (3px)
            border_size = 3
            border_image = Image.new("RGBA", (size + border_size * 2, size + border_size * 2), (255, 255, 255, 255))
            border_mask = Image.new("L", (size + border_size * 2, size + border_size * 2), 0)
            border_draw = ImageDraw.Draw(border_mask)
            border_draw.ellipse((0, 0, size + border_size * 2, size + border_size * 2), fill=255)
            border_image.putalpha(border_mask)

            # Paste circular profile on border
            border_image.paste(circular_profile, (border_size, border_size), circular_profile)

            # Position in bottom-left with 20px padding
            profile_position = (20, dimensions["height"] - size - border_size * 2 - 20)
            base_image.paste(border_image, profile_position, border_image)
            print("[OVERLAY] Profile picture added at bottom-left")

        except Exception as e:
            print(f"[OVERLAY] Failed to add profile picture: {e}")

    # Convert to PNG data URL
    buffer = io.BytesIO()
    base_image.convert("RGB").save(buffer, format="PNG")
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.getvalue()).decode()
    data_url = f"data:image/png;base64,{image_base64}"

    print("[OVERLAY] Image composition complete")
    return data_url


def replace_placeholders(html: str, data: Dict[str, any], columns: list[str]) -> str:
    """
    Replace placeholders in HTML with actual data
    Also handles showing/hiding elements based on placeholder values

    Args:
        html: HTML template with placeholders like {column_name}
        data: Data dictionary
        columns: List of column names

    Returns:
        HTML with placeholders replaced
    """
    import re

    result = html

    # Replace each placeholder
    for col in columns:
        placeholder = f"{{{col}}}"
        value = str(data.get(col, ""))

        # Replace the placeholder
        result = result.replace(placeholder, value)

        # Special handling for image placeholders (like profile_pic)
        if col.lower() in ['profile_pic', 'profile_picture', 'avatar', 'image', 'photo']:
            if value and value.strip():
                # If placeholder has a value, show the image (remove display: none)
                result = re.sub(
                    r'(<img[^>]*id=["\']?profilePic["\']?[^>]*)(style=["\'][^"\']*display\s*:\s*none[^"\']*["\'])',
                    r'\1style=""',
                    result,
                    flags=re.IGNORECASE
                )
                # Hide the placeholder div
                result = re.sub(
                    r'(<div[^>]*id=["\']?placeholder["\']?[^>]*)(>)',
                    r'\1 style="display: none;">',
                    result,
                    flags=re.IGNORECASE
                )

    # Remove all <script> tags to prevent JavaScript interference
    result = re.sub(r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', '', result, flags=re.IGNORECASE)

    return result
