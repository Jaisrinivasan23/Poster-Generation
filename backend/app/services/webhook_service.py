"""
Webhook Service
Handles Django API integration for storing posters
"""
import httpx
from typing import Dict, Any
from app.config import settings


async def store_poster_to_django(
    poster_url: str,
    poster_name: str,
    user_id: int
) -> Dict[str, Any]:
    """
    Store poster to Django backend via webhooks

    Steps:
    1. Create Video entry
    2. Trigger webhook to create UserShareContent

    Args:
        poster_url: S3 URL of the poster
        poster_name: Campaign name
        user_id: Topmate user ID

    Returns:
        Result dict with success status
    """
    try:
        django_url = settings.django_api_url
        external_id = f"{poster_name}-{user_id}-{int(__import__('time').time() * 1000)}"

        print(f"  👤 User {user_id}:")

        # Step 1: Create Video entry
        print(f"    📹 Creating Video entry...")
        video_payload = {
            "external_id": external_id,
            "url": poster_url,
            "status": "COMPLETED",
            "user": user_id
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            video_response = await client.post(
                f"{django_url}/create-video/",
                json=video_payload
            )

            if not video_response.is_success:
                raise Exception(f"Video API failed: {video_response.status_code} - {video_response.text}")

            print(f"    ✅ Video created")

            # Step 2: Trigger webhook
            print(f"    🔗 Triggering webhook...")
            webhook_payload = {
                "id": external_id,
                "status": "succeeded",
                "output_format": "jpg",
                "template_tags": [f"-ms-{poster_name}"],  # Triggers monthly_stat_handler
                "template_id": f"email-forge-{poster_name}",
                "modifications": {
                    "campaign": poster_name,
                    "title": poster_name.replace("-", " ").upper(),
                    "description": f"Poster: {poster_name}",
                    "tag": "custom"
                },
                "metadata": f"email-forge-{user_id}-{int(__import__('time').time() * 1000)}"
            }

            webhook_response = await client.post(
                f"{django_url}/creatomate-webhook/",
                json=webhook_payload
            )

            if not webhook_response.is_success:
                raise Exception(f"Webhook failed: {webhook_response.status_code} - {webhook_response.text}")

            print(f"    ✅ UserShareContent created")

            return {
                "success": True,
                "posterUrl": poster_url,
                "posterName": poster_name,
                "userId": user_id
            }

    except Exception as e:
        print(f"    ❌ Error: {e}")
        return {
            "success": False,
            "userId": user_id,
            "error": str(e)
        }


async def store_bulk_posters(posters: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    """
    Store multiple posters to Django

    Args:
        posters: List of {userId, posterUrl, posterName}

    Returns:
        List of results
    """
    print(f"📦 Storing {len(posters)} posters to Django...")

    results = []

    for poster in posters:
        result = await store_poster_to_django(
            poster["posterUrl"],
            poster["posterName"],
            poster["userId"]
        )
        results.append(result)

        # Small delay to avoid overwhelming Django
        await __import__('asyncio').sleep(0.1)

    success_count = sum(1 for r in results if r["success"])
    print(f"✅ Successfully stored {success_count}/{len(posters)} posters")

    return results
