"""
Website generation service using OpenRouter API with Gemini fallback.
Produces high-quality, production-ready portfolio websites.
"""
import httpx
import json
import time
import base64
from typing import Dict, Any, Optional, List, Tuple, Union
from logging_config import logger
from config import settings
from services.builder_system_prompt import BUILDER_SYSTEM_PROMPT
from services.llm_response_handler import LLMResponseHandler
from services.design_context_extractor import extract_design_context


# Template definitions for website styles
WEBSITE_TEMPLATES = {
    "modern-minimal": {
        "id": "modern-minimal",
        "name": "Modern Minimal",
        "description": "Clean, minimalist design with focus on content and whitespace",
        "preview": "/templates/modern-minimal.png",
        "style_guide": """
        - Color scheme: White background, dark text, single accent color
        - Typography: Sans-serif fonts, large headings, generous line-height
        - Layout: Single column, centered content, max-width container
        - Animations: Subtle fade-ins, minimal hover effects
        - Hero: Full-width with profile photo centered, minimal text
        """
    },
    "bold-creative": {
        "id": "bold-creative",
        "name": "Bold & Creative",
        "description": "Vibrant colors, bold typography, and dynamic layouts",
        "preview": "/templates/bold-creative.png",
        "style_guide": """
        - Color scheme: Vibrant gradient backgrounds, contrasting colors
        - Typography: Bold, eye-catching headings, mix of fonts
        - Layout: Asymmetric sections, overlapping elements
        - Animations: Dynamic hover effects, scroll animations
        - Hero: Full-screen with bold statement, floating elements
        """
    },
    "professional-corporate": {
        "id": "professional-corporate",
        "name": "Professional Corporate",
        "description": "Trust-building design for consultants and business professionals",
        "preview": "/templates/professional-corporate.png",
        "style_guide": """
        - Color scheme: Navy blue, white, gold accents
        - Typography: Serif headings, clean sans-serif body
        - Layout: Traditional grid, clear sections, professional spacing
        - Animations: Subtle, business-appropriate transitions
        - Hero: Professional photo, credentials prominently displayed
        """
    },
    "dark-elegant": {
        "id": "dark-elegant",
        "name": "Dark & Elegant",
        "description": "Sophisticated dark theme with premium feel",
        "preview": "/templates/dark-elegant.png",
        "style_guide": """
        - Color scheme: Dark backgrounds (#0a0a0a, #1a1a1a), light text, gold/purple accents
        - Typography: Elegant fonts, good contrast
        - Layout: Spacious, luxury-brand inspired
        - Animations: Smooth reveals, elegant hover states
        - Hero: Dark overlay on image, glowing accents
        """
    },
    "vibrant-gradient": {
        "id": "vibrant-gradient",
        "name": "Vibrant Gradient",
        "description": "Eye-catching gradients and modern glass effects",
        "preview": "/templates/vibrant-gradient.png",
        "style_guide": """
        - Color scheme: Multi-color gradients (purple to pink to orange), glassmorphism
        - Typography: Modern sans-serif, white text on gradients
        - Layout: Card-based with frosted glass effects
        - Animations: Gradient animations, smooth transitions
        - Hero: Full gradient background, floating profile card
        """
    }
}


class LLMResponse:
    """Wrapper class for LLM responses"""
    def __init__(self, text: str, provider: str, model: str):
        self.text = text
        self.provider = provider
        self.model = model


