# Paired research component activation

`research_environment.py` installs and verifies RapidMeta and AACT-kit together.
Both runtime checks must succeed before one active manifest selects the pair.
This adds safe selection of versioned research sources; Sentinel/Overmind hooks,
TruthCert keys, ProjectIndex, private memory and Python environments retain their
existing independent installation contracts.

## Verified ingredients and reuse

The coordinator reuses `component-lock.json`, `component_source.py`,
`rapidmeta_install.py` and `aact_install.py`, whose exact-source adapters already
have Windows/Linux source canaries. The full-chain workflow runs the Linux
installer with `verify-full-install.py` and the Windows installer through
`windows_install_smoke.ps1`. Both paths combine Sentinel, Overmind, ProjectIndex
and the extractor with paired research activation. They do not rewrite the
legacy installers or call them on a personal machine as a test. A configured CI
path is not evidence of a passing run; inspect the workflow result for the exact
revision being evaluated.

New code is limited to generation records, a single active pointer, exclusive
operation locking, repeated verification, rollback and their negative controls.
The coordinator neither installs dependencies nor edits shell/registry settings.

## Use

Use Python 3.11+ with pandas and NumPy available in its normal environment. For
the tested CPython 3.13 x86_64 Windows/Linux runtime, install
`requirements-aact-canary.lock` in a dedicated virtual environment using pip's
`--require-hashes --only-binary=:all:` options. Python user-site/PYTHONPATH-only
packages do not satisfy the isolated runtime check.

```bash
python scripts/research_environment.py install --root ./research-environment
python scripts/research_environment.py verify --root ./research-environment
python scripts/research_environment.py rollback --root ./research-environment --release FULL_64_CHARACTER_RELEASE_ID
```

The commands are identical in PowerShell. Choose an explicit dedicated root;
an existing nonempty unmarked directory is refused. Successful commands return
JSON with `status`, the exact two-component `scope`, the release ID and verified
absolute component paths. Consumers can read those paths for the current session.
Existing `RAPIDMETA_KIT_PATH` / `AACT_KIT_PATH` bindings are not redirected.

To upgrade, review a full component lock and pass it with `install --lock PATH`.
The schema and full source commits are validated as in the standalone installers.
Environment-variable ref overrides are not used by this coordinator. A change
in component lock, coordinator/adapter bytes or observed runtime versions yields
a distinct generation; the previous generation remains available for inspection.

## Transaction boundary

1. Validate the lock and probe the actual selected Python runtime before creating
   a root. Require a dedicated root marker and refuse linked managed paths.
2. Acquire an exclusive operation lock. Competing installs, verification or
   rollback refuse rather than run concurrently.
3. Create a separate generation with a saved lock. Run both real adapters, require
   runtime-verified receipts and recheck both source trees after the adapters.
   Write a deterministic release record binding source selection, runtime
   versions, verifier bytes and component results.
4. Recheck that the active pointer has not changed, flush a new pointer file and
   atomically replace `active.json` on the same filesystem. This single selection
   prevents an old/new component mixture. An unverified candidate is never active.
5. `verify` re-executes both adapters and compares the results with the recorded
   results. `rollback` does the same before selecting the specified old generation.
   A changed runtime/verifier profile requires a newly verified generation.

Failed candidates and previous generations are retained. No recursive cleanup,
reset or stash discards user work. An interrupted process can leave an operation
lock; the next command refuses. Inspect the lock's process/owner information and
ensure the operation has stopped before explicitly removing that one lock file.
An incomplete generation can be retried only if its saved lock and source trees
still satisfy the contract.

Atomic selection is not a database transaction over the whole ecosystem or a
power-loss durability guarantee. It does not lock a Python environment against
external package changes, authenticate trusted source commits, prevent hostile
filesystem races, sign scientific evidence or certify an Overmind project verdict.
Existing processes keep whichever component paths they previously resolved.

