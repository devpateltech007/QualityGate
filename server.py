import hmac, hashlib, json
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
import os
import threading
from agent import handle_pr
from stats import get_stats

load_dotenv()
app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/webhook', methods=['POST'])
def webhook():
    sig = request.headers.get('X-Hub-Signature-256', '')
    body = request.get_data()
    expected = 'sha256=' + hmac.new(
        os.environ['GITHUB_WEBHOOK_SECRET'].encode(),
        body, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(sig, expected):
        return 'Invalid signature', 401

    payload = request.json
    action = payload.get('action')

    if action in ('opened', 'synchronize'):
        # Run in background so webhook returns fast
        thread = threading.Thread(
            target=handle_pr,
            args=(payload,)
        )
        thread.start()

    return 'ok', 200

@app.route('/api/stats')
def stats():
    return jsonify(get_stats())

if __name__ == '__main__':
    app.run(port=3000, debug=True)