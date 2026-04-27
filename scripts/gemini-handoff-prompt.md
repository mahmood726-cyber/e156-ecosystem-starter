# Hi Gemini! I just ran the e156-ecosystem-starter installer on this machine.

The installer copied AI-agent rules, memory templates, and (optionally)
Sentinel/Overmind/ProjectIndex into my home dir. Your job now is the
"second half" of the install — the parts that need an agent, not a script.

Please do these in order. Stop and ask me if any step would touch something
outside my home directory or modify system PATH.

1. **Sanity-check the install.** Read `~/.claude/rules/rules.md` and confirm
   the four rules files are present (`rules.md`, `e156.md`, `advanced-stats.md`,
   `lessons.md`). If any are missing, tell me which ones and stop.

2. **Diagnose missing prereqs and tell me what to install.** Run `python --version`,
   `Rscript --version`, `node --version`, `gh --version`, `git --version`. For
   each one that's missing or too old (Python <3.11, R <4.5, Node <20), print
   the exact install URL and a one-line reason it matters for E156 work. Don't
   try to install them yourself — let me see the list and decide.

3. **If `gh` is installed but not authenticated**, tell me to run `gh auth login`
   and wait. Don't proceed until I confirm.

4. **Smoke-test Sentinel and Overmind (only if installed).** If `sentinel` is
   on PATH, run `sentinel --version`. If `overmind` is on PATH, run
   `overmind meta-verify` and report the verdict. Both failing = environment
   problem, both passing = ready to ship.

5. **Pick a first project.** Ask me which of the 8 example projects from
   `docs/index.html` ("Forest-plot tool from scratch", "PRISMA flow generator",
   etc.) I want to start with. When I answer, run
   `pip install git+https://github.com/mahmood726-cyber/e156-student-starter.git@main`
   then `student new <slug>` to scaffold it under `~/code/<slug>/`.

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
