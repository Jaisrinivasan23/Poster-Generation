# FASTAPI TEMPLATE INTEGRATION PROMPT

## CONTEXT: INTEGRATING TEMPLATE MANAGEMENT FOR TOPMATE TESTIMONIAL POSTERS

I have an existing FastAPI application for HTML-based poster generation. I need to add a **template management system** to handle testimonial posters with versioning, live preview, and dynamic placeholder replacement.

### Current Setup
- FastAPI backend already exists
- Using Playwright for HTML-to-image rendering
- AWS S3 for image storage
- PostgreSQL database

### Integration Requirements
The system needs to integrate with a Django backend (Topmate) that currently uses Creatomate API for poster generation. I want to replace Creatomate with my own HTML-based service.

---

## DJANGO BACKEND CONTEXT (What calls my service)

### Current Creatomate Integration Pattern
```python
# Django calls Creatomate like this (video_generator/creatomate_util.py):
def generate_video(template_id, custom_data, webhook_url, metadata, user=None):
    url = "https://api.creatomate.com/v1/renders"
    headers = {"Authorization": f"Bearer {CREATOMATE_API_KEY}"}
    data = {
        "template_id": template_id,
        "modifications": custom_data,
        "webhook_url": webhook_url
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 202:
        videos = []
        for render in response.json():
            videos.append(Video.objects.create(
                external_id=render["id"],
                url=render["url"],
                user=user,
            ))
        return response.json(), videos
```

### Alternative Pattern (Imejis)
```python
# Django also has this synchronous pattern (video_generator/imejis_util.py):
class ImejisUtil:
    def generate_image_url(self, template_id, custom_data, metadata={}, user=None) -> str:
        url = f"https://api.imejis.io/api/designs/{template_id}"
        headers = {"dma-api-key": settings.IMEJIS_API_KEY}
        response = requests.post(url, headers=headers, data=json.dumps(custom_data))
        
        if response.status_code == 200:
            image_data = response.content
            s3_key = f"imejis_output/{user.id}/{uuid.uuid4()}.png"
            s3_url = upload_bytes_to_aws(data=image_data, s3_key=s3_key)
            return s3_url
```

### How Django Will Call My Service
Django will create a new utility file `html_poster_util.py` that follows the same pattern:

```python
# video_generator/html_poster_util.py (to be created in Django)
def generate_asset(template_id, custom_data, metadata, user, check_duplicate=False):
    response = requests.post(
        f'{HTML_POSTER_SERVICE_URL}/generate',  # My FastAPI service
        json={
            'template_id': template_id,      # e.g., 'testimonial_latest'
            'custom_data': custom_data,      # e.g., {'consumer_name': 'John', 'consumer_message': 'Great!'}
            'metadata': metadata             # e.g., {'user_id': 123, 'id': 456}
        },
        timeout=30
    )
    
    result = response.json()
    
    # Django creates Video model with returned URL
    video = Video.objects.create(
        user=user,
        url=result['url'],  # S3 URL I return
        status='COMPLETED',
        template_id=template_id
    )
    
    return (None, [video])
```

### Django Testimonial Model Usage
```python
# user/models.py - Testimonial model
class Testimonial(models.Model):
    def generate_testimonial_image(self, force=False, via='html'):
        if via == 'html':
            from video_generator import html_poster_util
            
            image_data = {
                'consumer_name': self.get_follower_name(),
                'consumer_message': self.plain_text,
                'testimonial_id': str(self.id),
            }
            
            _, assets = html_poster_util.generate_asset(
                template_id='testimonial_latest',  # Always sends this
                custom_data=image_data,
                metadata={"user_id": self.user.id, "id": self.id},
                user=self.user
            )
            
            self.image_url = assets[0].url
            return self.image_url
```

---

## REQUIREMENTS FOR MY FASTAPI SERVICE

### 1. DATABASE SCHEMA

Create these PostgreSQL tables:

```sql
-- Templates with versioning
CREATE TABLE templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    section VARCHAR(50) NOT NULL,           -- 'testimonial', 'top_new_launch', etc.
    name VARCHAR(200) NOT NULL,              -- 'Modern Testimonial Design'
    html_content TEXT NOT NULL,              -- HTML with {{placeholders}}
    css_content TEXT,                        -- Optional CSS
    version INTEGER NOT NULL,                -- Auto-incremented: 1, 2, 3...
    is_active BOOLEAN DEFAULT false,         -- Only one active per section
    preview_data JSONB,                      -- Sample data for preview
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_section_version UNIQUE(section, version)
);

-- Extracted placeholders
CREATE TABLE template_placeholders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID REFERENCES templates(id) ON DELETE CASCADE,
    placeholder_name VARCHAR(100) NOT NULL,
    sample_value TEXT,
    data_type VARCHAR(50) DEFAULT 'text',
    is_required BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Generation history
CREATE TABLE poster_generations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID REFERENCES templates(id),
    user_id INTEGER NOT NULL,
    testimonial_id VARCHAR(100),
    input_data JSONB,
    output_url TEXT,
    template_version INTEGER,
    generation_time_ms INTEGER,
    status VARCHAR(20) DEFAULT 'success',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_templates_section_active ON templates(section, is_active);
CREATE INDEX idx_templates_section_version ON templates(section, version DESC);
```

