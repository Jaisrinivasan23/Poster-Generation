"""
Storage Service
Handles S3 uploads and local file storage
"""
import boto3
import io
import base64
from typing import Optional, Dict
from app.config import settings


def is_s3_configured() -> bool:
    """Check if S3 credentials are configured"""
    return bool(
        settings.aws_s3_bucket and
        settings.aws_access_key_id and
        settings.aws_secret_access_key
    )


async def upload_to_s3(file_content: bytes, filename: str) -> str:
    """
    Upload file to S3

    Args:
        file_content: File content as bytes
        filename: Filename

    Returns:
        S3 URL
    """
    if not is_s3_configured():
        raise Exception("S3 is not configured")

    s3_client = boto3.client(
        "s3",
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_region
    )

    # Upload to S3
    s3_client.put_object(
        Bucket=settings.aws_s3_bucket,
        Key=filename,
        Body=file_content,
        ContentType="image/png"
    )

    # Return public URL
    return f"{settings.s3_base_url}/{filename}"


def data_url_to_bytes(data_url: str) -> bytes:
    """
    Convert data URL to bytes

    Args:
        data_url: Data URL (data:image/png;base64,...)

    Returns:
        Image bytes
    """
    # Remove data URL prefix
    base64_data = data_url.split(",", 1)[1]
    return base64.b64decode(base64_data)


async def upload_image(image_bytes: bytes = None, data_url: str = None, filename: str = None) -> Dict[str, str]:
    """
    Upload image (to S3 or local storage)

    Args:
        image_bytes: Image as bytes (optional)
        data_url: Image as data URL (optional, used if image_bytes not provided)
        filename: Filename

    Returns:
        Dict with 'url' and 'key' of uploaded image
    """
    # Get bytes from either parameter
    if image_bytes is None:
        if data_url is None:
            raise ValueError("Either image_bytes or data_url must be provided")
        image_bytes = data_url_to_bytes(data_url)

    # Upload to S3
    if is_s3_configured():
        print("    [S3] Uploading to S3...")
        s3_url = await upload_to_s3(image_bytes, filename)
        return {"url": s3_url, "key": filename}
    else:
        # For local development, convert bytes to data URL
        print("    [S3] S3 not configured, returning data URL")
        image_base64 = base64.b64encode(image_bytes).decode()
        local_url = f"data:image/png;base64,{image_base64}"
        return {"url": local_url, "key": filename}
