# Security policy

## Supported versions

Only the `main` branch is supported. Tagged releases are pinned in
`scripts/install-sentinel.{ps1,sh}` (`SENTINEL_REF`) and
`scripts/install-overmind.{ps1,sh}` (`OVERMIND_REF`); fix-forward via a new
release rather than back-porting.

## Trust boundaries

The starter has three install entry points:

1. **Bootstrap layer** — `bootstrap/e156-setup.bat`, `bootstrap/e156-setup.sh`,
   `docs/bootstrap.ps1`. These are NOT SHA-gated. They run before any gate fires
   and are responsible for downloading the rest of the repo.
2. **Install layer** — `install/install.ps1` and `install/install.sh`.
   Each self-verifies its SHA-256 against `docs/HASH.txt` (PowerShell) or
   `docs/HASH-linux.txt` (bash), fetched from the same origin, before doing
   anything else.
3. **Chain installers** — `scripts/install-sentinel.{ps1,sh}` etc. These
   pip-install Sentinel + Overmind from GitHub, pinned to a tagged release or
   known-good commit SHA by default.

The SHA gate catches **download tampering** of the install layer (corrupted
download, MitM injection on a hostile network). It does NOT catch:

- Compromise of the GitHub repo itself (a bad actor with push access can update
  both `install.ps1` and `docs/HASH.txt` together and the gate passes).
- Tampering of the bootstrap layer (that runs before the gate).
- Tampering of the upstream pinned Sentinel / Overmind packages on PyPI / GitHub.

For high-trust installs (e.g. a department lab with sensitive data), prefer
git-cloning a tagged release with a verified GPG signature and running
`install.ps1` from the clone, rather than `irm | iex` from the bootstrap.

## Install transcript secret redaction

Every install writes a transcript log of the run for debugging. Before exit, the
log is automatically scrubbed for API keys, tokens, and HMAC values that may
have been pasted, echoed, or otherwise captured. Patterns covered:

- Google AI Studio keys (`AIza…`)
- OpenAI / Anthropic keys (`sk-…` / `sk-ant-…`)
- GitHub tokens (`ghp_/gho_/ghs_/ghu_…`)
- AWS access keys (`AKIA…`)
- 64-hex strings (TruthCert HMAC, generic crypto)
- JWTs (`eyJ…token…`)
- `setx` / `export` of any `*_KEY` / `*_TOKEN` / `*_SECRET` / `*_PASS` / `*_HMAC`
  env var

If you find a secret pattern that survives redaction, file it as a security issue
(see below) — that's a bug.

## Reporting a vulnerability

Please don't file public issues for security problems.

Email **`mahmood726@gmail.com`** with `e156-ecosystem-starter security:` in the
subject line. We aim to acknowledge within 72 hours.

For non-security bugs, use [the regular issue tracker](https://github.com/mahmood726-cyber/e156-ecosystem-starter/issues/new/choose).
