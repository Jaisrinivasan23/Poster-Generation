# Template Generation API Documentation

## Base URL
```
http://localhost:8000/api
```

---

## Endpoints

### 1. Upload Template
**POST** `/templates/upload`

Upload a new HTML template with placeholders.

**Request Body:**
```json
{
  "section": "testimonial",
  "name": "Modern Testimonial Design",
  "html_content": "<div style='padding:40px'>{{consumer_name}}: {{consumer_message}}</div>",
  "css_content": "",
  "set_as_active": true
}
```

**Response:**
```json
{
  "template_id": "uuid",
  "version": 1,
  "section": "testimonial",
  "placeholders": [
    {"name": "consumer_name", "sample_value": null, "data_type": "text", "is_required": true},
    {"name": "consumer_message", "sample_value": null, "data_type": "text", "is_required": true}
  ],
  "message": "Template uploaded successfully (version 1)"
}
```

---

### 2. Generate Poster (Async with TaskIQ + RedPanda)
**POST** `/templates/generate`

Generate a poster from template using parallel processing.

**Request Body:**
```json
{
  "template_id": "testimonial_latest",
  "custom_data": {
    "consumer_name": "John Doe",
    "consumer_message": "Excellent mentor!",
    "rating": "5.0"
  },
  "metadata": {
    "user_id": 123,
    "testimonial_id": "test_001"
  }
}
```

**Response:**
```json
{
  "success": true,
  "job_id": "template_gen_abc123",
  "message": "Poster generation queued successfully",
  "status_endpoint": "/api/templates/job/template_gen_abc123"
}
```

**Processing Flow:**
1. FastAPI validates template exists
2. Creates job record in database
3. Logs to `template_generation_logs`
4. Queues task to TaskIQ
5. TaskIQ publishes to RedPanda
6. Worker picks up job
7. Renders HTML → PNG (Playwright)
8. Uploads to S3
9. Logs result to `template_poster_results`
10. Sends SSE completion event

---

### 3. Check Job Status
**GET** `/templates/job/{job_id}`

Get status and results of a generation job.

**Response:**
```json
{
  "job_id": "template_gen_abc123",
  "status": "completed",
  "template_section": "testimonial",
  "template_version": 1,
  "total_items": 1,
  "processed_items": 1,
  "success_count": 1,
  "failure_count": 0,
  "created_at": "2026-01-22T11:47:30Z",
  "started_at": "2026-01-22T11:47:31Z",
  "completed_at": "2026-01-22T11:47:40Z",
  "results": [
    {
      "entity_id": "test_001",
      "url": "https://s3.amazonaws.com/.../poster.png",
      "status": "completed",
      "generation_time_ms": 9119,
      "error": null
    }
  ]
}
```

**Job Status Values:**
- `queued` - Job created, waiting for worker
- `processing` - Worker is generating poster
- `completed` - Successfully generated
- `failed` - Generation failed

---

### 4. List Templates
**GET** `/templates?section=testimonial`

List all templates, optionally filtered by section.

**Response:**
```json
{
  "section": "testimonial",
  "templates": [
    {
      "id": "uuid",
      "section": "testimonial",
      "name": "Modern Testimonial",
      "version": 2,
      "is_active": true,
      "created_at": "2026-01-22T10:00:00Z",
      "placeholders": [
        {"name": "consumer_name", "sample_value": null}
      ]
    }
  ],
  "active_template": {...}
}
```

---

### 5. Activate Template
**POST** `/templates/{template_id}/activate`

Set a specific template version as active.

**Response:**
```json
{
  "template_id": "uuid",
  "section": "testimonial",
  "version": 2,
  "is_active": true,
  "message": "Template activated successfully"
}
```

---

## Template ID Format

Template IDs follow the pattern: `{section}_latest`

**Examples:**
- `testimonial_latest` → Latest active template in "testimonial" section
- `top_new_launch_latest` → Latest active template in "top_new_launch" section
- `announcement_latest` → Latest active template in "announcement" section

The system automatically resolves `_latest` to the current active version.

---

## Placeholder Syntax

Use double curly braces in HTML templates:

```html
<div>
  <h1>{{consumer_name}}</h1>
  <p>{{consumer_message}}</p>
  <span>Rating: {{rating}}/5</span>
</div>
```

Placeholders are automatically extracted and validated.

---

## Database Tables

### `templates`
Stores HTML template definitions
- `id` (UUID)
- `section` (VARCHAR)
- `name` (VARCHAR)
- `html_content` (TEXT)
- `css_content` (TEXT)
- `version` (INTEGER)
- `is_active` (BOOLEAN)
- `preview_data` (JSONB)

### `template_generation_jobs`
Tracks generation jobs
- `job_id` (VARCHAR)
- `template_id` (UUID)
- `status` (ENUM)
- `total_items` (INTEGER)
- `processed_items` (INTEGER)
- `success_count` (INTEGER)
- `failure_count` (INTEGER)
- `input_data` (JSONB)
- `metadata` (JSONB)

