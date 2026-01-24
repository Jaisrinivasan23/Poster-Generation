# PostgreSQL Database Schema

## Overview

All poster generation data is stored in PostgreSQL with 4 main tables:
1. `batch_jobs` - Job metadata and status
2. `generated_posters` - Individual poster records with user data
3. `job_logs` - Logs for each job
4. `poster_failure_details` - Detailed failure information

---

## 1. Table: `generated_posters` (Main Storage)

**This is where user data from Topmate API is stored!**

### Schema:
```sql
CREATE TABLE generated_posters (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id VARCHAR(100) NOT NULL,
    user_identifier VARCHAR(255),         -- Username from CSV
    username VARCHAR(255),                 -- Username from CSV
    display_name VARCHAR(255),             -- From CSV or Topmate API
    poster_url VARCHAR(500),               -- S3 URL of generated poster
    s3_key VARCHAR(500),                   -- S3 key for poster
    status job_status DEFAULT 'pending',   -- pending/processing/completed/failed
    processing_time_ms INTEGER,            -- How long generation took
    error_message TEXT,                    -- Error if generation failed
    metadata JSONB DEFAULT '{}',           -- ✅ USER DATA STORED HERE!
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### Metadata Field (JSONB)

**This is the KEY field where Topmate API data is stored!**

#### When CSV has user_id:
```json
{
  "user_id": 1058727
}
```

#### When fetched from Topmate API:
```json
{
  "user_id": 1058727,
  "display_name": "Phase",
  "profile_pic": "https://topmate-assets.com/profile.jpg",
  "bio": "Product designer and mentor",
  "fetched_from_api": true
}
```

### Example Row:
```
id: 9a3f7d82-5e4b-4f3a-9c6d-1b2e8a4f3c5d
job_id: job_a926e02f7e5a
user_identifier: phase
username: phase
display_name: Phase
poster_url: https://topmate-staging.s3.ap-south-1.amazonaws.com/job_xxx/phase_xxx.png
s3_key: job_xxx/phase_xxx.png
status: completed
processing_time_ms: 2341
error_message: NULL
metadata: {
  "user_id": 1058727,
  "display_name": "Phase",
  "profile_pic": "https://...",
  "bio": "Product designer...",
  "fetched_from_api": true
}
created_at: 2026-01-22 05:52:10+00
updated_at: 2026-01-22 05:52:12+00
```

---

## 2. Table: `batch_jobs`

Stores job-level information.

### Schema:
```sql
CREATE TABLE batch_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id VARCHAR(100) UNIQUE NOT NULL,
    campaign_name VARCHAR(255),
    status job_status DEFAULT 'pending',
    total_items INTEGER DEFAULT 0,
    processed_items INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    template_html TEXT,                    -- HTML template for generation
    template_url VARCHAR(500),
    poster_size VARCHAR(50),               -- instagram-square, etc.
    model VARCHAR(50),                     -- flash/pro
    user_identifiers TEXT,                 -- Original CSV usernames
    metadata JSONB DEFAULT '{}',
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### Example Row:
```
id: 1a2b3c4d-5e6f-7890-abcd-ef1234567890
job_id: job_a926e02f7e5a
campaign_name: Q1 Marketing Campaign
status: completed
total_items: 157
processed_items: 157
success_count: 155
failure_count: 2
template_html: <div style="...">...</div>
poster_size: instagram-square
model: flash
user_identifiers: phase,testuser,johndoe,...
metadata: {
  "skip_overlays": true,
  "dimensions": {"width": 1080, "height": 1080}
}
created_at: 2026-01-22 05:52:00+00
started_at: 2026-01-22 05:52:02+00
completed_at: 2026-01-22 05:57:45+00
```

---

## 3. Table: `job_logs`

Stores logs for debugging and monitoring.

### Schema:
```sql
CREATE TABLE job_logs (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(100) NOT NULL,
    level log_level DEFAULT 'INFO',        -- DEBUG/INFO/WARNING/ERROR/CRITICAL
    message TEXT NOT NULL,
    details JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### Example Rows:
```
id: 1
job_id: job_a926e02f7e5a
level: INFO
message: CSV job processing started - 157 posters to generate
details: {}
created_at: 2026-01-22 05:52:02+00

