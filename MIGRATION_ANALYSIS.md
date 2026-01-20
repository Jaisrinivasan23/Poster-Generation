# Poster Generation - Migration Analysis

## Overview
Migration of poster generation system from **Next.js TypeScript** backend to **FastAPI Python** backend while keeping the exact same Next.js frontend.

## Architecture

### Current Stack (TypeScript)
- **Frontend**: Next.js 14 (React, TypeScript, Tailwind CSS)
- **Backend**: Next.js API Routes (TypeScript)
- **Image Processing**: Sharp (Node.js)
- **AI Generation**: OpenRouter API (Gemini 3 Pro/Flash)
- **Storage**: Topmate Django API (via webhooks)

### Target Stack (FastAPI Migration)
- **Frontend**: Next.js 14 (No changes - exact copy)
- **Backend**: FastAPI (Python 3.11+)
- **Image Processing**: Pillow (Python)
- **AI Generation**: OpenRouter API (same)
- **Storage**: Topmate Django API (same webhooks)

---

## Core Features to Migrate

### 1. AI Prompt Generation
**Current**: `/api/generate-poster/route.ts`

**Features**:
- Generate 3 design variants (A, B, C strategies)
- Reference image support (template inspiration)
- HTML generation or Direct image generation modes
- OpenRouter API integration (Gemini 3 Pro/Flash)
- Topmate profile integration
- Database record integration (selected records from MCP - **SKIP THIS**)

**Key Functions**:
```typescript
- callOpenRouter() - AI generation via OpenRouter
- fetchImageAsDataUrl() - Convert image URL to base64
- callOpenRouterForImage() - Direct image generation (Gemini 2.5 Flash Image)
- getCreativeDirection() - AI creative director for variant C
```

**FastAPI Endpoint**: `POST /api/generate-poster`

---

### 2. CSV Upload & Bulk Generation
**Current**: `/api/generate-bulk/route.ts`

**Features**:
- **3 Generation Modes**:
  1. **Prompt Mode**: AI generates template with dummy data
  2. **HTML Mode**: User provides HTML template
  3. **CSV Mode**: Upload CSV → replace placeholders → batch generate
- Batch processing (8 concurrent)
- Image overlay (logo + profile pic)
- S3 upload
- Retry logic for rate limits

**Key Functions**:
```typescript
- convertDynamicHtmlToPlaceholder() - Remove JavaScript from HTML templates
- replacePlaceholders() - Fill template with CSV data
- callOpenRouterForImage() - Generate images from templates
- overlayLogoAndProfile() - Add branding overlays
```

**FastAPI Endpoint**: `POST /api/generate-bulk`

---

### 3. Save to Topmate DB (Webhook)
**Current**: `/api/save-bulk-posters/route.ts`

**Features**:
- Lookup user_id from username (Topmate API)
- Upload images to S3
- Store in Django via webhook (create Video + UserShareContent)
- Batch processing with rate limit handling
- Retry logic with exponential backoff

**Key Functions**:
```typescript
- fetchTopmateProfile() - Get user data from Topmate
- uploadImage() - S3 or local storage
- storeBulkPosters() - Django webhook integration
```

**FastAPI Endpoint**: `POST /api/save-bulk-posters`

---

## Library Utilities (lib folder)

### 1. topmate.ts
**Purpose**: Topmate API client

**Functions**:
```typescript
- fetchTopmateProfile(username) → TopmateProfile
  API: https://gcp.galactus.run/fetchByUsername/?username={username}

- fetchProfileByUserId(userId) → TopmateProfile
  API: https://gcp.galactus.run/api/users/{userId}
  Fallback: MCP query (SKIP THIS - use API only)

- parseUserIdentifiers(input) → { usernames[], userIds[] }
  Parse comma/newline separated list
```

**TopmateProfile Schema**:
```typescript
{
  user_id: string
  username: string
  display_name: string
  profile_pic: string
  bio: string
  total_bookings: number
  average_rating: number
  services: TopmateService[]
  badges: TopmateBadge[]
  // ... more fields
}
```

**Python Migration**: Use `httpx` or `aiohttp` for async API calls

---