### `template_generation_logs`
Detailed logs for each job
- `job_id` (VARCHAR)
- `level` (ENUM: INFO, WARNING, ERROR)
- `message` (TEXT)
- `details` (JSONB)
- `created_at` (TIMESTAMP)

### `template_poster_results`
Individual poster generation results
- `job_id` (VARCHAR)
- `entity_id` (VARCHAR)
- `custom_data` (JSONB)
- `output_url` (VARCHAR)
- `s3_key` (VARCHAR)
- `status` (ENUM)
- `generation_time_ms` (INTEGER)
- `error_message` (TEXT)

---

## Error Handling

### 404 - Template Not Found
```json
{
  "detail": "No active template found for section 'testimonial'"
}
```

### 500 - Generation Failed
```json
{
  "detail": "Rendering error: ..."
}
```

Errors are logged to:
- `template_generation_logs` table
- `template_poster_results` table (with error_message)

---

## Performance

### Single Poster Generation
- Queue time: < 100ms
- Processing time: 8-12 seconds
  - HTML rendering: 5-8s
  - S3 upload: 2-3s
- Total: ~9 seconds average

### Parallel Processing (Future)
With batch endpoint, 100 posters can be generated in parallel:
- Sequential: ~15 minutes (100 × 9s)
- Parallel (10 workers): ~2 minutes
- **Speedup: 7-8x**

---

## Example Integration (Django)

```python
import requests
import time

class PosterGenerationService:
    BASE_URL = "http://fastapi:8000/api"

    def generate_testimonial_poster(self, testimonial):
        """Generate poster for a testimonial"""

        # Generate poster
        response = requests.post(
            f"{self.BASE_URL}/templates/generate",
            json={
                "template_id": "testimonial_latest",
                "custom_data": {
                    "consumer_name": testimonial.consumer_name,
                    "consumer_message": testimonial.message,
                    "rating": str(testimonial.rating)
                },
                "metadata": {
                    "user_id": testimonial.user_id,
                    "testimonial_id": str(testimonial.id)
                }
            }
        )

        if not response.ok:
            raise Exception(f"Generation failed: {response.text}")

        job_id = response.json()["job_id"]

        # Poll for completion (or use webhooks/SSE)
        for _ in range(30):  # 30 attempts × 1s = 30s timeout
            status_response = requests.get(
                f"{self.BASE_URL}/templates/job/{job_id}"
            )
            status = status_response.json()

            if status["status"] == "completed" and status["results"]:
                poster_url = status["results"][0]["url"]

                # Update Django model
                testimonial.poster_url = poster_url
                testimonial.poster_generated_at = timezone.now()
                testimonial.save()

                return poster_url

            elif status["status"] == "failed":
                error = status["results"][0].get("error", "Unknown error")
                raise Exception(f"Generation failed: {error}")

            time.sleep(1)

        raise Exception("Generation timeout after 30 seconds")
```

---

## Monitoring Queries

### Check Recent Jobs
```sql
SELECT job_id, status, template_section,
       total_items, success_count, failure_count,
       created_at
FROM template_generation_jobs
ORDER BY created_at DESC
LIMIT 10;
```

### Check Logs for Job
```sql
SELECT level, message, details, created_at
FROM template_generation_logs
WHERE job_id = 'template_gen_abc123'
ORDER BY created_at DESC;
```

### Check Failed Generations
```sql
SELECT job_id, entity_id, error_message, custom_data
FROM template_poster_results
WHERE status = 'failed'
ORDER BY created_at DESC
LIMIT 20;
```

### Performance Metrics
```sql
SELECT
    template_section,
    COUNT(*) as total_jobs,
    AVG(generation_time_ms) as avg_time_ms,
    MAX(generation_time_ms) as max_time_ms,
    MIN(generation_time_ms) as min_time_ms
FROM template_poster_results
WHERE status = 'completed'
GROUP BY template_section;
```

---

## Production Checklist

✅ Database migrations applied
✅ Templates table created
✅ Job tracking tables created
✅ TaskIQ worker running
✅ RedPanda broker running
✅ S3 credentials configured
✅ Playwright installed in worker
✅ Error logging enabled
✅ API endpoints tested

---

## Next Steps

1. **Add Webhooks** - Notify Django when generation completes
2. **Add SSE Streaming** - Real-time progress updates
3. **Batch Endpoint** - Generate multiple posters in one request
4. **Template Validation** - Validate placeholders before upload
5. **Image Optimization** - Compress PNGs before S3 upload
6. **Retry Logic** - Auto-retry failed generations
7. **Rate Limiting** - Prevent API abuse
8. **Caching** - Cache rendered templates

---

## Support

For issues, check:
1. Docker container logs: `docker-compose logs backend`
2. Worker logs: `docker-compose logs taskiq-worker`
3. Database logs: Check `template_generation_logs` table
4. RedPanda console: http://localhost:8080
