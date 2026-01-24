# Testing RedPanda Parallel Batch Processing

## Prerequisites

1. **Start Services**:
```bash
cd backend
docker-compose up -d
```

2. **Verify Services are Running**:
```bash
# Check all services
docker-compose ps

# Should see:
# - poster-redpanda (healthy)
# - poster-redpanda-console (running)
# - poster-postgres (healthy)
# - poster-backend (healthy)
```

3. **Access RedPanda Console**:
- Open browser: http://localhost:8080
- You should see topics: poster.generation.requests, poster.generation.results, etc.

---

## Test 1: CSV Batch Processing (Parallel)

### Create Test CSV Job
```bash
curl -X POST http://localhost:8000/api/generate-bulk \
  -H "Content-Type: application/json" \
  -d '{
    "bulkMethod": "csv",
    "csvData": [
      {"username": "user1", "name": "John Doe", "title": "Software Engineer"},
      {"username": "user2", "name": "Jane Smith", "title": "Product Manager"},
      {"username": "user3", "name": "Bob Johnson", "title": "Designer"},
      {"username": "user4", "name": "Alice Williams", "title": "Data Scientist"},
      {"username": "user5", "name": "Charlie Brown", "title": "DevOps Engineer"},
      {"username": "user6", "name": "Diana Prince", "title": "UX Researcher"},
      {"username": "user7", "name": "Ethan Hunt", "title": "Security Engineer"},
      {"username": "user8", "name": "Fiona Gallagher", "title": "Marketing Manager"}
    ],
    "csvTemplate": "<html><body style=\"width:1080px;height:1080px;background:#1a1a2e;color:white;display:flex;flex-direction:column;justify-content:center;align-items:center;font-family:Arial;\"><h1>{name}</h1><h2>{title}</h2><p>@{username}</p></body></html>",
    "csvColumns": ["username", "name", "title"],
    "size": "instagram-square",
    "model": "flash",
    "skipOverlays": false
  }'
```

**Expected Response**:
```json
{
  "success": true,
  "jobId": "job_abc123def456",
  "status": "queued",
  "totalItems": 8,
  "campaignName": "CSV Bulk Generation",
  "createdAt": "2026-01-21T...",
  "sseEndpoint": "/api/batch/jobs/job_abc123def456/stream",
  "message": "🔴 Job queued for RedPanda processing. Connect to SSE endpoint for live progress."
}
```

### Monitor Progress via SSE
```bash
# Copy the jobId from above response
JOB_ID="job_abc123def456"

# Connect to SSE stream
curl -N http://localhost:8000/api/batch/jobs/$JOB_ID/stream
```

**Expected SSE Events**:
```
event: connected
data: {"job_id":"job_abc123def456","connection_id":"conn_12345678","message":"Connected to job updates"}

event: status
data: {"job_id":"job_abc123def456","status":"queued","processed":0,"total":8,"success_count":0,"failure_count":0}

event: progress
data: {"job_id":"job_abc123def456","processed":1,"total":8,"success_count":1,"failure_count":0,"percent_complete":12.5,"current_user":"user1","phase":"processing"}

event: poster_completed
data: {"job_id":"job_abc123def456","username":"user1","poster_url":"https://s3.amazonaws.com/...","success":true}

[... more progress and poster_completed events ...]

event: job_completed
data: {"job_id":"job_abc123def456","success_count":8,"failure_count":0,"total_time_seconds":6.5,"results":[...]}
```

### Check Backend Logs
```bash
docker logs -f poster-backend

# You should see:
# 🔴 [REDPANDA] Received job message: job_abc123def456 (type: csv)
# 🔄 [PROCESS] Starting CSV job processing: job_abc123def456
# 📦 [PROCESS] Processing 8 rows in 1 batches
# 🔄 [BATCH 1/1] Processing 8 rows in parallel...
# ✅ [POSTER] Success: user1 (1/8)
# ✅ [POSTER] Success: user2 (2/8)
# ... (all 8 processed in parallel)
# 🎉 [COMPLETE] CSV Job job_abc123def456 finished!
```

### Verify Database
```bash
# Connect to PostgreSQL
docker exec -it poster-postgres psql -U poster_user -d poster_generation

# Check job status
SELECT job_id, status, total_items, processed_items, success_count, failure_count
FROM batch_jobs
WHERE job_id = 'job_abc123def456';

# Check generated posters
SELECT username, status, poster_url, processing_time_ms
FROM generated_posters
WHERE job_id = 'job_abc123def456'
ORDER BY created_at;

# Exit
\q
```

---

## Test 2: HTML Batch Processing with Topmate Profiles

