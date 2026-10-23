# Full Linux installation integration canary (research-stage)

This check is a real networked integration test for the **default Linux
`install/install.sh --full` chain**, not a validation of any scientific result.
It is separate from `.github/workflows/test.yml`, which tests individual
wrappers without downloading the dependency repositories.

**Run:** [Full-system installer integration workflow](../.github/workflows/full-system-integration.yml)
on pull requests affecting installer contracts, manual dispatch, and Mondays.
The workflow runs on a disposable Ubuntu 24.04 GitHub runner, creates a Python
virtual environment, checks the installer SHA, runs the full installer without
interactive prompts, then invokes a fail-closed verifier.

**Real components exercised**

| Layer | Evidence required |
|---|---|
| Agent rules/context/memory | All rule and context files exist across Claude/Gemini/Codex; ProjectIndex template rendered; memory exists |
| Sentinel | Real pinned-release package installed, pre-push hook in the student sample git repo, live scan of that repo returns 0 |
| Overmind / TruthCert | Real package installed, 64-hex random key with owner-only permissions, `overmind meta-verify` returns 0 |
| ProjectIndex | Real scaffold, manifest and `reconcile_counts.py` execution succeed |
| RCT extractor | Real checkout at pinned release with the bridge module, two-specialty real imports succeed |

The verifier prints PASS or FAIL for each check and exits nonzero on a
missing file, invalid key, missing CLI, bad import, failing canary or timeout.
`tests/test_full_install_verifier.py` uses explicitly **synthetic temporary
fixtures** as negative controls; those fixtures never count as an actual
installation.

**What remains outside the result**

- Windows PowerShell `-Full` install (Pester tests are separate).
- Optional Meta-Harness release installation and scientific search/adjudication,
  RapidMeta, AACT, Pairwise70, and actual DOI/certificate publication.
- Browser UI and real student login/authentication to commercial agent CLIs.
- Exact upstream dependency reproducibility: the installer pins Sentinel,
  Overmind and extractor to release **tags**, but indirect Python dependency
  versions are not all hash-locked. This test checks the **current** ecosystem,
  not whether an old dependency resolution can be reconstructed offline.
- A CI canary does **not** demonstrate scientific correctness or independent
  human adjudication.

**Static versus dynamic disclosure**

| Input | Kind | Source |
|---|---|---|
| Expected target paths and command names | Static contract | Current installer source |
| Installed file contents, key mode, scanner output, parser imports | Live dynamic | Disposable GitHub runner |
| Sentinel / Overmind / extractor release tags | Externally resolved | Current upstream Git tags, which are not immutable checksums |
| Unit-test layouts | Synthetic | Isolated `tmp_path`, solely to prove refusal behavior |
| Scientific result or meta-analysis effect size | None | Not tested or asserted |

**Run locally:** To check an *already installed* Unix system without
modifying it, use `python scripts/verify-full-install.py`. To run the
installer itself, use a **disposable machine or container**. The installer
changes a user's agent configuration, creates local keys and installs
dependencies; do not run it on a personal workstation for CI.
