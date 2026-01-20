# Poster Generation

AI-powered poster generation tool integrated with Topmate profiles. Create stunning posters for social media using profile data, AI-generated content, and customizable templates.

## Features

- 🎨 **Single Poster Creation** - Generate personalized posters from Topmate profiles
- 📊 **Smart Data Analysis** - AI analyzes your prompt to suggest relevant profile data
- 🖼️ **Reference Image Support** - Upload design references or choose from templates
- 📱 **Multiple Formats** - Instagram Square, Story, Carousel support
- 🔄 **Bulk Generation** - Generate posters for multiple users via CSV
- ☁️ **S3 Storage** - Automatic upload to AWS S3
- 🔗 **Topmate Integration** - Direct integration with Topmate API

## Architecture

```
├── frontend/          # Next.js 14 (TypeScript)
│   ├── app/
│   │   ├── components/   # React components
│   │   ├── lib/          # Utility functions
│   │   └── types/        # TypeScript types
│   └── package.json
│
├── backend/           # FastAPI (Python)
│   ├── app/
│   │   ├── routers/      # API endpoints
│   │   ├── services/     # Business logic
│   │   └── config.py     # Configuration
│   ├── requirements.txt
│   └── docker-compose.yml
```

## Prerequisites

- **Node.js** 18+ (for frontend)
- **Docker** & **Docker Compose** (for backend)
- **OpenRouter API Key** (for AI generation)
- **AWS S3 Credentials** (optional, for image storage)

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/Jaisrinivasan23/Poster-Generation.git
cd Poster-Generation
```

### 2. Backend Setup (Docker)

```bash
cd backend

# Create .env file with your credentials:
# - OPENROUTER_API_KEY=your_openrouter_key
# - DJANGO_API_URL=https://your-topmate-api.com
# - AWS credentials (optional)

# Start the backend
docker-compose up -d --build
```

The backend will be available at `http://localhost:8000`

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The frontend will be available at `http://localhost:3000`

## Environment Variables

### Backend (.env)

```env
# Required
OPENROUTER_API_KEY=sk-or-v1-xxxxx

# Topmate API
DJANGO_API_URL=https://gcp.galactus.run

# Optional - AWS S3 for image storage
AWS_S3_BUCKET=your-bucket
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_REGION=ap-south-1
S3_BASE_URL=https://your-bucket.s3.region.amazonaws.com

# Server config
BASE_URL=http://localhost:8000
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
```

### Frontend (.env.local)

```env
# Optional - defaults to localhost:8000
NEXT_PUBLIC_BACKEND_API_URL=http://localhost:8000
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check with Topmate API status |
| `/api/generate-poster` | POST | Generate single poster |
| `/api/generate-bulk` | POST | Generate bulk posters |
| `/api/generate-template` | POST | Generate template with dummy data |
| `/api/analyze-prompt` | POST | Analyze prompt for relevant fields |
| `/api/export-poster` | POST | Export poster as PNG/PDF |
| `/api/upload-s3` | POST | Upload image to S3 |

## Usage

### Single Poster Creation

1. Enter a Topmate username
2. Describe the poster you want (e.g., "Create a poster showcasing my total bookings")
3. Click **"Analyze Prompt & Fetch Relevant Data"**
4. Review and select the data fields to include
5. Optionally upload a reference image or select a template
6. Click **"Generate Poster"**

### Bulk Generation

1. Switch to **"Bulk Generation"** mode
2. Upload a CSV file with usernames
3. Define your HTML template with placeholders
4. Generate posters for all users

## Tech Stack

### Frontend
- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS
- React Hooks

### Backend
- FastAPI (Python 3.11)
- Playwright (HTML to PNG conversion)
- OpenRouter API (AI generation - Gemini models)
- boto3 (AWS S3)
- Docker

## Development

### Run Backend Locally (without Docker)

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
playwright install chromium
uvicorn app.main:app --reload --port 8000
```

### Build Frontend for Production

```bash
cd frontend
npm run build
npm start
```

## License

MIT License

