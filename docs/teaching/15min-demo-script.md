# 15-minute live demo script

Use this as a talking-points outline for a live demo to students. Tested-friendly: every step has a "if X happens, do Y" branch.

## Before the demo (set up once)

- Open https://mahmood726-cyber.github.io/e156-ecosystem-starter/ in a browser tab. Have a second tab ready at github.com/codespaces (so you can show how to STOP a codespace at the end).
- Have a sample project topic ready, e.g. "Forest plot tool from scratch". Mention it's one of the eight worked examples on the landing page.

## Minute 0–2: The "why" (no slides, just speak)

- "You've all been told to use AI agents. None of them know your supervisor's workflow. So you spend the first month re-explaining what 'good' looks like in every conversation."
- "This setup teaches the agent your supervisor's workflow once. Every conversation after that, the agent already knows."

## Minute 2–4: Click the button

- Show the green "Open in GitHub Codespaces" button.
- Click it. Walk through what happens: GitHub auth → "Configuring codespace…" appears → wait.
- **If the wait feels long**: "This takes 2-3 minutes the first time because it's installing 5 things. After this, opening the same codespace is instant." Show the progress markers in the creation log if visible.

## Minute 4–7: Read the on-attach banner

- When the terminal pops up, read the banner aloud line-by-line:
  - "rules pack — your AI agent reads these to follow the E156 method"
  - "Memory scaffold — what your AI agent remembers between sessions"
  - "Sentinel guard — checks code for 20 common mistakes before saving to GitHub"
  - "TruthCert key — signs your finished paper so it can't be tampered with"
  - "ProjectIndex — keeps a list of all your projects in one file"
- Point out the `[OK]` marks on each line. "If any of these said `[--]`, that means it failed to install — and you'd know to ask for help."

## Minute 7–11: Run `e156 start`

- In the terminal, type `e156 start`. Hit Enter.
- Gemini CLI opens. **First time**: it asks for Google sign-in. Walk through the browser popup.
- The handoff briefing has been pre-loaded. The agent reads it and starts diagnosing.
- **Read the agent's first response aloud**. Note that it's checking for prerequisites — Python, R, Node, gh — and tells you what to install if anything's missing. Stop here for questions.

## Minute 11–13: Pick a project

- The agent will ask "which of the 8 example projects do you want to start?"
- Pick "Forest plot tool from scratch". Watch what happens:
  - The agent runs `find-related-repos.py` first (the recon step).
  - It surfaces 2-3 prior projects from Mahmood's portfolio.
  - It tells you in 3 lines what's reusable vs net-new.
- This is the **portfolio recon** behaviour — "before any new project, look at what already exists."

## Minute 13–15: Stop the codespace

- Ctrl+C out of Gemini.
- Switch to the github.com/codespaces tab.
- Show the running codespace, click ⋯ → "Stop codespace".
- "Important. If you don't do this, you'll burn through your free 60 hours in a week. Codespaces are like leaving the lights on — they auto-suspend after 30 minutes idle, but those 30 minutes still count against your tier. Stop manually when done."

## Q&A bullet points (anticipate)

- **"Do I have to use Gemini?"** No. Gemini is free; Claude Code is the alternative if you have an Anthropic API key. Either works with the same handoff briefing.
- **"What if the install fails?"** The on-attach banner shows `[OK]` / `[--]` per component. If something failed, the agent in step 1 of the briefing diagnoses prereqs and tells you what's missing.
- **"Do I have to use the codespace, or can I install on my laptop?"** Both work. Codespace is easier for first-time users; local install is faster long-term and works offline.
- **"What if I leave my supervisor's lab — do I lose this?"** No. Everything is yours: your fork on GitHub, your `~/.claude/` directory, your own modifications. The rules pack is MIT-licensed.

## End the demo

- Tell students: "Try it yourself this evening. The next class, bring whatever the agent helped you draft. We'll read each other's work."
