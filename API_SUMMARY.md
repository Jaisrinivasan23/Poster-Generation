# Template Generation API - Summary

## Endpoint Overview

**Endpoint:** `POST /api/templates/generate`

**Purpose:** Generate poster images from HTML templates with dynamic placeholder values using parallel processing architecture.

**Processing Model:** Async queue-based with synchronous response (queues to TaskIQ/RedPanda, waits for result)

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
        "consumer_name": "Jane Smith",
        "consumer_message": "Amazing mentorship session!",
        "rating": "5.0"
    },
    "metadata": {
        "user_id": 123,
        "testimonial_id": "12345"
    }
}
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `template_id` | string | Yes | Template identifier in format `{section}_latest` (e.g., `testimonial_latest`) |
| `custom_data` | object | Yes | Key-value pairs to replace `{{placeholders}}` in template HTML |
| `metadata` | object | Optional | Additional tracking data (not used in rendering) |

---

## Response Format

### Success Response (200 OK)
```json
{
    "url": "https://topmate-staging.s3.ap-south-1.amazonaws.com/templates/testimonial/12345_1737554400.png",
    "template_version_used": 3,
    "template_name": "Modern Testimonial Design",
    "generation_time_ms": 9150
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `url` | string | S3 URL of the generated poster image (PNG, 1200x630) |
| `template_version_used` | integer | Version number of the template that was used |
| `template_name` | string | Name of the template |
| `generation_time_ms` | integer | Time taken to generate the poster in milliseconds |

---

## Processing Flow

```
1. External Service (Django/Your App)
   ↓
2. POST /api/templates/generate
   ↓
3. FastAPI Endpoint:
   - Parse template_id ("testimonial_latest" → section = "testimonial")
   - Query database for active template
   - Create job record in template_generation_jobs
   - Log to template_generation_logs
   ↓
4. Queue to TaskIQ
   ↓
5. TaskIQ publishes to RedPanda Queue
   ↓
6. Worker picks up job (parallel processing):
   - Fetch template HTML/CSS from database
   - Replace {{placeholders}} with custom_data values
   - Render HTML → PNG using Playwright (1200x630 viewport)
   - Upload PNG to S3: templates/{section}/{entity_id}_{timestamp}.png
   - Save result to template_poster_results table
   ↓
7. FastAPI polls database (every 1 second, max 60 seconds)
   ↓
8. Returns result:
   {
     "url": "https://s3.../poster.png",
     "template_version_used": 3,
     "template_name": "...",
     "generation_time_ms": 9150
   }
```

---

## Function Logic

### Step 1: Parse Template ID
```python
template_id = "testimonial_latest"
section = template_id.split("_")[0]  # "testimonial"
```

### Step 2: Fetch Active Template
```sql
SELECT id, version, name, html_content, css_content
FROM templates
WHERE section = 'testimonial' AND is_active = true
ORDER BY version DESC
LIMIT 1
```

### Step 3: Replace Placeholders
```python
html = "<div>{{consumer_name}}: {{consumer_message}}</div>"
custom_data = {"consumer_name": "Jane Smith", "consumer_message": "Amazing!"}

# After replacement:
html = "<div>Jane Smith: Amazing!</div>"
```

### Step 4: Render to Image
```python
# Using Playwright
page = await browser.new_page(viewport={'width': 1200, 'height': 630})
await page.set_content(html_with_css)
screenshot = await page.screenshot(type='png')
```

### Step 5: Upload to S3
```python
# S3 Key format:
s3_key = f"templates/{section}/{entity_id}_{timestamp}.png"
# Example: templates/testimonial/12345_1737554400.png

# Upload
s3_url = upload_to_s3(screenshot, s3_key)
```

### Step 6: Save Result
```sql
INSERT INTO template_poster_results
(job_id, output_url, generation_time_ms, status, ...)
VALUES (...)
```

### Step 7: Return Response
```python
return {
    "url": s3_url,
    "template_version_used": template_version,
    "template_name": template_name,
    "generation_time_ms": generation_time
}
```

---

## Error Responses

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
    "detail": "Rendering error: Invalid HTML syntax"
}
```

**Causes:**
- Invalid HTML in template
- Missing required placeholders
- Playwright rendering error
- S3 upload failure

**Debug:**
```sql
SELECT * FROM template_generation_logs
WHERE job_id = 'template_gen_xxx'
ORDER BY created_at DESC;
```

---

### 504 - Generation Timeout
```json
{
    "detail": "Generation timeout - poster generation took too long"
}
```

**Cause:** Poster generation took longer than 60 seconds.

**Solution:** Check worker logs and RedPanda queue health.

---

## Performance Characteristics

