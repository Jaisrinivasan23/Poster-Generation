"""
Pydantic models for poster generation
"""
from pydantic import BaseModel, field_validator
from typing import Optional, List, Dict, Any, Literal, Union


# Topmate Profile Models
class TopmateService(BaseModel):
    id: Union[str, int]
    title: str
    description: Optional[str] = ""
    type: int = 1
    duration: int = 30
    charge: Dict[str, Any] = {"amount": 0, "currency": "INR"}
    booking_count: int = 0
    promised_response_time: Optional[Union[str, int]] = None

    @field_validator('id', mode='before')
    @classmethod
    def convert_id_to_str(cls, v):
        return str(v) if v is not None else None

    @field_validator('promised_response_time', mode='before')
    @classmethod
    def convert_response_time_to_str(cls, v):
        return str(v) if v is not None else None


class TopmateBadge(BaseModel):
    id: Union[str, int]
    name: str
    description: Optional[str] = None
    image_url: Optional[str] = None

    @field_validator('id', mode='before')
    @classmethod
    def convert_id_to_str(cls, v):
        return str(v) if v is not None else None


class TopmateProfile(BaseModel):
    user_id: Union[str, int]
    username: str
    first_name: str = ""
    last_name: str = ""
    display_name: str
    profile_pic: str = ""
    bio: str = ""
    description: Optional[str] = None
    linkedin_url: Optional[str] = None
    instagram_url: Optional[str] = None
    twitter_url: Optional[str] = None
    timezone: str = "UTC"

    # Metrics
    total_bookings: int = 0
    total_reviews: int = 0
    total_ratings: int = 0
    average_rating: float = 0.0
    expertise_count: int = 0
    expertise_category: Optional[Union[str, int]] = None

    # Services and badges
    services: List[TopmateService] = []
    badges: List[TopmateBadge] = []

    # Social proof
    liked_properties: Optional[Union[Dict[str, int], List[Dict]]] = None
    testimonials_count: int = 0
    ai_testimonial_summary: Optional[str] = None

    # Meta
    meta_image: Optional[str] = None
    join_date: Optional[str] = None

    @field_validator('user_id', mode='before')
    @classmethod
    def convert_user_id_to_str(cls, v):
        return str(v) if v is not None else None

    @field_validator('expertise_category', mode='before')
    @classmethod
    def convert_expertise_category_to_str(cls, v):
        return str(v) if v is not None else None

    @field_validator('liked_properties', mode='before')
    @classmethod
    def convert_liked_properties(cls, v):
        if v is None:
            return None
        # If it's a list, convert to dict (or keep as is since we accept both)
        if isinstance(v, list):
            return v  # We accept list now with Union type
        return v


# Poster Configuration
PosterStyle = Literal["professional", "creative", "minimal", "bold", "elegant", "tech", "playful"]
PosterSize = Literal["instagram-square", "instagram-portrait", "instagram-story", "linkedin-post", "twitter-post", "facebook-post", "a4-portrait", "custom"]
PosterMode = Literal["single", "carousel"]
GenerationMode = Literal["html", "image"]


class PosterDimensions(BaseModel):
    width: int
    height: int


class PosterConfig(BaseModel):
    topmateUsername: str
    style: PosterStyle = "professional"
    size: PosterSize = "instagram-square"
    customDimensions: Optional[PosterDimensions] = None
    mode: PosterMode = "single"
    carouselSlides: Optional[int] = None
    generationMode: GenerationMode = "html"
    prompt: str
    includeServices: bool = False
    includeBadges: bool = False
    includeTestimonials: bool = False
    includeStats: bool = True


class GeneratedPoster(BaseModel):
    generationMode: GenerationMode
    html: Optional[str] = None
    imageUrl: Optional[str] = None
    imageData: Optional[str] = None
    dimensions: PosterDimensions
    style: PosterStyle
    topmateProfile: TopmateProfile
    generatedAt: str
    variantIndex: Optional[int] = None
    slideIndex: Optional[int] = None
    strategyName: Optional[str] = None


# API Request/Response Models
UserMode = Literal["expert", "admin"]

class GeneratePosterRequest(BaseModel):
    config: PosterConfig
    referenceImage: Optional[str] = None
    model: Literal["pro", "flash"] = "pro"
    userMode: UserMode = "admin"  # Default to admin for backward compatibility


class GeneratePosterResponse(BaseModel):
    success: bool
    posters: Optional[List[GeneratedPoster]] = None
    carousels: Optional[List[List[GeneratedPoster]]] = None
    mode: Optional[str] = None
    error: Optional[str] = None


# Bulk Generation Models
BulkMethod = Literal["prompt", "html", "csv"]


class GenerateBulkRequest(BaseModel):
    bulkMethod: BulkMethod
    htmlTemplate: Optional[str] = None
    csvTemplate: Optional[str] = None
    csvData: Optional[List[Dict[str, Any]]] = None
    csvColumns: Optional[List[str]] = None
    selectedTemplateImageUrl: Optional[str] = None
    userIdentifiers: Optional[str] = None
    posterName: str
    originalPrompt: Optional[str] = None
    size: PosterSize
    customWidth: Optional[int] = None
    customHeight: Optional[int] = None
    skipOverlays: bool = False
    model: Literal["pro", "flash"] = "pro"
    topmateLogo: Optional[str] = None


class BulkGenerationResult(BaseModel):
    userId: Optional[str] = None
    username: str
    imageUrl: str = ""
    posterUrl: str = ""
    success: bool
    error: Optional[str] = None


class GenerateBulkResponse(BaseModel):
    success: bool
    results: List[BulkGenerationResult]
    successCount: int
    failureCount: int


# Save Bulk Posters Models
class SavePosterItem(BaseModel):
    userId: Optional[Union[str, int]] = None
    username: str
    posterUrl: str

    @field_validator('userId', mode='before')
    @classmethod
    def convert_user_id_to_int(cls, v):
        """Convert userId to int for processing"""
        if v is None:
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None


class SaveBulkPostersRequest(BaseModel):
    posters: List[SavePosterItem]
    posterName: str


class SaveResult(BaseModel):
    success: bool
    userId: Optional[int] = None
    posterUrl: Optional[str] = None
    error: Optional[str] = None


class SaveBulkPostersResponse(BaseModel):
    success: bool
    results: List[SaveResult]
    successCount: int
    failureCount: int
