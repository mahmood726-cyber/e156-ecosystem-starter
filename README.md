# e156-ecosystem-starter

Bootstrap Mahmood's quality-dev ecosystem on a student's laptop.

This is not a single tool. It is the **install layer** that turns a fresh
Windows machine into the same environment he uses to ship E156 papers and
meta-analysis tools: agent CLIs (Claude Code / Gemini CLI / Codex) plus
curated rules, memory scaffolding, and (coming in later phases) Sentinel,
TruthCert, and Overmind-lite.

## What you get

| Layer | Ship status | What it does |
|---|---|---|
| `rules/*.md` | v0.1.0 | Four curated rules files copied to `~/.claude/rules/`, `~/.gemini/rules/`, `~/.codex/rules/`: workflow + testing + HTML-app patterns (`rules.md`), E156 format (`e156.md`), statistics gotchas (`advanced-stats.md`), bug-prevention lessons (`lessons.md`). |
| `AGENTS.md` + `CLAUDE.md` / `GEMINI.md` / `CODEX.md` | v0.1.0 | Canonical + per-agent context files. Each agent auto-reads its own pointer; all pointers agree that `AGENTS.md` wins. |
| `memory/` scaffold | v0.1.0 | Starter `MEMORY.md` index + 4 type templates (`user` / `feedback` / `project` / `reference`). Dropped only when your memory dir is empty — never clobbers existing memory. |
| Sentinel pre-push hook | v0.5.0 (Phase 2) | Clones & installs the fail-closed rule engine in your workbook repo. |
| TruthCert CLI | v0.5.0 (Phase 3) | HMAC-signed bundle certification for submissions. |
| Overmind-lite | v0.5.0 (Phase 3) | On-demand portfolio verifier. |
| `student` CLI | separate repo | Narrow submission pipeline: see [`e156-student-starter`](https://github.com/mahmood726-cyber/e156-student-starter). |

## Quick start

Prerequisites: Windows 10+, PowerShell 5.1+, at least one of
[Claude Code](https://docs.anthropic.com/en/docs/claude-code),
[Gemini CLI](https://github.com/google-gemini/gemini-cli), or
[Codex](https://github.com/openai/codex) installed.

```powershell
git clone https://github.com/mahmood726-cyber/e156-ecosystem-starter
cd e156-ecosystem-starter
.\install\install.ps1
```

The installer will:

1. Verify its own SHA against `docs/HASH.txt` (tamper gate)
2. Detect which agent CLIs are on PATH and print install URLs for any missing
3. Copy `rules/*.md` into each agent's config dir (`.claude/rules/`, `.gemini/rules/`, `.codex/rules/`)
4. Drop `AGENTS.md` + `CLAUDE.md` + `GEMINI.md` + `CODEX.md` into each config dir
5. Bootstrap an empty memory scaffold in each agent's memory dir (preserves existing memory if present)

Flags:

- `-DryRun` — only verify the SHA gate, exit 0
- `-Force` — overwrite existing user-edited rules (default: back them up as `*.user`)
- `-Import` — dot-source helpers only (used by Pester tests)

## Design principles (from `AGENTS.md`)

1. **OA-only.** No paid data sources.
2. **No secrets.** Credentials go in env vars or gitignored files, never committed.
3. **Memory != evidence.** Verify current state before quoting memory.
4. **Fail-closed.** Any unclear state is an error, not a silent default.
5. **Determinism.** Same input, same output; pinned seeds for stochastic methods.

See [`AGENTS.md`](AGENTS.md) for the full rules.

## What's in each rules file

- [`rules/rules.md`](rules/rules.md) — workflow, testing, HTML-app patterns (consolidated 2026-04-15)
- [`rules/e156.md`](rules/e156.md) — 7-sentence paper contract, workbook protection, deploy pipeline
- [`rules/advanced-stats.md`](rules/advanced-stats.md) — statistical gotchas (pooling, heterogeneity, NMA, DTA, Bayesian, survival)
- [`rules/lessons.md`](rules/lessons.md) — accumulated mistake-prevention rules from past sessions

## Adapting to your own setup

The rules reference Mahmood-specific paths (`C:\E156\`, `C:\ProjectIndex\`,
`C:\Sentinel\`, `C:\overmind\`, GitHub user `mahmood726-cyber`). These
encode a *working* setup — you can either:

1. Replicate the layout at the same paths (easiest), or
2. Substitute your own paths and update the rules files after install
   (your edits are preserved when you re-run `install.ps1` — your version
   is backed up as `<name>.md.user`)

## License

MIT. Rules files are released as curated working-process documentation.
Use, adapt, fork freely.

## Companion repos

- [`e156-student-starter`](https://github.com/mahmood726-cyber/e156-student-starter) — narrow submission-pipeline CLI (`student new`, `student validate`, `student publish`, etc.)
- [`e156-binary-mirror`](https://github.com/mahmood726-cyber/e156-binary-mirror) — content-stable mirror of large pinned binaries
