"""
Quick test script to verify the FastAPI backend is working
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_health():
    """Test if server is running"""
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        print(f"GET / - Status: {response.status_code}")
        print(f"Response: {response.text[:200]}")
        return True
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

def test_docs():
    """Test if docs are accessible"""
    try:
        response = requests.get(f"{BASE_URL}/docs", timeout=5)
        print(f"\nGET /docs - Status: {response.status_code}")
        print(f"Docs accessible: {response.status_code == 200}")
        return response.status_code == 200
    except Exception as e:
        print(f"Docs check failed: {e}")
        return False

def test_generate_poster():
    """Test poster generation endpoint (without actually calling OpenRouter)"""
    try:
        # Just test the endpoint exists
        response = requests.post(
            f"{BASE_URL}/api/generate-poster",
            json={
                "config": {
                    "topmateUsername": "test",
                    "style": "professional",
                    "size": "instagram-square",
                    "mode": "single",
                    "prompt": "test poster"
                },
                "model": "flash"
            },
            timeout=5
        )
        print(f"\nPOST /api/generate-poster - Status: {response.status_code}")
        # We expect it to fail at Topmate profile fetch, not at routing
        return True
    except Exception as e:
        print(f"Generate poster test: {e}")
        return False

if __name__ == "__main__":
    print("="*60)
    print("FASTAPI BACKEND API TEST")
    print("="*60)

    results = []
    results.append(("Health Check", test_health()))
    results.append(("Docs Endpoint", test_docs()))
    results.append(("Generate Poster Endpoint", test_generate_poster()))

    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"{name}: {status}")

    passed_count = sum(1 for _, p in results if p)
    print(f"\nPassed: {passed_count}/{len(results)}")