### Create Test HTML Job
```bash
curl -X POST http://localhost:8000/api/generate-bulk \
  -H "Content-Type: application/json" \
  -d '{
    "bulkMethod": "html",
    "htmlTemplate": "<html><body style=\"width:1080px;height:1080px;background:linear-gradient(135deg,#667eea,#764ba2);color:white;display:flex;flex-direction:column;justify-content:center;align-items:center;font-family:Arial;\"><h1>{display_name}</h1><h2>@{username}</h2><p>{bio}</p></body></html>",
    "userIdentifiers": "saifalikhan8,testuser,demouser",
    "size": "instagram-square",
    "model": "flash",
    "skipOverlays": false
  }'
```

**Note**: Replace the usernames with actual Topmate usernames that exist in your system.

### Monitor via Frontend
1. Open your frontend (Next.js app)
2. Go to Bulk Generation flow
3. Paste the job ID or watch live progress if integrated

---

## Test 3: Check Parallel Processing Performance

### Test with 16 Users (Should Create 2 Batches)
```bash
curl -X POST http://localhost:8000/api/generate-bulk \
  -H "Content-Type: application/json" \
  -d '{
    "bulkMethod": "csv",
    "csvData": [
      {"username": "user1", "name": "User 1", "title": "Title 1"},
      {"username": "user2", "name": "User 2", "title": "Title 2"},
      {"username": "user3", "name": "User 3", "title": "Title 3"},
      {"username": "user4", "name": "User 4", "title": "Title 4"},
      {"username": "user5", "name": "User 5", "title": "Title 5"},
      {"username": "user6", "name": "User 6", "title": "Title 6"},
      {"username": "user7", "name": "User 7", "title": "Title 7"},
      {"username": "user8", "name": "User 8", "title": "Title 8"},
      {"username": "user9", "name": "User 9", "title": "Title 9"},
      {"username": "user10", "name": "User 10", "title": "Title 10"},
      {"username": "user11", "name": "User 11", "title": "Title 11"},
      {"username": "user12", "name": "User 12", "title": "Title 12"},
      {"username": "user13", "name": "User 13", "title": "Title 13"},
      {"username": "user14", "name": "User 14", "title": "Title 14"},
      {"username": "user15", "name": "User 15", "title": "Title 15"},
      {"username": "user16", "name": "User 16", "title": "Title 16"}
    ],
    "csvTemplate": "<html><body style=\"width:1080px;height:1080px;background:#1a1a2e;color:white;display:flex;flex-direction:column;justify-content:center;align-items:center;font-family:Arial;\"><h1>{name}</h1><h2>{title}</h2></body></html>",
    "csvColumns": ["username", "name", "title"],
    "size": "instagram-square",
    "model": "flash"
  }'
```

**Watch Logs for Batch Processing**:
```bash
docker logs -f poster-backend | grep BATCH

# Expected output:
# 📦 [PROCESS] Processing 16 rows in 2 batches
# 🔄 [BATCH 1/2] Processing 8 rows in parallel...
# ... (8 completions)
# 🔄 [BATCH 2/2] Processing 8 rows in parallel...
# ... (8 completions)
```

**Performance Metrics**:
- Batch 1 (8 posters): ~3-5 seconds
- Batch 2 (8 posters): ~3-5 seconds
- Total time: ~6-10 seconds

**Without Parallel Processing** (old code):
- 16 posters × 3 seconds each = ~48 seconds ❌

**With Parallel Processing** (fixed code):
- 2 batches × 4 seconds each = ~8 seconds ✅

---

## Test 4: Test Image Overlays

### Test with Logo and Profile Picture
```bash
# First, convert a logo to base64
LOGO_BASE64="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA..."

curl -X POST http://localhost:8000/api/generate-bulk \
  -H "Content-Type: application/json" \
  -d '{
    "bulkMethod": "csv",
    "csvData": [
      {"username": "testuser", "name": "Test User", "title": "Engineer"}
    ],
    "csvTemplate": "<html><body style=\"width:1080px;height:1080px;background:#f0f0f0;display:flex;align-items:center;justify-content:center;\"><h1 style=\"color:#333;\">Test Overlay</h1></body></html>",
    "csvColumns": ["username", "name", "title"],
    "size": "instagram-square",
    "model": "flash",
    "topmateLogo": "'$LOGO_BASE64'",
    "skipOverlays": false
  }'
```

**Verify Overlay**:
1. Download the generated poster
2. Check that logo appears in **top-right corner** with 20px padding
3. If profile picture was included, verify it's in **bottom-left corner** as a circle with white border

---

## Test 5: Check RedPanda Topics

### View Topics in RedPanda Console
1. Open http://localhost:8080
2. Go to "Topics"
3. Click on "poster.generation.requests"
4. You should see messages with job data

