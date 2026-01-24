"""
Template Management Models
For external backend integration (Django Topmate)
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


# ============ Request Models ============

class UploadTemplateRequest(BaseModel):
    """Request to upload a new template"""
    section: str = Field(..., description="Template category (testimonial, top_new_launch, etc.)")
    name: str = Field(..., description="Human-readable template name")
    html_content: str = Field(..., description="HTML with {{placeholder}} syntax")
    css_content: Optional[str] = Field(None, description="Optional CSS styles")
    preview_data: Optional[Dict[str, Any]] = Field(None, description="Sample data for preview")
    set_as_active: bool = Field(False, description="Activate this template immediately")


class GenerateFromTemplateRequest(BaseModel):
    """Request to generate poster from template (called by Django)"""
    template_id: str = Field(..., description="Template identifier (e.g., 'testimonial_latest')")
    custom_data: Dict[str, Any] = Field(..., description="Placeholder values")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata (user_id, id, etc.)")


class UpdateTemplateRequest(BaseModel):
    """Request to update template (creates new version)"""
    name: Optional[str] = None
    html_content: Optional[str] = None
    css_content: Optional[str] = None
    preview_data: Optional[Dict[str, Any]] = None


# ============ Response Models ============

class PlaceholderInfo(BaseModel):
    """Information about a placeholder"""
    name: str
    sample_value: Optional[str] = None
    data_type: str = "text"
    is_required: bool = True


class TemplateInfo(BaseModel):
    """Template information"""
    id: str
    section: str
    name: str
    version: int
    is_active: bool
    created_at: datetime
    placeholders: List[PlaceholderInfo] = []


class UploadTemplateResponse(BaseModel):
    """Response after uploading template"""
    template_id: str
    version: int
    section: str
    placeholders: List[PlaceholderInfo]
    message: str


class GenerateFromTemplateResponse(BaseModel):
    """Response after generating poster"""
    url: str = Field(..., description="S3 URL of generated image")
    template_version_used: int
    template_name: str
    generation_time_ms: int


class TemplatePreviewResponse(BaseModel):
    """Response for template preview"""
    template_id: str
    html_preview: str
    preview_image_base64: str
    placeholders: List[PlaceholderInfo]


class ListTemplatesResponse(BaseModel):
    """Response for listing templates"""
    section: str
    templates: List[TemplateInfo]
    active_template: Optional[TemplateInfo] = None


class ActivateTemplateResponse(BaseModel):
    """Response after activating template"""
    template_id: str
    section: str
    version: int
    is_active: bool
    message: str


# ============ Database Models ============

class Template(BaseModel):
    """Template database model"""
    id: UUID
    section: str
    name: str
    html_content: str
    css_content: Optional[str]
    version: int
    is_active: bool
    preview_data: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TemplatePlaceholder(BaseModel):
    """Template placeholder database model"""
    id: UUID
    template_id: UUID
    placeholder_name: str
    sample_value: Optional[str]
    data_type: str
    is_required: bool
    created_at: datetime

    class Config:
        from_attributes = True


class PosterGeneration(BaseModel):
    """Poster generation history model"""
    id: UUID
    template_id: Optional[UUID]
    user_id: int
    entity_id: Optional[str]
    input_data: Dict[str, Any]
    output_url: str
    template_version: Optional[int]
    generation_time_ms: int
    status: str
    error_message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
