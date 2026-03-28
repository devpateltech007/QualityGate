import hmac, hashlib
import json
import requests
import os
import sys
from dotenv import load_dotenv

load_dotenv()

SECRET = os.getenv('GITHUB_WEBHOOK_SECRET', 'your_secret')
URL = 'http://localhost:3000/webhook'

def send_mock_pr(type='high'):
    if type == 'high':
        # Triggering > 80% (30 + 20 + 25 + 25 = 100 or 80 if we omit one)
        payload = {
            "action": "opened",
            "pull_request": {
                "number": 101,
                "title": "Add feature: AI auto-generated code",
                "body": "What this change does: added a bunch of code. risks: none. rollback: just revert.",
                "commits": 1,
                "user": {"login": "ai-bot"}
            },
            "repository": {"full_name": "owner/repo"},
            "installation": {"id": 123456},
            "mock_diff": """+ // AI generated comment
+ // Self-commenting code
+ // Highly uniform structure
+ def generated_function():
+     pass
""" + ("\n+ // More comments here\n+ def dummy(): pass" * 300)
        }
    else:
        # Triggering < 40%
        # Small diff (0), multiple commits (0), descriptive title (0), low comment density (0)
        payload = {
            "action": "opened",
            "pull_request": {
                "number": 202,
                "title": "Fix memory leak in buffer allocation",
                "body": "This fixes a small memory leak by ensuring the buffer is cleared.",
                "commits": 3,
                "user": {"login": "human-dev"}
            },
            "repository": {"full_name": "owner/repo"},
            "installation": {"id": 123456},
            "mock_diff": """+ def fix_buffer():
+    buffer = []
+    # ensure it is emptied
+    buffer.clear()
"""
        }

    body = json.dumps(payload).encode()
    sig = 'sha256=' + hmac.new(
        SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    headers = {
        'X-Hub-Signature-256': sig,
        'Content-Type': 'application/json'
    }

    try:
        print(f"Sending {type.upper()} AI score mock PR to {URL}...")
        response = requests.post(URL, data=body, headers=headers)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    mode = 'high'
    if len(sys.argv) > 1 and sys.argv[1] in ('high', 'low'):
        mode = sys.argv[1]
    send_mock_pr(mode)
