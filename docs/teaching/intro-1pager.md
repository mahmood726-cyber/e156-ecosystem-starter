# E156 Ecosystem Starter — what it is, why it matters (1-page intro)

**For students.** This is a one-click setup that turns a fresh laptop (or a free GitHub-hosted browser environment) into the same research-development environment used by the `mahmood726-cyber` portfolio. After the install, your AI agent (Gemini, Claude, or Codex) reads four rules files that encode the same method used to ship 270+ research repos: brainstorm → spec-lock → plan-lock → TDD → audit. Plus, every time you save your work to GitHub, a quality scanner (Sentinel) checks for 20 of the most common research-code mistakes, and a verifier (Overmind) tells you whether your numbers actually reproduce.

**For lecturers.** It collapses what used to be a two-week onboarding (install Python + R + Node + 15 packages + 4 agent CLIs + write your own coding rules + figure out a verification workflow) into ~3 minutes. A class of 30 students can all be on the same baseline by the end of the first session, with the same enforcement rules as Mahmood's lab. The novelty is not the tools (those are off-the-shelf) — it's that the rules are **incident-backed** (every rule comes from a specific past failure) and **enforced** (Sentinel blocks bad patterns at git-push time, not just during code review).

## What lands on the student's machine

| Component | What it does in plain English |
|---|---|
| **Rules pack** | Four `.md` files the AI agent reads. They tell it the workflow Mahmood uses + 100+ specific bug-prevention rules from past incidents. |
| **Memory scaffold** | A folder where the AI agent remembers things between sessions (your preferences, project notes, what worked, what didn't). |
| **Sentinel** | A scanner that runs every time the student does `git push`. Blocks 20 specific bad patterns (hardcoded paths, fake security signatures, silently-wrong code). |
| **Overmind** | A verifier the student runs before declaring a paper "done". Checks tests + smoke + numerical baselines + emits a signed certificate. |
| **ProjectIndex** | A markdown file listing all the student's projects. Stops the "I forgot I already wrote that" problem. |
| **Gemini CLI / Claude Code** | The AI agent itself. Free (Gemini, Google account) or paid (Claude, Anthropic API key). |

## What it doesn't do

- It does NOT write the paper for the student. The agent helps; the thinking is theirs.
- It does NOT replace methodology training (epidemiology, biostatistics, clinical interpretation).
- It does NOT auto-fix bad code. Sentinel blocks; the student fixes.
- It does NOT enforce a single methodology. The rules are for *Mahmood's* method (E156 micro-papers + spec-locked workflow). Students with different supervisors should fork and edit.

## How to assign it to a class

1. Send students to https://mahmood726-cyber.github.io/e156-ecosystem-starter/
2. Tell them: "Click the green button. Sign in with GitHub. Wait 3 minutes. Type `e156 start` in the terminal that pops up. Follow the agent."
3. Their first paper comes out of the agent-led workflow. Use the agent's output as the basis for class discussion.

## License

All materials in this repo are MIT-licensed. Fork, adapt, redistribute freely.
