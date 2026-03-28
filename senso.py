import hashlib, os, time, requests
from typing import Dict

def run_senso(diff: str) -> dict:
    """
    Performs a code review using Senso AI's verified Knowledge Base workflow.
    """
    KEY = os.environ.get("SENSO_API_KEY")
    BASE = "https://apiv2.senso.ai/api/v1"
    HEADERS = {"X-API-Key": KEY, "Content-Type": "application/json"}

    if not KEY:
        print("⚠️ Senso API Key missing. Skipping real API call.")
        return get_mock_fallback()

    try:
        # 1. Request upload / detect duplicate
        file_bytes = diff.encode('utf-8')
        file_name = f"diff_{int(time.time())}.txt"
        
        print(f"      📡 Requesting Senso ingestion for {file_name}...")
        resp = requests.post(f"{BASE}/org/kb/upload", headers=HEADERS, json={
            "files": [{
                "filename": file_name,
                "file_size_bytes": len(file_bytes),
                "content_type": "text/plain",
                "content_hash_md5": hashlib.md5(file_bytes).hexdigest(),
            }]
        })
        
        # Senso returns 422 if the content is a duplicate (conflict)
        if resp.status_code not in (200, 422):
            print(f"      ❌ Senso Ingestion Error {resp.status_code}: {resp.text}")
            return get_mock_fallback()

        data = resp.json()
        result = data["results"][0]
        status = result.get("status")

        if status == "upload_pending":
            content_id = result["content_id"]
            upload_url = result["upload_url"]

            # 2. Upload to S3
            print(f"      📤 Uploading diff to Senso storage...")
            requests.put(upload_url, data=file_bytes).raise_for_status()

            # 3. Poll until processed
            print(f"      ⏳ Waiting for indexing...")
            while True:
                r = requests.get(f"{BASE}/org/content/{content_id}", headers=HEADERS)
                item = r.json()
                status = item.get("processing_status") or item.get("status")
                print(f"         └ Status: {status}")
                if status == "complete" or status == "indexed":
                    print("      ✅ Analysis ready.")
                    break
                if status is None:
                    print(f"         ⚠️ Unexpected response structure: {item}")
                time.sleep(2)
        elif status == "conflict":
            content_id = result["existing_content_id"]
            print(f"      ♻️ Reusing existing analysis for this diff.")
        else:
            print(f"      ❓ Unexpected Senso status: {status}")
            return get_mock_fallback()

        # 4. Search / Review
        print(f"      🔍 Extracting AI review findings...")
        # Use a retry loop to ensure indexing has settled
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
            
        print(f"      ⚠️ No results found after search retries.")
    except Exception as e:
        print(f"      ❌ Senso Workflow Error: {e}")

    return get_mock_fallback()
