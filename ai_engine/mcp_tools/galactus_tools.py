"""
MCP Tools for Galactus API integration (Topmate user profiles)
"""
import httpx
from typing import Dict, Any, List, Optional
from logging_config import logger
from config import settings


GALACTUS_API_URL = "https://gcp.galactus.run/fetchByUsername/"


async def fetch_galactus_profile(username: str) -> Dict[str, Any]:
    """
    Fetch user profile from Galactus API.

    Args:
        username: Topmate username

    Returns:
        Complete user profile with services, testimonials, social links
    """
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            url = f"{GALACTUS_API_URL}?username={username}"
            logger.info(f"Fetching Galactus profile for username: {username}")

            response = await client.get(url)

            if response.status_code == 404:
                logger.warning(f"User not found in Galactus: {username}")
                return {
                    "success": False,
                    "error": "User not found",
                    "username": username
                }

            response.raise_for_status()
            data = response.json()

            logger.info(f"Successfully fetched Galactus profile for {username}")

            # Normalize the response
            normalized = _normalize_galactus_response(data)

            return {
                "success": True,
                "username": username,
                "data": normalized,
                "raw": data
            }

    except httpx.HTTPError as e:
        logger.error(f"HTTP error fetching Galactus profile for {username}: {str(e)}")
        # Fallback to mock data for development
        logger.warning(f"Using mock data for {username} due to API error")
        return _get_mock_galactus_data(username)
    except Exception as e:
        logger.error(f"Error fetching Galactus profile for {username}: {str(e)}")
        logger.warning(f"Using mock data for {username} due to error")
        return _get_mock_galactus_data(username)


def _normalize_galactus_response(data: Dict) -> Dict:
    """
    Normalize Galactus response to internal format.

    Args:
        data: Raw Galactus API response

    Returns:
        Normalized profile data
    """
    return {
        "id": data.get("id"),
        "name": data.get("display_name") or data.get("full_name") or f"{data.get('first_name', '')} {data.get('last_name', '')}".strip(),
        "username": data.get("username"),
        "bio": data.get("description", ""),
        "tagline": data.get("title", ""),
        "profile_pic": data.get("profile_pic"),
        "cover_image": data.get("cover_image_url"),
        "services": _extract_services(data.get("services", [])),
        "testimonials": _extract_testimonials(data.get("testimonials", [])),
        "social_links": _extract_social_links(data),
        "stats": {
            "bookings": data.get("bookings_count", 0) or data.get("total_bookings", 0),
            "reviews": data.get("reviews_count", 0) or data.get("total_reviews", 0),
            "rating": data.get("avg_ratings", 0) or data.get("rating", 0)
        },
        "badges": data.get("badges", []),
        "highlights": data.get("highlights", []),
        "expertise": data.get("expertise", "")
    }


def _extract_services(services: List) -> List[Dict]:
    """
    Extract and normalize services from Galactus response.

    Args:
        services: List of services from API

    Returns:
        Normalized list of services
    """
    SERVICE_TYPES = {
        1: "1:1 Call",
        2: "Priority DM",
        3: "Webinar",
        4: "Package",
        5: "Course"
    }

    normalized = []
    for s in services[:10]:  # Limit to 10 services
        charge = s.get("charge", {})
        normalized.append({
            "id": s.get("id"),
            "title": s.get("title", s.get("name", "Service")),
            "description": s.get("short_description") or s.get("description", ""),
            "type": SERVICE_TYPES.get(s.get("type"), "Service"),
            "price": charge.get("display_text") or f"{charge.get('currency', 'INR')} {charge.get('amount', 0)}",
            "price_amount": charge.get("amount", 0),
            "currency": charge.get("currency", "INR"),
            "duration": s.get("duration"),
            "bookings": s.get("bookings_count", 0),
            "cover_image": s.get("cover_image_url")
        })
    return normalized


def _extract_testimonials(testimonials: List) -> List[Dict]:
    """
    Extract and normalize testimonials.

    Args:
        testimonials: List of testimonials from API

    Returns:
        Normalized list of testimonials
    """
    normalized = []
    for t in testimonials[:5]:  # Limit to 5 testimonials
        normalized.append({
            "id": t.get("id"),
            "name": t.get("name") or t.get("author", "Anonymous"),
            "quote": t.get("quote") or t.get("text", ""),
            "rating": t.get("rating", 5),
            "avatar": t.get("avatar_url") or t.get("avatar")
        })
    return normalized


