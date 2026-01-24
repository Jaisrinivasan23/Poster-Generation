#!/usr/bin/env python3
"""
Quick Test - Template Generation
Run this to quickly test if template generation works
"""
import requests
import sys

print("\n🧪 QUICK TEMPLATE TEST\n")

# Check backend
try:
    r = requests.get("http://localhost:8000/health", timeout=3)
    if r.status_code != 200:
        print("❌ Backend not healthy")
        sys.exit(1)
    print("✅ Backend running")
except:
    print("❌ Backend not running (start with: cd backend && python run_server.py)")
    sys.exit(1)

# Test generation
payload = {
    "template_id": "testimonial_latest",
    "custom_data": {
        "consumer_name": "Quick Test",
        "consumer_message": "Testing template generation...",
        "testimonial_id": "999",
        "overlay": {"fill_color": "#3B82F6"}
    },
    "metadata": {"user_id": 1, "id": "999", "type": "testimonial"}
}

print("🎨 Generating poster...")
try:
    r = requests.post("http://localhost:8000/api/templates/generate", json=payload, timeout=120)
    if r.status_code == 200:
        result = r.json()
        print(f"✅ SUCCESS!")
        print(f"📍 URL: {result['url']}")
        print(f"⏱️  Time: {result.get('generation_time_ms')}ms")
    else:
        print(f"❌ FAILED: {r.status_code}")
        print(r.json())
        sys.exit(1)
except requests.exceptions.Timeout:
    print("⏰ Timeout - check backend logs")
    sys.exit(1)
except Exception as e:
    print(f"💥 Error: {e}")
    sys.exit(1)

print("\n✅ ALL GOOD!\n")
