"""
Storage Service
Handles S3 uploads and local file storage
"""
import boto3
import io
import base64
from typing import Optional
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


async def upload_image(data_url: str, filename: str) -> str:
    """
    Upload image (to S3 or local storage)

    Args:
        data_url: Image as data URL
        filename: Filename

    Returns:
        URL to uploaded image
    """
    # Convert data URL to bytes
    image_bytes = data_url_to_bytes(data_url)

    # Upload to S3
    if is_s3_configured():
        print("    [S3] Uploading to S3...")
        return await upload_to_s3(image_bytes, filename)
    else:
        # For local development, could save to local storage
        # For now, just return the data URL (frontend will handle)
        print("    [S3] S3 not configured, returning data URL")
        return data_url