id: 2
job_id: job_a926e02f7e5a
level: INFO
message: [FRONTEND ERROR] sse_error: Connection failed
details: {
  "error_type": "sse_error",
  "error_message": "Connection failed",
  "user_agent": "Mozilla/5.0...",
  "source": "frontend"
}
created_at: 2026-01-22 05:53:15+00
```

---

## 4. Table: `poster_failure_details`

Stores detailed information about failed poster generations.

### Schema:
```sql
CREATE TABLE poster_failure_details (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id VARCHAR(100) NOT NULL,
    poster_id UUID,                        -- References generated_posters(id)
    user_identifier VARCHAR(255),
    username VARCHAR(255),
    failure_type VARCHAR(100),             -- api_error/timeout/validation_error
    error_message TEXT,
    error_details JSONB DEFAULT '{}',
    retry_count INTEGER DEFAULT 0,
    html_template TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

---

## Data Flow

### 1. CSV Upload → Generation
```
CSV: username
     phase

↓ Backend fetches from Topmate API

generated_posters table:
{
  username: "phase",
  display_name: "Phase",
  metadata: {
    "user_id": 1058727,
    "display_name": "Phase",
    "profile_pic": "https://...",
    "bio": "Product designer...",
    "fetched_from_api": true
  }
}
```

### 2. Save to Topmate DB
```
Frontend calls: /api/batch/jobs/{job_id}/posters-for-save

Backend reads from generated_posters table:
SELECT username, poster_url, metadata->>'user_id' as user_id
FROM generated_posters
WHERE job_id = 'job_xxx' AND status = 'completed'

Returns:
[{
  username: "phase",
  posterUrl: "https://s3.../poster.png",
  userId: 1058727  ← From PostgreSQL metadata
}]

Frontend sends to /api/save-bulk-posters with userId
Backend saves to Django (Video + UserShareContent)
```

---

## Query Examples

### Get all posters with user_id for a job:
```sql
SELECT
    username,
    poster_url,
    metadata->>'user_id' as user_id,
    metadata->>'display_name' as display_name,
    metadata->>'profile_pic' as profile_pic
FROM generated_posters
WHERE job_id = 'job_a926e02f7e5a'
  AND status = 'completed'
  AND metadata ? 'user_id';
```

### Get posters missing user_id:
```sql
SELECT username, poster_url
FROM generated_posters
WHERE job_id = 'job_a926e02f7e5a'
  AND status = 'completed'
  AND NOT (metadata ? 'user_id');
```

### Get job statistics:
```sql
SELECT
    job_id,
    campaign_name,
    status,
    total_items,
    success_count,
    failure_count,
    (success_count::float / NULLIF(total_items, 0) * 100) as success_rate,
    completed_at - started_at as processing_duration
FROM batch_jobs
WHERE job_id = 'job_a926e02f7e5a';
```

### Check if user_id was fetched from API:
```sql
SELECT
    username,
    metadata->>'user_id' as user_id,
    metadata->>'fetched_from_api' as fetched_from_api
FROM generated_posters
WHERE job_id = 'job_a926e02f7e5a'
  AND metadata ? 'fetched_from_api';
```

---

## Connect to PostgreSQL

### Using Docker:
```bash
docker exec -it poster-postgres psql -U postgres -d poster_db
```

### Sample Queries:
```sql
-- List all jobs
SELECT job_id, campaign_name, status, total_items, success_count
FROM batch_jobs
ORDER BY created_at DESC
LIMIT 10;

-- Get poster details for a job
SELECT username, display_name, status,
       metadata->>'user_id' as user_id,
       metadata->>'fetched_from_api' as fetched_from_api
FROM generated_posters
WHERE job_id = 'job_xxx';

-- Check logs for a job
SELECT level, message, created_at
FROM job_logs
WHERE job_id = 'job_xxx'
ORDER BY created_at DESC;
```

---

## Summary

**Where user data is stored:** `generated_posters.metadata` (JSONB field)

**What is stored:**
- ✅ `user_id` - From CSV or Topmate API
- ✅ `display_name` - From CSV or Topmate API
- ✅ `profile_pic` - From Topmate API
- ✅ `bio` - From Topmate API
- ✅ `fetched_from_api` - Boolean flag indicating if data came from API

**Why JSONB?**
- Flexible: Can store any profile data
- Queryable: Can use `metadata->>'user_id'` to extract values
- Indexed: Can create GIN index for fast queries
- No schema changes: Add new fields without ALTER TABLE