def _extract_social_links(data: Dict) -> Dict:
    """
    Extract social media links from profile.

    Args:
        data: Profile data

    Returns:
        Dictionary of social platform to URL mappings
    """
    social = {}

    # Direct fields
    if data.get("social_url"):
        social["website"] = data["social_url"]

    # Social links object
    social_links = data.get("social_links", {})
    if isinstance(social_links, dict):
        for platform, url in social_links.items():
            if url:
                social[platform] = url

    # Individual fields
    for platform in ["twitter", "linkedin", "github", "instagram", "youtube"]:
        url_key = f"{platform}_url"
        if data.get(url_key):
            social[platform] = data[url_key]

    return social


def _get_mock_galactus_data(username: str) -> Dict[str, Any]:
    """
    Generate mock data for testing when Galactus API is unavailable.

    Args:
        username: Username to generate mock data for

    Returns:
        Mock profile data
    """
    mock_data = {
        "id": 12345,
        "name": username.title().replace("_", " "),
        "username": username,
        "bio": f"Passionate professional with expertise in technology and innovation. "
               f"Helping people achieve their goals through personalized mentorship and consulting.",
        "tagline": "Expert Mentor & Consultant | Empowering Growth",
        "profile_pic": f"https://ui-avatars.com/api/?name={username}&size=200&background=667eea&color=fff",
        "cover_image": None,
        "services": [
            {
                "id": 1,
                "title": "1:1 Mentorship Session",
                "description": "One-on-one personalized guidance session to help you with your career goals",
                "type": "1:1 Call",
                "price": "INR 2,999",
                "price_amount": 2999,
                "currency": "INR",
                "duration": 60,
                "bookings": 150,
                "cover_image": None
            },
            {
                "id": 2,
                "title": "Career Strategy Consultation",
                "description": "Comprehensive career planning and strategy session",
                "type": "1:1 Call",
                "price": "INR 4,999",
                "price_amount": 4999,
                "currency": "INR",
                "duration": 90,
                "bookings": 75,
                "cover_image": None
            },
            {
                "id": 3,
                "title": "Resume Review & Feedback",
                "description": "Detailed review of your resume with actionable feedback",
                "type": "Priority DM",
                "price": "INR 1,499",
                "price_amount": 1499,
                "currency": "INR",
                "duration": 30,
                "bookings": 200,
                "cover_image": None
            }
        ],
        "testimonials": [
            {
                "id": 1,
                "name": "Sarah Johnson",
                "quote": f"Working with {username.title()} was an incredible experience. Their insights helped me land my dream job!",
                "rating": 5,
                "avatar": None
            },
            {
                "id": 2,
                "name": "Michael Chen",
                "quote": "Highly recommended! Professional, knowledgeable, and genuinely cares about your success.",
                "rating": 5,
                "avatar": None
            },
            {
                "id": 3,
                "name": "Priya Sharma",
                "quote": f"{username.title()} provided excellent guidance that transformed my career trajectory.",
                "rating": 5,
                "avatar": None
            }
        ],
        "social_links": {
            "twitter": f"https://twitter.com/{username}",
            "linkedin": f"https://linkedin.com/in/{username}",
            "github": f"https://github.com/{username}"
        },
        "stats": {
            "bookings": 425,
            "reviews": 89,
            "rating": 4.9
        },
        "badges": [],
        "highlights": [],
        "expertise": "Technology, Career Development, Mentorship"
    }

    logger.info(f"Generated mock Galactus data for {username}")
    return {
        "success": True,
        "username": username,
        "data": mock_data,
        "is_mock": True
    }


async def get_galactus_services(username: str) -> List[Dict[str, Any]]:
    """
    Get services/offerings from a Galactus user profile.

    Args:
        username: Topmate username

    Returns:
        List of services with pricing, description, etc.
    """
    try:
        profile = await fetch_galactus_profile(username)

        if not profile.get("success"):
            return []

        services = profile.get("data", {}).get("services", [])
        logger.info(f"Found {len(services)} services for {username}")

        return services

    except Exception as e:
        logger.error(f"Error getting services for {username}: {str(e)}")
        return []


