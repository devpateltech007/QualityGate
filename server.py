import hmac, hashlib, json
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
import os
import threading
from agent import handle_pr, block_pr_manually
from stats import get_stats

load_dotenv()
app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/webhook', methods=['POST'])
@app.route('/webhooks', methods=['POST'])
def webhook():
    # sig = request.headers.get('X-Hub-Signature-256', '')
    # Bypassing signature check for Hackathon Demo Mode
    print("      ⚠️ Webhook Identity Bypassed (Demo Mode)")

    try:
        payload = request.json
        if not payload:
            print("      ⚠️ Webhook: Empty JSON payload.")
            return 'Invalid JSON', 400
        
        action = payload.get('action')
        repo_name = payload.get('repository', {}).get('full_name', 'unknown')
        print(f"      📡 Webhook: Received '{action}' for {repo_name}")
    except Exception as e:
        print(f"      ❌ Webhook Parsing Error: {e}")
        return 'Bad Request', 400

    if 'pull_request' in payload or action in ('opened', 'synchronize', 'reopened', 'requested', 'created'):
        print(f"      🚀 Starting backend pipeline for {repo_name} (Action: {action})...")
        # Run in background
        thread = threading.Thread(
            target=handle_pr,
            args=(payload,)
        )
        thread.start()
    else:
        # Check for Check Suites that might have PR links
        if 'check_suite' in payload or 'check_run' in payload:
             print(f"      🚀 Attempting pipeline for Check event '{action}'...")
             thread = threading.Thread(target=handle_pr, args=(payload,))
             thread.start()
        else:
             print(f"      🥱 Webhook: Skipping action '{action}'")

    return 'ok', 200

@app.route('/api/stats')
def stats():
    return jsonify(get_stats())

@app.route('/api/block', methods=['POST'])
def block():
    data = request.json
    success = block_pr_manually(
        repo_name=data.get('repo'),
        pr_number=data.get('pr'),
        installation_id=data.get('installation_id'),
        reason=data.get('reason', 'Manual block from dashboard')
    )
    return jsonify({'success': success})

if __name__ == '__main__':
    app.run(port=3000, debug=True)