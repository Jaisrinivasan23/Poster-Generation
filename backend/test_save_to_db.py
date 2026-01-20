"""
Test script for saving posters to Topmate DB
"""
import requests
import json
import sys
import io

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# API endpoint
api_url = "http://localhost:8000/api/save-bulk-posters"

# Test data - using the generated poster from previous test
payload = {
    "posterName": "samplee",
    "posters": [
        {
            "username": "phase",
            "posterUrl": "https://topmate-staging.s3.ap-south-1.amazonaws.com/phase-1768581818987.png"
            # userId is optional - will be looked up automatically
        }
    ]
}

print("[TEST] Testing save to Topmate DB...")
print(f"[TEST] Campaign: {payload['posterName']}")
print(f"[TEST] Posters to save: {len(payload['posters'])}")
print(f"[TEST] User: {payload['posters'][0]['username']}")
print(f"[TEST] Poster URL: {payload['posters'][0]['posterUrl']}")
print()

print("[API] Sending request to /api/save-bulk-posters...")
response = requests.post(api_url, json=payload, timeout=120)

print(f"\n[API] Response Status: {response.status_code}")
print(f"[API] Response Body:")
print(json.dumps(response.json(), indent=2))

if response.status_code == 200:
    result = response.json()
    print(f"\n[SUCCESS] Save operation completed!")
    print(f"[STATS] Total posters: {len(result.get('results', []))}")
    print(f"[STATS] Successful: {result.get('successCount', 0)}")
    print(f"[STATS] Failed: {result.get('failureCount', 0)}")

    # Print details for each result
    for i, res in enumerate(result.get('results', [])):
        print(f"\n{i+1}. Result:")
        if res.get('success'):
            print(f"   [SUCCESS] Saved successfully")
            print(f"   [USER_ID] {res.get('userId')}")
            print(f"   [POSTER_URL] {res.get('posterUrl')}")
        else:
            print(f"   [ERROR] Failed: {res.get('error')}")
else:
    print(f"\n[ERROR] Request failed with status {response.status_code}")
    try:
        error_detail = response.json()
        print(f"[ERROR] Details: {json.dumps(error_detail, indent=2)}")
    except:
        print(f"[ERROR] Response: {response.text}")
