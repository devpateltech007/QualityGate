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
        print(f"GitHub API error: {e}")
        # Fallback to payload diff if provided (e.g. for re-runs) or empty
        diff = payload.diff or ''

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

        record(context.pr_number, 'blocked', context.ai_score, ["Missing design notes for high-AI contribution"])
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

    try:
        g = get_github_client(context.installation_id)
        if g:
            repo = g.get_repo(context.repo_name)
            pull = repo.get_pull(context.pr_number)
            pull.create_issue_comment(comment)
            print(f"      ✅ Feedback posted to GitHub.")
    except Exception as e:
        print(f"      ❌ GitHub API error: {e}")

    record(context.pr_number, 'passed', context.ai_score, context.review_issues)
    print(f"      ✅ Pipeline finished successfully.")
    return context

# --- Manual Actions (for Dashboard) ---

def block_pr_manually(repo_name: str, pr_number: int, installation_id: int, reason: str = "Manual block from dashboard"):
    print(f"🚨 Manually blocking PR #{pr_number} in {repo_name}...")
    try:
        g = get_github_client(installation_id)
        repo = g.get_repo(repo_name)
        pull = repo.get_pull(pr_number)
        
        pull.create_issue_comment(f"## ⛔ PR Blocked Manually\n\n**Reason**: {reason}")
        pull.add_to_labels('blocked-manually')
        record(pr_number, 'blocked', 0, [reason])
        print(f"      ✅ PR #{pr_number} blocked successfully.")
        return True
    except Exception as e:
        print(f"      ❌ Failed to block PR: {e}")
        return False

# --- Main pipeline ---

def handle_pr(payload: dict):
    print(f"      ▶️ Pipeline started for {payload.get('repository', {}).get('full_name')}")
    try:
        # Resolve PR object (could be at top level or inside check_suite/check_run)
        pr = payload.get('pull_request')
        if not pr:
            if 'check_suite' in payload:
                pr_list = payload['check_suite'].get('pull_requests', [])
                if pr_list: pr = pr_list[0]
            elif 'check_run' in payload:
                pr_list = payload['check_run'].get('pull_requests', [])
                if pr_list: pr = pr_list[0]

        if not pr:
            print(f"      ⚠️ No Pull Request found in payload. Keys: {list(payload.keys())}")
            # Fallback 2: Search by SHA!
            head_sha = None
            if 'check_suite' in payload:
                head_sha = payload['check_suite'].get('head_sha')
            elif 'check_run' in payload:
                head_sha = payload['check_run'].get('head_sha', payload['check_run'].get('check_suite', {}).get('head_sha'))
            
            if head_sha:
                branch_name = None
                if 'check_suite' in payload:
                    branch_name = payload['check_suite'].get('head_branch')
                elif 'check_run' in payload:
                    branch_name = payload['check_run'].get('head_branch')
                
                print(f"      🔍 Searching for PR by SHA: {head_sha[:7]} or Branch: {branch_name}...")
                from agent import get_github_client
                g = get_github_client(payload.get('installation', {}).get('id', 0))
                repo = g.get_repo(payload['repository']['full_name'])
                
                open_pulls = list(repo.get_pulls(state='open'))
                print(f"      📊 Found {len(open_pulls)} open PRs in {repo.full_name}")
                
                for p in open_pulls:
                    if p.head.sha == head_sha or p.head.ref == branch_name:
                        pr = {'number': p.number, 'title': p.title, 'body': p.body, 'commits': p.commits}
                        print(f"      ✅ Found PR #{p.number} via {'SHA' if p.head.sha == head_sha else 'Branch'} search!")
                        break
        
        if not pr:
            print("      🛑 No PR associated with this event. Stopping.")
            return

        input_data = PRPayload(
            installation_id=payload.get('installation', {}).get('id', 0),
            pr_number=pr['number'],
            pr_title=pr.get('title', 'Unknown PR'),
            pr_body=pr.get('body') or '',
            pr_commits=pr.get('commits', 1),
            repo_name=payload['repository']['full_name'],
            diff=payload.get('mock_diff')
        )
        print(f"      🧪 Context created for PR #{input_data.pr_number}")
        ctx = fetch_diff(input_data)
        ctx = detect_ai(ctx)
        ctx = design_note_gate(ctx)
        ctx = senso_review(ctx)
        ctx = post_quality_comment(ctx)
        print(f"      🏁 Pipeline finished for PR #{input_data.pr_number}")
    except Exception as e:
        print(f"      ❌ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()