### Check Consumer Lag
```bash
docker exec -it poster-redpanda rpk group describe poster-generation-workers

# Expected output:
# GROUP                        COORDINATOR  STATE  TOTAL-LAG  MEMBERS
# poster-generation-workers    0            Stable 0          1
```

---

## Test 6: Error Handling

### Test with Invalid User
```bash
curl -X POST http://localhost:8000/api/generate-bulk \
  -H "Content-Type: application/json" \
  -d '{
    "bulkMethod": "html",
    "htmlTemplate": "<html>...</html>",
    "userIdentifiers": "nonexistent_user_12345",
    "size": "instagram-square",
    "model": "flash"
  }'
```

**Expected**:
- Job should still be created
- SSE should show failure event
- Database should have failure_count = 1
- Error logged in job_logs table

---

## Test 7: Load Test (100 Users)

### Create 100 Users Job
```python
# generate_100_users.py
import requests
import json

csv_data = [
    {"username": f"user{i}", "name": f"User {i}", "title": f"Title {i}"}
    for i in range(1, 101)
]

response = requests.post(
    "http://localhost:8000/api/generate-bulk",
    json={
        "bulkMethod": "csv",
        "csvData": csv_data,
        "csvTemplate": "<html><body style='width:1080px;height:1080px;background:#1a1a2e;color:white;display:flex;flex-direction:column;justify-content:center;align-items:center;'><h1>{name}</h1></body></html>",
        "csvColumns": ["username", "name", "title"],
        "size": "instagram-square",
        "model": "flash"
    }
)

print(json.dumps(response.json(), indent=2))
```

Run:
```bash
python generate_100_users.py
```

**Expected Performance**:
- 100 posters / 8 per batch = 13 batches
- Estimated time: 13 batches × 4 seconds = ~52 seconds
- Monitor via SSE stream or RedPanda Console

---

## Debugging

### View All Logs
```bash
# Backend logs
docker logs -f poster-backend

# RedPanda logs
docker logs -f poster-redpanda

# PostgreSQL logs
docker logs -f poster-postgres
```

### Check Database Stats
```sql
-- Average processing time per poster
SELECT AVG(processing_time_ms) as avg_ms,
       MIN(processing_time_ms) as min_ms,
       MAX(processing_time_ms) as max_ms
FROM generated_posters
WHERE status = 'completed';

-- Success rate
SELECT
  status,
  COUNT(*) as count,
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
FROM generated_posters
GROUP BY status;

-- Jobs by status
SELECT status, COUNT(*)
FROM batch_jobs
GROUP BY status;
```

### Check RedPanda Health
```bash
docker exec -it poster-redpanda rpk cluster health
docker exec -it poster-redpanda rpk topic list
```

---

## Common Issues

### Issue 1: RedPanda not starting
**Solution**:
```bash
docker-compose down -v
docker-compose up -d redpanda
# Wait 30 seconds
docker logs poster-redpanda
```

### Issue 2: Backend can't connect to RedPanda
**Solution**: Check REDPANDA_BROKER env var
```bash
docker exec -it poster-backend env | grep REDPANDA
# Should show: REDPANDA_BROKER=redpanda:9092
```

### Issue 3: Job stuck in "queued" status
**Solution**: Check if job manager consumer is running
```bash
docker logs poster-backend | grep "Job manager started"
docker logs poster-backend | grep "Job consumer started"
```

### Issue 4: Posters not generating
**Solution**: Check image conversion service
```bash
docker logs poster-backend | grep "OVERLAY"
docker logs poster-backend | grep "HTML"
```

---

## Success Criteria

✅ **All tests pass if**:
1. Jobs are created and queued successfully
2. SSE events are received in real-time
3. Posters are generated in parallel (check logs for batch processing)
4. Images are uploaded to S3 with correct URLs
5. Database contains correct job and poster records
6. RedPanda consumer lag is 0
7. No errors in logs (except for intentional error tests)
8. Image overlays (logo, profile pic) render correctly
9. Performance: 8 posters in ~4 seconds, not ~24 seconds

---

## Next Steps After Testing

1. ✅ Verify all tests pass
2. 🔄 Test Topmate DB integration (save-bulk-posters endpoint)
3. 🔄 Add monitoring (Prometheus + Grafana for RedPanda metrics)
4. 🔄 Add alerting for failed jobs
5. 🔄 Optimize batch size based on server capacity
6. 🔄 Add retry logic for transient failures
7. 🔄 Implement job cancellation
8. 🔄 Add job priority queues

---

## Cleanup

```bash
# Stop all services
docker-compose down

# Remove volumes (WARNING: Deletes all data)
docker-compose down -v

# Remove dangling images
docker image prune -f
```
