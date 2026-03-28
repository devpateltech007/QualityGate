import hashlib
import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

KEY = os.environ["SENSO_API_KEY"]
BASE = "https://apiv2.senso.ai/api/v1"
HEADERS = {"X-API-Key": KEY, "Content-Type": "application/json"}

file_path = "refund.txt"
with open(file_path, "rb") as f:
    file_bytes = f.read()

# 1) Request upload / detect duplicate
resp = requests.post(f"{BASE}/org/kb/upload", headers=HEADERS, json={
    "files": [{
        "filename": file_path,
        "file_size_bytes": len(file_bytes),
        "content_type": "text/plain",
        "content_hash_md5": hashlib.md5(file_bytes).hexdigest(),
    }]
})

print("upload status:", resp.status_code)
print(resp.text)

data = resp.json()
result = data["results"][0]
status = result.get("status")

if status == "upload_pending":
    content_id = result["content_id"]
    upload_url = result["upload_url"]

    put_resp = requests.put(upload_url, data=file_bytes)
    print("put status:", put_resp.status_code)
    print(put_resp.text[:300])
    put_resp.raise_for_status()

    print(f"Ingesting {file_path}... content_id={content_id}")

    # 2) Poll only for fresh uploads
    while True:
        r = requests.get(
            f"{BASE}/org/content/{content_id}",
            headers={"X-API-Key": KEY},
        )
        print("poll status:", r.status_code)
        print(r.text[:300])
        r.raise_for_status()

        item = r.json()
        processing_status = item.get("processing_status")
        print("processing_status:", processing_status)

        if processing_status == "complete":
            break

        time.sleep(1)

    print("Knowledge indexed.")

elif status == "conflict":
    content_id = result["existing_content_id"]
    print(f"Duplicate detected. Reusing existing content_id={content_id}")
    print("Skipping /org/content polling for duplicate KB content.")

else:
    raise RuntimeError(f"Unexpected upload result: {data}")

# 3) Search, with retries in case indexing is still settling
for attempt in range(10):
    search_resp = requests.post(f"{BASE}/org/search", headers=HEADERS, json={
        "query": "What is the refund policy?",
        "max_results": 3,
    })

    print("search status:", search_resp.status_code)
    print(search_resp.text[:1000])
    search_resp.raise_for_status()

    search = search_resp.json()
    results = search.get("results", [])

    if results:
        print(f"\nAgent answer: {search.get('answer')}")
        print("\nSources:")
        for r in results:
            print(f"  [{r['score']:.2f}] {r['title']}: {r['chunk_text'][:80]}...")
        break

    print(f"No search results yet, retrying... ({attempt + 1}/10)")
    time.sleep(2)
else:
    print("No results after retries.")