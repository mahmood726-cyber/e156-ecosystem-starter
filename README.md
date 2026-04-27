# e156-ecosystem-starter

Bootstrap Mahmood's quality-dev ecosystem on a student's laptop.

This is not a single tool. It is the **install layer** that turns a fresh
Windows machine into the same environment he uses to ship E156 papers and
meta-analysis tools: agent CLIs (Claude Code / Gemini CLI / Codex) plus
curated rules, memory scaffolding, Sentinel pre-push hook, Overmind
verifier, and ProjectIndex registry.

> **New here?** After you finish the install, read [`STUDENT-WORKFLOW.md`](STUDENT-WORKFLOW.md)
> for the brainstorm→spec-lock→plan-lock→TDD→audit method, the worked-example
> repos to clone, and how the Sentinel + Overmind quality gates fit together.
> The rules give you Mahmood's enforcement; the workflow doc gives you his method.

## What you get

| Layer | Ship status | What it does |
|---|---|---|
| `rules/*.md` | v0.1.0 | Four curated rules files copied to `~/.claude/rules/`, `~/.gemini/rules/`, `~/.codex/rules/`: workflow + testing + HTML-app patterns (`rules.md`), E156 format (`e156.md`), statistics gotchas (`advanced-stats.md`), bug-prevention lessons (`lessons.md`). |
| `AGENTS.md` + `CLAUDE.md` / `GEMINI.md` / `CODEX.md` | v0.1.0 | Canonical + per-agent context files. Each agent auto-reads its own pointer; all pointers agree that `AGENTS.md` wins. |
| `memory/` scaffold | v0.1.0 | Starter `MEMORY.md` index + 4 type templates (`user` / `feedback` / `project` / `reference`). Dropped only when your memory dir is empty — never clobbers existing memory. |
| Sentinel pre-push hook | **v0.2.0** | `scripts/install-sentinel.ps1 -Repo <path>` pip-installs `sentinel` from the public repo and installs a pre-push hook with 20 rules (blocks: hardcoded paths, placeholder HMAC, silent sentinels, committed `.claude/` configs, empty-DataFrame access, stale agent-config versions). Bypass via `SENTINEL_BYPASS=1 git push` (logged to `~/.sentinel-logs/bypass.log`). |
| Overmind verifier | **v0.3.0** | `scripts/install-overmind.ps1` pip-installs [overmind](https://github.com/mahmood726-cyber/overmind) from GitHub and generates a 64-hex-char `TRUTHCERT_HMAC_KEY` saved as a User env var. Run `overmind scan --repo <path>` for on-demand verification; emits PASS / FAIL / UNVERIFIED / REJECT verdicts. |
| TruthCert engine | **v0.3.0** | Bundled inside Overmind (`overmind/verification/truthcert_engine.py`). HMAC-signs a certification bundle for each verified project. Requires `TRUTHCERT_HMAC_KEY` env var — installer generates and stores it. |
| ProjectIndex seed | **v0.3.0** | `scripts/install-projectindex.ps1 -Root <dir>` drops a starter `INDEX.md` (active / submission-ready / shipped / triage sections) + `reconcile_counts.py` that fails-closed when listed project paths don't exist on disk. Parameterized — not hardcoded to `C:\ProjectIndex\`. |
| `push-portfolio.py` | **v0.4.0** | Lightweight clone of Mahmood's `push_all_repos.py`. Scans any directory tree (configurable via `--scan-dir` / `PORTFOLIO_SCAN_DIRS` env) for git repos and either pushes existing ones or creates new GitHub repos via `gh`. Guards against the "parent repo config inheritance" gotcha (bare `.git` subdirs won't falsely inherit the home dir's remote). Flags: `--dry-run`, `--report`, `--new-only`, `--no-recursive`. |
| `student` CLI | separate repo | Narrow submission pipeline: see [`e156-student-starter`](https://github.com/mahmood726-cyber/e156-student-starter). |

## Quick start

Prerequisites: Windows 10+, PowerShell 5.1+, at least one of
[Claude Code](https://docs.anthropic.com/en/docs/claude-code),
[Gemini CLI](https://github.com/google-gemini/gemini-cli), or
[Codex](https://github.com/openai/codex) installed.

```powershell
git clone https://github.com/mahmood726-cyber/e156-ecosystem-starter
cd e156-ecosystem-starter
.\install\install.ps1               # base + interactive prompts for sub-installers (v0.6.0)
# or
.\install\install.ps1 -Full         # everything non-interactively
# or
.\install\install.ps1 -NonInteractive  # base only, skip chain prompts (CI-safe)
```

The installer will:

1. Verify its own SHA against `docs/HASH.txt` (tamper gate)
2. Detect which agent CLIs are on PATH and print install URLs for any missing
3. Copy `rules/*.md` into each agent's config dir (`.claude/rules/`, `.gemini/rules/`, `.codex/rules/`)
4. Drop `AGENTS.md` + `CLAUDE.md` + `GEMINI.md` + `CODEX.md` into each config dir
5. Bootstrap an empty memory scaffold in each agent's memory dir (preserves existing memory if present)
6. **Chain** (v0.6.0): Ask whether to also install Sentinel, Overmind+TruthCert, and ProjectIndex. `-Full` skips the prompts and runs all three with defaults; `-NonInteractive` skips the chain entirely.

Flags:

- `-DryRun` — only verify the SHA gate, exit 0
- `-Force` — overwrite existing user-edited rules (default: back them up as `*.user`)
- `-Full` — chain Sentinel (current dir) + Overmind + ProjectIndex (C:\ProjectIndex) non-interactively
- `-NonInteractive` — skip all chain prompts (base install only)
- `-InstallSentinel <repo-path>` — chain Sentinel into a specific repo
- `-InstallOvermind` — chain Overmind + TruthCert HMAC-key setup
- `-ProjectIndexRoot <dir>` — chain ProjectIndex seed at this dir
- `-Import` — dot-source helpers only (used by Pester tests)

### Adding Sentinel to your workbook (v0.2.0)

```powershell
# From the ecosystem-starter dir, pointing at the repo you want protected:
.\scripts\install-sentinel.ps1 -Repo C:\Projects\my-paper
```

This `pip install`s the [Sentinel](https://github.com/mahmood726-cyber/Sentinel)
rule engine **pinned to a tagged release** (`v0.1.0` by default) and writes a
pre-push hook at `<repo>\.git\hooks\pre-push`. From then on, every `git push`
runs the 20-rule scan in ~2 seconds and blocks on P0 violations.

To opt into bleeding-edge or roll back to a known-good ref:

```powershell
$env:SENTINEL_REF = 'main';   .\scripts\install-sentinel.ps1 -Repo .   # bleeding edge
$env:SENTINEL_REF = 'v0.0.9'; .\scripts\install-sentinel.ps1 -Repo .   # rollback
$env:SENTINEL_REF = $null   # restore default (v0.1.0)
```

Flags:
- `-Mode warn` (default) — log findings, allow push
- `-Mode block` — abort push on any BLOCK
- `-SkipPipInstall` — assume `sentinel` is already on PATH, skip pip
- `-Import` — dot-source helpers only (used by Pester tests)

To bypass a BLOCK when you're confident it's a false positive:
```powershell
$env:SENTINEL_BYPASS = '1'; git push; $env:SENTINEL_BYPASS = $null
```
Each bypass is logged to `~/.sentinel-logs/bypass.log` — the log path cannot
be redirected to `NUL`.

### Adding Overmind + TruthCert (v0.3.0)

```powershell
.\scripts\install-overmind.ps1
```

This `pip install`s [overmind](https://github.com/mahmood726-cyber/overmind)
(which bundles the TruthCert engine) **pinned to a known-good commit SHA**,
generates a 64-hex-char `TRUTHCERT_HMAC_KEY` if you don't already have one,
saves it as a User env var, and runs `overmind meta-verify` as a canary.
Override the pin via `$env:OVERMIND_REF = 'main'` (or any branch/tag/SHA).
From then on you can verify any repo with:

```powershell
overmind scan --repo C:\Projects\my-paper
overmind run-once --repo C:\Projects\my-paper
```

Back up the HMAC key somewhere safe — losing it invalidates all prior
signed bundles. Pass `-HmacKey <existing-key>` to the installer to reuse a
key across machines.

### Adding a portfolio index (v0.3.0)

```powershell
.\scripts\install-projectindex.ps1 -Root C:\ProjectIndex
```

Drops two files:

- `INDEX.md` — markdown template with `## Active projects` / `Submission-ready` /
  `Shipped` / `Triage` sections. Add one line per project as you start them.
- `reconcile_counts.py` — parameterised drift-detection script. Run
  `python reconcile_counts.py --root <dir>` and it exits 1 if any project
  link in `INDEX.md` points at a path that doesn't exist on disk.

Example:
```powershell
python C:\ProjectIndex\reconcile_counts.py --root C:\ProjectIndex
# -> OK: 3 project(s) in INDEX.md, all paths resolve.
```

### Pushing your portfolio (v0.4.0)

```powershell
# One-off scan + action
python .\scripts\push-portfolio.py --scan-dir C:\Projects --github-user your-handle

# Persistent config via env vars
$env:PORTFOLIO_SCAN_DIRS = "C:\Projects;D:\Projects"
$env:PORTFOLIO_GITHUB_USER = "your-handle"
python .\scripts\push-portfolio.py --report      # just print status table
python .\scripts\push-portfolio.py --dry-run     # preview actions
python .\scripts\push-portfolio.py --new-only    # create + push only repos without a remote
```

For each repo found:
- If no `origin` remote → `gh repo create <user>/<name> --public --source <path> --push`
- If `origin` set → `git push origin HEAD`

Skips: `node_modules`, `venv`, `.venv`, `__pycache__`, `build`, `dist`,
`site-packages`, `.pytest_cache`, `.mypy_cache`.

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

## Other languages

Abridged landing pages are available in:

- 🇫🇷 [Français](https://mahmood726-cyber.github.io/e156-ecosystem-starter/fr/)
- 🇵🇹 [Português](https://mahmood726-cyber.github.io/e156-ecosystem-starter/pt/)
- 🇸🇦 [العربية](https://mahmood726-cyber.github.io/e156-ecosystem-starter/ar/) (RTL)

These cover the install command, verify step, and prereqs — the full English
page remains canonical for everything else (security model, troubleshooting,
example projects, design principles). Install commands themselves are
identical across all four languages.

## Privacy: install transcripts auto-redact secrets

The installer writes a transcript log of every run (so you can attach it to
a GitHub issue if something breaks). On exit, the log is automatically
scrubbed for API keys, tokens, and high-entropy secrets that may have been
pasted, echoed, or otherwise captured during the run:

- Google AI Studio keys (`AIza…`) → `[REDACTED-google-api-key]`
- OpenAI / Anthropic keys (`sk-…` / `sk-ant-…`) → `[REDACTED-openai-key]` / `[REDACTED-anthropic-key]`
- GitHub tokens (`ghp_/gho_/ghs_/ghu_…`) → `[REDACTED-github-token]`
- AWS access keys (`AKIA…`) → `[REDACTED-aws-access-key]`
- 64-hex strings (TruthCert HMAC, generic crypto) → `[REDACTED-64hex]`
- JWTs (`eyJ…token…`) → `[REDACTED-jwt]`
- `setx` / `export` of `*_KEY` / `*_TOKEN` / `*_SECRET` / `*_PASS` / `*_HMAC` env vars → value redacted

Redaction runs in-place after `Stop-Transcript` (PowerShell) or via an
`EXIT` trap (bash), so even partial / failed installs get a sanitised log.
Tests cover all eight pattern families on both shells.

## CI

Every push and PR runs three jobs via GitHub Actions ([`.github/workflows/test.yml`](.github/workflows/test.yml)):

- **Pester (Windows):** all PowerShell test suites, ~78 tests covering
  install helpers, redaction, supply-chain pinning, SHA gate, doctor report,
  Sentinel/Overmind/ProjectIndex/update wrappers.
- **Bash (Ubuntu):** ~22 bash tests covering install.sh helpers, redaction,
  pinning, dot-source hygiene, rollback, template rendering.
- **Lint:** ShellCheck (severity `error`) on all `.sh` files +
  PSScriptAnalyzer (severity `error`) on all `.ps1` files.

The intent is that any regression in install path, secret-redaction, or
supply-chain pinning fails CI before reaching a student.

## License

MIT. Rules files are released as curated working-process documentation.
Use, adapt, fork freely.

## Companion repos

- [`e156-student-starter`](https://github.com/mahmood726-cyber/e156-student-starter) — narrow submission-pipeline CLI (`student new`, `student validate`, `student publish`, etc.)
- [`e156-binary-mirror`](https://github.com/mahmood726-cyber/e156-binary-mirror) — content-stable mirror of large pinned binaries
