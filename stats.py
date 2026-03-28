import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'stats.json')
_records = []

def _save():
    with open(DB_PATH, 'w') as f:
        json.dump(_records, f, indent=4)

if os.path.exists(DB_PATH):
    try:
        with open(DB_PATH, 'r') as f:
            _records = json.load(f)
    except:
        _records = []

def record(pr_number, status, ai_score, review_issues=None):
    _records.append({
        'pr': pr_number,
        'status': status,
        'ai_score': ai_score,
        'issues': review_issues or [],
        'timestamp': datetime.utcnow().isoformat()
    })
    _save()

def get_stats():
    total = len(_records)
    flagged = sum(1 for r in _records if r['ai_score'] > 60)
    blocked = sum(1 for r in _records if r['status'] == 'blocked')
    return {
        'total': total,
        'flagged_percent': round((flagged / total) * 100) if total else 0,
        'blocked_count': blocked,
        'recent': list(reversed(_records[-20:]))
    }