### 2. API ENDPOINTS TO IMPLEMENT

#### A. Template Upload (Admin)
```
POST /templates/upload
Content-Type: multipart/form-data

Request:
{
    "section": "testimonial",
    "name": "Modern Design",
    "html_content": "<div class='testimonial'><h2>{{consumer_name}}</h2><p>{{consumer_message}}</p></div>",
    "css_content": ".testimonial { padding: 20px; font-family: Arial; }",
    "preview_data": {
        "consumer_name": "John Doe",
        "consumer_message": "Great session! Highly recommended."
    },
    "set_as_active": true  // Checkbox value
}

Response:
{
    "template_id": "uuid-here",
    "version": 1,
    "section": "testimonial",
    "placeholders": [
        {"name": "consumer_name", "sample_value": "John Doe"},
        {"name": "consumer_message", "sample_value": "Great session!"}
    ],
    "message": "Template uploaded successfully"
}

Logic:
1. Auto-increment version number for the section
2. Extract placeholders from HTML using regex: /\{\{([^}]+)\}\}/g
3. Save template to database
4. If set_as_active=true, deactivate all other templates in same section
5. Save extracted placeholders with sample values
```

#### B. Generate Poster (Called by Django)
```
POST /generate

Request:
{
    "template_id": "testimonial_latest",
    "custom_data": {
        "consumer_name": "Jane Smith",
        "consumer_message": "Amazing mentorship session!",
        "testimonial_id": "12345"
    },
    "metadata": {
        "user_id": 123,
        "id": 12345
    }
}

Response:
{
    "url": "https://s3.amazonaws.com/bucket/testimonials/12345_1737554400.png",
    "template_version_used": 3,
    "template_name": "Modern Design",
    "generation_time_ms": 1250
}

Logic:
1. Parse template_id: 'testimonial_latest' → section = 'testimonial'
2. Query database:
   SELECT * FROM templates 
   WHERE section = 'testimonial' AND is_active = true 
   ORDER BY version DESC LIMIT 1
3. Replace {{placeholders}} in HTML with values from custom_data
4. Render HTML to image using Playwright:
   - Create page with viewport 1200x630
   - Set HTML content with CSS
   - Take screenshot
5. Upload to S3: testimonials/{testimonial_id}_{timestamp}.png
6. Log generation to poster_generations table
7. Return S3 URL
```

#### C. Template Preview
```
GET /templates/{template_id}/preview

Response:
{
    "template_id": "uuid",
    "html_preview": "<div>John Doe: Great session!</div>",
    "preview_image_url": "data:image/png;base64,iVBORw0KG...",
    "placeholders": [
        {"name": "consumer_name", "sample_value": "John Doe"},
        {"name": "consumer_message", "sample_value": "Great session!"}
    ]
}

Logic:
1. Fetch template from database
2. Replace placeholders with preview_data
3. Render to image using Playwright
4. Return as base64 data URL
```

#### D. List Templates
```
GET /templates?section=testimonial

Response:
{
    "section": "testimonial",
    "templates": [
        {
            "id": "uuid-1",
            "name": "Modern Design",
            "version": 3,
            "is_active": true,
            "created_at": "2026-01-20T10:30:00Z"
        },
        {
            "id": "uuid-2",
            "name": "Classic Design",
            "version": 2,
            "is_active": false,
            "created_at": "2026-01-15T09:20:00Z"
        }
    ],
    "active_template": {"id": "uuid-1", "version": 3}
}
```

#### E. Activate Template
```
POST /templates/{template_id}/activate

Response:
{
    "template_id": "uuid",
    "section": "testimonial",
    "version": 2,
    "is_active": true,
    "message": "Template activated for testimonial generation"
}

Logic:
1. Get template's section
2. Set is_active=false for all templates in that section
3. Set is_active=true for this template
```

#### F. Update Template (Creates New Version)
```
PUT /templates/{template_id}

Request:
{
    "name": "Updated Modern Design",
    "html_content": "<div>...</div>",
    "css_content": "...",
    "preview_data": {...}
}

Response:
{
    "template_id": "new-uuid",
    "version": 4,
    "message": "New version created"
}

Logic:
1. Get current template's section and version
2. Create new template with version = current_version + 1
3. Copy all fields with new content
```

