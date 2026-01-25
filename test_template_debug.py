"""
Advanced Test Script with Debugging
Tests template generation with detailed logging
"""
import requests
import json
import time
import sys

# Configuration
BACKEND_URL = "http://localhost:8000"

def test_template_exists():
    """Check if testimonial template exists"""
    print("\n📋 Checking if template exists...")
    try:
        response = requests.get(f"{BACKEND_URL}/api/templates?section=testimonial", timeout=10)
        if response.status_code == 200:
            data = response.json()
            templates = data.get('templates', [])
            active = data.get('active_template')
            
            print(f"   Found {len(templates)} testimonial template(s)")
            if active:
                print(f"   ✅ Active template: {active['name']} (version {active['version']})")
                return True
            else:
                print(f"   ⚠️  No active template found")
                return False
        else:
            print(f"   ❌ Failed to fetch templates: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
        return False

def test_generation():
    """Test poster generation"""
    print("\n🎨 Testing poster generation...")
    
    payload = {
        "template_id": "testimonial_latest",
        "custom_data": {
            "consumer_name": "Test Consumer",
            "consumer_message": "This is a test testimonial message that is quite long to test wrapping and layout...",
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
    
    print("\n📤 Sending request...")
    print(f"   Endpoint: /api/templates/generate")
    print(f"   Payload: {json.dumps(payload, indent=2)}")
    
    start = time.time()
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/templates/generate",
            json=payload,
            timeout=120
        )
        
        elapsed = time.time() - start
        
        print(f"\n⏱️  Request completed in {elapsed:.2f}s")
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ SUCCESS!")
            print(f"\n Result:")
            print(json.dumps(result, indent=2))
            
            if 'url' in result:
                print(f"\n🎯 Generated Poster:")
                print(f"   URL: {result['url']}")
                print(f"   Template: {result.get('template_name')} (v{result.get('template_version_used')})")
                print(f"   Generation time: {result.get('generation_time_ms')}ms")
                
                # Try to download the image
                print(f"\n🖼️  Downloading image to verify...")
                try:
                    img_response = requests.get(result['url'], timeout=10)
                    if img_response.status_code == 200:
                        size_kb = len(img_response.content) / 1024
                        print(f"   ✅ Image downloaded: {size_kb:.2f} KB")
                        
                        # Save locally for inspection
                        filename = f"test_testimonial_{int(time.time())}.png"
                        with open(filename, 'wb') as f:
                            f.write(img_response.content)
                        print(f"   💾 Saved as: {filename}")
                    else:
                        print(f"   ⚠️  Could not download: {img_response.status_code}")
                except Exception as e:
                    print(f"   ❌ Download error: {str(e)}")
                
                return True
        else:
            print(f"\n❌ FAILED!")
            try:
                error = response.json()
                print(f"\n📄 Error Response:")
                print(json.dumps(error, indent=2))
            except:
                print(f"   {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"\n⏰ TIMEOUT (>120s)")
        return False
    except Exception as e:
        print(f"\n💥 ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def check_health():
    """Check backend health"""
    print("\n🏥 Checking backend health...")
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=5)
        if response.status_code == 200:
            print("   ✅ Backend is healthy")
            return True
        print(f"   ⚠️  Status: {response.status_code}")
        return False
    except:
        print("   ❌ Backend not responding")
        return False

def check_services():
    """Check batch processing services"""
    print("\n🔧 Checking services...")
    try:
        response = requests.get(f"{BACKEND_URL}/api/batch/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            services = data.get('services', {})
            print(f"   Database: {'✅' if services.get('database') else '❌'}")
            print(f"   RedPanda: {'✅' if services.get('redpanda') else '❌'}")
            print(f"   SSE Connections: {services.get('sse_connections', 0)}")
            return data.get('success', False)
        return False
    except:
        print("   ⚠️  Could not check services")
        return False

def main():
    print("\n" + "🚀 " * 30)
    print(" TEMPLATE GENERATION DEBUG TEST")
    print("🚀 " * 30)
    
    # Step 1: Health check
    if not check_health():
        print("\n❌ Backend is not running!")
        print("\nTo start the backend:")
        print("  cd backend")
        print("  python run_server.py")
        return False
    
    # Step 2: Check services
    check_services()
    
    # Step 3: Check template
    if not test_template_exists():
        print("\n⚠️  Warning: No active testimonial template found")
        print("\nYou may need to upload a template first:")
        print("  POST /api/templates/upload")
    
    # Step 4: Test generation
    success = test_generation()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ ALL TESTS PASSED")
    else:
        print("❌ TESTS FAILED")
    print("=" * 60 + "\n")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
