# Component installation contract: M2 first increment

Scope: lock Sentinel/Overmind's existing source pins and replace RapidMeta's
tag-only install check with exact checkout verification and a generator smoke
test. This extends existing installers, not upstream analytical code. M2's full
ecosystem installation matrix remains a later increment.

## Verified ingredients

Inspected starter scripts: `install-rapidmeta.sh`, `install-rapidmeta.ps1`,
`refresh-ecosystem-pins.py`, `verify-full-install.py` and the existing component
tests. The current full-chain workflow covers Sentinel, Overmind, ProjectIndex
and the extractor; it does not include RapidMeta or AACT-kit.

GitHub's RapidMeta `v1.1.0` tag object
[`c04e8dc42335df4473572cbef9b2c7cfb585d19f`](https://api.github.com/repos/mahmood726-cyber/rapidmeta-kit/git/tags/c04e8dc42335df4473572cbef9b2c7cfb585d19f)
resolved on 2026-11-11 to commit
[`3de5e44cc7624138309868db1dbfa49320682e66`](https://github.com/mahmood726-cyber/rapidmeta-kit/commit/3de5e44cc7624138309868db1dbfa49320682e66).
The tag is unsigned. A local checkout's same-named tag resolved to
`1dc3540aec91e3228e5b7d5fbb6b1b66783a944d`; its HEAD was `368137d`. The lock uses
the inspected GitHub commit, not either local ref. That commit was fetched into
a separate scratch checkout before implementation; `clone.py`, its base template
and bundled assets exist there. No clinical claims from its example configurations
are used as validation data.

## Contract and sequence

1. Strictly parse `scripts/component-lock.json`. Reject duplicates, missing
   components, malformed commits or unsupported adapters. Check the two frozen
   Sentinel/Overmind installer mirrors against the lock in CI.
2. RapidMeta defaults to the lock's exact SHA. An explicit override must also be
   a full lowercase commit. Branches and tags are refused before mutation.
3. Validate runtime and target. Refuse dirty checkouts, a different origin,
   symlinked or nested targets and non-repository directories. Never stash,
   reset, clean or overwrite user work. A different existing HEAD is refused;
   install a new commit in a fresh target so a failed candidate cannot replace
   an active installation. Atomic upgrades remain future work. Fetch only the exact requested commit,
   check out detached, and compare observed HEAD to the requested commit.
4. `--skip-clone` still checks identity and cleanliness. It cannot bless an
   arbitrary directory merely because a file named `clone.py` exists.
5. Generate disposable, explicitly synthetic output twice. Require the fixture
   markers, local asset resolution and deterministic bytes. Record expected and
   observed commits, adapter version and output hash. This is a CLI generation
   canary, not browser E2E, source adjudication or numerical validation.
6. Persist discovery paths only after verification succeeds. Session-only mode
   avoids persistent shell/registry changes. Failed execution exits nonzero and
   emits no success receipt. Automatic pin refresh cannot advance this lock.
   Conflicting persisted paths require an explicit user edit; rerunning an
   identical Bash binding is idempotent and shell metacharacters are quoted.

## Test isolation and acceptance

Core controls use disposable local Git repositories and real Git commands, not
PATH stubs. Wrapper tests use disposable homes; PowerShell uses session-only mode.
Tests must not invoke real installers against the user's home or rewrite user
environment variables. Network is forbidden for fixture tests. A separate CI
matrix may fetch the real locked RapidMeta commit on disposable Windows/Linux
runners. Preserve explicit scope for platforms not executed.

Required cases: clean exact checkout, repeat verification, unknown commit,
mutable/option-shaped ref, wrong origin, dirty tracked/untracked/ignored files,
nested directory, symlink, missing source or assets, crashing/no-output generator,
wrong output markers, nondeterministic bytes, missing tool and lock drift.

## Static versus dynamic disclosure

| Item | Kind | Meaning |
|---|---|---|
| Locked commits and runtime floors | Static, source-inspected | Reviewed source selection; not authenticity or transitive dependency locking |
| Synthetic smoke config | Static engineering fixture | No real patients, trial identifiers or research findings |
| Checkout status, observed SHA, artifact hashes | Dynamic execution | Identifies the tested checkout and output |
| Sentinel/Overmind mirror check | Dynamic source validation | Does not execute those components or issue a release verdict |
| Real RapidMeta generator canary | Dynamic execution when run | Does not establish browser correctness, offline rendering or analytical accuracy |

The selected RapidMeta HTML still references external CDN resources. An offline
generator run does not establish a completely offline browser experience.

## Local verification on 2026-11-11

The targeted component, pin-refresh, local-verifier and governance suite passed
144 tests on Windows with Git Bash available. An earlier invocation without Bash
on PATH failed seven local-verifier prerequisite checks; rerunning with the
required executable resolved those failures. The final Bash persistence review
also checks that a correct binding cannot conceal a second, conflicting binding.
The component suite was rerun after that change. Research-layer Bash helpers,
the component lock, gate registry and protective-state ratchet passed.

The real locked RapidMeta generator completed twice with matching output and
asset hashes: 65 directly referenced local assets and two external resources.
The [execution receipt](../benchmarks/components/rapidmeta-windows.json) binds
the observed source commit, verifier bytes and component specification. It is
an engineering canary, not a held-out evaluation. Sentinel's changed-file scan
returned no blocking findings; warnings remain. Cross-platform CI evidence is
recorded on the draft pull request. macOS execution, browser E2E, full-chain M2
coverage and a fresh project-specific Overmind release verdict are outstanding.

The first remote Windows run exposed a genuine path-alias bug: its temporary
root used an 8.3 spelling while resolved assets used the full spelling. The
verifier now resolves the output path before both containment checks and relative
asset naming. A regression test reproduced the failure before the fix and also
checks that an asset outside the output directory remains refused. The real
generator receipt was refreshed after this fix; its output and asset hashes
remained unchanged.
