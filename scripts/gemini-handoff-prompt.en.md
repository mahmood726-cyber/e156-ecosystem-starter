# Hi Gemini! I just ran the e156-ecosystem-starter installer on this machine.

The installer copied AI-agent rules, memory templates, and (optionally)
Sentinel/Overmind/ProjectIndex into my home dir. Your job now is the
"second half" of the install — the parts that need an agent, not a script.

Please do these in order. Stop and ask me if any step would touch something
outside my home directory or modify system PATH.

**For each step, the convention is:**
- "I will run X" = YOU (the agent) execute the command in your shell tool.
- "Tell me to run X" = print the command for ME (the user) to run myself in my own terminal.
- "Ask me Y" = pause and wait for my answer before continuing.

This is important because I am a beginner and may not know which commands are
safe to type myself.

1. **YOU run** `cat ~/.claude/rules/rules.md | head -5` to confirm the rules
   pack is installed. If the file is missing or empty, tell me which file
   and stop. Do not try to fix it.

2. **YOU run** these prereq checks: `python --version`, `Rscript --version`,
   `node --version`, `gh --version`, `git --version`. For each one that's
   missing or too old (Python <3.11, R <4.5, Node <20), print the exact
   install URL and a one-line reason it matters for E156 work. Do NOT try
   to install missing ones yourself — surface the list and let me decide.

3. **If `gh` is installed but not authenticated** (you'll see this from
   `gh auth status`), **TELL ME to run** `gh auth login` and wait for me
   to confirm before proceeding.

4. **Smoke-test Sentinel and Overmind (only if installed).** If `sentinel` is
   on PATH, run `sentinel --version`. If `overmind` is on PATH, run
   `overmind meta-verify` and report the verdict. Both failing = environment
   problem, both passing = ready to ship.

5. **Pick a first project.** Ask me which of the 8 example projects from
   `docs/index.html` ("Forest-plot tool from scratch", "PRISMA flow generator",
   etc.) I want to start with. When I answer, **before scaffolding anything**,
   run portfolio recon:
   ```
   python /workspaces/e156-ecosystem-starter/scripts/find-related-repos.py "<my topic>" --top 5
   ```
   (For local installs, replace the path with wherever you cloned
   `e156-ecosystem-starter/`.) Read the top 5 hits — name, README excerpt,
   code-grep results. Tell me in 3 lines what's reusable from existing repos
   vs what is genuinely net-new. Then run
   `pip install git+https://github.com/mahmood726-cyber/e156-student-starter.git@main`
   and `student new <slug>` to scaffold under `~/code/<slug>/`. In the new
   repo's `docs/<criterion>.md`, cite the prior repos by name.

6. **Read STUDENT-WORKFLOW.md** at
   https://raw.githubusercontent.com/mahmood726-cyber/e156-ecosystem-starter/main/STUDENT-WORKFLOW.md
   so you understand the brainstorm → spec-lock → plan-lock → TDD → audit
   method before you write a single line of code in the new project.

7. **Stop here and tell me what to do next.** Don't auto-implement the project.
   The installer's job was to get the rules in place; the project's job is for
   us to do together using the spec-locked method.

Constraints:
- Do not modify files outside `~/.claude/`, `~/.gemini/`, `~/.codex/`, or `~/code/`.
- Do not run anything as `sudo` / admin.
- If anything fails, show me the exact command and error — don't guess at fixes.
