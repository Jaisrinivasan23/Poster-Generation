# FastAPI Poster Generation Backend

Python FastAPI backend for poster generation, migrated from Next.js TypeScript.

## Features

- AI poster generation via OpenRouter (Gemini 3 Pro/Flash)
- CSV upload & bulk generation
- Topmate API integration
- Django webhook storage
- S3 image uploads
- Batch processing with rate limiting

## Setup

### 1. Install Dependencies

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate

# Install packages
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy .env.example to .env
cp .env.example .env

# Edit .env with your credentials
```

Required variables:
- `OPENROUTER_API_KEY` - OpenRouter API key
- `DJANGO_API_URL` - Django backend URL (default: https://gcp.gravitron.run)
- `AWS_S3_BUCKET`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` - S3 credentials
- `CORS_ORIGINS` - Allowed frontend origins (comma-separated)

### 3. Run Server

```bash
# Development server with auto-reload
uvicorn app.main:app --reload --port 8000

# Production server
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

API will be available at `http://localhost:8000`

## API Endpoints

### POST /api/generate-poster
Generate poster with AI (single or carousel mode)

**Request:**
```json
{
  "config": {
    "topmateUsername": "johndoe",
    "prompt": "Fiery women empowerment poster",
    "size": "instagram-square",
    "mode": "single",
    "generationMode": "html"
  },
  "model": "pro",
  "referenceImage": "data:image/..."
}
```

**Response:**
```json
{
  "success": true,
  "posters": [...],
  "mode": "single"
}
```

### POST /api/generate-bulk
Bulk poster generation (CSV, HTML template, or AI prompt)

**Request:**
```json
{
  "bulkMethod": "csv",
  "csvData": [...],
  "csvColumns": ["username", "name"],
  "csvTemplate": "<html>...",
  "posterName": "campaign-name",
  "size": "instagram-square"
}
```

### POST /api/save-bulk-posters
Save generated posters to Topmate Django DB

**Request:**
```json
{
  "posters": [
    {"username": "johndoe", "posterUrl": "https://..."}
  ],
  "posterName": "campaign-name"
}
```

## Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Environment configuration
│   ├── routers/             # API endpoints
│   │   ├── generate_poster.py
│   │   ├── generate_bulk.py
│   │   └── save_bulk_posters.py
│   ├── services/            # Business logic
│   │   ├── topmate_client.py
│   │   ├── openrouter_client.py
│   │   ├── image_processor.py
│   │   ├── storage_service.py
│   │   └── webhook_service.py
│   └── models/              # Pydantic models
│       └── poster.py
├── requirements.txt
├── .env.example
└── README.md
```

## Development

### Running Tests
```bash
pytest
```

### Code Formatting
```bash
black app/
```

### Type Checking
```bash
mypy app/
```

## Notes

- **No MCP/PostgreSQL**: Removed database integration, uses only Topmate API
- **Same Endpoints**: Matches original TypeScript API exactly
- **HTML to PNG**: Currently placeholder - needs Playwright/Puppeteer integration
- **Rate Limiting**: Implements exponential backoff for Topmate API

## Troubleshooting

### CORS Errors
Add your frontend URL to `CORS_ORIGINS` in `.env`:
```
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
```

### S3 Upload Failures
Verify AWS credentials and bucket permissions:
```bash
aws s3 ls s3://your-bucket-name
```

### OpenRouter API Errors
Check API key and credits at https://openrouter.ai/

## License

Same as original project
