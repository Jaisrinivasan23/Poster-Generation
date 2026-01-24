"""
Upload sample template and test generation
"""
import requests
import json
import time
from pathlib import Path

BACKEND_URL = "http://localhost:8000"

# Read template from file
template_html = Path("sample_template_1080x1080.html").read_text()

# Upload template
print("📤 Uploading template...")
upload_response = requests.post(
    f"{BACKEND_URL}/api/templates/upload",
    json={
        "section": "testimonial",
        "name": "Square Testimonial Card",
        "html_content": template_html,
        "css_content": "",
        "set_as_active": True,
        "preview_data": {
            "consumer_name": "John Doe",
            "consumer_message": "This is amazing! Highly recommended.",
            "testimonial_id": "123",
            "overlay_fill_color": "#3B82F6"
        }
    }
)

if upload_response.status_code == 200:
    result = upload_response.json()
    print(f"✅ Template uploaded: {result['template_id']}")
    print(f"   Version: {result['version']}")
else:
    print(f"❌ Upload failed: {upload_response.status_code}")
    print(upload_response.text)
    exit(1)

# Wait a bit
time.sleep(2)

# Test generation
print("\n🎨 Testing poster generation...")
generate_response = requests.post(
    f"{BACKEND_URL}/api/templates/generate",
    json={
        "template_id": "testimonial_latest",
        "custom_data": {
            "consumer_name": "Sarah Johnson",
            "consumer_message": "Absolutely fantastic service! The team went above and beyond to ensure everything was perfect.",
            "testimonial_id": "456",
            "overlay": {
                "fill_color": "#8B5CF6"
            }
        },
        "metadata": {
            "user_id": 100,
            "id": "456",
            "type": "testimonial"
        }
    },
    timeout=70
)

if generate_response.status_code == 200:
    result = generate_response.json()
    print(f"✅ Poster generated!")
    print(f"   URL: {result['url']}")
    print(f"   Template: {result['template_name']} (v{result['template_version_used']})")
    print(f"   Time: {result['generation_time_ms']}ms")
    
    # Download and check dimensions
    print("\n📥 Downloading image...")
    img_response = requests.get(result['url'])
    if img_response.status_code == 200:
        img_path = f"generated_poster_{int(time.time())}.png"
        with open(img_path, 'wb') as f:
            f.write(img_response.content)
        print(f"   Saved: {img_path}")
        
        # Check dimensions
        from PIL import Image
        img = Image.open(img_path)
        print(f"   Size: {img.size[0]}x{img.size[1]}")
        
        if img.size == (1080, 1080):
            print("\n✅ SUCCESS! Image is 1080x1080")
        else:
            print(f"\n❌ WARNING: Expected 1080x1080, got {img.size[0]}x{img.size[1]}")
else:
    print(f"❌ Generation failed: {generate_response.status_code}")
    print(generate_response.text)
