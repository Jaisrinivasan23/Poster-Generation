"""
S3 upload router - FastAPI version
Migrated from: frontend/app/api/upload-s3/route.ts and frontend/app/api/save-local/route.ts
Both routes do the same thing (upload to S3), so combined into one
"""
import boto3
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from app.config import settings
from app.services.database import database_service

router = APIRouter()


class TemplateImageResponse(BaseModel):
    id: str
    name: str
    url: str
    category: str
    created_at: str


class CustomFontResponse(BaseModel):
    id: str
    font_name: str
    font_family: str
    file_url: str
    file_format: str
    created_at: str


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


# ============ Admin Template Image Management ============

@router.post("/api/template-images/upload")
async def upload_template_image(
    file: UploadFile = File(...),
    name: str = Form(...),
    category: str = Form("minimal"),
    uploaded_by: str = Form("admin")
):
    """Upload a new template image (admin only)"""
    if not file:
        raise HTTPException(status_code=400, detail="No file provided")
    
    # Validate file type
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    try:
        # Upload to S3
        file_content = await file.read()
        url = await upload_to_s3(
            file_content=file_content,
            filename=file.filename or "template.png",
            content_type=file.content_type,
            prefix="template-images"
        )
        
        # Save to database
        query = """
            INSERT INTO template_images (name, url, category, uploaded_by)
            VALUES ($1, $2, $3, $4)
            RETURNING id, name, url, category, created_at
        """
        
        result = await database_service.fetchrow(query, name, url, category, uploaded_by)
        
        if not result:
            raise HTTPException(status_code=500, detail="Failed to save template to database")
        
        return {
            "success": True,
            "template": {
                "id": str(result['id']),
                "name": result['name'],
                "url": result['url'],
                "category": result['category'],
                "created_at": result['created_at'].isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Template upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/api/template-images")
async def get_template_images():
    """Get all active template images"""
    try:
        query = """
            SELECT id, name, url, category, created_at
            FROM template_images
            WHERE is_active = true
            ORDER BY created_at DESC
        """
        
        rows = await database_service.fetch(query)
        
        templates = [
            {
                "id": str(row['id']),
                "name": row['name'],
                "url": row['url'],
                "category": row['category'],
                "created_at": row['created_at'].isoformat()
            }
            for row in rows
        ]
        
        return {"templates": templates}
        
    except Exception as e:
        print(f"Failed to fetch templates: {e}")
        return {"templates": []}


@router.delete("/api/template-images/{template_id}")
async def delete_template_image(template_id: str):
    """Delete a template image (soft delete)"""
    try:
        query = """
            UPDATE template_images
            SET is_active = false
            WHERE id = $1
            RETURNING id
        """
        
        result = await database_service.fetchrow(query, template_id)
        
        if not result:
            raise HTTPException(status_code=404, detail="Template not found")
        
        return {"success": True, "message": "Template deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Delete error: {e}")
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")


# ============ Admin Custom Font Management ============

@router.post("/api/custom-fonts/upload")
async def upload_custom_font(
    file: UploadFile = File(...),
    font_name: str = Form(...),
    font_family: str = Form(...),
    uploaded_by: str = Form("admin")
):
    """Upload a custom font file (admin only)"""
    if not file:
        raise HTTPException(status_code=400, detail="No file provided")
    
    # Validate file type
    file_format = file.filename.split('.')[-1].lower() if file.filename else ''
    valid_formats = ['ttf', 'woff', 'woff2', 'otf']
    
    if file_format not in valid_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid font format. Supported: {', '.join(valid_formats)}"
        )
    
    try:
        # Upload to S3
        file_content = await file.read()
        url = await upload_to_s3(
            file_content=file_content,
            filename=file.filename or f"{font_family}.{file_format}",
            content_type=f"font/{file_format}",
            prefix="custom-fonts"
        )
        
        # Save to database
        query = """
            INSERT INTO custom_fonts (font_name, font_family, file_url, file_format, uploaded_by)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (font_family) DO UPDATE
            SET file_url = $3, file_format = $4, updated_at = NOW()
            RETURNING id, font_name, font_family, file_url, file_format, created_at
        """
        
        result = await database_service.fetchrow(
            query, font_name, font_family, url, file_format, uploaded_by
        )
        
        if not result:
            raise HTTPException(status_code=500, detail="Failed to save font to database")
        
        return {
            "success": True,
            "font": {
                "id": str(result['id']),
                "font_name": result['font_name'],
                "font_family": result['font_family'],
                "file_url": result['file_url'],
                "file_format": result['file_format'],
                "created_at": result['created_at'].isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Font upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/api/custom-fonts")
async def get_custom_fonts():
    """Get all active custom fonts"""
    try:
        query = """
            SELECT id, font_name, font_family, file_url, file_format, created_at
            FROM custom_fonts
            WHERE is_active = true
            ORDER BY font_family ASC
        """
        
        rows = await database_service.fetch(query)
        
        fonts = [
            {
                "id": str(row['id']),
                "font_name": row['font_name'],
                "font_family": row['font_family'],
                "file_url": row['file_url'],
                "file_format": row['file_format'],
                "created_at": row['created_at'].isoformat()
            }
            for row in rows
        ]
        
        return {"fonts": fonts}
        
    except Exception as e:
        print(f"Failed to fetch fonts: {e}")
        return {"fonts": []}


@router.delete("/api/custom-fonts/{font_id}")
async def delete_custom_font(font_id: str):
    """Delete a custom font (soft delete)"""
    try:
        query = """
            UPDATE custom_fonts
            SET is_active = false
            WHERE id = $1
            RETURNING id
        """
        
        result = await database_service.fetchrow(query, font_id)
        
        if not result:
            raise HTTPException(status_code=404, detail="Font not found")
        
        return {"success": True, "message": "Font deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Delete error: {e}")
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")
