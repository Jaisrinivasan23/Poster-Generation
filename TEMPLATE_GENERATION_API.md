# Template Generation API Endpoint

## Endpoint: `POST /api/templates/generate`

Generate a poster from a template using async processing with TaskIQ + RedPanda.

---

## Request Format

### URL
```
POST http://localhost:8000/api/templates/generate
```

### Headers
```
Content-Type: application/json
```

### Request Body

```json
{
  "template_id": "testimonial_latest",
  "custom_data": {
    "consumer_name": "John Doe",
    "consumer_message": "Excellent mentorship session! Very helpful.",
    "rating": "5.0"
  },
  "metadata": {
    "user_id": 123,
    "testimonial_id": "test_001"
  }
}
```

---

## Request Parameters

### 1. `template_id` (string, required)
The template identifier in the format: `{section}_latest`

**Examples:**
- `"testimonial_latest"` - Latest active template in "testimonial" section
- `"announcement_latest"` - Latest active template in "announcement" section
- `"top_new_launch_latest"` - Latest active template in "top_new_launch" section

**How it works:**
- The system extracts the section name (before `_latest`)
- Fetches the active template for that section from the database
- Uses that template's HTML/CSS for generation

---

### 2. `custom_data` (object, required)
**Key-value pairs that replace placeholders in the template HTML.**

The keys must match the placeholder names in your template HTML.

**Example Template HTML:**
```html
<div style="padding: 40px; font-family: Arial;">
  <h1>{{consumer_name}}</h1>
  <p>{{consumer_message}}</p>
  <div>Rating: {{rating}}/5</div>
</div>
```

**Corresponding custom_data:**
```json
{
  "consumer_name": "Jane Smith",
  "consumer_message": "Great experience!",
  "rating": "5.0"
}
```

**Important Notes:**
- All placeholder names are case-sensitive
- Placeholders use double curly braces: `{{placeholder_name}}`
- Values are inserted as plain text (HTML will be escaped)
- Missing placeholders will remain as `{{placeholder_name}}` in output

---

### 3. `metadata` (object, optional)
**Additional data for tracking/logging purposes.**

This data is NOT used in template rendering, only for:
- Tracking which entity the poster belongs to
- Logging and debugging
- Stored in database for reference

**Common metadata fields:**
```json
{
  "user_id": 123,              // User who requested generation
  "testimonial_id": "test_001", // ID of the entity (testimonial, launch, etc.)
  "campaign_name": "Q1 2024",  // Campaign identifier
  "source": "external_api"     // Where request came from
}
```

**Note:** The `testimonial_id` or `id` field in metadata is used as the `entity_id` in the S3 filename and database records.

---

## Response Format

### Success Response (200 OK)

```json
{
  "success": true,
  "job_id": "template_gen_4148d9d6f362",
  "message": "Poster generation queued successfully",
  "status_endpoint": "/api/templates/job/template_gen_4148d9d6f362"
}
```

**Response Fields:**
- `success` (boolean) - Always `true` for successful queue
- `job_id` (string) - Unique job identifier for tracking
- `message` (string) - Human-readable success message
- `status_endpoint` (string) - Endpoint to check job status

---

## Checking Job Status

Use the `status_endpoint` to poll for completion:

### Request
```
GET http://localhost:8000/api/templates/job/{job_id}
```

### Response (In Progress)
```json
{
  "job_id": "template_gen_4148d9d6f362",
  "status": "processing",
  "template_section": "testimonial",
  "template_version": 1,
  "total_items": 1,
  "processed_items": 0,
  "success_count": 0,
  "failure_count": 0,
  "created_at": "2026-01-22T11:47:30Z",
  "started_at": "2026-01-22T11:47:31Z",
  "completed_at": null,
  "results": []
}
```