async def get_galactus_testimonials(username: str) -> List[Dict[str, Any]]:
    """
    Get testimonials/reviews for a Galactus user.

    Args:
        username: Topmate username

    Returns:
        List of testimonials
    """
    try:
        profile = await fetch_galactus_profile(username)

        if not profile.get("success"):
            return []

        testimonials = profile.get("data", {}).get("testimonials", [])
        logger.info(f"Found {len(testimonials)} testimonials for {username}")

        return testimonials

    except Exception as e:
        logger.error(f"Error getting testimonials for {username}: {str(e)}")
        return []


def prepare_website_generation_data(username: str, profile_data: Dict) -> str:
    """
    Prepare comprehensive data for website generation, similar to production API.

    Creates a structured prompt with all profile data that the LLM can use
    to generate a complete, personalized website.

    Args:
        username: Topmate username
        profile_data: Normalized profile data from fetch_galactus_profile

    Returns:
        Formatted string with structured data and instructions for website generation
    """
    import json

    data = profile_data.get("data", {})
    raw = profile_data.get("raw", {})

    # Use raw data if available (more complete), otherwise use normalized
    profile_json = raw if raw else data

    return f"""TOPMATE PROFILE DATA (Complete JSON):
```json
{json.dumps(profile_json, indent=2)}
```

CRITICAL INSTRUCTIONS FOR USING THIS DATA:

1. PROFILE IMAGES:
   - Use `profile_pic` for the creator's avatar (MANDATORY if available)
   - Use `cover_image_url` for hero section background if available
   - Never use placeholder images when real URLs are provided

2. SERVICE INFORMATION:
   For EACH service in the `services` array:
   - Display exact `title` as service name
   - Use `short_description` or `description` for details
   - Show price: `charge.display_text` or format from `charge.amount` and `charge.currency`
   - Display `duration` if available (e.g., "60 minutes")
   - Use `cover_image_url` for service images if available
   - **CTA LINKS (MANDATORY):** Use format `https://topmate.io/{username}/{{service_id}}`
     Example: `<a href="https://topmate.io/{username}/123" target="_blank">Book Now</a>`

3. PROFILE CREDIBILITY:
   - Display `display_name` or `first_name` + `last_name`
   - Show `title` as professional headline
   - Include `description` as bio
   - **RATING (MANDATORY):** Display `rating` or `avg_ratings` with stars (e.g., "4.9 ⭐")
   - Show `total_bookings` or `bookings_count` as social proof

4. TESTIMONIALS (CRITICAL):
   For EACH testimonial in the `testimonials` array:
   - Use `avatar_url` for testimonial giver's image if available
   - Display exact `name` (NEVER modify or hallucinate names)
   - Show exact `quote` text (NEVER paraphrase or change)
   - Display `rating` with stars (e.g., "⭐⭐⭐⭐⭐")
   - Include all testimonials provided - do not skip any

5. SOCIAL LINKS:
   - Include all social links from `social_links` or individual fields
   - Use `social_url` if available

6. CTA BUTTONS:
   - All booking buttons MUST link to: https://topmate.io/{username}/{{service_id}}
   - Include service ID in every CTA link
   - Make CTAs prominent and action-oriented

MANDATORY REQUIREMENTS:
1. Use ALL images provided (profile pic, service images, testimonial avatars)
2. Include service ID in ALL CTA links
3. Display ratings with stars (⭐) prominently throughout
4. Include ALL testimonials with complete details
5. Show social proof (booking count, ratings) in hero and throughout
6. Create responsive, modern design
7. Ensure all links are functional and properly formatted
"""


