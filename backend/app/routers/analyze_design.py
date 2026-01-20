"""
Design analysis router - FastAPI version
Migrated from: frontend/app/api/analyze-design/route.ts
"""
import re
import json
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException
from anthropic import Anthropic

router = APIRouter()

# ============================================================================
# DESIGN ANALYSIS PROMPT - EXACT COPY FROM TYPESCRIPT
# ============================================================================

DESIGN_ANALYSIS_PROMPT = """You are an expert email designer analyzing a reference image to extract design characteristics.
Analyze this email design image and extract the following design tokens that can be used to generate a similar-styled email.

Return a JSON object with this EXACT structure:
{
  "colorPalette": {
    "primary": "#hex - dominant brand/header color",
    "secondary": "#hex - secondary/background color",
    "accent": "#hex - CTA button or highlight color",
    "background": "#hex - main background color",
    "text": "#hex - primary text color",
    "mutedText": "#hex - secondary/subtle text color"
  },
  "typography": {
    "headlineStyle": "serif | sans-serif | display",
    "bodyStyle": "serif | sans-serif",
    "headlineWeight": "normal | medium | semibold | bold | extrabold",
    "sizeContrast": "low | medium | high - difference between headline and body sizes"
  },
  "layout": {
    "structure": "single-column | two-column | mixed",
    "alignment": "left | center | mixed",
    "density": "spacious | balanced | compact",
    "heroStyle": "image-full | image-contained | text-only | split"
  },
  "aesthetic": {
    "direction": "minimal | modern | elegant | bold | playful | corporate | editorial",
    "mood": "one word describing the overall feel",
    "distinctiveElements": ["list", "of", "notable", "design", "features"]
  },
  "components": {
    "hasHeroImage": true/false,
    "hasFeatureIcons": true/false,
    "hasSocialLinks": true/false,
    "ctaStyle": "pill | rounded | square | outlined",
    "dividerStyle": "line | space | color-block | none"
  },
  "summary": "2-3 sentence description of the design style that captures its essence"
}

Be precise with color extraction - try to identify the exact hex values visible in the design.
For typography, describe what you see rather than guessing specific fonts.
Return ONLY the JSON object, no additional text."""


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class ColorPalette(BaseModel):
    primary: Optional[str] = None
    secondary: Optional[str] = None
    accent: Optional[str] = None
    background: Optional[str] = None
    text: Optional[str] = None
    mutedText: Optional[str] = None


class Typography(BaseModel):
    headlineStyle: Optional[str] = None
    bodyStyle: Optional[str] = None
    headlineWeight: Optional[str] = None
    sizeContrast: Optional[str] = None


class Layout(BaseModel):
    structure: Optional[str] = None
    alignment: Optional[str] = None
    density: Optional[str] = None
    heroStyle: Optional[str] = None


class Aesthetic(BaseModel):
    direction: Optional[str] = None
    mood: Optional[str] = None
    distinctiveElements: Optional[List[str]] = None


class Components(BaseModel):
    hasHeroImage: Optional[bool] = None
    hasFeatureIcons: Optional[bool] = None
    hasSocialLinks: Optional[bool] = None
    ctaStyle: Optional[str] = None
    dividerStyle: Optional[str] = None


class DesignTokens(BaseModel):
    colorPalette: Optional[ColorPalette] = None
    typography: Optional[Typography] = None
    layout: Optional[Layout] = None
    aesthetic: Optional[Aesthetic] = None
    components: Optional[Components] = None
    summary: Optional[str] = None


class AnalyzeDesignRequest(BaseModel):
    apiKey: str
    imageData: str  # base64 encoded image
    imageType: str  # mime type like image/png


class AnalyzeDesignResponse(BaseModel):
    success: bool
    designTokens: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    raw: Optional[str] = None


# ============================================================================
# API ENDPOINT
# ============================================================================

@router.post("/analyze-design", response_model=AnalyzeDesignResponse)
async def analyze_design(request: AnalyzeDesignRequest):
    """
    Analyze a design image and extract design tokens.
    Migrated from: frontend/app/api/analyze-design/route.ts
    """
    try:
        if not request.apiKey:
            raise HTTPException(status_code=400, detail="API key is required")
        
        if not request.imageData:
            raise HTTPException(status_code=400, detail="Image data is required")
        
        client = Anthropic(api_key=request.apiKey)
        
        # Map image type to Anthropic's expected format
        media_type = request.imageType
        if media_type not in ["image/png", "image/jpeg", "image/gif", "image/webp"]:
            media_type = "image/png"  # Default to PNG
        
        # Use Claude's vision capability to analyze the image
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": request.imageData,
                            },
                        },
                        {
                            "type": "text",
                            "text": DESIGN_ANALYSIS_PROMPT,
                        },
                    ],
                }
            ],
        )
        
        # Extract the text response
        analysis_text = ""
        if response.content and response.content[0].type == "text":
            analysis_text = response.content[0].text
        
        # Parse the JSON response
        try:
            # Clean up the response if it has markdown code blocks
            cleaned = re.sub(r'^```json\s*\n?', '', analysis_text, flags=re.IGNORECASE)
            cleaned = re.sub(r'\n?```\s*$', '', cleaned, flags=re.IGNORECASE)
            cleaned = cleaned.strip()
            
            design_tokens = json.loads(cleaned)
            
            return AnalyzeDesignResponse(
                success=True,
                designTokens=design_tokens,
            )
            
        except json.JSONDecodeError:
            return AnalyzeDesignResponse(
                success=False,
                error="Failed to parse design analysis",
                raw=analysis_text,
            )
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        if "api_key" in error_msg.lower() or "authentication" in error_msg.lower():
            raise HTTPException(status_code=401, detail="Invalid API key")
        raise HTTPException(status_code=500, detail=f"Design analysis failed: {error_msg}")
