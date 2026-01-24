# New Flow: Auto-Fetch user_id from Topmate API

## Overview

**CSV no longer requires user_id!** The system now automatically fetches user details from Topmate API during poster generation and stores them in PostgreSQL for later use.

## Flow

### 1. CSV Upload (Frontend)
- **Required**: `username` column only
- **Optional**: `user_id`, `display_name`, `profile_pic`, etc.
- No validation error if user_id is missing

### 2. Poster Generation (Backend)
For each CSV row:

**Step 1: Check CSV for user_id**
```python
user_id = row.get("user_id") or row.get("userId")
```

**Step 2: If no user_id, fetch from Topmate API**
```python
if not user_id:
    topmate_profile = await fetch_topmate_profile(username)
    if topmate_profile:
        user_id = topmate_profile.user_id
        # Also get display_name, profile_pic, bio, etc.
```

**Step 3: Store in PostgreSQL**
```python
metadata = {
    "user_id": user_id,
    "display_name": topmate_profile.display_name,
    "profile_pic": topmate_profile.profile_pic,
    "bio": topmate_profile.bio,
    "fetched_from_api": True
}
await database_service.create_poster_record(
    job_id=job_id,
    username=username,
    metadata=metadata  # ✅ Stored in PostgreSQL
)
```

**Step 4: Generate poster**
- Convert HTML to image
- Upload to S3
- Update poster record with URL

### 3. Save to Topmate DB (Backend + Frontend)

**Frontend:**
```javascript
// Fetch posters WITH user_id from PostgreSQL
const response = await apiFetch(`/api/batch/jobs/${jobId}/posters-for-save`);
// Response includes user_id from metadata
const posters = response.posters; // [{username, posterUrl, userId}]

// Send to save endpoint
await apiFetch('/api/save-bulk-posters', {
    posters: posters  // ✅ Includes userId from PostgreSQL
});
```

**Backend:**
```python
# Save endpoint receives posters with userId
for poster in request.posters:
    user_id = poster.userId  # ✅ From PostgreSQL, not from API
    # Create Video + UserShareContent in Django
    await store_poster_to_django(user_id, poster_url, poster_name)
```

## Benefits

1. **✅ Simpler CSV**: Only username required
2. **✅ Parallel API Calls**: Fetch all profiles in parallel during generation (10 at a time)
3. **✅ No Repeated Calls**: Fetch once during generation, reuse from DB during save
4. **✅ Faster Save**: No API calls during save (just read from PostgreSQL)
5. **✅ Profile Data Stored**: display_name, profile_pic, bio all stored for future use

## Example CSV Files

### Minimal CSV (username only)
```csv
username
phase
testuser
johndoe
```

### CSV with user_id (skips API fetch)
```csv
username,user_id
phase,1058727
testuser,67890
```

### Full CSV (all optional fields)
```csv
username,user_id,display_name,profile_pic
phase,1058727,Phase Test,https://example.com/pic.jpg
```

## Backend Logs

### Generation with API Fetch:
```
🔍 [CSV-POSTER phase] No user_id in CSV - fetching from Topmate API...
✅ [CSV-POSTER phase] Fetched from Topmate API: user_id=1058727
✅ [CSV-POSTER phase] user_id: 1058727 (from Topmate API)
💾 [CSV-POSTER phase] Poster record created (ID: poster_xxx)
📋 [CSV-POSTER phase] Metadata: {'user_id': 1058727, 'display_name': 'Phase', 'profile_pic': '...', 'fetched_from_api': True}
```

### Save to DB (uses PostgreSQL):
```
ℹ️ [SAVE-JOB] Saving poster for: phase
ℹ️ [SAVE-JOB] Using userId: 1058727  ← From PostgreSQL metadata
✅ [SAVE-JOB] Saved to Topmate DB: phase
```

## Testing

**Test File Created:** `test_csv_no_userid.csv`
```csv
username,display_name
phase,Phase Test User
```

**Test Steps:**
1. Upload `test_csv_no_userid.csv` (no user_id column)
2. Generate posters
3. Watch backend logs - should see API fetch
4. Click "Save to Database"
5. Should save successfully using user_id from PostgreSQL

## Files Modified

### Frontend:
- `frontend/app/components/PosterCreator.tsx`
  - Removed user_id validation error
  - Removed warning banner
  - CSV upload now accepts username-only files

### Backend:
- `backend/app/services/job_manager.py`
  - Added Topmate API fetch during generation
  - Stores full profile data in PostgreSQL metadata
  - Parallel processing (already exists)

### No Changes Needed:
- `backend/app/routers/batch_processing.py` - endpoint already returns user_id from metadata
- `backend/app/routers/save_bulk_posters.py` - already uses userId from request
- Frontend save logic - already fetches from `/posters-for-save` endpoint
