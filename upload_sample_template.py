"""
Upload Sample Testimonial Template
Creates a simple testimonial template for testing
"""
import requests
import json

BACKEND_URL = "http://localhost:8000"

# Sample testimonial template HTML (using {placeholder} format like bulk generation)
TEMPLATE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            width: 1080px;
            height: 1080px;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            background: {overlay_fill_color};
            padding: 60px;
            overflow: hidden;
        }
        .card {
            max-width: 800px;
            width: 100%;
            background: white;
            border-radius: 24px;
            padding: 60px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.2);
        }
        .quote-icon {
            text-align: center;
            margin-bottom: 40px;
        }
        .quote-icon svg {
            width: 60px;
            height: 60px;
        }
        .message {
            font-size: 28px;
            line-height: 1.6;
            color: #1a1a1a;
            margin: 0 0 40px 0;
            font-weight: 400;
            text-align: center;
        }
        .author-section {
            text-align: center;
            border-top: 2px solid {overlay_fill_color};
            padding-top: 30px;
        }
        .author-name {
            font-size: 24px;
            font-weight: 700;
            color: #1a1a1a;
            margin: 0 0 8px 0;
        }
        .testimonial-info {
            font-size: 18px;
            color: #666;
            margin: 0;
        }
    </style>
</head>
<body>
    <div class="card">
        <div class="quote-icon">
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M7.5 12C7.5 10.343 6.157 9 4.5 9c-1.657 0-3 1.343-3 3s1.343 3 3 3c.386 0 .755-.074 1.094-.209L7.5 16.5v-4.5z" fill="{overlay_fill_color}" opacity="0.3"/>
                <path d="M19.5 12c0-1.657-1.343-3-3-3s-3 1.343-3 3 1.343 3 3 3c.386 0 .755-.074 1.094-.209L19.5 16.5V12z" fill="{overlay_fill_color}" opacity="0.3"/>
            </svg>
        </div>
        
        <p class="message">"{consumer_message}"</p>
        
        <div class="author-section">
            <p class="author-name">{consumer_name}</p>
            <p class="testimonial-info">Testimonial #{testimonial_id}</p>
        </div>
    </div>
</body>
</html>
"""

TEMPLATE_CSS = ""  # CSS is now inline in HTML

PREVIEW_DATA = {
    "consumer_name": "John Doe",
    "consumer_message": "This product changed my life! Absolutely amazing experience from start to finish.",
    "testimonial_id": "123",
    "overlay_fill_color": "#3B82F6"  # Flattened from overlay.fill_color
}

def upload_template():
    """Upload testimonial template"""
    print("\n📤 Uploading testimonial template...")
    
    payload = {
        "section": "testimonial",
        "name": "Modern Testimonial Card",
        "html_content": TEMPLATE_HTML,
        "css_content": TEMPLATE_CSS,
        "set_as_active": True,
        "preview_data": PREVIEW_DATA
    }
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/templates/upload",
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Template uploaded successfully!")
            print(f"\n Details:")
            print(f"   Template ID: {result['template_id']}")
            print(f"   Version: {result['version']}")
            print(f"   Section: {result['section']}")
            print(f"   Placeholders: {len(result.get('placeholders', []))}")
            
            for p in result.get('placeholders', []):
                print(f"      - {p['name']}")
            
            return True
        else:
            print(f"❌ Upload failed: {response.status_code}")
            try:
                print(json.dumps(response.json(), indent=2))
            except:
                print(response.text)
            return False
            
    except Exception as e:
        print(f"💥 Error: {str(e)}")
        return False

def check_health():
    """Check backend"""
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=5)
        return response.status_code == 200
    except:
        return False

if __name__ == "__main__":
    print("\n" + "🎨 " * 30)
    print(" UPLOAD TESTIMONIAL TEMPLATE")
    print("🎨 " * 30)
    
    if not check_health():
        print("\n❌ Backend not running!")
        print("   Start with: cd backend && python run_server.py")
        exit(1)
    
    success = upload_template()
    
    if success:
        print("\n" + "="*60)
        print("✅ TEMPLATE UPLOADED")
        print("="*60)
        print("\nYou can now test generation with:")
        print("  python test_template_generation.py")
        print("\nOr run the debug version:")
        print("  python test_template_debug.py")
    else:
        print("\n❌ UPLOAD FAILED")
    
    exit(0 if success else 1)