### Response (Completed)
```json
{
  "job_id": "template_gen_4148d9d6f362",
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
      "url": "https://topmate-staging.s3.ap-south-1.amazonaws.com/templates/testimonial/test_001_1769082459.png",
      "status": "completed",
      "generation_time_ms": 9119,
      "error": null
    }
  ]
}
```

**Key Fields:**
- `status` - Job status: `queued`, `processing`, `completed`, or `failed`
- `results[0].url` - **S3 URL of the generated poster image (PNG)**
- `results[0].generation_time_ms` - Time taken to generate (milliseconds)
- `results[0].status` - Individual result status

---

## Complete Usage Example

### Step 1: Generate Poster
```bash
curl -X POST http://localhost:8000/api/templates/generate \
  -H "Content-Type: application/json" \
  -d '{
    "template_id": "testimonial_latest",
    "custom_data": {
      "consumer_name": "Sarah Johnson",
      "consumer_message": "Amazing mentor! Helped me launch my startup.",
      "rating": "5.0"
    },
    "metadata": {
      "user_id": 456,
      "testimonial_id": "testi_12345"
    }
  }'
```

**Response:**
```json
{
  "success": true,
  "job_id": "template_gen_abc123def456",
  "message": "Poster generation queued successfully",
  "status_endpoint": "/api/templates/job/template_gen_abc123def456"
}
```

### Step 2: Poll for Completion
```bash
curl http://localhost:8000/api/templates/job/template_gen_abc123def456
```

**Poll every 1-2 seconds until `status` is `completed` or `failed`.**

### Step 3: Get S3 URL
Once status is `completed`, extract the poster URL:
```json
{
  "status": "completed",
  "results": [
    {
      "url": "https://topmate-staging.s3.ap-south-1.amazonaws.com/templates/testimonial/testi_12345_1769082459.png"
    }
  ]
}
```

**This URL is the final poster image (1200x630 PNG).**

---

## Processing Flow

```
External Service
    ↓
POST /api/templates/generate
    ↓
FastAPI validates template exists
    ↓
Creates job record in PostgreSQL
    ↓
Logs to template_generation_logs
    ↓
Queues to TaskIQ worker
    ↓
TaskIQ publishes to RedPanda queue
    ↓
Worker picks up job:
    - Fetches template HTML/CSS from DB
    - Replaces {{placeholders}} with custom_data values
    - Renders HTML → PNG using Playwright (1200x630)
    - Uploads PNG to S3
    - Logs result to template_poster_results
    ↓
Poll /api/templates/job/{job_id} to get S3 URL
```

---

## Error Handling

### 404 - Template Not Found
```json
{
  "detail": "No active template found for section 'testimonial'"
}
```

**Cause:** No active template exists for the specified section.

**Solution:** Upload a template for that section and set it as active.

---

### 500 - Generation Failed
```json
{
  "detail": "Rendering error: ..."
}
```

**Common causes:**
- Invalid HTML in template
- Missing required placeholders
- S3 upload failure
- Playwright rendering timeout

**Check logs:**
```sql
SELECT * FROM template_generation_logs
WHERE job_id = 'template_gen_abc123'
ORDER BY created_at DESC;
```

---

## Performance

- **Queue time:** < 100ms (async, returns immediately)
- **Processing time:** 8-12 seconds per poster
  - HTML rendering: 5-8 seconds
  - S3 upload: 2-3 seconds
- **Total end-to-end:** ~9 seconds average

**Recommended polling:**
- Poll every 1 second
- Timeout after 30 seconds
- Check `status` field for completion

---

## S3 Output

### File Format
- **Format:** PNG image
- **Dimensions:** 1200x630 pixels (default)
- **Naming:** `{section}/{entity_id}_{timestamp}.png`

### Example S3 Key
```
templates/testimonial/test_001_1769082459.png
```

### S3 URL Structure
```
https://topmate-staging.s3.ap-south-1.amazonaws.com/templates/{section}/{entity_id}_{timestamp}.png
```

