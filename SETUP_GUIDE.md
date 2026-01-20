# Quick Setup Guide - Poster Generation Migration

## What Was Created

A complete poster generation system with **separated frontend and backend**:

```
poster-generation-migration/
├── frontend/          # Next.js 14 (exact copy - no changes needed)
├── backend/           # FastAPI Python (NEW - migrated from TypeScript)
├── MIGRATION_ANALYSIS.md   # Detailed technical analysis
└── README.md          # Main documentation
```

## Key Features

✅ **2 Generation Modes**:
1. **AI Prompt** - Generate posters using AI (OpenRouter/Gemini)
2. **CSV Upload** - Bulk generate from CSV data

✅ **Same Endpoints** - Exact API compatibility with original TypeScript

✅ **Topmate Integration** - Fetch profiles & store via Django webhook

✅ **No MCP/Database** - Uses only Topmate API (simplified)

## Quick Start

### 1. Backend Setup (FastAPI)

```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate    # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env
# Edit .env with your API keys

# Run server
uvicorn app.main:app --reload --port 8000
```

Backend will run at: **http://localhost:8000**

### 2. Frontend Setup (Next.js)

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
copy .env.example .env.local
# Edit .env.local:
# NEXT_PUBLIC_BASE_URL=http://localhost:8000

# Run dev server
npm run dev
```

Frontend will run at: **http://localhost:3000**

## Environment Variables

### Backend (.env)
```bash
OPENROUTER_API_KEY=sk-or-v1-xxx...     # Get from openrouter.ai
DJANGO_API_URL=https://gcp.gravitron.run
AWS_S3_BUCKET=your-bucket-name
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=xxx...
AWS_REGION=us-east-1
CORS_ORIGINS=http://localhost:3000
```

### Frontend (.env.local)
```bash
NEXT_PUBLIC_BASE_URL=http://localhost:8000   # Point to FastAPI backend
NEXT_PUBLIC_DJANGO_API_URL=https://gcp.gravitron.run
NEXT_PUBLIC_AWS_S3_BUCKET=your-bucket-name
NEXT_PUBLIC_AWS_ACCESS_KEY_ID=AKIA...
NEXT_PUBLIC_AWS_SECRET_ACCESS_KEY=xxx...
NEXT_PUBLIC_AWS_REGION=us-east-1
```

## API Endpoints (FastAPI Backend)

All endpoints maintain exact compatibility with original TypeScript:

### 1. Generate Poster (AI)
```http
POST http://localhost:8000/api/generate-poster
Content-Type: application/json

{
  "config": {
    "topmateUsername": "johndoe",
    "prompt": "Create a professional poster about mentorship",
    "size": "instagram-square",
    "mode": "single"
  },
  "model": "pro"
}
```

### 2. Generate Bulk (CSV)
```http
POST http://localhost:8000/api/generate-bulk
Content-Type: application/json

{
  "bulkMethod": "csv",
  "csvData": [...],
  "csvColumns": ["username", "name"],
  "csvTemplate": "<html>...</html>",
  "posterName": "my-campaign",
  "size": "instagram-square"
}
```

### 3. Save to Topmate DB
```http
POST http://localhost:8000/api/save-bulk-posters
Content-Type: application/json

{
  "posters": [
    {"username": "user1", "posterUrl": "https://s3..."}
  ],
  "posterName": "campaign-name"
}
```

## Testing

### 1. Test Backend Health
```bash
curl http://localhost:8000/health
```

Should return:
```json
{
  "status": "healthy",
  "django_api": "https://gcp.gravitron.run",
  "s3_bucket": "your-bucket-name"
}
```

### 2. Test AI Generation
Open frontend at http://localhost:3000 and:
1. Enter Topmate username
2. Enter prompt (e.g., "Professional mentorship poster")
3. Click Generate
4. View 3 design variants

### 3. Test CSV Bulk Generation
1. Switch to "Bulk" mode
2. Upload CSV file with columns: `username`, `name`, etc.
3. Paste HTML template with placeholders: `{username}`, `{name}`
4. Click Generate Bulk
5. Download generated posters

## Project Structure

### Backend (FastAPI)
```
backend/
├── app/
│   ├── main.py                    # FastAPI entry point
│   ├── config.py                  # Settings
│   ├── routers/
│   │   ├── generate_poster.py     # AI generation endpoint
│   │   ├── generate_bulk.py       # Bulk generation endpoint
│   │   └── save_bulk_posters.py   # Save to DB endpoint
│   ├── services/
│   │   ├── topmate_client.py      # Topmate API client
│   │   ├── openrouter_client.py   # OpenRouter API client
│   │   ├── image_processor.py     # Image overlays (Pillow)
│   │   ├── storage_service.py     # S3 uploads (boto3)
│   │   └── webhook_service.py     # Django webhooks
│   └── models/
│       └── poster.py              # Pydantic schemas
├── requirements.txt
├── .env.example
└── README.md
```

### Frontend (Next.js) - No Changes
```
frontend/
├── app/
│   ├── api/              # (Will call FastAPI backend)
│   ├── components/       # React components
│   ├── lib/              # Utilities
│   └── types/            # TypeScript types
├── package.json
└── next.config.ts
```

## What's Different from Original

### Removed
- ❌ MCP integration (PostgreSQL database queries)
- ❌ Direct database client
- ❌ Complex DB field discovery

### Changed
- ✅ Backend: TypeScript → Python (FastAPI)
- ✅ Image Processing: Sharp → Pillow
- ✅ HTTP Client: fetch → httpx

### Same
- ✅ Frontend: Exact copy (no changes)
- ✅ API Endpoints: Same paths & schemas
- ✅ .env Variables: Same names
- ✅ Topmate Integration: Same flow
- ✅ Django Webhooks: Same payload format

## Known Limitations

1. **HTML to PNG Conversion**: Not yet implemented in FastAPI
   - Requires Playwright or Puppeteer integration
   - Currently returns placeholder

2. **Image Overlays**: Basic implementation
   - Works for logo and profile pictures
   - May need refinement for complex cases

## Next Steps

1. ✅ Backend structure created
2. ✅ Services implemented (Topmate, OpenRouter, S3, Django)
3. ✅ API endpoints created
4. ⏳ **TODO**: Implement HTML to PNG conversion (Playwright)
5. ⏳ **TODO**: Test full flow end-to-end
6. ⏳ **TODO**: Add error handling improvements
7. ⏳ **TODO**: Add logging and monitoring

## Troubleshooting

### Backend won't start
```bash
# Check Python version (need 3.11+)
python --version

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### CORS errors
Add your frontend URL to backend `.env`:
```bash
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
```

### Topmate API rate limits
Increase delays in `webhook_service.py`:
```python
DELAY_BETWEEN_REQUESTS = 5  # Increase to 5 seconds
```

### S3 upload failures
Test S3 credentials:
```bash
aws s3 ls s3://your-bucket-name --profile your-profile
```

## Support & Documentation

- **MIGRATION_ANALYSIS.md** - Detailed technical migration guide
- **backend/README.md** - Backend-specific documentation
- **Frontend docs** - See original Next.js documentation

## Questions?

Check the migration analysis document for detailed explanations of all services and endpoints.
