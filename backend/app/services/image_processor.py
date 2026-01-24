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
    base_image_bytes: bytes,
    topmate_logo: Optional[str],
    profile_image: Optional[str]
) -> bytes:
    """
    Overlay logo and profile picture on base image

    Args:
        base_image_bytes: Base image as bytes
        topmate_logo: Topmate logo as data URL (optional)
        profile_image: Profile picture as data URL (optional)

    Returns:
        Composited image as bytes
    """
    print("[OVERLAY] Starting image composition")

    # Load base image from bytes
    base_image = Image.open(io.BytesIO(base_image_bytes))

    # Convert to RGBA
    base_image = base_image.convert("RGBA")
    dimensions = {"width": base_image.width, "height": base_image.height}

    # Add logo overlay (top-right corner)
    if topmate_logo:
        print("[OVERLAY] Adding Topmate logo")
        try:
            if topmate_logo.startswith("data:"):
                logo_data = base64.b64decode(topmate_logo.split(",", 1)[1])
                logo_image = Image.open(io.BytesIO(logo_data))
            else:
                async with httpx.AsyncClient() as client:
                    response = await client.get(topmate_logo)
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
    if profile_image:
        print("[OVERLAY] Adding profile picture")
        try:
            # Parse profile picture from data URL
            if profile_image.startswith("data:"):
                profile_data = base64.b64decode(profile_image.split(",", 1)[1])
                profile_img = Image.open(io.BytesIO(profile_data))
            else:
                # Fetch from URL
                async with httpx.AsyncClient() as client:
                    response = await client.get(profile_image)
                    profile_img = Image.open(io.BytesIO(response.content))

            # Create circular mask
            size = 100  # Profile picture diameter
            profile_img = profile_img.resize((size, size), Image.Resampling.LANCZOS)
            profile_img = profile_img.convert("RGBA")

            # Create circular mask
            mask = Image.new("L", (size, size), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, size, size), fill=255)

            # Apply mask
            circular_profile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            circular_profile.paste(profile_img, (0, 0))
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

    # Convert to PNG bytes
    buffer = io.BytesIO()
    base_image.convert("RGB").save(buffer, format="PNG")
    buffer.seek(0)

    print("[OVERLAY] Image composition complete")
    return buffer.getvalue()


def replace_placeholders(html: str, data: Dict[str, any], columns: Optional[list[str]] = None) -> str:
    """
    Replace placeholders in HTML with actual data
    Also handles showing/hiding elements based on placeholder values

    Args:
        html: HTML template with placeholders like {column_name}
        data: Data dictionary
        columns: List of column names (if None, uses all keys from data dict)

    Returns:
        HTML with placeholders replaced
    """
    import re

    result = html

    # If columns not provided, use all keys from data dict
    if columns is None:
        columns = list(data.keys())

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
