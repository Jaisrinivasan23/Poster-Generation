# Template Generation Testing Guide

## 🎯 What Was Fixed

### Issues Identified:
1. **Hardcoded dimensions** (1200x630) instead of proper poster size (1080x1080)
2. **Nested placeholder data not supported** (e.g., `overlay.fill_color`)
3. **Using suboptimal rendering function** instead of proven `convert_html_to_png`
4. **Insufficient rendering wait time** causing cut-off images

### Changes Applied:

#### 1. **template_service.py** - Enhanced Placeholder Replacement
- ✅ Now supports nested data structures (e.g., `{{overlay.fill_color}}`)
- ✅ Uses regex for more robust placeholder matching
- ✅ Handles missing placeholders gracefully

#### 2. **poster_tasks.py** - Improved Image Rendering
- ✅ Changed dimensions from 1200x630 to **1080x1080** (Instagram square)
- ✅ Uses proven `convert_html_to_png` function with better rendering
- ✅ Builds complete HTML document with proper CSS injection
- ✅ Added detailed logging for debugging

---

## 🚀 How to Test

### Prerequisites
Make sure your backend is running:
```bash
cd backend
python run_server.py
```

### Step 1: Upload Sample Template (First Time Only)
```bash
python upload_sample_template.py
```

This creates a sample testimonial template with:
- Modern card design
- Quote icon
- Nested color support
- Proper 1080x1080 sizing

### Step 2: Test Generation

**Simple Test:**
```bash
python test_template_generation.py
```

**Debug Test (Recommended):**
```bash
python test_template_debug.py
```

The debug version:
- Checks backend health
- Verifies template exists
- Downloads and saves generated image locally
- Provides detailed error logging

---

## 📝 Test Request Format

```json
{
    "template_id": "testimonial_latest",
    "custom_data": {
        "consumer_name": "Test Consumer",
        "consumer_message": "This is a test testimonial message...",
        "testimonial_id": "3",
        "overlay": {
            "fill_color": "#3B82F6"
        }
    },
    "metadata": {
        "user_id": 32,
        "id": "3",
        "type": "testimonial"
    }
}
```

### Key Features Tested:
- ✅ Simple placeholders: `{{consumer_name}}`
- ✅ Nested placeholders: `{{overlay.fill_color}}`
- ✅ Proper image dimensions (1080x1080)
- ✅ Full HTML rendering with CSS
- ✅ S3 upload and URL generation

---

## 🔍 Expected Output

### Successful Generation:
```
✅ SUCCESS!

 Result:
{
  "url": "https://s3.amazonaws.com/bucket/templates/testimonial/3_1234567890.png",
  "template_version_used": 1,
  "template_name": "Modern Testimonial Card",
  "generation_time_ms": 2500
}

🎯 Generated Poster:
   URL: https://...
   Template: Modern Testimonial Card (v1)
   Generation time: 2500ms

🖼️  Downloading image to verify...
   ✅ Image downloaded: 245.67 KB
   💾 Saved as: test_testimonial_1737554400.png
```

### What to Check:
1. **Image size**: Should be ~200-500 KB
2. **Dimensions**: 1080x1080 pixels
3. **Content**: All placeholders replaced correctly
4. **Layout**: Not cut off or distorted
5. **Colors**: `overlay.fill_color` applied correctly

---

## 🐛 Troubleshooting

### Image Still Cut Off?
Check the HTML template's dimensions match:
```html
<div style="width: 1080px; height: 1080px; ...">
```

### Placeholders Not Replaced?
Verify placeholder syntax:
- ✅ `{{consumer_name}}` - Simple
- ✅ `{{overlay.fill_color}}` - Nested
- ❌ `{{ consumer_name }}` - Extra spaces (may fail)

### Timeout Error?
- Increase timeout in test script
- Check backend logs for errors
- Verify TaskIQ workers are running

### Missing Template?
Run upload script first:
```bash
python upload_sample_template.py
```

---

##  Backend Logs to Monitor

When testing, watch for these log messages:

```
✅ Job queued: template_gen_abc123 (section: testimonial)
🔵 [TASKIQ] Task started for job: template_gen_abc123 (type: template_poster)
[TEMPLATE] Rendering poster: testimonial (entity_id: 3)
[HTML2PNG] Screenshot captured: 245678 bytes
[TEMPLATE] Uploaded to S3: https://...
✅ [TASKIQ] Task completed for job: template_gen_abc123
```

---

## 🎨 Template Customization

To create your own template:

```python
html = """
<div style="width: 1080px; height: 1080px; ...">
    <h1>{{title}}</h1>
    <p style="color: {{theme.primary_color}}">{{message}}</p>
</div>
"""

custom_data = {
    "title": "Hello World",
    "message": "Test message",
    "theme": {
        "primary_color": "#FF0000"
    }
}
```

### Supported Placeholders:
- Simple: `{{key}}`
- Nested: `{{parent.child}}`
- Deep nesting: `{{level1.level2.level3}}`

---

## ✅ Success Criteria

Your test passes if:
1. ✅ Request completes in <60 seconds
2. ✅ Returns valid S3 URL
3. ✅ Image downloads successfully
4. ✅ Image is 1080x1080 pixels
5. ✅ All placeholders are replaced
6. ✅ Nested color values applied
7. ✅ No content cut off or distorted

---

## 🔗 API Endpoints Reference

- `POST /api/templates/upload` - Upload new template
- `POST /api/templates/generate` - Generate from template
- `GET /api/templates` - List all templates
- `GET /api/templates/{id}/preview` - Preview template
- `GET /api/templates/job/{job_id}` - Get job status

---

## 📞 Support

If issues persist:
1. Check backend logs: `backend/logs/`
2. Verify database tables: `templates`, `template_poster_results`
3. Test S3 upload separately
4. Confirm TaskIQ is processing tasks

**Happy Testing! 🎉**