### Timing Breakdown
- **Queue time:** < 100ms (FastAPI → TaskIQ → RedPanda)
- **Processing time:** 8-12 seconds
  - Template fetch: ~50ms
  - HTML rendering (Playwright): 5-8 seconds
  - S3 upload: 2-3 seconds
- **Polling overhead:** 1-60 seconds (waits for completion)
- **Total response time:** ~9-12 seconds

### Scalability
- **Parallel processing:** Multiple workers can process jobs simultaneously
- **Queue-based:** Non-blocking architecture scales horizontally
- **Database pooling:** Connection pool handles concurrent requests
- **S3 CDN:** Generated images served from CloudFront

### Rate Limits
- **Concurrent requests:** No hard limit (scales with workers)
- **Recommended:** 10-50 workers for production
- **Queue capacity:** RedPanda can handle thousands of messages

---

## Usage Examples

### Python Example
```python
import requests

def generate_testimonial_poster(testimonial):
    """Generate poster for a testimonial"""

    response = requests.post(
        'http://localhost:8000/api/templates/generate',
        json={
            'template_id': 'testimonial_latest',
            'custom_data': {
                'consumer_name': testimonial.consumer_name,
                'consumer_message': testimonial.message,
                'rating': str(testimonial.rating)
            },
            'metadata': {
                'user_id': testimonial.user_id,
                'testimonial_id': str(testimonial.id)
            }
        },
        timeout=70  # 60s generation + 10s buffer
    )

    if response.status_code == 200:
        data = response.json()
        poster_url = data['url']

        # Save to database
        testimonial.poster_url = poster_url
        testimonial.poster_version = data['template_version_used']
        testimonial.save()

        return poster_url
    else:
        raise Exception(f"Generation failed: {response.json()['detail']}")
```

### cURL Example
```bash
curl -X POST http://localhost:8000/api/templates/generate \
  -H "Content-Type: application/json" \
  -d '{
    "template_id": "testimonial_latest",
    "custom_data": {
      "consumer_name": "Jane Smith",
      "consumer_message": "Excellent mentorship!",
      "rating": "5.0"
    },
    "metadata": {
      "user_id": 123,
      "testimonial_id": "12345"
    }
  }'
```

**Response:**
```json
{
  "url": "https://topmate-staging.s3.ap-south-1.amazonaws.com/templates/testimonial/12345_1737554400.png",
  "template_version_used": 1,
  "template_name": "Modern Testimonial Design",
  "generation_time_ms": 9150
}
```

### Django Integration
```python
# services/poster_service.py
from django.conf import settings
import requests

class PosterGenerationService:
    FASTAPI_URL = settings.FASTAPI_URL  # "http://fastapi:8000"

    def generate_poster(self, template_section, custom_data, metadata):
        """
        Generate poster from template

        Args:
            template_section: str - "testimonial", "announcement", etc.
            custom_data: dict - Placeholder values
            metadata: dict - Tracking data

        Returns:
            dict with 'url', 'template_version_used', etc.
        """
        try:
            response = requests.post(
                f'{self.FASTAPI_URL}/api/templates/generate',
                json={
                    'template_id': f'{template_section}_latest',
                    'custom_data': custom_data,
                    'metadata': metadata
                },
                timeout=70
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout:
            raise Exception('Poster generation timeout')
        except requests.exceptions.RequestException as e:
            raise Exception(f'Poster generation failed: {str(e)}')


# Usage in views
def create_testimonial(request):
    testimonial = Testimonial.objects.create(
        user=request.user,
        consumer_name=request.POST['consumer_name'],
        message=request.POST['message'],
        rating=request.POST['rating']
    )

    # Generate poster
    poster_service = PosterGenerationService()
    result = poster_service.generate_poster(
        template_section='testimonial',
        custom_data={
            'consumer_name': testimonial.consumer_name,
            'consumer_message': testimonial.message,
            'rating': str(testimonial.rating)
        },
        metadata={
            'user_id': request.user.id,
            'testimonial_id': testimonial.id
        }
    )

    # Save poster URL
    testimonial.poster_url = result['url']
    testimonial.poster_version = result['template_version_used']
    testimonial.save()

    return JsonResponse({
        'success': True,
        'poster_url': result['url']
    })
```

---

## Template Sections

Common template sections and their custom_data requirements:

### Testimonial
```json
{
    "template_id": "testimonial_latest",
    "custom_data": {
        "consumer_name": "John Doe",
        "consumer_message": "Excellent mentor!",
        "rating": "5.0"
    }
}
```

### Announcement
```json
{
    "template_id": "announcement_latest",
    "custom_data": {
        "title": "New Feature Launch",
        "description": "We've launched something amazing!",
        "date": "January 22, 2026"
    }
}
```

### Top New Launch
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

**Note:** The exact `custom_data` fields depend on the placeholders in your uploaded template HTML. Use the Template Manager UI to see detected placeholders.

