"""
Test script for bulk poster generation
"""
import requests
import csv
import json
import sys
import io

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Read CSV file
csv_file = r"D:\Downloads\Dummy Sheet - Sheet2 (1).csv"
csv_data = []
csv_columns = []

with open(csv_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    csv_columns = reader.fieldnames
    for row in reader:
        csv_data.append(row)

print(f"[CSV] Loaded {len(csv_data)} rows from CSV")
print(f"[CSV] Columns: {csv_columns}")
print(f"[CSV] First row: {csv_data[0]}")

# HTML Template with placeholder
html_template = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Debut - Top Poster</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: Arial, sans-serif;
        }
        .poster-container {
            position: relative;
            width: 1080px;
            height: 1350px;
            background-color: #000;
            margin: 0 auto;
            overflow: hidden;
        }
        .background-image {
            position: absolute;
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        .profile-placeholder {
            position: absolute;
            left: 47px;
            top: 53px;
            width: 231px;
            height: 231px;
            border-radius: 50%;
            background-color: #fff;
            overflow: hidden;
            border: 4px solid #fff;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .profile-image {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        .profile-placeholder-empty {
            width: 100%;
            height: 100%;
            background-color: #e5e5e5;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #999;
            font-size: 48px;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="poster-container">
        <img src="https://res.cloudinary.com/topmate/image/upload/v1768285646/December%20Recap%2025/Base%20Posters/debut_q4loz4.png" alt="Debut" class="background-image">
        <div class="profile-placeholder">
            <img src="{profile_pic}" alt="Profile" class="profile-image">
        </div>
    </div>
</body>
</html>'''

# API Request
api_url = "http://localhost:8000/api/generate-bulk"

payload = {
    "bulkMethod": "csv",
    "csvTemplate": html_template,
    "csvData": csv_data,
    "csvColumns": csv_columns,
    "posterName": "samplee",
    "size": "instagram-portrait",
    "skipOverlays": False,
    "topmateLogo": None
}

print("\n[API] Sending request to API...")
print(f"[API] Payload size: {len(json.dumps(payload))} bytes")

response = requests.post(api_url, json=payload, timeout=300)

print(f"\n[API] Response Status: {response.status_code}")
print(f"[API] Response Body:")
print(json.dumps(response.json(), indent=2))

if response.status_code == 200:
    result = response.json()
    print(f"\n[SUCCESS] Success!")
    print(f"[STATS] Total results: {len(result.get('results', []))}")
    print(f"[STATS] Successful: {result.get('successCount', 0)}")
    print(f"[STATS] Failed: {result.get('failureCount', 0)}")

    # Print details for each result
    for i, res in enumerate(result.get('results', [])):
        print(f"\n{i+1}. {res.get('username')}:")
        if res.get('success'):
            print(f"   [SUCCESS] Success")
            print(f"   [IMAGE] Image URL: {res.get('imageUrl')}")
        else:
            print(f"   [ERROR] Failed: {res.get('error')}")
else:
    print(f"[ERROR] Request failed!")