### 3. CORE UTILITIES TO IMPLEMENT

#### A. Placeholder Extraction
```python
import re

def extract_placeholders(html: str) -> list:
    """Extract all {{placeholder}} from HTML"""
    pattern = r'\{\{([^}]+)\}\}'
    matches = re.findall(pattern, html)
    return list(set([m.strip() for m in matches]))
```

#### B. Placeholder Replacement
```python
def replace_placeholders(html: str, data: dict) -> str:
    """Replace {{key}} with value from data"""
    result = html
    for key, value in data.items():
        result = result.replace(f'{{{{{key}}}}}', str(value))
    return result
```

#### C. Playwright Renderer
```python
from playwright.async_api import async_playwright
import base64

async def render_to_image(html: str, css: str = None) -> bytes:
    """Render HTML to PNG using Playwright"""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1200, 'height': 630})
        
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{ font-family: Arial, sans-serif; }}
                {css or ''}
            </style>
        </head>
        <body>{html}</body>
        </html>
        """
        
        await page.set_content(full_html)
        screenshot = await page.screenshot(type='png', full_page=True)
        await browser.close()
        return screenshot

async def render_to_base64(html: str, css: str = None) -> str:
    """Render and return base64 for preview"""
    screenshot = await render_to_image(html, css)
    return base64.b64encode(screenshot).decode('utf-8')
```

#### D. S3 Upload
```python
import boto3
from datetime import datetime

def upload_to_s3(image_bytes: bytes, section: str, entity_id: str) -> str:
    """Upload image to S3 and return URL"""
    s3 = boto3.client('s3')
    bucket = 'your-bucket-name'
    timestamp = int(datetime.now().timestamp())
    key = f"{section}/{entity_id}_{timestamp}.png"
    
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=image_bytes,
        ContentType='image/png'
    )
    
    return f"https://{bucket}.s3.amazonaws.com/{key}"
```

### 4. EXAMPLE FLOW

```python
# Example /generate endpoint implementation
@app.post("/generate")
async def generate_poster(request: GenerateRequest):
    # 1. Extract section
    section = request.template_id.replace('_latest', '')  # 'testimonial_latest' → 'testimonial'
    
    # 2. Fetch latest template
    template = await db.fetch_one(
        "SELECT * FROM templates WHERE section = $1 AND is_active = true ORDER BY version DESC LIMIT 1",
        [section]
    )
    
    # 3. Replace placeholders
    html = replace_placeholders(template['html_content'], request.custom_data)
    
    # 4. Render
    image_bytes = await render_to_image(html, template['css_content'])
    
    # 5. Upload
    s3_url = upload_to_s3(image_bytes, section, request.custom_data.get('testimonial_id'))
    
    # 6. Log
    await db.execute(
        "INSERT INTO poster_generations (...) VALUES (...)",
        [...]
    )
    
    return {"url": s3_url, "template_version_used": template['version']}
```

---

## DELIVERABLES NEEDED

1. ✅ Database migrations for the 3 tables above
2. ✅ FastAPI routers for all 6 endpoints (upload, generate, preview, list, activate, update)
3. ✅ Placeholder extraction utility using regex
4. ✅ Playwright renderer for HTML-to-image conversion
5. ✅ S3 upload utility with proper error handling
6. ✅ Template versioning logic (auto-increment, activation)
7. ✅ Error handling and logging for all operations
8. ✅ Response models using Pydantic matching the schemas above

---

## TESTING CHECKLIST

Once implemented, I should be able to:

1. Upload a template with {{consumer_name}} and {{consumer_message}} placeholders
2. See it auto-detect the 2 placeholders
3. Preview it with sample data
4. Activate it as the latest template
5. Call /generate with template_id='testimonial_latest' and get back an S3 URL
6. Create version 2 by updating the template
7. Switch between versions by activating different templates

---

## CONFIGURATION NEEDED

```python
# Environment variables to add
DATABASE_URL=postgresql://user:pass@localhost/posterdb
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_S3_BUCKET=your-bucket
PLAYWRIGHT_BROWSERS_PATH=/path/to/browsers
```

---

## ADMIN UI REQUIREMENTS (Optional - After API is complete)

### UI Layout
- Left sidebar: List of all templates with version numbers
- Center: Template editor with HTML/CSS textareas
- Right sidebar: Placeholder table with sample values
- Bottom: Live preview panel showing rendered image

### Features Needed
- Auto-detect placeholders when HTML changes
- Live preview updates when sample values change
- Checkbox to "Use as latest template"
- Template versioning history
- One-click template activation

---

**Please implement this template management system in my existing FastAPI application following the patterns and schemas provided above. Focus on the 6 core endpoints first, then add the admin UI if time permits.**
