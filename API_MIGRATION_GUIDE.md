# API Migration Guide

## Overview

The frontend has been updated to call FastAPI backend endpoints instead of Next.js API routes for the following endpoints:

### Migrated Endpoints (Using FastAPI Backend)

- ✅ `/api/generate-poster` - Single poster generation
- ✅ `/api/generate-bulk` - Bulk poster generation (CSV, HTML, Prompt modes)
- ✅ `/api/save-bulk-posters` - Save bulk posters to database

### Still Using Next.js API Routes

The following endpoints remain on Next.js and will be called locally:

- `/api/chat` - Chat functionality
- `/api/export-poster` - Export poster to PNG/PDF
- `/api/complete-carousel` - Complete carousel generation
- `/api/generate-template` - Generate poster templates
- `/api/mcp/discover-fields` - MCP field discovery
- `/api/analyze-design` - Design analysis
- `/api/generate-image` - Image generation
- `/api/upload-s3` - S3 upload
- `/api/save-local` - Local save

## What Changed

### 1. New API Utility (`app/lib/api.ts`)

Created a smart API client that automatically routes requests:
- Migrated endpoints → FastAPI backend (`http://localhost:8000`)
- Non-migrated endpoints → Next.js API routes (local)

```typescript
import { apiFetch } from '../lib/api';

// Automatically routes to correct backend
const response = await apiFetch('/api/generate-poster', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(data)
});
```

### 2. Updated Components

All components now use `apiFetch` instead of `fetch`:
- ✅ `PosterCreator.tsx`
- ✅ `BulkGenerationFlow.tsx`
- ✅ `TopmateShare.tsx`

### 3. Environment Configuration

Updated `.env.local` to include:
```bash
NEXT_PUBLIC_BACKEND_API_URL=http://localhost:8000
```

## Running the Stack

### 1. Start FastAPI Backend (Docker)

```bash
cd backend
docker-compose up --build
```

Backend will be available at: `http://localhost:8000`

### 2. Start Next.js Frontend

```bash
cd frontend
npm install  # First time only
npm run dev
```

Frontend will be available at: `http://localhost:3000`

## Verification

### Check Backend Health

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "django_api": "https://gcp.gravitron.run",
  "s3_bucket": "topmate-staging"
}
```

### Check API Routing

Open browser console and look for API calls:
- `[API] FastAPI → http://localhost:8000/api/generate-poster` ✅ Backend
- `[API] Next.js → /api/chat` ✅ Local

## Troubleshooting

### CORS Issues

If you see CORS errors, check:
1. Backend `CORS_ORIGINS` in `backend/.env` includes `http://localhost:3000`
2. Backend Docker container is running

### Connection Refused

If frontend can't connect to backend:
1. Ensure Docker container is running: `docker ps`
2. Check backend is on port 8000: `http://localhost:8000/health`
3. Verify `NEXT_PUBLIC_BACKEND_API_URL` in `frontend/.env.local`

### Mixed Content (HTTPS/HTTP)

If deploying to production:
- Update `NEXT_PUBLIC_BACKEND_API_URL` to use HTTPS
- Ensure backend has SSL/TLS configured

## Next Steps

To complete the migration, these endpoints should be ported to FastAPI:

1. **Export Functionality** (`/api/export-poster`)
   - HTML to PNG/PDF conversion
   - Multi-page PDF support
   
2. **Template Generation** (`/api/generate-template`)
   - AI template generation with dummy data
   
3. **Carousel Completion** (`/api/complete-carousel`)
   - Generate remaining carousel slides
   
4. **Chat** (`/api/chat`)
   - Streaming chat with context
   
5. **MCP Integration** (`/api/mcp/discover-fields`)
   - Database field discovery

## Architecture

```
┌─────────────────┐
│   Frontend      │
│   (Next.js)     │
│   :3000         │
└────────┬────────┘
         │
         ├──────────────────────────────────┐
         │                                  │
         │ (Migrated)                       │ (Not Migrated)
         ▼                                  ▼
┌─────────────────┐              ┌─────────────────┐
│   FastAPI       │              │   Next.js API   │
│   Backend       │              │   Routes        │
│   :8000         │              │   (Local)       │
└────────┬────────┘              └─────────────────┘
         │
         ├─ generate-poster
         ├─ generate-bulk
         └─ save-bulk-posters
```