class OpenRouterWebsiteGenerator:
    """Website generator using OpenRouter API with Gemini fallback"""

    GALACTUS_API_URL = "https://gcp.galactus.run/fetchByUsername/"
    OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

    # Primary and fallback models - Claude first for better instruction following
    PRIMARY_MODELS = [
        "anthropic/claude-sonnet-4",
        "anthropic/claude-3.5-sonnet",
        "google/gemini-2.0-flash-001",
    ]

    def __init__(self, api_key: str = None):
        """Initialize OpenRouter client"""
        self.api_key = api_key or settings.OPENROUTER_API_KEY
        self.gemini_api_key = settings.GEMINI_API_KEY
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not configured")
        logger.info(f"Initialized OpenRouterWebsiteGenerator")

    async def fetch_galactus_profile(self, username: str) -> Optional[Dict[str, Any]]:
        """Fetch user profile from Galactus API."""
        try:
            logger.info(f"Fetching Galactus profile for: {username}")

            async with httpx.AsyncClient(timeout=30.0) as client:
                url = f"{self.GALACTUS_API_URL}?username={username}"
                response = await client.get(url)

                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Successfully fetched Galactus profile for {username}")
                    logger.info(f"Profile has {len(data.get('services', []))} services")
                    return data
                else:
                    logger.error(f"Galactus API error: {response.status_code}")
                    return None

        except Exception as e:
            logger.error(f"Error fetching Galactus profile: {str(e)}")
            return None

    async def _download_image(self, image_url: str) -> Optional[Tuple[bytes, str]]:
        """Download image and return (content, mime_type)"""
        try:
            logger.info(f"Downloading image from URL: {image_url}")
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(image_url)
                response.raise_for_status()

                mime_type = response.headers.get('content-type', 'image/png')
                if 'image' not in mime_type:
                    mime_type = 'image/png'

                logger.info(f"Image downloaded successfully. Size: {len(response.content)} bytes, MIME: {mime_type}")
                return (response.content, mime_type)
        except Exception as e:
            logger.error(f"Failed to download image: {str(e)}")
            return None

    async def _call_openrouter(
        self,
        system_prompt: str,
        user_prompt: str,
        image_data: Optional[Tuple[bytes, str]] = None
    ) -> LLMResponse:
        """Call OpenRouter API with fallback models"""
        logger.info("Calling OpenRouter API...")

        # Build messages
        messages = [{"role": "system", "content": system_prompt}]

        # Handle image if provided
        if image_data:
            image_content, mime_type = image_data
            image_base64 = base64.b64encode(image_content).decode('utf-8')

            user_content = [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{image_base64}"
                    }
                },
                {
                    "type": "text",
                    "text": user_prompt
                }
            ]
            messages.append({"role": "user", "content": user_content})
        else:
            messages.append({"role": "user", "content": user_prompt})

        last_error = None

        # Try each model in sequence
        for model in self.PRIMARY_MODELS:
            try:
                logger.info(f"Trying OpenRouter model: {model}")

                async with httpx.AsyncClient(timeout=180.0) as client:
                    response = await client.post(
                        self.OPENROUTER_API_URL,
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://topmate.io",
                            "X-Title": "AI Website Builder"
                        },
                        json={
                            "model": model,
                            "messages": messages,
                            "max_tokens": 16384,
                            "temperature": 0.7
                        }
                    )

                    if response.status_code == 200:
                        result = response.json()
                        response_text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                        logger.info(f"Successfully got response from OpenRouter model: {model}")
                        return LLMResponse(text=response_text, provider="openrouter", model=model)
                    else:
                        error_text = response.text
                        logger.error(f"OpenRouter model {model} failed: {response.status_code} - {error_text}")
                        last_error = Exception(f"{response.status_code}: {error_text}")

            except Exception as e:
                logger.error(f"OpenRouter model {model} failed: {str(e)}")
                last_error = e
                continue

        # All OpenRouter models failed, try Gemini fallback
        logger.warning("All OpenRouter models failed, attempting Gemini fallback...")
        return await self._call_gemini_fallback(system_prompt, user_prompt, image_data, last_error)

    async def _call_gemini_fallback(
        self,
        system_prompt: str,
        user_prompt: str,
        image_data: Optional[Tuple[bytes, str]] = None,
        previous_error: Exception = None
    ) -> LLMResponse:
        """Fallback to Gemini API when OpenRouter fails"""
        logger.info("Falling back to Gemini API...")

        if not self.gemini_api_key:
            raise Exception(f"All OpenRouter models failed and GEMINI_API_KEY not configured. Previous error: {previous_error}")

        try:
            # Use Gemini REST API directly
            gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.gemini_api_key}"

            # Build request
            contents = []

            # Add system instruction as first user message (Gemini style)
            combined_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"

            if image_data:
                image_content, mime_type = image_data
                image_base64 = base64.b64encode(image_content).decode('utf-8')
                contents.append({
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": image_base64
                            }
                        },
                        {"text": combined_prompt}
                    ]
                })
            else:
                contents.append({
                    "parts": [{"text": combined_prompt}]
                })

            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(
                    gemini_url,
                    json={
                        "contents": contents,
                        "generationConfig": {
                            "maxOutputTokens": 16384,
                            "temperature": 0.7
                        }
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    response_text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    logger.info("Successfully got response from Gemini fallback")
                    return LLMResponse(text=response_text, provider="gemini", model="gemini-2.0-flash")
                else:
                    error_text = response.text
                    logger.error(f"Gemini fallback failed: {response.status_code} - {error_text}")
                    raise Exception(f"Gemini fallback failed: {response.status_code}")

        except Exception as e:
            logger.error(f"Gemini fallback also failed: {str(e)}")
            raise Exception(f"All LLM providers failed. Last error: {str(e)}")

    async def generate_website(
        self,
        username: str,
        user_prompt: str = "",
        template_id: str = "modern-minimal",
        image_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate complete website HTML from Topmate profile"""
        try:
            start_time = time.time()
            logger.info(f"Generating website for username: {username} with template: {template_id}")

            # Fetch profile from Galactus API
            profile_data = await self.fetch_galactus_profile(username)

            if not profile_data:
                logger.warning(f"No profile found, using mock data for {username}")
                profile_data = self._generate_mock_profile(username)

            # Get template style guide
            template = WEBSITE_TEMPLATES.get(template_id, WEBSITE_TEMPLATES["modern-minimal"])

            # Download image if provided
            image_data = None
            if image_url:
                image_data = await self._download_image(image_url)

            # Build the prompt with structured vars data
            prompt = self._build_website_prompt(username, profile_data, user_prompt, template, image_url)

            logger.info(f"Calling LLM with prompt length: {len(prompt)} characters")

            # Call LLM with fallback support
            llm_response = await self._call_openrouter(
                system_prompt=BUILDER_SYSTEM_PROMPT,
                user_prompt=prompt,
                image_data=image_data
            )

            # Clean the response
            html_content = LLMResponseHandler.handle_response(llm_response.text)
            html_content = LLMResponseHandler.clean_html(html_content)

            if not html_content:
                return {"success": False, "error": "No content generated"}

            # Extract design context from generated HTML
            try:
                design_context = extract_design_context(html_content, template_id)
                logger.info(f"Extracted design context: fonts={design_context.get('fonts', {}).get('display')}, template={template_id}")
            except Exception as e:
                logger.warning(f"Failed to extract design context: {str(e)}")
                design_context = {"template_id": template_id}

            execution_time = time.time() - start_time
            logger.info(f"Website generated successfully for {username} in {execution_time:.2f}s using {llm_response.provider}/{llm_response.model}")

            return {
                "success": True,
                "html": html_content,
                "username": username,
                "model": llm_response.model,
                "provider": llm_response.provider,
                "execution_time": execution_time,
                "design_context": design_context,
                "template_id": template_id
            }

        except Exception as e:
            logger.error(f"Error generating website for {username}: {str(e)}")
            return {"success": False, "error": str(e)}

    def _build_website_prompt(
        self,
        username: str,
        profile_data: Dict[str, Any],
        user_prompt: str,
        template: Dict[str, Any],
        image_url: Optional[str] = None
    ) -> str:
        """Build user prompt matching production website_builder.py format"""

        if not profile_data or not isinstance(profile_data, dict):
            profile_data = {}

        # Build vars_data structure (same as production)
        vars_data = profile_data.copy()
        vars_data["username"] = username

        # Start building the prompt
        prompt_parts = []

        # Add image reference if provided
        if image_url:
            prompt_parts.append("Please take the reference of screenshot provided in the image. Follow the design not the content.")

        # Add template style
        template_name = template.get("name", "Modern")
        style_guide = template.get("style_guide", "")
        prompt_parts.append(f"Create a {template_name} style portfolio website.")
        if style_guide:
            prompt_parts.append(style_guide)

        # Add user request
        if user_prompt:
            prompt_parts.append(f"\nUser Request: {user_prompt}")

        # Add structured vars data section (EXACT format from production)
        vars_section = f"""
STRUCTURED DATA (JSON):
```json
{json.dumps(vars_data, indent=2)}
```

CRITICAL INSTRUCTIONS FOR USING THIS DATA:

1. PROFILE IMAGES:
   - Use the exact URL from `profile_pic` for the user's avatar/profile image
   - Use `cover_image` if available for hero section backgrounds
   - DO NOT use placeholder images if real URLs are provided

2. PROFILE INFORMATION:
   - Display `first_name`, `last_name`, or `display_name` prominently
   - Use `title` as the professional headline
   - Include `description` as the bio/about text
   - Display `rating` with star icons (e.g., "⭐ 4.9/5") if available
   - Show `total_bookings` as social proof (e.g., "200+ sessions completed")

3. SERVICES (CRITICAL - DO NOT SKIP):
   For EACH service in the `services` array:
   - Use `cover_image_url` as the service image (first priority)
   - Use `document_thumbnail_url` as fallback if cover_image_url is not available
   - Display service `title` or `name`
   - Show `short_description` or `description`
   - Display pricing: `charge.amount` and `charge.currency` (e.g., "$99 USD")
   - Show `duration` if available (e.g., "60 minutes")
   - **IMPORTANT**: Add CTA buttons with Topmate booking links:
     * Format: `https://topmate.io/{username}/{{service_id}}`
     * Replace {{service_id}} with the service `id` field
     * Example: `<a href="https://topmate.io/{username}/12345">Book Now</a>`
   - Display service `rating` if available
   - Show `booking_count` as social proof if available

4. TESTIMONIALS (IF AVAILABLE):
   For EACH testimonial in the `testimonials` array:
   - Use `avatar_url` for the testimonial giver's image
   - Display `name` of the person
   - Show the exact `quote` text
   - Display `rating` with stars (e.g., "⭐⭐⭐⭐⭐")
   - NEVER modify or paraphrase testimonial quotes
   - NEVER hallucinate testimonials - only use provided ones

5. SOCIAL PROOF:
   - Display `rating` prominently (e.g., "4.9 ⭐ rating")
   - Show `total_bookings` or `total_reviews` if available
   - Include verification badges from `badges` array if present

6. LINKS & SOCIAL:
   - Use `social_url` for social media links
   - Use `website_url` if available
   - Include links from the `links` array

EXAMPLE SERVICE CTA STRUCTURE:
```html
<a href="https://topmate.io/{username}/{{service_id}}" target="_blank" class="btn-primary">
  Book {{service_title}} - ${{amount}}
</a>
```

MANDATORY: Use ALL images, ratings, and testimonials provided above. Do not skip any service or testimonial.
"""
        prompt_parts.append(vars_section)

        # Add final instructions (same as production)
        prompt_parts.append(""" Return only clean HTML code without any markdown formatting or code block markers like ```html or ```. Start directly with <!DOCTYPE html> and end with </html>.

IMPORTANT: Do NOT use base64 encoded images (data:image/...). Instead use:
- Placeholder image services like https://picsum.photos/800/600 for sample images
- https://via.placeholder.com/800x600 for placeholder images
- External image URLs from unsplash.com or other services
- URLs from the provided vars/profile data
- Keep images lightweight and use external URLs only""")

        return "\n".join(prompt_parts)

    def _generate_mock_profile(self, username: str) -> Dict[str, Any]:
        """Generate mock profile data when API fails"""
        return {
            "display_name": username.title(),
            "title": "Professional Consultant & Mentor",
            "description": f"Welcome to {username.title()}'s profile. I'm a passionate professional dedicated to helping individuals and teams achieve their goals through personalized guidance and expert consulting.",
            "profile_pic": f"https://ui-avatars.com/api/?name={username}&size=200&background=667eea&color=fff&bold=true",
            "avg_ratings": 4.9,
            "bookings_count": 150,
            "reviews_count": 45,
            "expertise": "Career Development, Business Strategy, Personal Growth, Leadership",
            "services": [
                {
                    "id": "1",
                    "title": "1:1 Mentorship Session",
                    "short_description": "Personalized one-on-one guidance to help you navigate your career challenges.",
                    "duration": 30,
                    "type": "1:1 Call",
                    "bookings_count": 75,
                    "charge": {"display_text": "₹999", "amount": 999, "currency": "INR"}
                },
                {
                    "id": "2",
                    "title": "Career Strategy Deep Dive",
                    "short_description": "Comprehensive session to create a detailed roadmap for your career.",
                    "duration": 60,
                    "type": "1:1 Call",
                    "bookings_count": 50,
                    "charge": {"display_text": "₹1,999", "amount": 1999, "currency": "INR"}
                },
                {
                    "id": "3",
                    "title": "Resume & LinkedIn Review",
                    "short_description": "Get detailed feedback on your resume and LinkedIn profile.",
                    "duration": 45,
                    "type": "Priority DM",
                    "bookings_count": 25,
                    "charge": {"display_text": "₹799", "amount": 799, "currency": "INR"}
                }
            ],
            "testimonials": [
                {
                    "name": "Sarah Johnson",
                    "quote": "The mentorship session was incredibly valuable. Got practical advice that helped me land my dream job!",
                    "rating": 5,
                    "designation": "Product Manager"
                },
                {
                    "name": "Rahul Sharma",
                    "quote": "Very insightful session. The career roadmap we created gave me clarity on my next steps.",
                    "rating": 5,
                    "designation": "Software Engineer"
                }
            ],
            "badges": [
                {"name": "Top Mentor", "description": "Recognized as a top mentor"},
                {"name": "Quick Responder", "description": "Responds within 24 hours"}
            ],
            "social_urls": {
                "linkedin": f"https://linkedin.com/in/{username}",
                "twitter": f"https://twitter.com/{username}"
            }
        }


def get_available_templates() -> List[Dict[str, Any]]:
    """Get list of available website templates for the frontend."""
    return [
        {
            "id": template["id"],
            "name": template["name"],
            "description": template["description"],
            "preview": template["preview"]
        }
        for template in WEBSITE_TEMPLATES.values()
    ]