---

## Database Records

### template_generation_jobs
Tracks the job status:
```sql
SELECT job_id, status, success_count, failure_count
FROM template_generation_jobs
WHERE job_id = 'template_gen_abc123';
```

### template_poster_results
Stores the final result:
```sql
SELECT entity_id, output_url, generation_time_ms, status
FROM template_poster_results
WHERE job_id = 'template_gen_abc123';
```

### template_generation_logs
Detailed logs for debugging:
```sql
SELECT level, message, details
FROM template_generation_logs
WHERE job_id = 'template_gen_abc123'
ORDER BY created_at DESC;
```

---

## Integration Example (Python)

```python
import requests
import time

def generate_testimonial_poster(testimonial_data):
    """
    Generate a poster for a testimonial

    Args:
        testimonial_data: dict with consumer_name, consumer_message, rating

    Returns:
        str: S3 URL of generated poster
    """
    # Step 1: Trigger generation
    response = requests.post(
        'http://localhost:8000/api/templates/generate',
        json={
            'template_id': 'testimonial_latest',
            'custom_data': {
                'consumer_name': testimonial_data['name'],
                'consumer_message': testimonial_data['message'],
                'rating': str(testimonial_data['rating'])
            },
            'metadata': {
                'testimonial_id': testimonial_data['id']
            }
        }
    )

    if not response.ok:
        raise Exception(f"Generation failed: {response.text}")

    job_id = response.json()['job_id']
    print(f"Job queued: {job_id}")

    # Step 2: Poll for completion
    for attempt in range(30):  # 30 second timeout
        time.sleep(1)

        status_response = requests.get(
            f'http://localhost:8000/api/templates/job/{job_id}'
        )
        status_data = status_response.json()

        if status_data['status'] == 'completed':
            poster_url = status_data['results'][0]['url']
            print(f"Poster generated: {poster_url}")
            return poster_url

        elif status_data['status'] == 'failed':
            error = status_data['results'][0].get('error', 'Unknown error')
            raise Exception(f"Generation failed: {error}")

    raise Exception("Generation timeout after 30 seconds")


# Usage
poster_url = generate_testimonial_poster({
    'id': 'testi_12345',
    'name': 'John Doe',
    'message': 'Great mentor!',
    'rating': 5.0
})
```

---

## Custom Data by Template Section

### Testimonial Template
```json
{
  "template_id": "testimonial_latest",
  "custom_data": {
    "consumer_name": "John Doe",
    "consumer_message": "Excellent mentorship session!",
    "rating": "5.0"
  }
}
```

### Announcement Template
```json
{
  "template_id": "announcement_latest",
  "custom_data": {
    "title": "New Feature Launch",
    "description": "We've launched a new feature!",
    "date": "January 22, 2026"
  }
}
```

### Top New Launch Template
```json
{
  "template_id": "top_new_launch_latest",
  "custom_data": {
    "product_name": "My Startup",
    "launch_date": "Q1 2026",
    "tagline": "Revolutionizing the industry"
  }
}
```

**Note:** The `custom_data` fields depend on the placeholders in your uploaded template HTML. Check the template's placeholder list before calling the API.

---

## Summary

✅ **Endpoint:** `POST /api/templates/generate`
✅ **Authentication:** None (add if needed)
✅ **Rate Limiting:** None (add if needed)
✅ **Processing:** Async (returns job_id immediately)
✅ **Polling:** Use `/api/templates/job/{job_id}`
✅ **Output:** S3 URL of PNG image (1200x630)
✅ **Performance:** ~9 seconds per poster
✅ **Logs:** All operations logged to PostgreSQL

**Your external service should:**
1. Call `/api/templates/generate` with template_id and custom_data
2. Receive job_id immediately
3. Poll `/api/templates/job/{job_id}` every 1 second
4. Extract S3 URL from results when status is 'completed'
5. Save S3 URL to your model
