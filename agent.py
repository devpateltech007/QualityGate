import railtracks as rt
import os, re
from pydantic import BaseModel
from typing import Optional, List
from github import Github, Auth, GithubIntegration
from senso import run_senso
from stats import record

# --- Pydantic models ---

class PRPayload(BaseModel):
    installation_id: int
    pr_number: int
    pr_title: str
    pr_body: str
    pr_commits: int
    repo_name: str
    diff: Optional[str] = None

class ReviewContext(BaseModel):
    installation_id: int
    pr_number: int
    pr_title: str
    pr_body: str
    pr_commits: int
    repo_name: str
    diff: str = ''
    ai_score: int = 0
    blocked: bool = False
    review_summary: str = ''
    review_issues: List[str] = []
    review_corrections: List[str] = []
    review_full: str = ''

# --- GitHub client helper (not a node, just a utility) ---

def get_github_client(installation_id):
    # Skip real GitHub calls if we're using the test ID
    if installation_id == 123456:
        return None

    with open(os.environ['GITHUB_PRIVATE_KEY_PATH'], 'r') as f:
        private_key = f.read()
    integration = GithubIntegration(
        auth=Auth.AppAuth(int(os.environ['GITHUB_APP_ID']), private_key)
    )
    token = integration.get_access_token(installation_id).token
    return Github(auth=Auth.Token(token))

# --- Railtracks nodes (Pydantic in, Pydantic out) ---

@rt.function_node
def fetch_diff(payload: PRPayload) -> ReviewContext:
    print(f"\n[1/5] 📥 Fetching diff for PR #{payload.pr_number} in {payload.repo_name}...")
    
    if payload.installation_id == 123456:
        print("      🛠️ Test Mode: Using mock diff from payload.")
        diff = payload.diff or 'No diff provided.'
    else:
        try:
            g = get_github_client(payload.installation_id)
            repo = g.get_repo(payload.repo_name)
            pull = repo.get_pull(payload.pr_number)

            diff_parts = []
            for f in pull.get_files():
                if f.patch:
                    diff_parts.append(f.patch)
            diff = '\n'.join(diff_parts)
        except Exception as e:
            print(f"GitHub API error (falling back to mock data): {e}")
            diff = getattr(payload, 'diff', 'No diff provided.')

    ctx = ReviewContext(
        installation_id=payload.installation_id,
        pr_number=payload.pr_number,
        pr_title=payload.pr_title,
        pr_body=payload.pr_body,
        pr_commits=payload.pr_commits,
        repo_name=payload.repo_name,
        diff=diff
    )
    print(f"      ✅ Diff fetched ({len(diff)} characters)")
    return ctx

@rt.function_node
def detect_ai(context: ReviewContext) -> ReviewContext:
    print(f"[2/5] 🤖 Analyzing AI probability...")
    lines = context.diff.split('\n')
    added = [l for l in lines if l.startswith('+')]

    score = 0
    if len(added) > 300:
        score += 30
    msg = context.pr_title + (context.pr_body or '')
    if re.search(r'add feature|fix bug|update code|refactor', msg, re.I):
        score += 20
    uniform_comments = sum(1 for l in added if re.match(r'^\+\s*//', l))
    if added and uniform_comments / len(added) > 0.3:
        score += 25
    if context.pr_commits == 1 and len(added) > 200:
        score += 25

    context.ai_score = min(score, 100)
    print(f"      📊 AI Confidence Score: {context.ai_score}%")
    return context

@rt.function_node
def design_note_gate(context: ReviewContext) -> ReviewContext:
    print(f"[3/5] 🧱 Checking Quality Gate (Design Notes)...")
    has_design_note = bool(re.search(
        r'what this (does|change)|risk|rollback', context.pr_body, re.I
    ))

    if context.ai_score > 60 and not has_design_note:
        if context.installation_id == 123456:
             print(f"      🚨 BLOCKED (Mock): High AI score ({context.ai_score}%) and missing design notes.")
        else:
            g = get_github_client(context.installation_id)
            repo = g.get_repo(context.repo_name)
            pull = repo.get_pull(context.pr_number)
            pull.create_issue_comment(f"""## ⛔ Quality Gate — Design Note Required

**AI-generated content detected**: {context.ai_score}% confidence

Please add to your PR description before reviewers are notified:
```
**What this change does:**
[explain here]

**Risks:**
[explain here]

**Rollback plan:**
[explain here]
```

Edit the description or push a new commit to re-trigger review.""")
            pull.add_to_labels('needs-design-note')
            print(f"      🚨 BLOCKED: GitHub comment posted.")

        record(context.pr_number, 'blocked', context.ai_score)
        context.blocked = True
    else:
        print(f"      ✅ PASSED: No block required.")

    return context

@rt.function_node
def senso_review(context: ReviewContext) -> ReviewContext:
    if context.blocked:
        print(f"[4/5] ⏩ Skipping Senso review (PR is blocked).")
        return context
    
    print(f"[4/5] 🔍 Running Senso AI code review...")

    review = run_senso(context.diff)
    context.review_summary = review.get('summary', '')
    context.review_issues = [
        f"**{i.get('file', '?')}**: {i.get('message', '')}"
        for i in review.get('issues', [])
    ]
    context.review_corrections = review.get('corrections', [])
    context.review_full = review.get('full', '')
    print(f"      ✅ Senso analysis complete. Found {len(context.review_issues)} issues.")
    return context

@rt.function_node
def post_quality_comment(context: ReviewContext) -> ReviewContext:
    if context.blocked:
        print(f"[5/5] 🏁 Pipeline finished (Stats updated).")
        return context

    print(f"[5/5] 📜 Preparing final quality feedback...")

    issues_md = '\n'.join(f'- {i}' for i in context.review_issues) or '_No issues found_'
    corrections_md = '\n'.join(f'- {c}' for c in context.review_corrections) or '_No corrections_'

    comment = f"""## ✅ Quality Gate Passed

**AI-generated content**: {context.ai_score}% confidence

### Senso AI Analysis
{context.review_summary or 'No summary available'}

### Issues Found
{issues_md}

### Suggested Corrections
{corrections_md}

<details><summary>Full analysis</summary>

{context.review_full}
</details>"""

    if context.installation_id == 123456:
        print("      🛠️ Test Mode: Skipping GitHub comment posting.")
    else:
        try:
            g = get_github_client(context.installation_id)
            if g:
                repo = g.get_repo(context.repo_name)
                pull = repo.get_pull(context.pr_number)
                pull.create_issue_comment(comment)
                print(f"      ✅ Feedback posted to GitHub.")
        except Exception as e:
            print(f"      ❌ GitHub API error: {e}")

    record(context.pr_number, 'passed', context.ai_score)
    print(f"      ✅ Pipeline finished successfully.")
    return context

# --- Main pipeline ---

def handle_pr(payload: dict):
    try:
        pr = payload['pull_request']
        input_data = PRPayload(
            installation_id=payload['installation']['id'],
            pr_number=pr['number'],
            pr_title=pr.get('title', ''),
            pr_body=pr.get('body') or '',
            pr_commits=pr.get('commits', 1),
            repo_name=payload['repository']['full_name'],
            diff=payload.get('mock_diff')  # Allow passing a mock diff via webhook
        )
        ctx = fetch_diff(input_data)
        ctx = detect_ai(ctx)
        ctx = design_note_gate(ctx)
        ctx = senso_review(ctx)
        ctx = post_quality_comment(ctx)
    except Exception as e:
        print(f'Pipeline error: {e}')