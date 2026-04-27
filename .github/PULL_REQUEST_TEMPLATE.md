## What does this PR do?
<!-- One-sentence summary. -->

## Why?
<!-- The "why" is more important than the "what" — what user-visible problem does this solve, or what risk does it close? -->

## How has this been tested?
- [ ] `bash tests/test-install-sh.bash` passes locally
- [ ] `Invoke-Pester` against changed test files passes locally
- [ ] Manual install on a clean VM / WSL sandbox (describe below)
- [ ] N/A — docs / translation only

<!-- If you ran a manual install, describe the OS, PowerShell version, and what you verified. -->

## Type of change
- [ ] Bug fix (non-breaking, no API change)
- [ ] New feature (non-breaking, additive)
- [ ] Breaking change (existing students re-running install will see different behaviour)
- [ ] Docs / translation
- [ ] CI / tooling
- [ ] Refactor (no behaviour change)

## Checklist
- [ ] No hardcoded local paths (`C:\Users\...`, `/home/<user>/...`) in shipped code
- [ ] No new runtime dependencies added (or, if added, justified in the description)
- [ ] If touching `install/install.{ps1,sh}`, regenerated `docs/HASH{,-linux}.txt` (the Pester self-SHA test does this automatically)
- [ ] If adding a new function, added a test for it
- [ ] If touching translated pages, kept code blocks untranslated and noted the canonical English version

## Anything reviewers should know?
<!-- Edge cases, follow-ups, deferred work, screenshots. -->
