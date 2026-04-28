# E156 Ecosystem Starter — what it is, why it matters (1-page intro)

**For students.** This is a one-click setup that turns a fresh laptop (or a free GitHub-hosted browser environment) into the same research-development environment used by the `mahmood726-cyber` portfolio. After the install, your AI agent (Gemini, Claude, or Codex) reads four rules files that encode the same method used to ship 270+ research repos: brainstorm → spec-lock → plan-lock → TDD → audit. Plus, every time you save your work to GitHub, a quality scanner (Sentinel) checks for 20 of the most common research-code mistakes, and a verifier (Overmind) tells you whether your numbers actually reproduce.

**For lecturers.** It collapses what used to be a two-week onboarding (install Python + R + Node + 15 packages + 4 agent CLIs + write your own coding rules + figure out a verification workflow) into ~3 minutes. A class of 30 students can all be on the same baseline by the end of the first session, with the same enforcement rules as Mahmood's lab. The novelty is not the tools (those are off-the-shelf) — it's that the rules are **incident-backed** (every rule comes from a specific past failure) and **enforced** (Sentinel blocks bad patterns at git-push time, not just during code review).

## What lands on the student's machine

| Component | What it does in plain English |
|---|---|
| **Rules pack** | Four `.md` files the AI agent reads. They tell it the workflow Mahmood uses + 100+ specific bug-prevention rules from past incidents. |
| **Memory scaffold** | A folder where the AI agent remembers things between sessions (your preferences, project notes, what worked, what didn't). |
| **Sentinel** | A scanner that runs every time the student does `git push`. Blocks 20 specific bad patterns — see the list below. |
| **Overmind** | A verifier the student runs before declaring a paper "done". Checks tests + smoke + numerical baselines + emits a signed certificate. |
| **ProjectIndex** | A markdown file listing all the student's projects. Stops the "I forgot I already wrote that" problem. |
| **Gemini CLI / Claude Code** | The AI agent itself. Free (Gemini, Google account) or paid (Claude, Anthropic API key). |

## What Sentinel actually blocks (the "20 patterns")

Each rule comes from a real past incident in Mahmood's portfolio. Source: `~/.claude/rules/lessons.md` + the [Sentinel](https://github.com/mahmood726-cyber/Sentinel) repo's `docs/rules.md`. Use this list when teaching: every rule has a *why* line tying it to a concrete failure that wasted real time.

1. **`P0-hardcoded-local-path`** — `C:\Users\me\...` or `/home/<user>/...` in committed code.
2. **`P0-placeholder-hmac`** — committed strings like `SIG_RSA_SHA256_...` or `REPLACE_ME` in security-sensitive fields.
3. **`P0-silent-failure-sentinel`** — `return "unknown"` / `return None` on schema mismatch instead of raising.
4. **`P0-xss-sink`** — `innerHTML = userInput` without escape, in JS / HTML files.
5. **`P0-localStorage-collision`** — same `localStorage` key used across HTML variants without prefix.
6. **`P1-empty-dataframe-access`** — `.iloc[0]` / `.values[0]` without an upstream `if df.empty` guard.
7. **`P1-committed-claude-config`** — `.claude/`, `.codex/`, `.gemini/` directories appearing in the working tree.
8. **`P1-stale-agent-config-version`** — config file's `version:` field doesn't match the installed CLI version.
9. **`P1-js-lockfile-present`** — `package.json` exists without `package-lock.json`.
10. **`P1-js-scripts-resolvable`** — `package.json` declares `scripts` pointing at non-existent files.
11. **`P0-py-stdout-reassignment-in-test`** — `sys.stdout = ...` at module level in `test_*.py` (breaks pytest capture).
12. **`P1-cp1252-mojibake-in-utf8-source`** — `â€"`, `â”€`, `â˜…` patterns indicating an editor mis-saved UTF-8.
13. **`P1-citation-swap-on-references`** — diff to a `references[]` array where author surnames change without explanation (academic-integrity guard).
14. **`P0-derived-fields-without-source`** — derived statistic (HR, RR, OR) committed without the source data file or extraction comment.
15. **`P1-csv-formula-injection`** — CSV cell starting with `=`, `+`, `@`, `\t`, `\r` (Excel formula vector).
16. **`P1-redos-pattern`** — regex pattern with nested unbounded quantifiers (`(\w+)+`, `[\w\s]+?`).
17. **`P1-uppercase-pkg-name-in-import`** — `import Sentinel` instead of `import sentinel` (Windows-vs-Linux case bug).
18. **`P2-bom-in-source`** — UTF-8 BOM in `.py` / `.sh` / `.js` files (breaks shebangs, breaks JSON parsers).
19. **`P2-skip-marker-in-shipped-file`** — `sentinel:skip-file` marker in code outside test fixtures (someone bypassed and forgot to fix).
20. **`P2-windows-line-endings-in-shell-script`** — `\r\n` line endings in `.sh` files (breaks `/bin/bash` shebang on Linux).

Each rule is documented with a one-line *why* and the exact past incident at the Sentinel repo. Students who think a rule is wrong should fork Sentinel and edit — incident-backed rules are not gospel for every project.

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
