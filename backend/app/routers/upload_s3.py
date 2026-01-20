"""
S3 upload router - FastAPI version
Migrated from: frontend/app/api/upload-s3/route.ts and frontend/app/api/save-local/route.ts
Both routes do the same thing (upload to S3), so combined into one
"""
import boto3
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File
from app.config import settings

router = APIRouter()


async def upload_to_s3(file_content: bytes, filename: str, content_type: str, prefix: str = "posters") -> str:
    """Upload file to S3 and return the public URL"""
    
    # Validate S3 configuration
    if not settings.aws_s3_bucket or not settings.aws_access_key_id or not settings.aws_secret_access_key:
        raise HTTPException(status_code=500, detail="S3 configuration missing")
    
    # Initialize S3 client
    s3_client = boto3.client(
        "s3",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )
    
    # Generate unique key
    timestamp = int(datetime.now().timestamp() * 1000)
    key = f"{prefix}/{timestamp}-{filename}"
    
    # Upload to S3
    try:
        s3_client.put_object(
            Bucket=settings.aws_s3_bucket,
            Key=key,
            Body=file_content,
            ContentType=content_type,
            ACL="public-read",
        )
    except Exception as e:
        print(f"S3 upload error: {e}")
        raise HTTPException(status_code=500, detail=f"S3 upload failed: {str(e)}")
    
    # Construct the public URL
    if settings.s3_base_url:
        url = f"{settings.s3_base_url}/{key}"
    else:
        url = f"https://{settings.aws_s3_bucket}.s3.{settings.aws_region}.amazonaws.com/{key}"
    
    return url


@router.post("/upload-s3")
async def upload_s3(file: UploadFile = File(...)):
    """
    Upload a file to S3.
    Migrated from: frontend/app/api/upload-s3/route.ts
    
    Returns: { url: string } - The public URL of the uploaded file
    """
    if not file:
        raise HTTPException(status_code=400, detail="No file provided")
    
    try:
        file_content = await file.read()
        url = await upload_to_s3(
            file_content=file_content,
            filename=file.filename or "upload.png",
            content_type=file.content_type or "image/png",
            prefix="posters"
        )
        
        return {"url": url}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"S3 upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/save-local")
async def save_local(file: UploadFile = File(...)):
    """
    Save a file (uploads to S3 in production).
    Migrated from: frontend/app/api/save-local/route.ts
    
    Note: Despite the name "save-local", this actually uploads to S3 
    for AWS Lambda compatibility. The name is kept for backward compatibility.
    
    Returns: { path: string } - The public URL of the uploaded file (as 'path' for backward compat)
    """
    if not file:
        raise HTTPException(status_code=400, detail="No file provided")
    
    try:
        file_content = await file.read()
        url = await upload_to_s3(
            file_content=file_content,
            filename=file.filename or "upload.png",
            content_type=file.content_type or "image/png",
            prefix="generated-posters"
        )
        
        # Return as 'path' for backward compatibility with save-local API
        return {"path": url}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Save error: {e}")
        raise HTTPException(status_code=500, detail=f"Save failed: {str(e)}")
