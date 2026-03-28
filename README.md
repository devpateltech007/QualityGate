# 🤖 AI Review Bot — Smart Quality Gate

An automated, agentic pull request review system built with **Railtracks** and **Senso AI**. It identifies AI-generated code, detects architectural "smells," and provides a premium dashboard for manual administrative control.

## ✨ Features

-   **AI Detection Heuristics**: Multi-layered analysis (volume, density, metadata, style) to identify "AI Slop."
-   **Senso AI Integration**: Deep code review using the Senso Knowledge Base API to find complex memory leaks and architectural patterns.
-   **Mission Control Dashboard**: A premium, glassmorphic UI to monitor PR activity in real-time.
-   **Persistent Tracking**: All review data is saved locally to `stats.json`, surviving server restarts and reloads.
-   **Manual Overrides**: Admins can block problematic PRs directly from the dashboard with one click.
-   **Resilient Webhooks**: Handles all PR event types and uses SHA-search fallbacks if payload data is missing.

## 🛠️ Tech Stack

-   **Backend**: Python, Flask, threading.
-   **AI Orchestration**: [Railtracks](https://railtracks.ai) (Agentic Graph).
-   **Code Analysis**: [Senso AI](https://senso.ai) (Indexing & Search).
-   **API Integration**: PyGithub (GitHub App).
-   **Frontend**: Vanilla HTML/CSS/JS (Glassmorphic Design).

## 🚀 Quick Start

### 1. Prerequisites
Ensure you have Python installed and create a `.env` file with these keys:
```env
GITHUB_APP_ID=your_id
GITHUB_WEBHOOK_SECRET=your_secret
GITHUB_PRIVATE_KEY_PATH="private-key.pem"
SENSO_API_KEY=your_key
```

### 2. Installation
```bash
pip install flask railtracks pygithub requests python-dotenv
```

### 3. Launch
```bash
python server.py
```
Visit [http://localhost:3000](http://localhost:3000) to see the dashboard.

## 🧪 Demo Guide (Triggering the Gate)

To see the bot in action with a 100% "AI Slop" detection:
1.  Add a massive block of redundant code (400+ lines) to your repository.
2.  Enable robotic/pseudo-intellectual comments.
3.  Commit with a generic message like `"update code"`.
4.  Open a Pull Request and watch the **Quality Gate** block the PR and post a detailed Senso AI analysis!

---

**Built for the Multimodal AI Hackathon 2026** 🚀
