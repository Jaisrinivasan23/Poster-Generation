"""
Generate Bulk Router
POST /api/generate-bulk - Bulk poster generation (CSV, HTML template, or AI prompt)
"""
from fastapi import APIRouter, HTTPException
from app.models.poster import GenerateBulkRequest, GenerateBulkResponse, BulkGenerationResult
from app.services.topmate_client import fetch_topmate_profile, fetch_profile_by_user_id, parse_user_identifiers
from app.services.openrouter_client import fetch_image_as_data_url
from app.services.image_processor import overlay_logo_and_profile, replace_placeholders
from app.services.storage_service import upload_image
from app.services.html_to_image import convert_html_to_png
import asyncio

router = APIRouter()

# Poster size dimensions
POSTER_SIZE_DIMENSIONS = {
    "instagram-square": {"width": 1080, "height": 1080},
    "instagram-portrait": {"width": 1080, "height": 1350},
    "instagram-story": {"width": 1080, "height": 1920},
    "linkedin-post": {"width": 1200, "height": 1200},
    "twitter-post": {"width": 1200, "height": 675},
    "facebook-post": {"width": 1200, "height": 630},
    "a4-portrait": {"width": 2480, "height": 3508}
}


@router.post("/generate-bulk", response_model=GenerateBulkResponse)
async def generate_bulk(request: GenerateBulkRequest):
    """
    Bulk poster generation

    Supports 3 modes:
    1. CSV Mode: Upload CSV + HTML template → batch generate
    2. HTML Mode: HTML template + user identifiers → batch generate
    3. Prompt Mode: AI generates template (returns 3 variants)
    """
    try:
        # Get dimensions
        if request.size == "custom" and request.customWidth and request.customHeight:
            dimensions = {"width": request.customWidth, "height": request.customHeight}
        else:
            dimensions = POSTER_SIZE_DIMENSIONS.get(request.size, POSTER_SIZE_DIMENSIONS["instagram-square"])

        results = []

        # CSV MODE: Use CSV data directly
        if request.bulkMethod == "csv" and request.csvTemplate and request.csvData and request.csvColumns:
            print(f"[CSV] Processing {len(request.csvData)} rows")

            # Process in batches of 8
            BATCH_SIZE = 8
            for i in range(0, len(request.csvData), BATCH_SIZE):
                batch = request.csvData[i:i+BATCH_SIZE]
                print(f"[CSV] Batch {i//BATCH_SIZE + 1}/{(len(request.csvData) + BATCH_SIZE - 1)//BATCH_SIZE}")

                batch_tasks = []
                for row in batch:
                    batch_tasks.append(process_csv_row(
                        row=row,
                        csv_template=request.csvTemplate,
                        csv_columns=request.csvColumns,
                        dimensions=dimensions,
                        skip_overlays=request.skipOverlays,
                        topmate_logo=request.topmateLogo
                    ))

                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

                for result in batch_results:
                    if isinstance(result, Exception):
                        print(f"[CSV] Error: {result}")
                        results.append(BulkGenerationResult(
                            username="unknown",
                            success=False,
                            error=str(result)
                        ))
                    else:
                        results.append(result)

                # Brief delay between batches
                await asyncio.sleep(1)

        # HTML MODE: Fetch profiles and use HTML template
        elif request.bulkMethod == "html" and request.htmlTemplate and request.userIdentifiers:
            print(f"[HTML] Using HTML template mode")

            # Parse identifiers
            usernames, user_ids = parse_user_identifiers(request.userIdentifiers)
            print(f"[HTML] Parsed: {len(usernames)} usernames, {len(user_ids)} user IDs")

            # Fetch profiles
            profiles = []
            for username in usernames:
                try:
                    profile = await fetch_topmate_profile(username)
                    profiles.append(profile)
                except Exception as e:
                    print(f"[ERROR] Failed to fetch {username}: {e}")

            for user_id in user_ids:
                try:
                    profile = await fetch_profile_by_user_id(user_id)
                    profiles.append(profile)
                except Exception as e:
                    print(f"[ERROR] Failed to fetch user {user_id}: {e}")

            # Process in batches
            BATCH_SIZE = 8
            for i in range(0, len(profiles), BATCH_SIZE):
                batch = profiles[i:i+BATCH_SIZE]

                batch_tasks = []
                for profile in batch:
                    batch_tasks.append(process_html_template(
                        profile=profile,
                        html_template=request.htmlTemplate,
                        dimensions=dimensions,
                        topmate_logo=request.topmateLogo
                    ))

                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

                for result in batch_results:
                    if isinstance(result, Exception):
                        print(f"[ERROR] Error: {result}")
                    else:
                        results.append(result)

                await asyncio.sleep(1)

        else:
            raise HTTPException(status_code=400, detail="Invalid bulk generation request")

        success_count = sum(1 for r in results if r.success)
        failure_count = len(results) - success_count

        return GenerateBulkResponse(
            success=True,
            results=results,
            successCount=success_count,
            failureCount=failure_count
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def process_csv_row(
    row: dict,
    csv_template: str,
    csv_columns: list[str],
    dimensions: dict,
    skip_overlays: bool,
    topmate_logo: str | None
) -> BulkGenerationResult:
    """Process a single CSV row"""
    try:
        username = row.get("username") or row.get("Username") or "unknown"
        print(f"[CSV] Generating for {username}...")

        # Replace placeholders
        filled_html = replace_placeholders(csv_template, row, csv_columns)

        # Convert HTML to PNG using Playwright
        print(f"[CSV] Converting HTML to PNG for {username}...")
        png_data_url = await convert_html_to_png(
            html=filled_html,
            dimensions=dimensions,
            scale=1.0  # 1x resolution for faster processing
        )
        print(f"[CSV] Converted HTML to PNG for {username}")

        # Apply overlays if not skipped
        if not skip_overlays and topmate_logo:
            print(f"[CSV] Applying logo overlay for {username}...")
            png_data_url = await overlay_logo_and_profile(
                base_image_url=png_data_url,
                logo_url=topmate_logo,
                profile_pic_url=None,  # No profile pic for CSV mode
                dimensions=dimensions
            )
            print(f"[CSV] Completed image with overlays for {username}")

        # Upload to S3
        filename = f"{username}-{int(__import__('time').time() * 1000)}.png"
        uploaded_url = await upload_image(png_data_url, filename)
        print(f"[CSV] Uploaded to S3: {uploaded_url}")

        return BulkGenerationResult(
            username=username,
            imageUrl=uploaded_url,
            posterUrl=uploaded_url,
            success=True
        )

    except Exception as e:
        import traceback
        username = row.get("username") or row.get("Username") or "unknown"
        error_msg = str(e) or "Unknown error"
        print(f"[CSV] Failed for {username}: {error_msg}")
        print(f"[CSV] Traceback: {traceback.format_exc()}")
        return BulkGenerationResult(
            username=username,
            success=False,
            error=error_msg
        )


async def process_html_template(
    profile: any,
    html_template: str,
    dimensions: dict,
    topmate_logo: str | None
) -> BulkGenerationResult:
    """Process HTML template for a profile"""
    try:
        print(f"[HTML] Generating for {profile.username}...")

        # Replace placeholders
        filled_html = html_template
        filled_html = filled_html.replace("{display_name}", profile.display_name)
        filled_html = filled_html.replace("{username}", profile.username)
        filled_html = filled_html.replace("{profile_pic}", profile.profile_pic)
        filled_html = filled_html.replace("{bio}", profile.bio)
        filled_html = filled_html.replace("{total_bookings}", str(profile.total_bookings))
        filled_html = filled_html.replace("{average_rating}", str(profile.average_rating))

        # Convert HTML to PNG
        print(f"[HTML] Converting HTML to PNG for {profile.username}...")
        png_data_url = await convert_html_to_png(
            html=filled_html,
            dimensions=dimensions,
            scale=1.0
        )
        print(f"[HTML] Converted HTML to PNG for {profile.username}")

        # Apply overlays (logo + profile picture)
        print(f"[HTML] Applying logo and profile overlays for {profile.username}...")
        final_image_url = await overlay_logo_and_profile(
            base_image_url=png_data_url,
            logo_url=topmate_logo,
            profile_pic_url=profile.profile_pic,
            dimensions=dimensions
        )
        print(f"[HTML] Completed image with overlays for {profile.username}")

        # Upload to S3
        filename = f"{profile.username}-{int(__import__('time').time() * 1000)}.png"
        uploaded_url = await upload_image(final_image_url, filename)
        print(f"[HTML] Uploaded to S3: {uploaded_url}")

        return BulkGenerationResult(
            userId=profile.user_id,
            username=profile.username,
            imageUrl=uploaded_url,
            posterUrl=uploaded_url,
            success=True
        )

    except Exception as e:
        print(f"[HTML] Failed for {profile.username}: {e}")
        return BulkGenerationResult(
            userId=profile.user_id,
            username=profile.username,
            success=False,
            error=str(e)
        )
