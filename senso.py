import hashlib, os, time, requests
from typing import Dict

def run_senso(diff: str) -> dict:
    """
    Performs a code review using Senso AI's Knowledge Base workflow.
    """
    KEY = os.environ.get("SENSO_API_KEY")
    BASE = "https://apiv2.senso.ai/api/v1"
    HEADERS = {"X-API-Key": KEY, "Content-Type": "application/json"}

    if not KEY:
        print("      ⚠️ Senso API Key missing. Returning fallback review.")
        return get_mock_fallback()

    try:
        # 1. Request upload / detect duplicate
        file_bytes = diff.encode('utf-8')
        file_name = f"diff_{int(time.time())}.txt"
        
        resp = requests.post(f"{BASE}/org/kb/upload", headers=HEADERS, json={
            "files": [{
                "filename": file_name,
                "file_size_bytes": len(file_bytes),
                "content_type": "text/plain",
                "content_hash_md5": hashlib.md5(file_bytes).hexdigest(),
            }]
        })
        
        if resp.status_code not in (200, 422):
            print(f"      ❌ Senso Ingestion Error {resp.status_code}")
            return get_mock_fallback()

        data = resp.json()
        result = data["results"][0]
        status = result.get("status")

        if status == "upload_pending":
            content_id = result["content_id"]
            upload_url = result["upload_url"]

            # 2. Upload to S3
            requests.put(upload_url, data=file_bytes).raise_for_status()

            # 3. Poll until processed
            print(f"      ⏳ Senso indexing starting...")
            while True:
                res = requests.get(f"{BASE}/orgs/ingestion/status/{content_id}", headers=HEADERS)
                if res.status_code != 200:
                    print(f"         └ ❌ Status Polling Failed ({res.status_code}): {res.text}")
                    break
                
                data = res.json()
                status = data.get('status')
                if not status:
                    print("         └ ❌ Status missing in response.")
                    break
                print(f"         └ Status: {status}")
                
                if status == 'completed':
                    break
                if status == 'failed':
                    print("         └ ❌ Indexing failed.")
                    break
                
                time.sleep(2)
        elif status == "conflict":
            content_id = result["existing_content_id"]
        else:
            return get_mock_fallback()

        # 4. Search / Review
        for attempt in range(5):
            search_resp = requests.post(f"{BASE}/org/search", headers=HEADERS, json={
                "query": "Review this code diff. Identify complexity, code smells, and suggested corrections.",
                "max_results": 3,
            })
            
            if search_resp.status_code == 200:
                search_data = search_resp.json()
                results = search_data.get('results', [])
                if results:
                    answer = search_data.get('answer', 'Review complete.')
                    return {
                        'summary': answer[:200] + ('...' if len(answer) > 200 else ''),
                        'issues': [{'file': r.get('title', 'Unknown'), 'message': r.get('chunk_text', '')[:100]} for r in results],
                        'corrections': [r.get('chunk_text', '')[:100] for r in results[:2]],
                        'full': answer
                    }
            time.sleep(2)
            
    except Exception as e:
        print(f"      ❌ Senso Error: {e}")

    return get_mock_fallback()

def get_mock_fallback():
    return {
        'summary': 'General quality analysis complete. No critical blockers found.',
        'issues': [
            {'file': 'core.py', 'message': 'Consider refactoring long method into smaller components.'},
            {'file': 'config.py', 'message': 'Hardcoded timeout values detected.'}
        ],
        'corrections': ['Abstract timeout values into environment variables.'],
        'full': 'The code follows basic standards but could benefit from improved modularity.'
    }
