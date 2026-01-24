#!/usr/bin/env python3
"""Test script to create a CSV-based batch job"""
import requests
import time

# Read files
with open('test_csv_with_userid.csv', 'rb') as f:
    csv_content = f.read()

with open('test_template.html', 'r', encoding='utf-8') as f:
    template_content = f.read()

# Create batch job
print("🚀 Creating CSV batch job...")
response = requests.post(
    'http://localhost:8000/api/batch/csv-jobs',
    files={
        'csvFile': ('test.csv', csv_content, 'text/csv')
    },
    data={
        'csvTemplate': template_content,
        'campaignName': 'Test CSV with User ID',
        'width': '1080',
        'height': '1080',
        'skipOverlays': 'true'
    }
)

if response.status_code == 200:
    data = response.json()
    print(f"✅ Job created: {data['jobId']}")
    print(f"📊 Total items: {data['totalItems']}")
    print(f"🔗 SSE endpoint: {data['sseEndpoint']}")

    job_id = data['jobId']

    # Wait and check status
    print("\n⏳ Waiting for job to complete...")
    for i in range(30):
        time.sleep(2)
        status_response = requests.get(f'http://localhost:8000/api/batch/jobs/{job_id}')
        if status_response.status_code == 200:
            status_data = status_response.json()
            job = status_data['job']
            print(f"[{i*2}s] Status: {job['status']} | Processed: {job['processed_items']}/{job['total_items']} | Success: {job['success_count']} | Failed: {job['failure_count']}")

            if job['status'] in ['completed', 'failed']:
                print(f"\n✅ Job {job['status']}!")
                if job['status'] == 'failed':
                    print(f"❌ Error: {job.get('error_message', 'Unknown')}")
                break

    # Get results
    print("\n📋 Fetching results...")
    results_response = requests.get(f'http://localhost:8000/api/batch/jobs/{job_id}/results')
    if results_response.status_code == 200:
        results_data = results_response.json()
        print(f"✅ Success: {results_data['successCount']}")
        print(f"❌ Failed: {results_data['failureCount']}")

        for result in results_data['results']:
            if result.get('success'):
                print(f"  ✅ {result['username']}: {result.get('posterUrl', 'N/A')}")
            else:
                print(f"  ❌ {result['username']}: {result.get('error', 'Unknown error')}")
else:
    print(f"❌ Failed to create job: {response.status_code}")
    print(response.text)
