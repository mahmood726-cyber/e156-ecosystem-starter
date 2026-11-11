# Paired research component activation

`research_environment.py` installs and verifies RapidMeta and AACT-kit together.
Both runtime checks must succeed before one active manifest selects the pair.
This adds safe selection of versioned research sources; Sentinel/Overmind hooks,
TruthCert keys, ProjectIndex, private memory and Python environments retain their
existing independent installation contracts.

## Verified ingredients and reuse

The coordinator reuses `component-lock.json`, `component_source.py`,
`rapidmeta_install.py` and `aact_install.py`, whose exact-source adapters already
have Windows/Linux source canaries. The existing Linux full-chain workflow and
`verify-full-install.py` exercise Sentinel, Overmind, ProjectIndex and the
extractor. The new CI path combines that existing chain with paired research
activation. It does not rewrite the legacy installers or call them on a personal
machine as a test.

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

## Static versus dynamic disclosure

| Item | Kind | Meaning |
|---|---|---|
| Two-component scope and manifest schemas | Static engineering contract | Explicitly excludes legacy component mutation |
| Locked source selection | Inspected static configuration | Full Git identities; not release signatures |
| Coordinator tests | Synthetic filesystem/failure controls | No network, real snapshots or scientific claims |
| Runtime versions, verifier hashes and adapter receipts | Dynamic execution | Binds the selected runtime and tested source behavior |
| Active pointer and rollback | Dynamic filesystem operations | One atomic pair selection after fresh verification |
| Clinical accuracy, full Windows ecosystem, PostgreSQL | Not measured here | No completeness or scientific-performance claim |

Local verification on 2026-11-11: the coordinator, governance and existing
full-install verifier suite passed 100 tests, including 26 synthetic coordinator
controls. The actual pinned pair was installed in a separate Windows scratch root
using an isolated runtime environment. A deliberately missing-source candidate
was refused; the active pointer was unchanged and the original pair reverified.
The [recorded control](../benchmarks/components/research-environment-windows.json)
includes runtime/verifier identities without local paths. Both edited workflow
YAML files parsed. Sentinel reported no blocking findings; warnings remain.
Current-head Windows/Linux and full-chain CI results are recorded on the draft PR.
