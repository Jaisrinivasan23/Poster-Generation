# Quick Start Guide - Running Frontend with FastAPI Backend

## Prerequisites
- Docker Desktop installed and running
- Node.js 18+ installed

## Step 1: Start FastAPI Backend (Docker)

```bash
cd backend
docker-compose up --build
```

**Expected output:**
```
✓ Container poster-backend  Created
✓ Container poster-backend  Started
```

**Verify it's running:**
Open http://localhost:8000/health in your browser or:
```bash
curl http://localhost:8000/health
```

## Step 2: Start Next.js Frontend

```bash
cd frontend
npm install         # First time only
npm run dev
```

**Expected output:**
```
  ▲ Next.js 14.x.x
  - Local:        http://localhost:3000
  - Ready in 2.1s
```

## Step 3: Test the Application

Open http://localhost:3000 in your browser.

### Test Single Poster Generation:
1. Enter a Topmate username (e.g., `test-user`)
2. Enter a prompt (e.g., "Create a professional poster about my services")
3. Click "Generate Poster"
4. Check browser console for `[API] FastAPI → http://localhost:8000/api/generate-poster` ✅

### Test Bulk Generation:
1. Switch to "Bulk" mode
2. Enter a prompt for template generation
3. Enter multiple usernames
4. Click "Generate"
5. Check browser console for `[API] FastAPI → http://localhost:8000/api/generate-bulk` ✅

## Troubleshooting

### Backend container not starting?
```bash
# Check Docker logs
docker logs poster-backend

# Rebuild without cache
cd backend
docker-compose down
docker-compose build --no-cache
docker-compose up
```

### Frontend can't connect to backend?
1. Check backend is running: `curl http://localhost:8000/health`
2. Verify `.env.local` has: `NEXT_PUBLIC_BACKEND_API_URL=http://localhost:8000`
3. Restart frontend: `npm run dev`

### CORS errors?
1. Check `backend/.env` has: `CORS_ORIGINS=http://localhost:3000`
2. Restart backend: `docker-compose restart`

## Environment Files

### backend/.env (Required)
```bash
OPENROUTER_API_KEY=sk-or-v1-xxx
DJANGO_API_URL=https://gcp.gravitron.run
AWS_S3_BUCKET=topmate-staging
AWS_ACCESS_KEY_ID=YOUR_KEY
AWS_SECRET_ACCESS_KEY=YOUR_SECRET
AWS_REGION=ap-south-1
S3_BASE_URL=https://topmate-staging.s3.ap-south-1.amazonaws.com
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
```

### frontend/.env.local (Required)
```bash
NEXT_PUBLIC_BACKEND_API_URL=http://localhost:8000
NEXT_PUBLIC_DJANGO_API_URL=https://gcp.galactus.run
# ... other variables
```

## Stop Everything

```bash
# Stop backend
cd backend
docker-compose down

# Stop frontend (in its terminal)
Ctrl+C
```

## API Routing Summary

| Endpoint | Target | Port |
|----------|--------|------|
| `/api/generate-poster` | FastAPI Backend | 8000 |
| `/api/generate-bulk` | FastAPI Backend | 8000 |
| `/api/save-bulk-posters` | FastAPI Backend | 8000 |
| `/api/export-poster` | Next.js Local | 3000 |
| `/api/chat` | Next.js Local | 3000 |
| Other endpoints | Next.js Local | 3000 |

**Check the console logs** to see which backend each API call is using!
