from datetime import datetime

_records = []

def record(pr_number, status, ai_score, review_issues=None):
    _records.append({
        'pr': pr_number,
        'status': status,
        'ai_score': ai_score,
        'issues': review_issues or [],
        'timestamp': datetime.utcnow().isoformat()
    })

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