## Disposable Windows full-chain verification

The `full-windows-install` job in
[`full-system-integration.yml`](../.github/workflows/full-system-integration.yml)
uses a fresh GitHub-hosted Windows Server 2022 runner and Python 3.13. Its
[`windows_install_smoke.ps1`](../scripts/windows_install_smoke.ps1) entrypoint
refuses local, self-hosted and non-Windows contexts before writing files. Runner
environment variables are an accidental-use guard, not a security sandbox;
never spoof them to run this script on a personal machine.

The job creates a new profile directory and Python virtual environment under
`RUNNER_TEMP`, checks the installer SHA, and runs the real `install.ps1 -Full`
and all four legacy subinstallers. It then installs, verifies and exercises the
failed-upgrade preservation control for the locked RapidMeta/AACT pair. The
final verification requires installed rules/context/memory, a blocking Sentinel
hook and live scan, Overmind's verifier-health JSON verdict, a valid generated
TruthCert registry key, the persisted extractor path and core import canary,
ProjectIndex reconciliation, pip dependency consistency, and Sentinel/Overmind
source commits matching the component lock. No agent CLI login is attempted.

Windows' User environment registry, known-folder Desktop and clipboard are not
isolated by changing `USERPROFILE`. The unmodified installers exercise those
APIs on the disposable runner account; that account's destruction contains the
side effects. This is why a temporary directory alone is insufficient to allow
local full-install testing. The Linux key-file contract is not substituted for
Windows' actual registry-key contract.

On success, the job uploads only `windows-install-manifest.json`: source commits,
installer/lock hashes, observed package/runtime versions, the paired generation,
check outcomes and coverage limits. The key, registry export, environment,
installation transcripts and private profile are not uploaded. Failed runs
produce no success receipt. The extractor's legacy release-tag selection is
recorded by its observed commit; this does not make that tag immutable or
authenticate its publisher. Legacy pip dependencies remain unpinned transitives.

This verifies installation integration on a prepared hosted runner, not setup of
a consumer Windows machine without Git/Python. Agent authentication, PDF extras,
PostgreSQL, hardware power loss, scientific performance and project certification
remain outside this job. The workflow has a bounded timeout and does not retry a
failed installation automatically. Local tests cover only refusal and confinement
controls; actual Windows full-chain verification requires a passing hosted run.

## Static versus dynamic disclosure

| Item | Kind | Meaning |
|---|---|---|
| Two-component scope and manifest schemas | Static engineering contract | Explicitly excludes legacy component mutation |
| Locked source selection | Inspected static configuration | Full Git identities; not release signatures |
| Coordinator tests | Synthetic filesystem/failure controls | No network, real snapshots or scientific claims |
| Runtime versions, verifier hashes and adapter receipts | Dynamic execution | Binds the selected runtime and tested source behavior |
| Active pointer and rollback | Dynamic filesystem operations | One atomic pair selection after fresh verification |
| Windows smoke paths and expected layer checks | Static engineering contract | Fresh hosted account only; no private-user installation |
| Windows full-chain receipt | Dynamic CI execution, only after success | Installer outputs, live canaries, installed sources and runtime; inspect exact revision/run |
| Clinical accuracy, consumer-machine bootstrap, PostgreSQL | Not measured here | No completeness or scientific-performance claim |

Local verification on 2026-11-11: the coordinator, governance and existing
full-install verifier suite passed 100 tests, including 26 synthetic coordinator
controls. The actual pinned pair was installed in a separate Windows scratch root
using an isolated runtime environment. A deliberately missing-source candidate
was refused; the active pointer was unchanged and the original pair reverified.
The [recorded control](../benchmarks/components/research-environment-windows.json)
includes runtime/verifier identities without local paths. Both edited workflow
YAML files parsed. Sentinel reported no blocking findings; warnings remain.
Current-head Windows/Linux and full-chain CI results are recorded on the draft PR.
