"""
Test Script for Template Generation API
Tests the /api/templates/generate endpoint with testimonial data
"""
import requests
import json
import time

# Configuration
BACKEND_URL = "http://localhost:8000"
ENDPOINT = f"{BACKEND_URL}/api/templates/generate"

# Test data matching your request
test_payload = {
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

def test_template_generation():
    """Test template generation endpoint"""
    print("\n" + "="*60)
    print("🧪 TESTING TEMPLATE GENERATION")
    print("="*60)
    
    print(f"\n📍 Endpoint: {ENDPOINT}")
    print(f"\n📦 Payload:")
    print(json.dumps(test_payload, indent=2))
    
    print(f"\n⏳ Sending POST request...")
    start_time = time.time()
    
    try:
        response = requests.post(
            ENDPOINT,
            json=test_payload,
            headers={"Content-Type": "application/json"},
            timeout=120  # 2 minute timeout (generation can take 60 seconds)
        )
        
        elapsed_time = time.time() - start_time
        
        print(f"\n⏱️  Total time: {elapsed_time:.2f}s")
        print(f"\n📡 Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ SUCCESS!")
            print(f"\n📊 Response Data:")
            print(json.dumps(result, indent=2))
            
            if 'url' in result:
                print(f"\n🖼️  Generated Poster URL:")
                print(f"   {result['url']}")
                print(f"\n📏 Template Version: {result.get('template_version_used', 'N/A')}")
                print(f"📝 Template Name: {result.get('template_name', 'N/A')}")
                print(f"⚡ Generation Time: {result.get('generation_time_ms', 0)}ms")
            
            return True
        else:
            print(f"\n❌ FAILED!")
            print(f"\n📄 Response:")
            try:
                error_data = response.json()
                print(json.dumps(error_data, indent=2))
            except:
                print(response.text)
            
            return False
            
    except requests.exceptions.Timeout:
        print(f"\n⏰ REQUEST TIMEOUT (>120s)")
        print("   The generation took too long. Check backend logs.")
        return False
    except requests.exceptions.ConnectionError:
        print(f"\n🔌 CONNECTION ERROR")
        print(f"   Could not connect to {BACKEND_URL}")
        print("   Make sure the backend is running.")
        return False
    except Exception as e:
        print(f"\n💥 ERROR: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return False

def check_backend_health():
    """Check if backend is running"""
    print("\n🏥 Checking backend health...")
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Backend is healthy")
            return True
        else:
            print(f"⚠️  Backend returned status {response.status_code}")
            return False
    except:
        print("❌ Backend is not responding")
        return False

if __name__ == "__main__":
    print("\n" + "🚀 "*30)
    print(" TEMPLATE GENERATION TEST SCRIPT")
    print("🚀 "*30)
    
    # Check backend health first
    if not check_backend_health():
        print("\n⚠️  Please start the backend server first:")
        print("   cd backend")
        print("   python run_server.py")
        exit(1)
    
    # Run test
    success = test_template_generation()
    
    print("\n" + "="*60)
    if success:
        print("✅ TEST PASSED")
    else:
        print("❌ TEST FAILED")
    print("="*60 + "\n")
    
    exit(0 if success else 1)
