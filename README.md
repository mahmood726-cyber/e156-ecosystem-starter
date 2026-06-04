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
| Sentinel pre-push hook | **v0.2.0** | `scripts/install-sentinel.ps1 -Repo <path>` pip-installs `sentinel` from the public repo and installs a pre-push hook with 53 rules (21 BLOCK / 28 WARN / 4 INFO; 656 tests) + skip-file marker (blocks: hardcoded paths, placeholder HMAC, silent sentinels, committed `.claude/` configs, empty-DataFrame access, stale agent-config versions, leaked secrets, MCP/JS lockfile + script integrity, baseline drift, dashboard-stat orphan, blueprint-implementation match). Bypass via `SENTINEL_BYPASS=1 git push` (logged to `~/.sentinel-logs/bypass.log`). |
| Overmind verifier | **v0.4.0** | `scripts/install-overmind.ps1` pip-installs [overmind](https://github.com/mahmood726-cyber/overmind) (pinned `328cb7f`) from GitHub and generates a 64-hex-char `TRUTHCERT_HMAC_KEY` saved as a User env var. Run `overmind scan --repo <path>` for on-demand verification (PASS / FAIL / UNVERIFIED / REJECT). **Now includes the offline evidence-synthesis subsystem**: a deterministic meta-analysis pooling engine + `overmind gold-benchmark` (MEASURED output-correctness — reproduces published pooled estimates, e.g. metafor BCG logRR to 0.0005, fail-closed), BM25+vector hybrid retrieval, screening-recall calibration vs the 0.95 bar, claim-grounding, PRISMA flow, and reporting-bias accounting (registry linkage, ROB-ME, outcome-switching). |
| TruthCert engine | **v0.3.0** | Bundled inside Overmind (`overmind/verification/truthcert_engine.py`). HMAC-signs a certification bundle for each verified project. Requires `TRUTHCERT_HMAC_KEY` env var — installer generates and stores it. |
| ProjectIndex seed | **v0.3.0** | `scripts/install-projectindex.ps1 -Root <dir>` drops a starter `INDEX.md` (active / submission-ready / shipped / triage sections) + `reconcile_counts.py` that fails-closed when listed project paths don't exist on disk. Parameterized — not hardcoded to `C:\ProjectIndex\`. |
| RCT extractor | **v0.5.0** | `scripts/install-extractor.ps1 -Target <dir>` clones [rct-extractor-v2](https://github.com/mahmood726-cyber/rct-extractor-v2) at a pinned commit and persists `RCT_EXTRACTOR_PATH` so the meta-system bridges auto-find it. Turns trial PDFs / abstract text into a [meta-starter-kit](https://github.com/mahmood726-cyber/meta-starter-kit) config — auto-detecting **cardiology, malaria, and HIV** (HIV MA agreement 97.9%, malaria 99.4%). The student's text→config path is **stdlib-only**; heavy PDF/scientific deps (numpy/scipy/pdfplumber, ~150 MB) are opt-in via `-WithPdfDeps`. Runs under `-Full` (core only). |
| `push-portfolio.py` | **v0.4.0** | Lightweight clone of Mahmood's `push_all_repos.py`. Scans any directory tree (configurable via `--scan-dir` / `PORTFOLIO_SCAN_DIRS` env) for git repos and either pushes existing ones or creates new GitHub repos via `gh`. Guards against the "parent repo config inheritance" gotcha (bare `.git` subdirs won't falsely inherit the home dir's remote). Flags: `--dry-run`, `--report`, `--new-only`, `--no-recursive`. |
| `long-term-plan` (optional) | separate repo | `scripts/install-long-term-plan.ps1` clones [`mahmood726-cyber/long-term-plan`](https://github.com/mahmood726-cyber/long-term-plan) (pinned to `v0.7.0`) into `~/code/long-term-plan/` and installs the only runtime dep (`pyyaml`). A weekly-refreshed, deterministic, locally-rendered project backlog with no LLM in the loop. Ships Mahmood's real backlog (43 ideas + 5 OKRs anchored to north stars) as a reference — students are expected to fork or replace `ideas.yaml` with their own. |
| `student` CLI | separate repo | Narrow submission pipeline: see [`e156-student-starter`](https://github.com/mahmood726-cyber/e156-student-starter). |
| **RapidMeta kit** | **v0.6.0** | `scripts/install-rapidmeta.ps1` clones [rapidmeta-kit](https://github.com/mahmood726-cyber/rapidmeta-kit) at a pinned commit and persists `RAPIDMETA_KIT_PATH`. `clone.py` turns a small JSON config into a self-contained RapidMeta meta-analysis **dashboard** — **stdlib-only, offline, zero deps, no LLM**. Run `bash run_example.sh` for a token-free example. |
| **AACT cockpit** | **v0.6.0** | `scripts/install-aact.ps1` clones [aact-cockpit](https://github.com/mahmood726-cyber/aact-cockpit) at a pinned commit and persists `AACT_COCKPIT_PATH`. A local DuckDB-backed cockpit for large-scale ClinicalTrials.gov/AACT analysis that emits self-auditing e156 capsules. Clone is free; **running** needs `duckdb`+`numpy` (opt-in `-WithDataDeps`/`--with-data-deps`) **and a local AACT snapshot**. Zero-setup path: read the committed `analyses/` + `templates/` examples. |
| **AACT kit** *(library)* | **v0.1.0** | `scripts/install-aact-kit.ps1` clones [aact-kit](https://github.com/mahmood726-cyber/aact-kit) at a pinned commit and persists `AACT_KIT_PATH`. The shared **library** other CT.gov projects import: one API to resolve / load / validate / aggregate AACT across five local backends (Postgres, SQLite, ZIP, pipe-delimited TSV dir, CSV dir). Only hard dep is `pandas` (`psycopg2` optional); install is opt-in `-WithDeps`/`--with-deps`. Zero-setup path: read `src/aact_kit/` + `README.md`. **Distinct from the AACT cockpit** above (which is a DuckDB analysis app). |
| **Pairwise70 workbench** | **v0.6.0** | `scripts/install-pairwise70.ps1` clones [pairwise70-workbench](https://github.com/mahmood726-cyber/pairwise70-workbench) at a pinned commit and persists `PAIRWISE70_PATH`. An offline gallery hub that shows + reproduces every Pairwise70-family analysis; **static HTML, stats run offline in the browser, no Python deps, no tokens** — just open `index.html`. |
| **E156 capsule + chart-kit** | **v0.6.0** | `scripts/install-e156-capsules.ps1` copies the **bundled** `templates/e156-capsule/` (no clone, **zero network**) and persists `E156_CAPSULES_PATH`. The E156 7-sentence capsule contract + a ~120-line **stdlib-only SVG chart-kit** (forest plot, no numpy/matplotlib) + a **pre-baked sample** capsule and chart you can read with **zero tokens**. The lowest-footprint layer in the ecosystem. |

> **The five layers above let students recreate Mahmood's meta-analysis tooling end-to-end.** Each defaults to an **offline / low-token** path and keeps heavy deps opt-in — see [`STUDENT-TOKEN-BUDGET.md`](STUDENT-TOKEN-BUDGET.md) for where tokens are (and aren't) spent.

## Quick start

### Easiest — open in your browser, full install, zero terminal

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/mahmood726-cyber/e156-ecosystem-starter?quickstart=1)

Click that badge. A free GitHub-hosted workspace opens in your browser with **the full system pre-installed**:

- Four rules files in `~/.claude/`, `~/.gemini/`, `~/.codex/`
- Memory scaffold (starter `MEMORY.md` + four templates)
- **Sentinel** pre-push hook in `~/code/my-first-repo/`
- **Overmind** verifier on PATH with a `TRUTHCERT_HMAC_KEY` generated and persisted to `~/.bashrc`
- **ProjectIndex** seed at `~/code/ProjectIndex/`
- **RCT extractor** (cardiology + malaria + HIV) cloned to `~/code/rct-extractor-v2/` with `RCT_EXTRACTOR_PATH` set
- **Gemini CLI** + **Claude Code CLI** pre-installed (`gemini` is free; `claude` needs an Anthropic key)

No PowerShell, no terminal experience, no admin rights, no API key required for Gemini. **Build takes ~2-3 minutes** (universal image cold start + 2 npm installs + 3 pip installs from GitHub). Free tier: 60 hours/month for personal/Education GitHub accounts; remember to **stop your codespace** when done so it doesn't burn your hours. See [`.devcontainer/`](.devcontainer/) for the exact orchestration: `on-create.sh` runs `install.sh --full --github-user $GH_USER`; `on-attach.sh` prints a status report on first terminal open per session.

### Local install — Windows / macOS / Linux / WSL

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

1. Verify its own SHA against `docs/HASH.txt` ([download-integrity check](docs/index.html#security) — catches MitM/corruption between Pages CDN and your laptop, **not** a repo compromise; for high-trust installs use the signed-tag git-clone path)
2. Detect which agent CLIs are on PATH and print install URLs for any missing
3. Copy `rules/*.md` into each agent's config dir (`.claude/rules/`, `.gemini/rules/`, `.codex/rules/`)
4. Drop `AGENTS.md` + `CLAUDE.md` + `GEMINI.md` + `CODEX.md` into each config dir
5. Bootstrap an empty memory scaffold in each agent's memory dir (preserves existing memory if present)
6. **Chain** (v0.6.0): Ask whether to also install Sentinel, Overmind+TruthCert, ProjectIndex, and the RCT extractor. `-Full` skips the prompts and runs all of them with defaults; `-NonInteractive` skips the chain entirely.

Flags:

- `-DryRun` — only verify the SHA gate, exit 0
- `-Force` — overwrite existing user-edited rules (default: back them up as `*.user`)
- `-Full` — chain Sentinel (current dir) + Overmind + ProjectIndex (C:\ProjectIndex) + RCT extractor (core only) non-interactively
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
rule engine **pinned to a known-good commit** (the 53-rule build) and writes a
pre-push hook at `<repo>\.git\hooks\pre-push`. From then on, every `git push`
runs the 53-rule scan in ~2 seconds and blocks on P0 violations.

To opt into bleeding-edge or roll back to a known-good ref:

```powershell
$env:SENTINEL_REF = 'main';   .\scripts\install-sentinel.ps1 -Repo .   # bleeding edge
$env:SENTINEL_REF = 'v0.0.9'; .\scripts\install-sentinel.ps1 -Repo .   # rollback
$env:SENTINEL_REF = $null   # restore default (pinned 53-rule commit)
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

### Adding a long-term-plan (optional)

```powershell
.\scripts\install-long-term-plan.ps1
.\scripts\install-long-term-plan.ps1 -Root C:\code\long-term-plan -Ref v0.7.0
```

Clones [`mahmood726-cyber/long-term-plan`](https://github.com/mahmood726-cyber/long-term-plan)
**pinned to a tagged release** (`v0.7.0` by default) into `~/code/long-term-plan/`
and installs the only runtime dep (`pyyaml`).

The published clone ships Mahmood's real backlog (43 ideas + 5 OKR-style
quarterly objectives anchored to north stars) as a reference. The expectation
is that you **fork or replace** the content with your own — edit
`ideas.yaml` / `objectives.yaml` / `north_star_tags.yaml` to point at your
work, then run the weekly reranker:

```powershell
cd ~\code\long-term-plan
python scripts\weekly_plan_update.py             # rerank + render
python scripts\weekly_plan_update.py --pick <id> # flip an idea to in-progress
python scripts\weekly_plan_update.py --add "..."  # append a new idea
```

Override the pin via `$env:LONG_TERM_PLAN_REF = 'main'` (or any branch/tag/SHA)
to opt into bleeding-edge.

Flags:
- `-Root <dir>` — target dir (default: `~\code\long-term-plan`)
- `-Ref <tag>` — git ref to check out (default: `v0.7.0`)
- `-Force` — re-run on an existing clone (otherwise idempotent)
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

- **Pester (Windows):** all PowerShell test suites, ~83 tests covering
  install helpers, redaction, supply-chain pinning, SHA gate, doctor report,
  hook-backup, second-rerun rules-backup, Sentinel/Overmind/ProjectIndex/update wrappers.
- **Bash (Ubuntu):** ~26 bash tests covering install.sh helpers, redaction,
  pinning, dot-source hygiene, rollback, template rendering, hook-backup,
  second-rerun rules-backup.
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