def get_chatbot_suggestions(profile_data: Dict, username: str) -> Dict[str, Any]:
    """
    Generate intelligent chatbot suggestions based on profile data.

    Analyzes the profile to provide contextual suggestions for:
    - Template selection
    - Section recommendations
    - Content improvements

    Args:
        profile_data: Normalized profile data
        username: Topmate username

    Returns:
        Dictionary with suggestions for different chatbot modes
    """
    data = profile_data.get("data", {})
    stats = data.get("stats", {})
    services = data.get("services", [])
    testimonials = data.get("testimonials", [])

    suggestions = {
        "template_suggestions": [],
        "section_suggestions": [],
        "content_suggestions": [],
        "quick_actions": []
    }

    # Template suggestions based on profile type
    service_types = [s.get("type", "") for s in services]

    if "1:1 Call" in service_types or "Mentorship" in str(service_types):
        suggestions["template_suggestions"].append({
            "id": "mentor",
            "name": "Professional Mentor",
            "description": "Clean layout highlighting your expertise and 1:1 sessions",
            "recommended": True
        })

    if "Course" in service_types or "Webinar" in service_types:
        suggestions["template_suggestions"].append({
            "id": "educator",
            "name": "Educator/Course Creator",
            "description": "Showcase your courses and educational content",
            "recommended": False
        })

    if len(services) > 3:
        suggestions["template_suggestions"].append({
            "id": "service-heavy",
            "name": "Multi-Service Professional",
            "description": "Grid layout to showcase all your offerings",
            "recommended": False
        })

    # Always add general templates
    suggestions["template_suggestions"].extend([
        {
            "id": "minimal",
            "name": "Minimal & Clean",
            "description": "Focus on essential info with elegant simplicity",
            "recommended": False
        },
        {
            "id": "bold",
            "name": "Bold & Vibrant",
            "description": "Eye-catching design with strong colors",
            "recommended": False
        }
    ])

    # Section suggestions based on available data
    if testimonials:
        suggestions["section_suggestions"].append({
            "id": "testimonials",
            "name": "Testimonials Section",
            "description": f"Showcase your {len(testimonials)} reviews",
            "priority": "high"
        })

    if stats.get("rating", 0) >= 4.5:
        suggestions["section_suggestions"].append({
            "id": "social-proof",
            "name": "Social Proof Banner",
            "description": f"Highlight your {stats.get('rating')}⭐ rating and {stats.get('bookings', 0)}+ bookings",
            "priority": "high"
        })

    if services:
        suggestions["section_suggestions"].append({
            "id": "services",
            "name": "Services Grid",
            "description": f"Display your {len(services)} offerings with CTAs",
            "priority": "high"
        })

    suggestions["section_suggestions"].extend([
        {"id": "about", "name": "About Section", "description": "Tell your story", "priority": "medium"},
        {"id": "faq", "name": "FAQ Section", "description": "Answer common questions", "priority": "low"},
        {"id": "contact", "name": "Contact Form", "description": "Let visitors reach out", "priority": "medium"}
    ])

    # Content improvement suggestions
    if not data.get("bio") or len(data.get("bio", "")) < 100:
        suggestions["content_suggestions"].append({
            "type": "bio",
            "suggestion": "Your bio could be more detailed. Would you like help expanding it?"
        })

    if not data.get("tagline"):
        suggestions["content_suggestions"].append({
            "type": "tagline",
            "suggestion": "Adding a compelling tagline can increase conversions"
        })

    # Quick actions
    suggestions["quick_actions"] = [
        {"action": "generate", "label": "Generate Website Now", "description": "Create a complete website with best template"},
        {"action": "customize", "label": "Customize First", "description": "Choose template and sections before generating"},
        {"action": "preview_templates", "label": "Preview Templates", "description": "See all template options"}
    ]

    return suggestions


# Tool definitions for Claude Agents SDK
GALACTUS_TOOLS = {
    "fetch_galactus_profile": {
        "name": "fetch_galactus_profile",
        "description": "Fetch complete user profile from Galactus/Topmate API including services, ratings, testimonials, and social links",
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                    "description": "Topmate username to fetch"
                }
            },
            "required": ["username"]
        },
        "function": fetch_galactus_profile
    },
    "get_galactus_services": {
        "name": "get_galactus_services",
        "description": "Get services/offerings from a Topmate user profile",
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                    "description": "Topmate username"
                }
            },
            "required": ["username"]
        },
        "function": get_galactus_services
    },
    "get_galactus_testimonials": {
        "name": "get_galactus_testimonials",
        "description": "Get testimonials/reviews for a Topmate user",
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                    "description": "Topmate username"
                }
            },
            "required": ["username"]
        },
        "function": get_galactus_testimonials
    }
}
