"""
Analyze poster prompt to determine relevant profile fields - FastAPI version
This endpoint uses AI to analyze a user's poster creation prompt and determine
which Topmate profile fields are most relevant for the poster.
"""
import json
import re
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException
from app.config import settings
from app.services.openrouter_client import call_openrouter

router = APIRouter()


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class FieldInfo(BaseModel):
    field: str
    value: str
    description: str


class AnalyzePromptRequest(BaseModel):
    prompt: str  # The user's poster creation prompt
    availableFields: List[FieldInfo]  # Available profile fields with their values


class AnalyzePromptResponse(BaseModel):
    relevantFields: List[str]
    reasoning: Optional[str] = None


# ============================================================================
# API ENDPOINT
# ============================================================================

@router.post("/analyze-prompt", response_model=AnalyzePromptResponse)
async def analyze_prompt(request: AnalyzePromptRequest):
    """
    Analyze a poster creation prompt to determine which profile fields are relevant.
    Returns only the fields that should be displayed/used for the poster.
    """
    try:
        if not request.prompt:
            raise HTTPException(status_code=400, detail="Prompt is required")
        
        if not request.availableFields:
            raise HTTPException(status_code=400, detail="Available fields are required")
        
        # Check OpenRouter API key
        if not settings.openrouter_api_key:
            raise HTTPException(status_code=500, detail="OpenRouter API key not configured")
        
        # Build the analysis prompt
        fields_description = "\n".join([
            f"- {f.field}: {f.description} (value: {f.value[:100]}{'...' if len(f.value) > 100 else ''})"
            for f in request.availableFields
        ])
        
        system_prompt = """You are a smart assistant that analyzes poster creation requests to determine which profile data fields are relevant. Be strict and selective - only return fields that are DIRECTLY mentioned or clearly implied by the user's request."""
        
        user_prompt = f"""USER'S POSTER REQUEST:
"{request.prompt}"

AVAILABLE PROFILE DATA FIELDS:
{fields_description}

TASK: Determine which fields are DIRECTLY RELEVANT to creating this specific poster. Be strict and selective.

RULES:
1. If the prompt mentions "booking" or "bookings", include "total_bookings"
2. If the prompt mentions "review" or "reviews", include "total_reviews" and optionally "average_rating"
3. If the prompt mentions "rating" or "stars", include "average_rating"
4. If the prompt mentions "service" or "services" or "offering", include "services"
5. If the prompt mentions "testimonial" or "feedback" or "what clients say", include "testimonials"
6. If the prompt mentions "badge" or "achievement", include "badges"
7. If the prompt mentions "bio" or "about" or "description", include "bio"
8. If the prompt mentions "name" or explicitly needs to identify the creator, include "display_name"
9. If the prompt mentions "photo" or "picture" or "image of me", include "profile_pic"
10. ONLY include fields that are DIRECTLY mentioned or clearly implied by the prompt
11. Do NOT include all fields by default - be selective

Return a JSON object with this exact format:
{{"relevantFields": ["field1", "field2"], "reasoning": "Brief explanation"}}

If ONLY bookings are mentioned, return ONLY total_bookings. Do not add extra fields.
Return ONLY the JSON object, no additional text."""
        
        # Call OpenRouter API
        response_text = await call_openrouter(
            model="google/gemini-2.0-flash-001",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=500
        )
        
        # Parse the JSON response
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                parsed = json.loads(json_match.group(0))
                relevant_fields = parsed.get('relevantFields', [])
                reasoning = parsed.get('reasoning', '')
                
                # Validate fields against available ones
                available_field_names = [f.field for f in request.availableFields]
                valid_fields = [f for f in relevant_fields if f in available_field_names]
                
                # If no valid fields found, return just display_name
                if not valid_fields:
                    valid_fields = ['display_name'] if 'display_name' in available_field_names else []
                
                return AnalyzePromptResponse(
                    relevantFields=valid_fields,
                    reasoning=reasoning
                )
            else:
                raise ValueError("No JSON found in response")
                
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract field names from text
            available_field_names = [f.field for f in request.availableFields]
            found_fields = []
            
            for field_name in available_field_names:
                if field_name.lower() in response_text.lower() or \
                   field_name.replace('_', ' ').lower() in response_text.lower():
                    found_fields.append(field_name)
            
            if not found_fields:
                found_fields = ['display_name'] if 'display_name' in available_field_names else []
            
            return AnalyzePromptResponse(
                relevantFields=found_fields,
                reasoning="Parsed from text response"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        if "api_key" in error_msg.lower() or "authentication" in error_msg.lower():
            raise HTTPException(status_code=401, detail="Invalid API key")
        raise HTTPException(status_code=500, detail=f"Prompt analysis failed: {error_msg}")
