# Publishing to Shipables.dev

To publish your **AI Review Bot** as a reusable skill on [Shipables](https://shipables.dev/), follow these steps:

### 1. Preparation
Your skill folder is located at: `c:\Users\ASUS ROG\Documents\Hackathons\Multimodal\ai-review-bot\skill\`

Ensure it contains:
- `SKILL.md`: Metadata and instructions.
- `agent.py`, `senso.py`, `server.py`, `stats.py`: Core logic files (Copy these into the folder).
- `templates/`, `static/`: UI assets.

### 2. Create a GitHub Repository
1. Initialize a new repo: `git init`.
2. Commit your code: `git add . && git commit -m "Initial skill release"`.
3. Push to a public GitHub repository (e.g., `devpateltech007/ai-review-bot-skill`).

### 3. Connect to Shipables
1. Go to [https://shipables.dev/publish](https://shipables.dev/publish).
2. Connect your GitHub account.
3. Select the repository you just created.
4. Shipables will automatically index your `SKILL.md` and make it searchable for other agents!

### 4. Verification
Once published, try searching for "AI Review Bot" on Shipables. You should see your premium glassmorphic dashboard featured as a highlighted skill!

**Good luck with your submission!** 🚀