### 2. topmate-share.ts
**Purpose**: Store posters to Django backend via webhooks

**Django API Base**: `process.env.NEXT_PUBLIC_DJANGO_API_URL`
(Default: https://gcp.gravitron.run)

**Workflow**:
```
1. Generate PNG from HTML (via /api/export-poster)
2. Upload to S3 or local storage
3. Create Video entry in Django:
   POST {django_url}/create-video/
   Body: {
     external_id: string
     url: string (S3 URL)
     status: "COMPLETED"
     user: number (user_id)
   }

4. Trigger webhook to create UserShareContent:
   POST {django_url}/creatomate-webhook/
   Body: {
     id: string (external_id)
     status: "succeeded"
     output_format: "jpg"
     template_tags: ["-ms-{posterName}"]
     template_id: "email-forge-{posterName}"
     modifications: {
       campaign: string
       title: string
       description: string
       tag: "custom"
     }
     metadata: string
   }
```

**Key Functions**:
```typescript
- sharePosterToSingleUser(posterUrl, posterName, userId) → ShareResult
- storeBulkPosters(posters[]) → ShareResult[]
```

**Python Migration**: Use `httpx` for Django API calls

---

### 3. image-overlay.ts
**Purpose**: Add logo and profile picture overlays to images

**Dependencies**: `sharp` (Node.js image processing library)

**Features**:
- Resize base image to target dimensions
- Add Topmate logo (top-right, 70px width)
- Add circular profile picture (bottom-left, 100px diameter, white border)
- Composite all layers
- Return as PNG data URL

**Function**:
```typescript
overlayLogoAndProfile(
  baseImageUrl: string,
  logoUrl: string | null,
  profilePicUrl: string | null,
  dimensions: { width, height }
) → string (data URL)
```

**Python Migration**: Use `Pillow` (PIL) for image processing
```python
from PIL import Image, ImageDraw
- Image.open() - load image
- Image.resize() - resize
- ImageDraw.ellipse() - create circular mask
- Image.paste() - composite layers
```

---

## Environment Variables (.env)

**Required Variables**:
```bash
# OpenRouter API (AI generation)
OPENROUTER_API_KEY=your_key_here

# Django API (storage)
NEXT_PUBLIC_DJANGO_API_URL=https://gcp.gravitron.run

# AWS S3 (image storage)
NEXT_PUBLIC_AWS_S3_BUCKET=bucket-name
NEXT_PUBLIC_AWS_ACCESS_KEY_ID=your_key
NEXT_PUBLIC_AWS_SECRET_ACCESS_KEY=your_secret
NEXT_PUBLIC_AWS_REGION=us-east-1
NEXT_PUBLIC_S3_BASE_URL=https://bucket.s3.region.amazonaws.com

# Base URL
NEXT_PUBLIC_BASE_URL=http://localhost:3000
```

**Skip These (MCP/DB)**:
```bash
# PostgreSQL - NOT NEEDED
POSTGRES_HOST
POSTGRES_PORT
POSTGRES_DATABASE
POSTGRES_USER
POSTGRES_PASSWORD
```

---

## API Endpoints to Implement in FastAPI

### 1. POST /api/generate-poster
**Request**:
```json
{
  "config": {
    "topmateUsername": "string",
    "prompt": "string",
    "size": "instagram-square",
    "mode": "single",
    "generationMode": "html"
  },
  "referenceImage": "data:image/...", // optional
  "model": "pro", // or "flash"
  "selectedRecords": [] // SKIP - not needed
}
```

**Response**:
```json
{
  "success": true,
  "posters": [
    {
      "generationMode": "html",
      "html": "<!DOCTYPE html>...",
      "dimensions": { "width": 1080, "height": 1080 },
      "topmateProfile": { ... },
      "variantIndex": 0,
      "strategyName": "reference-faithful"
    }
  ],
  "mode": "single"
}
```

---

### 2. POST /api/generate-bulk
**Request**:
```json
{
  "bulkMethod": "csv", // "prompt" | "html" | "csv"
  "csvData": [ {...}, {...} ], // CSV rows
  "csvColumns": ["username", "name", "..."],
  "csvTemplate": "<html>...",
  "posterName": "campaign-name",
  "size": "instagram-square",
  "customWidth": 1080,
  "customHeight": 1350,
  "skipOverlays": true,
  "topmateLogo": "data:image/..."
}
```

**Response**:
```json
{
  "success": true,
  "results": [
    {
      "username": "johndoe",
      "imageUrl": "https://s3.../image.png",
      "posterUrl": "https://s3.../image.png",
      "success": true
    }
  ],
  "successCount": 10,
  "failureCount": 0
}
```

---

### 3. POST /api/save-bulk-posters
**Request**:
```json
{
  "posters": [
    {
      "userId": "123",
      "username": "johndoe",
      "posterUrl": "https://s3.../image.png"
    }
  ],
  "posterName": "campaign-name"
}
```

**Response**:
```json
{
  "success": true,
  "results": [
    {
      "success": true,
      "userId": 123,
      "posterUrl": "https://s3.../image.png"
    }
  ],
  "successCount": 10,
  "failureCount": 0
}
```

---

## Migration Checklist

### Backend (FastAPI)
- [ ] Setup FastAPI project structure
- [ ] Install dependencies (httpx, pillow, boto3, python-multipart)
- [ ] Create `routers/generate_poster.py`
- [ ] Create `routers/generate_bulk.py`
- [ ] Create `routers/save_bulk_posters.py`
- [ ] Create `services/topmate_client.py`
- [ ] Create `services/openrouter_client.py`
- [ ] Create `services/image_processor.py`
- [ ] Create `services/storage_service.py` (S3)
- [ ] Create `services/webhook_service.py` (Django)
- [ ] Setup environment variables (.env)
- [ ] CORS configuration for Next.js frontend
- [ ] Error handling and logging

### Frontend (Next.js)
- [x] Copied to `frontend/` folder (no changes needed)
- [ ] Update API base URL to FastAPI backend
- [ ] Test all flows with new backend

### Testing
- [ ] Test AI prompt generation
- [ ] Test CSV upload flow
- [ ] Test bulk generation
- [ ] Test Topmate webhook storage
- [ ] Test S3 upload
- [ ] Test error handling

---

## Key Differences: TypeScript → Python

### 1. HTTP Clients
```typescript
// TypeScript (Next.js)
const response = await fetch(url, options)
```
```python
# Python (FastAPI)
import httpx
async with httpx.AsyncClient() as client:
    response = await client.post(url, json=data)
```

### 2. Image Processing
```typescript
// TypeScript (Sharp)
const buffer = await sharp(input)
  .resize(width, height)
  .png()
  .toBuffer()
```
```python
# Python (Pillow)
from PIL import Image
img = Image.open(input)
img = img.resize((width, height))
img.save(output, 'PNG')
```

### 3. Base64 Encoding
```typescript
// TypeScript
const base64 = Buffer.from(data).toString('base64')
```
```python
# Python
import base64
base64_str = base64.b64encode(data).decode('utf-8')
```

### 4. Async/Await
```typescript
// TypeScript
async function myFunction() {
  const result = await someAsyncOperation()
  return result
}
```
```python
# Python
async def my_function():
    result = await some_async_operation()
    return result
```

---

## Notes

1. **Skip MCP Integration**: No PostgreSQL database queries needed. Only use Topmate API endpoints.

2. **Same Endpoints**: Keep exact same endpoint paths for frontend compatibility.

3. **Same .env Variables**: Use identical environment variable names.

4. **Batch Processing**: Implement concurrent batch processing like TypeScript (asyncio.gather or ThreadPoolExecutor).

5. **Rate Limiting**: Add retry logic with exponential backoff for Topmate API (429 errors).

6. **Webhook Format**: Match exact Django webhook payload format from topmate-share.ts.

7. **S3 Upload**: Use boto3 for AWS S3 uploads (same as TypeScript flow).

---

## Next Steps

1. ✅ Frontend copied to `frontend/` folder
2. ✅ Backend analyzed and documented
3. ⏳ Create FastAPI project structure
4. ⏳ Implement core services (Topmate client, OpenRouter client)
5. ⏳ Implement API endpoints
6. ⏳ Test integration with Next.js frontend
