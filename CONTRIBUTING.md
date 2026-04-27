# Contributing to e156-ecosystem-starter

Thank you for your interest in improving the starter. This repo bootstraps a research-dev environment (rules + Sentinel + Overmind + ProjectIndex) for African research students. The bar is "a fresh student running the install on their laptop has zero broken steps." Contributions that move that bar matter.

## Quick contribution paths

- **Found a bug** in install.ps1, install.sh, or any of the chain installers? Open an issue with the install transcript log attached. The installer auto-redacts secrets from the log on exit, so it's safe to share. Logs live at:
  - Windows: `%LOCALAPPDATA%\e156\logs\install-<ts>.log`
  - Linux/WSL: `~/.local/state/e156/logs/install-<ts>.log`
  - macOS: `~/Library/Logs/e156/install-<ts>.log`
- **Improving a translation?** PRs against `docs/{fr,pt,ar}/index.html` are very welcome. The English page (`docs/index.html`) is canonical for any technical command; translated pages are abridged. If you're a native French/Portuguese/Arabic speaker, see [Translation contributions](#translation-contributions) below.
- **Adding a Sentinel rule?** That belongs in the upstream [Sentinel repo](https://github.com/mahmood726-cyber/Sentinel), not here. This repo just wraps the install.
- **Adding to the rules pack?** PRs against `rules/lessons.md` for new past-incident rules are welcome. Format: see existing entries — short rule, **Why:** line, **How to apply:** line, optional date.

## Development setup

```bash
git clone https://github.com/mahmood726-cyber/e156-ecosystem-starter
cd e156-ecosystem-starter

# Run the test suites locally
bash tests/test-install-sh.bash                                          # bash
pwsh -c "Invoke-Pester -Path install\pester.tests.ps1 -Output Minimal"   # PowerShell (Windows)
```

Both must be green before opening a PR. CI runs the same suites on every push.

## CI gates

Three jobs must pass in `.github/workflows/test.yml`:

1. **Pester (Windows)** — ~78 PowerShell tests covering install helpers, redaction, supply-chain pinning, SHA gate, hook-backup, doctor report.
2. **Bash (Ubuntu)** — ~25 bash tests covering install.sh helpers, redaction, pinning, dot-source hygiene, rollback, hook-backup.
3. **Lint** — ShellCheck (severity `error`) on all `.sh` files + PSScriptAnalyzer (severity `error`) on all `.ps1` files.

If you add new functionality, add a test for it in the same PR.

## Style

- **No new dependencies** unless absolutely necessary. The starter has zero non-stdlib runtime deps; please keep it that way.
- **Bash:** target POSIX-compatible bash 4+; LF line endings (enforced by `.gitattributes`); shellcheck `error` clean.
- **PowerShell:** target PowerShell 5.1+ (Windows-shipped baseline); native line endings; PSScriptAnalyzer `error` clean.
- **HTML/CSS:** mobile-first; tap targets ≥44×44px; AA color contrast; `lang` attrs on every multilingual element; `<bdi>` around mixed-script text.
- **No hardcoded local paths** (`C:\Users\...`, `/home/<user>/...`) in shipped code. Use `~`, `$env:USERPROFILE`, or the templated `{{NAME}}` placeholders.

## Translation contributions

The translated landing pages (`docs/fr/`, `docs/pt/`, `docs/ar/`) are abridged on purpose — they cover install, verify, and prereqs only. The English page remains canonical for security model, troubleshooting, and worked examples.

When suggesting translation improvements:

- Keep code blocks (shell commands, env vars) untranslated.
- Keep file paths untranslated.
- Translate only prose and UI copy.
- Note the canonical English version this is translating from in the PR description.

If you're adding a new language: copy `docs/fr/index.html` as a template, swap content, add `<link rel="alternate" hreflang>` entries to all four existing pages, and add a row to the language picker.

## Reporting a security issue

Please don't file public issues for security problems. Email `mahmood726@gmail.com` with `e156-ecosystem-starter security:` in the subject. We'll acknowledge within 72 hours.

## License

By contributing you agree your contributions will be licensed under the same MIT license that covers the rest of the repo.
