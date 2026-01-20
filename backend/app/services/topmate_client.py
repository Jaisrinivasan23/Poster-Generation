"""
Topmate API Client
Handles fetching user profiles from Topmate API
"""
import httpx
from typing import Optional
from app.models.poster import TopmateProfile, TopmateService, TopmateBadge

TOPMATE_API_BASE = "https://gcp.galactus.run/fetchByUsername"


async def fetch_topmate_profile(username: str) -> TopmateProfile:
    """
    Fetch Topmate profile by username

    Args:
        username: Topmate username

    Returns:
        TopmateProfile object

    Raises:
        Exception if profile not found or API error
    """
    url = f"{TOPMATE_API_BASE}/?username={username}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)

        if not response.is_success:
            raise Exception(f"Failed to fetch Topmate profile: {response.status_code}")

        data = response.json()

        # Transform API response to TopmateProfile
        profile = TopmateProfile(
            user_id=data.get("user_id") or data.get("id") or "",
            username=data.get("username", ""),
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            display_name=data.get("display_name") or data.get("name") or f"{data.get('first_name', '')} {data.get('last_name', '')}".strip(),
            profile_pic=data.get("profile_pic") or data.get("picture") or "",
            bio=data.get("bio") or data.get("description") or "",
            description=data.get("description"),
            linkedin_url=data.get("linkedin_url"),
            instagram_url=data.get("instagram_url"),
            twitter_url=data.get("twitter_url"),
            timezone=data.get("timezone", "UTC"),

            # Metrics
            total_bookings=data.get("total_bookings") or data.get("bookings_count") or 0,
            total_reviews=data.get("total_reviews") or data.get("reviews_count") or 0,
            total_ratings=data.get("total_ratings") or data.get("ratings_count") or 0,
            average_rating=data.get("average_rating") or data.get("rating") or 0.0,
            expertise_count=data.get("expertise_count", 0),
            expertise_category=data.get("expertise_category") or data.get("expertise"),

            # Services
            services=[
                TopmateService(
                    id=s.get("id", ""),
                    title=s.get("title", ""),
                    description=s.get("description", ""),
                    type=s.get("type", 1),
                    duration=s.get("duration", 30),
                    charge=s.get("charge", {"amount": 0, "currency": "INR"}),
                    booking_count=s.get("booking_count", 0),
                    promised_response_time=s.get("promised_response_time")
                )
                for s in data.get("services", [])
            ],

            # Badges
            badges=[
                TopmateBadge(
                    id=b.get("id", ""),
                    name=b.get("name", ""),
                    description=b.get("description"),
                    image_url=b.get("image_url")
                )
                for b in data.get("badges", [])
            ],

            # Social proof
            liked_properties=data.get("liked_properties"),
            testimonials_count=data.get("testimonials_count", 0),
            ai_testimonial_summary=data.get("ai_testimonial_summary"),

            # Meta
            meta_image=data.get("meta_image"),
            join_date=data.get("join_date") or data.get("created_at")
        )

        return profile


async def fetch_profile_by_user_id(user_id: int) -> TopmateProfile:
    """
    Fetch Topmate profile by numeric user_id

    Args:
        user_id: Numeric user ID

    Returns:
        TopmateProfile object

    Raises:
        Exception if profile not found
    """
    api_url = f"https://gcp.galactus.run/api/users/{user_id}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(api_url)

            if response.is_success:
                data = response.json()

                # Transform to TopmateProfile (same as fetch_topmate_profile)
                profile = TopmateProfile(
                    user_id=str(data.get("user_id") or data.get("id") or user_id),
                    username=data.get("username", f"user_{user_id}"),
                    first_name=data.get("first_name", ""),
                    last_name=data.get("last_name", ""),
                    display_name=data.get("display_name") or data.get("name") or f"{data.get('first_name', '')} {data.get('last_name', '')}".strip(),
                    profile_pic=data.get("profile_pic") or data.get("profile_image") or "",
                    bio=data.get("bio") or data.get("description") or "",
                    description=data.get("description") or data.get("bio"),
                    timezone=data.get("timezone", "UTC"),

                    # Metrics
                    total_bookings=data.get("total_bookings") or data.get("bookings_count") or 0,
                    total_reviews=data.get("total_reviews") or data.get("reviews_count") or 0,
                    total_ratings=data.get("total_ratings") or data.get("ratings_count") or 0,
                    average_rating=data.get("average_rating") or data.get("avg_rating") or 0.0,
                    expertise_count=data.get("expertise_count", 0),
                    expertise_category=data.get("expertise_category"),

                    # Services and badges
                    services=data.get("services", []),
                    badges=data.get("badges", []),
                    liked_properties=data.get("liked_properties"),
                    testimonials_count=data.get("testimonials_count", 0),
                    ai_testimonial_summary=data.get("ai_testimonial_summary"),

                    # Meta
                    meta_image=data.get("meta_image"),
                    join_date=data.get("join_date") or data.get("created_at")
                )

                return profile
        except Exception as e:
            raise Exception(f"Failed to fetch profile for user ID {user_id}: {str(e)}")

    raise Exception(f"User with ID {user_id} not found")


def parse_user_identifiers(input_str: str) -> tuple[list[str], list[int]]:
    """
    Parse comma or newline separated user identifiers

    Args:
        input_str: Comma or newline separated usernames and/or user IDs

    Returns:
        Tuple of (usernames list, user_ids list)
    """
    items = [item.strip() for item in input_str.replace("\n", ",").split(",") if item.strip()]

    usernames = []
    user_ids = []

    for item in items:
        if item.isdigit():
            user_ids.append(int(item))
        else:
            usernames.append(item)

    return usernames, user_ids