---

## Database Tables

### template_generation_jobs
Tracks each generation job:
```sql
SELECT job_id, status, template_section, template_version,
       success_count, failure_count, created_at
FROM template_generation_jobs
WHERE job_id = 'template_gen_xxx';
```

### template_poster_results
Stores individual results:
```sql
SELECT job_id, entity_id, output_url, generation_time_ms,
       status, error_message
FROM template_poster_results
WHERE job_id = 'template_gen_xxx';
```

### template_generation_logs
Detailed logs for debugging:
```sql
SELECT level, message, details, created_at
FROM template_generation_logs
WHERE job_id = 'template_gen_xxx'
ORDER BY created_at DESC;
```

---

## Monitoring & Debugging

### Check Recent Generations
```sql
SELECT
    j.job_id,
    j.template_section,
    j.status,
    r.output_url,
    r.generation_time_ms,
    j.created_at
FROM template_generation_jobs j
LEFT JOIN template_poster_results r ON j.job_id = r.job_id
ORDER BY j.created_at DESC
LIMIT 10;
```

### Check Failed Generations
```sql
SELECT
    r.job_id,
    r.entity_id,
    r.error_message,
    r.custom_data,
    j.template_section
FROM template_poster_results r
JOIN template_generation_jobs j ON r.job_id = j.job_id
WHERE r.status = 'failed'
ORDER BY r.created_at DESC
LIMIT 20;
```

### Performance Metrics
```sql
SELECT
    j.template_section,
    COUNT(*) as total_jobs,
    AVG(r.generation_time_ms) as avg_time_ms,
    MAX(r.generation_time_ms) as max_time_ms,
    MIN(r.generation_time_ms) as min_time_ms,
    SUM(CASE WHEN r.status = 'completed' THEN 1 ELSE 0 END) as success_count,
    SUM(CASE WHEN r.status = 'failed' THEN 1 ELSE 0 END) as failure_count
FROM template_generation_jobs j
LEFT JOIN template_poster_results r ON j.job_id = r.job_id
GROUP BY j.template_section;
```

### Check Worker Health
```bash
# Backend logs
docker-compose logs backend --tail 50

# Worker logs
docker-compose logs taskiq-worker --tail 50

# RedPanda health
curl http://localhost:8080  # RedPanda Console UI
```

---

## Key Features

✅ **Parallel Processing** - Multiple workers process jobs simultaneously
✅ **Queue-Based Architecture** - TaskIQ + RedPanda for scalability
✅ **Template Versioning** - Track which version generated each poster
✅ **Comprehensive Logging** - All operations logged to PostgreSQL
✅ **S3 Integration** - Direct upload to S3 with CDN support
✅ **Error Handling** - Detailed error messages with debugging info
✅ **Synchronous Response** - Returns direct URL (waits for completion)
✅ **Timeout Protection** - 60-second timeout prevents hanging requests
✅ **Placeholder System** - Dynamic `{{placeholder}}` replacement
✅ **Playwright Rendering** - High-quality HTML to PNG conversion

---

## Production Checklist

✅ Docker services running (FastAPI, PostgreSQL, Redis, RedPanda, TaskIQ workers)
✅ Database migrations applied
✅ S3 credentials configured
✅ Playwright installed in worker container
✅ Template uploaded and set as active
✅ Workers scaled appropriately (10+ workers recommended)
✅ Monitoring setup (logs, metrics, alerts)
✅ CDN configured for S3 URLs
✅ Backup strategy for templates database
✅ Error alerting configured

---

## Support & Troubleshooting

### Common Issues

**Issue:** "No active template found"
**Solution:** Upload a template for that section via Template Manager UI

**Issue:** Generation timeout (504)
**Solution:** Check worker logs, ensure TaskIQ workers are running, verify RedPanda health

**Issue:** Invalid HTML errors
**Solution:** Validate template HTML in Template Manager preview before uploading

**Issue:** S3 upload fails
**Solution:** Verify AWS credentials in environment variables, check S3 bucket permissions

### Getting Help

1. Check logs: `docker-compose logs backend taskiq-worker`
2. Query database: Check `template_generation_logs` table for errors
3. Verify services: All Docker containers should be healthy
4. Test with simple template: Upload basic HTML to isolate issue

---

## Summary

The `/api/templates/generate` endpoint provides a robust, scalable solution for generating poster images from HTML templates. It combines the benefits of parallel processing (TaskIQ + RedPanda) with a synchronous API response, making it easy to integrate into existing applications while maintaining high performance and reliability.

**Key Advantages:**
- Simple request/response API (no polling required)
- Parallel processing for scalability
- Comprehensive logging and error handling
- Template versioning and tracking
- S3 integration for CDN delivery
- Production-ready architecture
