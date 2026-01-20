"""
Save Bulk Posters Router
POST /api/save-bulk-posters - Save generated posters to Topmate Django DB
"""
from fastapi import APIRouter, HTTPException
from app.models.poster import SaveBulkPostersRequest, SaveBulkPostersResponse, SaveResult
from app.services.topmate_client import fetch_topmate_profile
from app.services.storage_service import upload_image
from app.services.webhook_service import store_poster_to_django
import asyncio

router = APIRouter()


@router.post("/save-bulk-posters", response_model=SaveBulkPostersResponse)
async def save_bulk_posters(request: SaveBulkPostersRequest):
    """
    Save bulk generated posters to Topmate Django database

    Steps for each poster:
    1. Lookup user_id from username (if not provided)
    2. Upload image to S3 (if data URL)
    3. Store to Django via webhook (Video + UserShareContent)
    """
    try:
        print(f"💾 [SAVE-BULK] Saving {len(request.posters)} posters...")

        results = []

        # Process in batches with rate limiting
        BATCH_SIZE = 10
        DELAY_BETWEEN_BATCHES = 5  # seconds
        DELAY_BETWEEN_REQUESTS = 2  # seconds

        for i in range(0, len(request.posters), BATCH_SIZE):
            batch = request.posters[i:i+BATCH_SIZE]
            print(f"📦 [SAVE-BULK] Batch {i//BATCH_SIZE + 1}/{(len(request.posters) + BATCH_SIZE - 1)//BATCH_SIZE}")

            for poster in batch:
                try:
                    print(f"  📤 Processing {poster.username}...")

                    # Lookup user_id if not provided
                    user_id = None
                    if poster.userId:
                        user_id = int(poster.userId)
                        print(f"    ✅ Using provided userId: {user_id}")
                    else:
                        # Lookup with retry logic
                        print(f"    🔍 Looking up userId for {poster.username}...")
                        MAX_RETRIES = 5
                        for retry in range(MAX_RETRIES):
                            try:
                                profile = await fetch_topmate_profile(poster.username)
                                if profile and profile.user_id:
                                    user_id = int(profile.user_id)
                                    print(f"    ✅ Found userId: {user_id}")
                                    break
                            except Exception as e:
                                if "429" in str(e):  # Rate limit
                                    backoff_delay = min(30, 5 * (2 ** retry))
                                    print(f"    ⚠️ Rate limited. Retry {retry+1}/{MAX_RETRIES} after {backoff_delay}s...")
                                    await asyncio.sleep(backoff_delay)
                                else:
                                    print(f"    ❌ Lookup failed: {e}")
                                    break

                        if not user_id:
                            print(f"    ❌ Skipping {poster.username} - no user_id found")
                            results.append(SaveResult(
                                success=False,
                                error="Failed to lookup user_id"
                            ))
                            continue

                        # Add delay after lookup
                        await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

                    # Upload image if data URL
                    final_url = poster.posterUrl
                    if poster.posterUrl.startswith("data:image/"):
                        print(f"    📤 Uploading image...")
                        filename = f"{poster.username}-{int(__import__('time').time() * 1000)}.png"
                        final_url = await upload_image(poster.posterUrl, filename)
                        print(f"    ✅ Uploaded: {final_url}")
                    else:
                        print(f"    ℹ️ Already a URL: {final_url}")

                    # Store to Django
                    result = await store_poster_to_django(
                        poster_url=final_url,
                        poster_name=request.posterName,
                        user_id=user_id
                    )

                    results.append(SaveResult(
                        success=result["success"],
                        userId=user_id,
                        posterUrl=final_url,
                        error=result.get("error")
                    ))

                except Exception as e:
                    print(f"    ❌ Processing failed for {poster.username}: {e}")
                    results.append(SaveResult(
                        success=False,
                        error=str(e)
                    ))

            # Delay between batches
            if i + BATCH_SIZE < len(request.posters):
                print(f"⏸️ [SAVE-BULK] Waiting {DELAY_BETWEEN_BATCHES}s before next batch...")
                await asyncio.sleep(DELAY_BETWEEN_BATCHES)

        if not results:
            raise HTTPException(status_code=500, detail="All saves failed")

        success_count = sum(1 for r in results if r.success)
        failure_count = len(results) - success_count

        print(f"✅ [SAVE-BULK] Saved {success_count}/{len(request.posters)} posters")

        return SaveBulkPostersResponse(
            success=True,
            results=results,
            successCount=success_count,
            failureCount=failure_count
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
